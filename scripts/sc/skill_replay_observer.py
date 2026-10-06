"""Child-process read observations for bounded replay (Accepted ADR-0058).

The observer is installed before the immutable validator is imported. A file
stat or a parent-side digest is not a successful read observation. This is a
Python validator adapter, not an OS sandbox or support for arbitrary binaries.
"""
from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
import runpy
import sys
from pathlib import Path


def main() -> int:
    entry, target, output, nonce, *arguments = sys.argv[1:]
    target_root = Path(target).resolve()
    observations = []
    original_open, original_io_open = builtins.open, io.open

    class Reader:
        def __init__(self, stream, path):
            self.stream, self.path = stream, path

        def observed(self, value):
            raw = value.encode(self.stream.encoding or "utf-8") if isinstance(value, str) else value
            if raw:
                observations.append({"path": self.path, "bytes_read": len(raw), "read_sha256": "sha256:" + hashlib.sha256(raw).hexdigest()})
            return value

        def read(self, *args):
            return self.observed(self.stream.read(*args))

        def read1(self, *args):
            return self.observed(self.stream.read1(*args))

        def readline(self, *args):
            return self.observed(self.stream.readline(*args))

        def readlines(self, *args):
            values = self.stream.readlines(*args)
            for value in values:
                self.observed(value)
            return values

        def readinto(self, buffer):
            count = self.stream.readinto(buffer)
            self.observed(bytes(buffer[:count]))
            return count

        def __iter__(self):
            return self

        def __next__(self):
            return self.observed(next(self.stream))

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __getattr__(self, name):
            # A validator bypassing the supported read interface gets no read
            # credit. In particular .buffer/.raw reads are not inferred.
            return getattr(self.stream, name)

    def wrap(opener):
        def opened(file, *args, **kwargs):
            stream = opener(file, *args, **kwargs)
            try:
                relative = Path(file).resolve().relative_to(target_root).as_posix()
                mode = args[0] if args else kwargs.get("mode", "r")
                if "r" in mode or "+" in mode:
                    return Reader(stream, relative)
            except (TypeError, ValueError, OSError):
                pass
            return stream
        return opened

    builtins.open, io.open = wrap(original_open), wrap(original_io_open)
    sys.path.insert(0, str(Path(entry).resolve().parent))
    sys.argv = [entry, *arguments]
    code = 0
    try:
        runpy.run_path(entry, run_name="__main__")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        builtins.open, io.open = original_open, original_io_open
        with original_open(output, "x", encoding="utf-8", newline="\n") as stream:
            json.dump({"nonce": nonce, "pid": os.getpid(), "target": str(target_root), "reads": observations}, stream, sort_keys=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
