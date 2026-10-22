"""Explicit offline scoped installation and native-tree verification."""
import argparse
import json
from pathlib import Path
from . import NativeError, verify
from .install import install


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["verify", "install-from-source"])
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--replace-native", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "install-from-source":
            if args.source_root is None:
                raise ValueError("SOURCE_REQUIRED")
            result = install(args.repository_root, args.source_root, args.replace_native)
            print(json.dumps(result))
            return 0
        lock = verify(args.repository_root)
        print(json.dumps({"ok": True, "version": lock["version"], "authorizes": []}))
        return 0
    except NativeError as exc:
        print(json.dumps(exc.result()))
        return 2
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc) if isinstance(exc, ValueError) else "FILESYSTEM_ERROR", "authorizes": []}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
