from __future__ import annotations

import argparse
import secrets


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Phase A admin token.")
    parser.add_argument("--bytes", type=int, default=32)
    args = parser.parse_args()

    if args.bytes < 24:
        raise SystemExit("--bytes must be at least 24")

    token = secrets.token_urlsafe(args.bytes)
    print("PHASE_A_ADMIN_TOKEN status=ok")
    print(f"token={token}")
    print("powershell_env=$env:PHASEA_ADMIN_TOKEN_HASH = \"<token>\"")
    print("warning=Store this token in the host secret store or service environment only. Do not commit it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
