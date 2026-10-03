#!/usr/bin/env python3
"""
Check text files for UTF-8 decode errors and common mojibake/garbled patterns.

Results are written under:
  logs/ci/<YYYY-MM-DD>/encoding/session-details.json
  logs/ci/<YYYY-MM-DD>/encoding/session-summary.json

Usage (Windows):
  py -3 scripts/python/check_encoding.py --since-today
  py -3 scripts/python/check_encoding.py --since "2025-11-13 00:00:00"
  py -3 scripts/python/check_encoding.py --files path1 path2 ...
  py -3 scripts/python/check_encoding.py --root docs
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import hashlib
from pathlib import Path
import json
import os
import re
import subprocess
import sys
from typing import Iterable, List


TEXT_EXT = {
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".xml",
    ".cs",
    ".csproj",
    ".sln",
    ".gd",
    ".tscn",
    ".tres",
    ".gitattributes",
    ".gitignore",
    ".ps1",
    ".py",
    ".ini",
    ".cfg",
    ".toml",
}

# Explicit binary extensions to skip from UTF-8 validation
BINARY_EXT = {
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".ogg",
    ".wav",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".zip",
    ".7z",
    ".rar",
    ".gz",
    ".tar",
    ".tgz",
    ".dll",
    ".exe",
    ".pdb",
    ".pck",
    ".import",
    ".ttf",
    ".otf",
    ".db",
    ".sqlite",
    ".sav",
    ".bak",
}

# Exclude vendor/test asset folders and known binaries
EXCLUDE_SUBSTRINGS = [
    "Tests.Godot/addons/gdUnit4/src/core/assets/",
    "Tests.Godot/addons/gdUnit4/src/update/assets/",
    "Tests.Godot/addons/gdUnit4/src/reporters/html/template/css/",
    "Tests.Godot/addons/gdUnit4/src/ui/settings/",
    "gitlog/export-logs.zip",
]

# Mojibake/garble indicators (heuristic, not a proof).
MOJIBAKE_REGEXES = [
    ("FFFD_REPLACEMENT", re.compile("\uFFFD")),
    ("CJK_MOJIBAKE", re.compile(r"[闁閻鐟鍗鈧缂濞閸鎮绱锛绗閿鍊鎯缁婵锟斤拷]")),
    ("CP1252_PUNCT", re.compile(r"(?:â€™|â€œ|â€�|â€”|â€˜|â€¢|â€¦|â„¢)")),
    ("BOM_AS_TEXT", re.compile(r"ï»¿")),
]

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def run_cmd(args: List[str]) -> str:
    p = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore"
    )
    out, _ = p.communicate()
    return out


def git_changed_since(since: str) -> List[str]:
    out = run_cmd(["git", "log", f"--since={since}", "--name-only", "--pretty=format:"])
    files = [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith(" ")]
    return sorted(set(files))


def git_changed_today() -> List[str]:
    today = dt.date.today().strftime("%Y-%m-%d")
    return git_changed_since(today + " 00:00:00")


def is_text_file(path: str) -> bool:
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    norm = path.replace("\\", "/")
    if any(s in norm for s in EXCLUDE_SUBSTRINGS):
        return False
    if ext in BINARY_EXT:
        return False
    if ext in TEXT_EXT:
        return True
    # Heuristic: treat small unknown files as text, larger files as likely binary.
    try:
        sz = os.path.getsize(path)
        return sz < 128 * 1024
    except Exception:
        return False


def iter_files_under(root_dir: str) -> List[str]:
    root_dir = os.path.abspath(root_dir)
    out: List[str] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.isfile(path) and is_text_file(path):
                out.append(path)
    return sorted(set(out))


def git_tracked_files(root: Path) -> List[str]:
    # A shallow checkout and an older commit date must still scan every source.
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    paths = completed.stdout.decode("utf-8", errors="strict").split("\0")
    return _filter_existing_files(str(root / path) for path in paths if path)


def validate_raw_evidence(root: Path, manifest: Path) -> tuple[dict, list[dict]]:
    """ADR-0005: preserve raw bytes; classify only hash-bound, exact UTF-8 copies."""
    captures = {}
    errors = []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != "encoding-raw-evidence.v1":
            raise ValueError("Unsupported raw evidence manifest schema")
        entries = data["entries"]
        if not isinstance(entries, list):
            raise ValueError("Raw evidence entries must be a list")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {}, [{"path": str(manifest), "error": str(exc)}]

    root = root.resolve()
    for row in entries:
        source_rel = str(row.get("source_path", "")) if isinstance(row, dict) else "<invalid>"
        try:
            if not isinstance(row, dict):
                raise ValueError("Raw capture entry must be an object")
            normalized_rel = str(row["normalized_path"])
            source = (root / source_rel).resolve()
            normalized = (root / normalized_rel).resolve()
            if not source.is_relative_to(root) or not normalized.is_relative_to(root):
                raise ValueError("Raw evidence path escapes repository")
            if not (
                source_rel.startswith("execution-plans/") and source_rel.endswith(".raw.txt")
                or source_rel.startswith("logs/") and source_rel.endswith(".txt")
            ):
                raise ValueError("Only historical terminal captures can be classified")
            if not normalized_rel.startswith("logs/") or not normalized_rel.endswith(".utf8.txt"):
                raise ValueError("Normalized evidence must be a UTF-8 sidecar under logs")
            if row["source_encoding"] != "utf-16":
                raise ValueError("Unsupported historical capture encoding")
            raw = source.read_bytes()
            if not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                raise ValueError("Historical UTF-16 capture must contain its BOM")
            if hashlib.sha256(raw).hexdigest() != row["source_sha256"]:
                raise ValueError("Raw capture hash changed")
            expected = raw.decode("utf-16").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            if expected != normalized.read_bytes():
                raise ValueError("Normalized sidecar does not match the raw capture")
            key = str(source)
            if key in captures:
                raise ValueError("Duplicate raw capture declaration")
            captures[key] = row
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"path": source_rel, "error": str(exc)})
    return captures, errors


def _summarize_hits(matches: Iterable[str], limit: int = 5) -> str:
    uniq: List[str] = []
    for m in matches:
        if m not in uniq:
            uniq.append(m)
        if len(uniq) >= limit:
            break
    return ",".join(uniq)


def check_utf8(path: str) -> dict:
    result = {
        "path": path,
        "utf8_ok": False,
        "has_bom": False,
        "mojibake_hits": [],
        "error": None,
    }
    try:
        raw = Path(path).read_bytes()
        result["has_bom"] = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8", errors="strict")
        result["utf8_ok"] = True

        hits_summary: List[str] = []
        for name, rx in MOJIBAKE_REGEXES:
            matches = rx.findall(text)
            if not matches:
                continue
            samples = _summarize_hits(matches)
            hits_summary.append(f"{name}:{len(matches)}:{samples}" if samples else f"{name}:{len(matches)}")

        ctrl = CONTROL_CHARS_RE.findall(text)
        if ctrl:
            hits_summary.append(f"CONTROL_CHARS:{len(ctrl)}")

        if hits_summary:
            result["mojibake_hits"] = hits_summary
    except UnicodeDecodeError as e:
        result["error"] = f"UnicodeDecodeError: {e}"
    except Exception as e:
        result["error"] = str(e)
    return result


def _filter_existing_files(paths: Iterable[str]) -> List[str]:
    out = []
    for p in paths:
        if os.path.isfile(p) and is_text_file(p):
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-today", action="store_true")
    ap.add_argument("--tracked", action="store_true", help="Scan all tracked text; verify immutable raw-capture sidecars")
    ap.add_argument("--since", default=None)
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--root", default=None, help="Scan all text files under a directory (overrides --since/--files)")
    args = ap.parse_args()

    if args.root:
        files = iter_files_under(args.root)
    elif args.tracked:
        files = git_tracked_files(Path.cwd())
    elif args.files:
        files = _filter_existing_files(args.files)
    elif args.since:
        files = _filter_existing_files(git_changed_since(args.since))
    else:
        files = _filter_existing_files(git_changed_today())

    date = dt.date.today().strftime("%Y-%m-%d")
    out_dir = os.path.join("logs", "ci", date, "encoding")
    os.makedirs(out_dir, exist_ok=True)

    raw_captures, raw_errors = ({}, [])
    if args.tracked and not args.root:
        raw_captures, raw_errors = validate_raw_evidence(
            Path.cwd(), Path(__file__).with_name("encoding_raw_evidence.json")
        )
    raw_evidence = []
    results = []
    bad = []
    for fpath in files:
        capture = raw_captures.get(str(Path(fpath).resolve()))
        if capture is not None:
            raw_evidence.append(capture)
            continue
        r = check_utf8(fpath)
        results.append(r)
        if not r["utf8_ok"]:
            bad.append(r)

    summary = {
        "scanned": len(results),
        "bad": len(bad),
        "bad_paths": [b["path"] for b in bad],
        "raw_evidence": raw_evidence,
        "raw_evidence_count": len(raw_evidence),
        "raw_evidence_errors": raw_errors,
        "mojibake_paths": [r["path"] for r in results if r.get("mojibake_hits")],
        "generated": dt.datetime.now().isoformat(),
    }

    with io.open(os.path.join(out_dir, "session-details.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with io.open(os.path.join(out_dir, "session-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"ENCODING_CHECK scanned={summary['scanned']} bad={summary['bad']} "
          f"raw_evidence={len(raw_evidence)} raw_evidence_errors={len(raw_errors)} out={out_dir}")
    return 0 if summary["bad"] == 0 and not raw_errors else 1


if __name__ == "__main__":
    sys.exit(main())

