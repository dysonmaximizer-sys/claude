#!/usr/bin/env python3
"""Generate a Maximizer demo-data upload CSV from the persistent cast registry.

The cast file stores static field values plus DATE RULES. Dates are never
stored as fixed values for story-critical contacts; they are recomputed
relative to the run date every time, so "turns 65 in 3 weeks" stays true
forever.

Usage:
  python3 generate_demo_data.py --cast <cast.json> --out <output.csv>
      [--story <story.json>] [--date YYYY-MM-DD] [--summary <summary.md>]

Story overlay format (written per demo story, only for records that change):
{
  "story": "one-line description",
  "overrides": [
    {
      "id": "<IDentification value>",            // required; shared by household members
      "name": "First Last",                       // required; disambiguates within shared ID.
                                                  // For Household/Company rows use the entry name.
      "set": {"Position": "CEO"},                 // static field changes
      "date_rules": {"Next KYC Review": {"rule": "days_from_today", "days": -10}},
      "note": "why this record changed"
    }
  ],
  "new_records": [                                // optional throwaway extras
    {"fields": {"First Name": "...", "Last Name": "...", "Entry Type": "Contact", ...},
     "date_rules": {...}, "note": "..."}
  ]
}

Date rule types:
  {"rule": "turns", "age": 65, "in_days": 21}
      Birthday is run_date + in_days, and the person turns `age` that day.
      Birth year is recomputed so this is always true.
  {"rule": "days_from_today", "days": -55}
      run_date + days. Negative = past (overdue / already happened).
  {"rule": "seeded_window", "min_days": -330, "max_days": -40}
      Deterministic pseudo-random date in the window, seeded per record ID,
      stable within a calendar week so re-runs in the same week are identical.
  {"rule": "kyc_cycle"}
      Next KYC Review = Last KYC Review + meta.kyc_cycle_days.
  {"rule": "static", "value": "1975-02-03"}
      Fixed value (rarely needed; omitting the rule keeps the stored value).

Exit code is non-zero if validation fails. Never hand a failing CSV to the
user.
"""
import argparse
import csv
import hashlib
import json
import sys
from datetime import date, timedelta


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--cast', required=True)
    p.add_argument('--story', default=None)
    p.add_argument('--out', required=True)
    p.add_argument('--date', default=None, help='Run date override (YYYY-MM-DD), default today')
    p.add_argument('--summary', default=None, help='Optional path for the change-summary markdown')
    return p.parse_args()


def seeded_offset(record_id, field, lo, hi, run_date):
    """Deterministic offset in [lo, hi], stable within the ISO week."""
    week = run_date.isocalendar()
    seed = f"{record_id}|{field}|{week[0]}-W{week[1]}"
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return lo + h % (hi - lo + 1)


def resolve_rule(rule, record, run_date, meta, resolved):
    kind = rule['rule']
    if kind == 'turns':
        target = run_date + timedelta(days=rule['in_days'])
        try:
            return target.replace(year=target.year - rule['age'])
        except ValueError:  # Feb 29 target in a non-leap birth year
            return target.replace(year=target.year - rule['age'], day=28)
    if kind == 'days_from_today':
        return run_date + timedelta(days=rule['days'])
    if kind == 'seeded_window':
        rid = record['fields'].get('IDentification', '') or record['fields'].get('Last Name', '')
        off = seeded_offset(rid, rule.get('_field', ''), rule['min_days'], rule['max_days'], run_date)
        return run_date + timedelta(days=off)
    if kind == 'kyc_cycle':
        last = resolved.get('Last KYC Review')
        if last is None:
            raise ValueError('kyc_cycle rule needs a Last KYC Review rule on the same record')
        return last + timedelta(days=meta.get('kyc_cycle_days', 365))
    if kind == 'static':
        return date.fromisoformat(rule['value'])
    raise ValueError(f'Unknown rule type: {kind}')


def age_on(birthdate, on):
    return on.year - birthdate.year - ((on.month, on.day) < (birthdate.month, birthdate.day))


def main():
    args = parse_args()
    run_date = date.fromisoformat(args.date) if args.date else date.today()

    with open(args.cast) as f:
        cast = json.load(f)
    meta = cast['meta']
    columns = meta['output_columns']
    fmt = meta.get('date_format', '%Y-%m-%d')

    story = None
    if args.story:
        with open(args.story) as f:
            story = json.load(f)

    # Apply story overrides. IDs are shared between a Household/Company and its
    # member Contacts (that is how Maximizer links them), so overrides match on
    # id + name. `name` is "First Last" for contacts, or the Household/Company
    # name for parent records.
    def rec_key(fields):
        person = f"{fields.get('First Name', '')} {fields.get('Last Name', '')}".strip()
        return (fields.get('IDentification', ''),
                person or fields.get('Company', '') or fields.get('Last Name', ''))

    overrides = {(o['id'], o['name']): o for o in (story or {}).get('overrides', [])}
    changed = []
    records = [dict(r) for r in cast['records']]
    seen_override_keys = set()
    for rec in records:
        k = rec_key(rec['fields'])
        if k in overrides:
            o = overrides[k]
            seen_override_keys.add(k)
            rec['fields'] = {**rec['fields'], **o.get('set', {})}
            rec['date_rules'] = {**rec.get('date_rules', {}), **o.get('date_rules', {})}
            if o.get('note'):
                rec['note'] = o['note']
            changed.append((rec, o.get('note', 'story override')))
    missing = set(overrides) - seen_override_keys
    if missing:
        sys.exit(f'ERROR: story overrides reference unknown id+name pairs: {sorted(missing)}')

    for nr in (story or {}).get('new_records', []):
        nr.setdefault('fields', {})
        nr['fields'].setdefault('IDentification', '')  # new records get no fake Maximizer ID
        records.append(nr)
        changed.append((nr, nr.get('note', 'new story record')))

    # Resolve date rules
    ordering = ['Birthdate', 'Last KYC Review', 'Next KYC Review', 'Last Modified Date']
    for rec in records:
        rules = rec.get('date_rules', {})
        resolved = {}
        fields_in_order = [f for f in ordering if f in rules] + [f for f in rules if f not in ordering]
        for field in fields_in_order:
            rule = dict(rules[field])
            rule['_field'] = field
            resolved[field] = resolve_rule(rule, rec, run_date, meta, resolved)
        for field, d in resolved.items():
            rec['fields'][field] = d.strftime(fmt)

    # ---- Validation ----
    errors, warnings = [], []
    keys = [rec_key(r['fields']) for r in records if r['fields'].get('IDentification')]
    if len(keys) != len(set(keys)):
        errors.append('Duplicate id+name combination in output')
    original_keys = {rec_key(r['fields']) for r in cast['records'] if r['fields'].get('IDentification')}
    missing_keys = original_keys - set(keys)
    if missing_keys:
        errors.append(f'Original records missing from output (replace-import would orphan them): {sorted(missing_keys)[:5]}')
    for rec in records:
        f = rec['fields']
        name = f"{f.get('First Name', '')} {f.get('Last Name', '')}".strip()
        for formula in meta.get('formula_fields_never_written', []):
            if f.get(formula):
                errors.append(f'{name}: formula field "{formula}" has a value — Maximizer computes this, leave blank')
        bd = f.get('Birthdate', '')
        if bd:
            b = date.fromisoformat(bd) if '-' in bd else None
            if b:
                a = age_on(b, run_date)
                if not 0 <= a <= 100:
                    errors.append(f'{name}: implausible age {a}')
        last_k, next_k = f.get('Last KYC Review', ''), f.get('Next KYC Review', '')
        if last_k and '-' in last_k and date.fromisoformat(last_k) > run_date:
            errors.append(f'{name}: Last KYC Review is in the future')
        if last_k and next_k and '-' in last_k and '-' in next_k:
            if date.fromisoformat(next_k) <= date.fromisoformat(last_k):
                errors.append(f'{name}: Next KYC Review not after Last KYC Review')
        if f.get('Entry Type') not in ('Contact', 'Household', 'Company', ''):
            warnings.append(f'{name}: unusual Entry Type "{f.get("Entry Type")}"')

    # ---- Write CSV ----
    with open(args.out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(columns)
        for rec in records:
            w.writerow([rec['fields'].get(c, '') or '' for c in columns])

    # ---- Change summary ----
    lines = [f"# Demo data refresh — {run_date.isoformat()}", '']
    if story:
        lines += [f"**Story:** {story.get('story', '')}", '']
    lines.append(f"{len(records)} records written ({len(changed)} changed by story, rest refreshed dates only).")
    lines.append('')
    lines.append('## Story-critical contacts this run')
    lines.append('')
    for rec in records:
        f = rec['fields']
        note = rec.get('note')
        if not note and rec not in [c[0] for c in changed]:
            continue
        name = f"{f.get('First Name', '')} {f.get('Last Name', '')}".strip() or f.get('Company', '')
        bits = []
        bd = f.get('Birthdate', '')
        if bd and rec.get('date_rules', {}).get('Birthdate'):
            b = date.fromisoformat(bd)
            nxt = b.replace(year=run_date.year)
            if nxt < run_date:
                nxt = nxt.replace(year=run_date.year + 1)
            bits.append(f"turns {age_on(b, nxt)} on {nxt.isoformat()} ({(nxt - run_date).days} days)")
        if f.get('Next KYC Review'):
            d = (date.fromisoformat(f['Next KYC Review']) - run_date).days
            bits.append(f"KYC due {f['Next KYC Review']} ({'overdue by ' + str(-d) + ' days' if d < 0 else 'in ' + str(d) + ' days'})")
        detail = '; '.join(bits)
        lines.append(f"- **{name}** — {note or 'story change'}{(' — ' + detail) if detail else ''}")
    if warnings:
        lines += ['', '## Warnings', ''] + [f'- {w}' for w in warnings]
    summary = '\n'.join(lines)
    if args.summary:
        with open(args.summary, 'w') as f:
            f.write(summary)
    print(summary)

    if errors:
        print('\nVALIDATION FAILED:', file=sys.stderr)
        for e in errors:
            print(f'  - {e}', file=sys.stderr)
        sys.exit(1)
    print(f'\nValidation passed. CSV written to {args.out}')


if __name__ == '__main__':
    main()
