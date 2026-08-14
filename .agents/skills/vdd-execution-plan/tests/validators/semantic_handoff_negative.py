from __future__ import annotations

from semantic_handoff import main as positive_main


def main() -> int:
    # The RED command must remain nonzero while the positive production handoff
    # contract is available; authorization injection is never a valid substitute.
    return 1 if positive_main() == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
