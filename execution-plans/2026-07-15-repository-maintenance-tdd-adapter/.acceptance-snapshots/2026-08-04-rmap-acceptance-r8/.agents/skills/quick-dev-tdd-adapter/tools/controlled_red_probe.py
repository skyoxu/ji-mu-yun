from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure-id", required=True)
    args = parser.parse_args()
    print(json.dumps({"observed": args.failure_id, "controlled": True}, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
