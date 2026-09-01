"""
Regression test for the 2026-09-01 newsletter failure — runs entirely offline.

The monthly newsletter died with `'ThinkingBlock' object has no attribute 'text'`
after the switch to Sonnet 5. Every agent read `message.content[0].text`, which
assumes the first content block is text. Sonnet 5 runs ADAPTIVE thinking by
default (Sonnet 4.6 did not), so the model decides per request whether to think —
and when it does, `content[0]` is a ThinkingBlock.

The bug had been live in all four agents for a day. It surfaced in the newsletter
first only because long synthesis triggers thinking while short classification
usually doesn't. That is exactly the kind of latent, workload-shaped failure the
offline suite cannot catch, because it fakes the agents.

Run from the competitive_intel/ directory:
    python3 -m scripts.test_response_parsing
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
from integrations.anthropic_retry import response_text  # noqa: E402


def msg(blocks, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(**b) for b in blocks], stop_reason=stop_reason
    )


def main() -> int:
    failures = []

    def check(label, fn, expect_error=None, expect=None):
        try:
            got = fn()
            ok = (expect_error is None) and got == expect
            detail = f"returned {got!r}"
        except Exception as e:
            ok = expect_error is not None and expect_error in str(e)
            detail = f"raised {type(e).__name__}: {e}"
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else f' — {detail}'}")
        if not ok:
            failures.append(label)

    print("response_text() against the shapes Sonnet 5 actually returns:\n")

    check("plain text response (the Sonnet 4.6 shape)",
          lambda: response_text(msg([{"type": "text", "text": '{"score": 7}'}])),
          expect='{"score": 7}')

    check("thinking block FIRST, then text (the shape that broke the newsletter)",
          lambda: response_text(msg([{"type": "thinking", "thinking": "hmm..."},
                                     {"type": "text", "text": '{"score": 7}'}])),
          expect='{"score": 7}')

    check("thinking block with no .text attribute at all does not raise AttributeError",
          lambda: response_text(msg([{"type": "thinking"},
                                     {"type": "text", "text": "ok"}])),
          expect="ok")

    check("text split across several blocks is concatenated",
          lambda: response_text(msg([{"type": "text", "text": "part one "},
                                     {"type": "text", "text": "part two"}])),
          expect="part one part two")

    check("truncated response raises a clear error instead of bad JSON",
          lambda: response_text(msg([{"type": "text", "text": '{"score": 7, "reas'}],
                                    stop_reason="max_tokens")),
          expect_error="max_tokens")

    check("thinking-only response raises instead of returning empty",
          lambda: response_text(msg([{"type": "thinking", "thinking": "..."}])),
          expect_error="no text block")

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}")
        return 1
    print("All checks passed — thinking blocks no longer break response parsing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
