from __future__ import annotations

from semantic_handoff import _valid


def main() -> int:
    value = _valid()
    value["authorizes"] = ["bootstrap"]
    return 1 if value["authorizes"] != [] else 0


if __name__ == "__main__":
    raise SystemExit(main())
