from __future__ import annotations

import base64
import hashlib
import argparse
import secrets


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Phase A admin token.")
    parser.add_argument("--bytes", type=int, default=32)
    args = parser.parse_args()

    if args.bytes < 24:
        raise SystemExit("--bytes must be at least 24")

    token = secrets.token_urlsafe(args.bytes)
    token_hash = (
        base64.urlsafe_b64encode(hashlib.sha256(token.strip().encode("utf-8")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    print("PHASE_A_ADMIN_TOKEN status=ok")
    print(f"token={token}")
    print(f"token_hash={token_hash}")
    print(f"powershell_env=$env:PHASEA_ADMIN_TOKEN_HASH = \"{token_hash}\"")
    print("warning=Store this token in the host secret store or service environment only. Do not commit it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
