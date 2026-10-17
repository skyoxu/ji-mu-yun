"""Restore only exact Q8-bound bytes; never execute tests or alter receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

WS = Path(__file__).resolve().parents[4]
Q8 = WS / "logs/08-05-real-skill-replay/review-repair-20261009/current-run-q8-recovery-r4"
OUT = Path(__file__).resolve().parent


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_bytes(revision, relative):
    spec = ":" + relative if revision == "index" else revision + ":" + relative
    return subprocess.check_output(["git", "show", spec], cwd=WS)


def inspect(revision, restore=False):
    bindings = {}
    for row in load(Q8 / "terminal-input.v2.json")["predecessors"]:
        root = WS / row["run_root"]
        for stage in ("probe", "red", "green", "refactor", "regression", "terminal"):
            base = root / "canonical-evidence" / stage
            receipt = base / "process-receipt.v2.json"
            if not receipt.is_file():
                continue
            data = load(receipt)
            refs = {str((base / (name + ".bin")).relative_to(WS)).replace("\\", "/"): data[name + "_sha256"]
                    for name in ("stdout", "stderr")}
            refs.update(data.get("target_hashes", {}))
            refs.update(data.get("fixture_hashes", {}))
            for relative, expected in refs.items():
                bindings.setdefault(relative, set()).add(expected)
    mismatches = []
    unresolved = []
    for relative, expected_set in bindings.items():
        if len(expected_set) != 1:
            unresolved.append({"path": relative, "conflicting_bindings": sorted(expected_set)})
            continue
        expected = next(iter(expected_set))
        path = WS / relative
        original = path.read_bytes()
        committed = git_bytes(revision, relative)
        if digest(original) == expected and digest(committed) == expected:
            continue
        normalized = original.replace(b"\r\n", b"\n")
        candidates = [original, committed, normalized, normalized.replace(b"\n", b"\r\n")]
        match = next((candidate for candidate in candidates if digest(candidate) == expected), None)
        row = {"path": relative, "expected": expected, "worktree_sha256": digest(original),
               "git_sha256": digest(committed), "recoverable": match is not None,
               "semantic_bytes_unchanged": match is not None and match.replace(b"\r\n", b"\n") == normalized}
        mismatches.append(row)
        if match is None or not row["semantic_bytes_unchanged"]:
            unresolved.append(row)
        elif restore and original != match:
            path.write_bytes(match)
    report = {"authorizes": [], "q8_input": str((Q8 / "terminal-input.v2.json").relative_to(WS)),
              "revision": revision, "bound_files": len(bindings), "mismatches": mismatches,
              "unresolved": unresolved, "tests_executed": False}
    destination = OUT / ("restoration.json" if restore else "inspection-" + revision.replace(":", "index") + ".json")
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"bound_files": len(bindings), "mismatches": len(mismatches), "unresolved": len(unresolved)}))
    for row in mismatches:
        print(row["path"], "recoverable=" + str(row["recoverable"]))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    inspect(args.revision, args.restore)
