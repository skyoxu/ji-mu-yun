"""Historical terminal entry; current closure uses direct behavioral validation.

ADR-0060. Status-only historical slice receipts cannot be rebound to current
contracts. The original terminal implementation remains in repository history.
"""
import json


def main() -> int:
    print(json.dumps({
        'status': 'blocked',
        'reason': 'legacy-terminal-is-not-current-authority',
        'next_command': 'py -3 scripts/python/verify_toolchain_workflow_repair.py',
        'authorizes': [],
    }, sort_keys=True))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
