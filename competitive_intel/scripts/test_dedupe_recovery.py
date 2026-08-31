"""
Regression test for the dedupe-poisoning bug — runs entirely offline.

Proves the invariant: a run that dies mid-scoring must leave nothing
permanently stuck.

The bug (fixed 2026-08-18): the daily poll wrote each change to Notion BEFORE
scoring it, and dedupe only asked "is this URL already in Notion?". So every row
written before a scoring failure was treated as a duplicate on every later run
and could never be scored. That stranded 183 rows.

Three scenarios, with changedetection.io, Notion, Teams and the Anthropic agents
all replaced by in-memory fakes:

  1. A run whose scoring breaks part-way through   → rows land Unscored.
  2. The next healthy run                          → every stranded row ends
                                                     Scored, with no duplicate
                                                     rows created.
  4. One scoring blip vs many                      → an isolated failure leaves
                                                     the row for the next sweep
                                                     and does NOT fail the run;
                                                     a systemic failure does.
  3. A row stranded OUTSIDE the 76h lookback       → still rescued, because the
                                                     rescue sweep reads the
                                                     database rather than the
                                                     poll feed. This is the case
                                                     status-aware dedupe alone
                                                     cannot reach. It is scored
                                                     silently: backlog does not
                                                     alert (RESCUE_SWEEP_ALERTS).

Run from the competitive_intel/ directory:
    python3 -m scripts.test_dedupe_recovery
Exit code 0 = all scenarios pass.
"""

import logging
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


# ── Fake Notion ────────────────────────────────────────────────────────────────

class FakeNotion:
    """In-memory stand-in for the Changes DB, with the same dedupe semantics."""

    def __init__(self):
        self.rows = {}
        self._next = 0

    # -- writes --
    def log_change(self, competitor_name, tier, url, raw_change, category="Other",
                   source_type="Web", detected_at=""):
        self._next += 1
        page_id = f"page-{self._next:03d}"
        self.rows[page_id] = {
            "page_id": page_id, "competitor": competitor_name, "tier": tier,
            "category": category, "url": url, "raw_change": raw_change,
            "ai_summary": "", "score": None, "score_reasoning": "",
            "status": "Unscored", "teams_alert_sent": False,
            "date_detected": detected_at,
        }
        return page_id

    def update_change_score(self, page_id, score, reasoning):
        self.rows[page_id].update(score=score, score_reasoning=reasoning, status="Scored")

    def update_change_summary(self, page_id, summary):
        self.rows[page_id]["ai_summary"] = summary

    def update_change_meta(self, page_id, tier="", category=""):
        if tier:
            self.rows[page_id]["tier"] = tier
        if category:
            self.rows[page_id]["category"] = category

    def mark_alert_sent(self, page_id):
        self.rows[page_id]["teams_alert_sent"] = True

    # -- reads --
    def find_existing_change(self, competitor_name, url, detected_at):
        if not detected_at:
            return None
        dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        lo, hi = dt - timedelta(hours=1), dt + timedelta(hours=1)
        matches = [
            r for r in self.rows.values()
            if r["competitor"] == competitor_name and r["url"] == url
            and r["date_detected"]
            and lo <= datetime.fromisoformat(r["date_detected"].replace("Z", "+00:00")) <= hi
        ]
        if not matches:
            return None
        matches.sort(key=lambda r: r["date_detected"], reverse=True)
        return dict(matches[0])

    def get_unscored_changes(self):
        rows = [r for r in self.rows.values() if r["status"] == "Unscored"]
        rows.sort(key=lambda r: r["date_detected"] or "")
        return [{"_fake": r} for r in rows]

    @staticmethod
    def extract_change_fields(page):
        return dict(page["_fake"])

    # -- assertions helpers --
    def counts(self):
        out = {}
        for r in self.rows.values():
            out[r["status"]] = out.get(r["status"], 0) + 1
        return out


# ── Fake module wiring ─────────────────────────────────────────────────────────

def install_fakes(notion, changes, failing_after=None, cluster_all_together=False):
    """
    Put fake modules in sys.modules so daily_poll/rescore pick them up.

    failing_after=N makes score_change raise on every call after the Nth,
    simulating the credit outage that broke scoring mid-run.
    """
    calls = {"score": 0, "alerts": [], "digests": [], "summaries": []}

    preflight = types.ModuleType("integrations.anthropic_preflight")
    preflight.preflight_or_exit = lambda *a, **k: {"ok": True}
    preflight.check_api_key = lambda *a, **k: {"ok": True}

    cd = types.ModuleType("integrations.changedetection_client")
    cd.get_recent_changes = lambda lookback_hours=76: list(changes)

    nc = types.ModuleType("integrations.notion_client")
    for name in ("log_change", "find_existing_change", "update_change_score",
                 "update_change_summary", "update_change_meta", "mark_alert_sent",
                 "get_unscored_changes", "extract_change_fields"):
        setattr(nc, name, getattr(notion, name))

    def score_change(competitor_name, tier, category, url, raw_change):
        calls["score"] += 1
        if failing_after is not None and calls["score"] > failing_after:
            raise RuntimeError("simulated: credit balance too low")
        # Deterministic: URLs ending in -hot score high enough to alert.
        score = 9 if url.endswith("-hot") else 3
        return score, f"scored {url}", "Feature"

    scoring = types.ModuleType("agents.scoring_agent")
    scoring.score_change = score_change

    summariser = types.ModuleType("agents.summariser_agent")

    def summarise_change(**kw):
        calls["summaries"].append(kw["url"])
        return f"summary of {kw['url']}"

    summariser.summarise_change = summarise_change

    dedup = types.ModuleType("agents.dedup_agent")
    if cluster_all_together:
        # every change is one insight — the shape that proves summarising is
        # per-cluster rather than per-row
        dedup.cluster_changes_by_insight = lambda name, items: [list(range(len(items)))]
    else:
        dedup.cluster_changes_by_insight = lambda name, items: [[i] for i in range(len(items))]

    teams = types.ModuleType("integrations.teams_client")

    def send_competitive_alert(**kw):
        calls["alerts"].append(kw["competitor"])
        return True

    def send_digest_alert(items, title, subtitle=""):
        calls["digests"].append([i["page_id"] for i in items])
        return True

    teams.send_competitive_alert = send_competitive_alert
    teams.send_digest_alert = send_digest_alert
    # The real module redacts webhook URLs out of exception text before logging.
    # The fake needs it too, since the jobs import it by name.
    teams.redact = str

    for name, mod in [
        ("integrations.anthropic_preflight", preflight),
        ("integrations.changedetection_client", cd),
        ("integrations.notion_client", nc),
        ("agents.scoring_agent", scoring),
        ("agents.summariser_agent", summariser),
        ("agents.dedup_agent", dedup),
        ("integrations.teams_client", teams),
    ]:
        sys.modules[name] = mod

    # jobs.rescore caches nothing at import time, but drop it so each scenario
    # re-resolves the fakes.
    sys.modules.pop("jobs.rescore", None)
    sys.modules.pop("jobs.daily_poll", None)
    return calls


def make_changes(n, hours_ago=2, hot_indexes=()):
    detected = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    out = []
    for i in range(n):
        suffix = "-hot" if i in hot_indexes else ""
        out.append({
            "competitor_name": "Wealthbox",
            "tier": "Tier 2",
            "url": f"https://wealthbox.com/page-{i}{suffix}",
            "raw_change": f"+ diff for page {i}",
            "category": "Other",
            "source_type": "Web",
            "detected_at": detected,
        })
    return out


# ── Scenarios ──────────────────────────────────────────────────────────────────

def main() -> int:
    failures = []

    def check(label, condition, detail=""):
        print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f' — {detail}'}")
        if not condition:
            failures.append(label)

    changes = make_changes(5, hot_indexes=(0,))

    # ── Scenario 1: scoring breaks after 2 rows ───────────────────────────────
    print("\nScenario 1 — run dies mid-scoring (scoring fails after 2 rows)")
    notion = FakeNotion()
    install_fakes(notion, changes, failing_after=2)
    from jobs.daily_poll import run as poll_run
    result = poll_run()
    counts = notion.counts()
    check("all 5 changes were written to Notion", len(notion.rows) == 5, f"rows={len(notion.rows)}")
    check("3 rows stranded as Unscored", counts.get("Unscored") == 3, f"counts={counts}")
    check("run reported errors (non-zero exit)", result["errors"] > 0, f"result={result}")

    # ── Scenario 2: next healthy run rescues them ─────────────────────────────
    print("\nScenario 2 — next healthy run (same fetch feed, working scorer)")
    calls = install_fakes(notion, changes, failing_after=None)
    sys.modules.pop("jobs.daily_poll", None)
    from jobs.daily_poll import run as poll_run2
    result2 = poll_run2()
    counts2 = notion.counts()
    check("no duplicate rows created", len(notion.rows) == 5, f"rows={len(notion.rows)}")
    check("0 rows left Unscored", counts2.get("Unscored", 0) == 0, f"counts={counts2}")
    check("all 5 rows Scored", counts2.get("Scored") == 5, f"counts={counts2}")
    check("healthy run reported 0 errors", result2["errors"] == 0, f"result={result2}")
    check("stranded rows were swept, not re-logged", result2["new_changes"] == 0,
          f"new_changes={result2['new_changes']}")

    # ── Scenario 3: stranded outside the lookback window ──────────────────────
    print("\nScenario 3 — row stranded 5 days ago, outside the 76h lookback")
    notion3 = FakeNotion()
    old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    stale_id = notion3.log_change(
        competitor_name="Equisoft", tier="Tier 1",
        url="https://equisoft.com/old-page-hot", raw_change="+ stale diff",
        detected_at=old,
    )
    # The poll feed no longer contains it — cd.io only reports the last 76h.
    calls3 = install_fakes(notion3, make_changes(1), failing_after=None)
    sys.modules.pop("jobs.daily_poll", None)
    from jobs.daily_poll import run as poll_run3
    result3 = poll_run3()
    check("stale row was rescued to Scored",
          notion3.rows[stale_id]["status"] == "Scored", notion3.rows[stale_id]["status"])
    check("stale row got a score", notion3.rows[stale_id]["score"] == 9,
          str(notion3.rows[stale_id]["score"]))
    # Policy from 2026-08-18 (RESCUE_SWEEP_ALERTS = False): a rescued row is old
    # news by the time it is scored, so it is scored SILENTLY. These two checks
    # deliberately assert the absence of an alert — before that change they
    # asserted the opposite.
    check("no digest sent for the rescued backlog row (silent by policy)",
          not any(stale_id in d for d in calls3["digests"]), f"digests={calls3['digests']}")
    check("Teams Alert Sent left unticked on the backlog row",
          notion3.rows[stale_id]["teams_alert_sent"] is False)
    check("healthy run reported 0 errors", result3["errors"] == 0, f"result={result3}")

    # ── Scenario 4: a transient blip is tolerated, systemic failure is not ────
    print("\nScenario 4 — one scoring blip vs a systemic scoring failure")
    notion4 = FakeNotion()
    install_fakes(notion4, make_changes(10), failing_after=9)  # 1 of 10 fails
    sys.modules.pop("jobs.daily_poll", None)
    from jobs.daily_poll import run as poll_run4
    r4 = poll_run4()
    check("1 blip in 10 does not fail the run", r4["errors"] == 0, f"result={r4}")
    check("the blip is still counted and reported", r4["scoring_failures"] == 1,
          f"scoring_failures={r4.get('scoring_failures')}")
    check("the failed row is left Unscored for the next sweep",
          notion4.counts().get("Unscored") == 1, f"counts={notion4.counts()}")

    notion5 = FakeNotion()
    install_fakes(notion5, make_changes(10), failing_after=2)  # 8 of 10 fail
    sys.modules.pop("jobs.daily_poll", None)
    from jobs.daily_poll import run as poll_run5
    r5 = poll_run5()
    check("8 of 10 failing DOES fail the run", r5["errors"] > 0, f"result={r5}")

    # ── Scenario 5: one insight across many pages costs ONE summary ───────────
    print("\nScenario 5 — 4 alert-worthy pages, one shared insight")
    notion6 = FakeNotion()
    shared = make_changes(4, hot_indexes=(0, 1, 2, 3))  # all above threshold
    calls6 = install_fakes(notion6, shared, cluster_all_together=True)
    sys.modules.pop("jobs.daily_poll", None)
    from jobs.daily_poll import run as poll_run6
    r6 = poll_run6()
    check("all 4 rows scored", r6["scored"] == 4, f"result={r6}")
    check("exactly ONE summary bought for the shared insight",
          len(calls6["summaries"]) == 1, f"summaries={calls6['summaries']}")
    check("exactly one Teams alert sent", len(calls6["alerts"]) == 1,
          f"alerts={calls6['alerts']}")
    check("only the representative row got an AI Summary in Notion",
          sum(1 for r in notion6.rows.values() if r["ai_summary"]) == 1,
          f"{[bool(r['ai_summary']) for r in notion6.rows.values()]}")

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}")
        return 1
    print("All checks passed — a mid-scoring failure leaves nothing permanently stuck.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
