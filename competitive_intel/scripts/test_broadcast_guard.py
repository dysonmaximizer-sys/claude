"""
Offline tests for the broadcast duplicate guard and the newsletter health check.

Both were added on 2026-09-01 when broadcasts became unattended. Before that a
human typed `confirm=SEND` and would notice sending August twice; now nothing
would. And nothing watched whether the newsletter went out at all — a failed
broadcast surfaced only as a Teams card, so a missed card meant a silent month.

Both key off the same fact — does Resend already hold a broadcast for this
month — so both are tested against a faked Resend.

Run from the competitive_intel/ directory:
    python3 -m scripts.test_broadcast_guard
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.newsletter_agent as na  # noqa: E402
import jobs.healthcheck as hc  # noqa: E402


def main() -> int:
    failures = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else f' — got {got!r}, want {want!r}'}")
        if not ok:
            failures.append(label)

    print("\nbroadcast_name() — the string all three call sites share")
    check("formats the month zero-padded", na.broadcast_name(2026, 8), "CI Newsletter 2026-08")
    check("handles December", na.broadcast_name(2026, 12), "CI Newsletter 2026-12")

    print("\ncheck_newsletter() — did last month go out?")
    import os
    os.environ["RESEND_API_KEY"] = "re_fake_for_test"
    real_find = na.find_broadcast

    def fake(status=None, name_match=True):
        def _f(name):
            if not name_match:
                return None
            return {"name": name, "status": status, "sent_at": "2026-09-01 20:16:37+00"}
        return _f

    # 4 September: August's edition is overdue if missing
    sept4 = datetime(2026, 9, 4, tzinfo=timezone.utc)
    na.find_broadcast = fake("sent")
    check("sent last month -> healthy", hc.check_newsletter(sept4)["ok"], True)
    na.find_broadcast = fake(None, name_match=False)
    r = hc.check_newsletter(sept4)
    check("missing broadcast -> problem", r["ok"], False)
    check("  and it names the month", "CI Newsletter 2026-08" in r["detail"], True)
    na.find_broadcast = fake("draft")
    check("draft-only broadcast -> problem", hc.check_newsletter(sept4)["ok"], False)

    # 2 September: the cron fires on the 1st-3rd, so silence is not yet a fault
    sept2 = datetime(2026, 9, 2, tzinfo=timezone.utc)
    na.find_broadcast = fake(None, name_match=False)
    check("missing but not yet due (day 2) -> healthy", hc.check_newsletter(sept2)["ok"], True)

    # 4 January: the previous month must roll back across the year boundary
    jan4 = datetime(2027, 1, 4, tzinfo=timezone.utc)
    seen = {}
    def capture(name):
        seen["name"] = name
        return {"name": name, "status": "sent", "sent_at": "2027-01-01 10:00:00+00"}
    na.find_broadcast = capture
    hc.check_newsletter(jan4)
    check("January looks for December of the previous year", seen.get("name"),
          "CI Newsletter 2026-12")

    na.find_broadcast = real_find
    del os.environ["RESEND_API_KEY"]
    check("no RESEND_API_KEY -> skipped, not failed", hc.check_newsletter(sept4)["ok"], True)

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}")
        return 1
    print("All checks passed — duplicate sends are refused and a missed month is caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
