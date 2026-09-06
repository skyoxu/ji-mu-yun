"""ADR-0041: bounded file discovery hints, never owner or oracle authority."""
import hashlib
from pathlib import Path
import re
import subprocess

PATH_CONTEXT_PROMPT = (
    "\nREPOSITORY PATH GROUNDING: repository_path_context lists existing file candidates, not assigned owners. "
    "Read relevant source and test files in the current repository before choosing paths; search further when "
    "the candidate list is incomplete. production_owners must be real repository-relative implementation "
    "filenames, never the obligation subject or component display name. allowed_write_paths must include "
    "the production files needed for the change. execution_snapshot_paths name existing RED selectors/fixtures "
    "or exact source-authorized planned test files; they are not names for future logs or observations. "
    "Do not invent logs/*.json as verification inputs, create placeholder files, or infer proof from a filename. "
    "Keep all frozen obligation semantics and existing path/coverage checks unchanged."
)


def _words(text):
    return set(re.findall(r"[a-z][a-z0-9]{2,}", text.lower())) - {
        "the", "and", "for", "with", "must", "before", "after", "from", "that", "this"}


def enrich_repository_context(root, payload, *, max_files=120):
    nested = isinstance(payload.get("input"), dict)
    semantic = payload["input"] if nested else payload
    if "repository_path_context" in semantic:
        return payload
    root = Path(root).resolve()
    context = {"schema": "vdd.repository-path-context.v1", "authority": "discovery-only",
               "complete": False, "files": []}
    try:
        proc = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"],
                              cwd=root, capture_output=True, timeout=5, check=False)
        if proc.returncode != 0:
            raise OSError("repository file discovery unavailable")
        candidates = []
        for name in sorted(set(proc.stdout.decode("utf-8").split("\0")) - {""}):
            parts = Path(name).parts
            if any(p in {".git", "logs", "execution-plans", "__pycache__", "node_modules", ".pytest_cache"}
                   or p.startswith(".tmp") for p in parts):
                continue
            path = root / name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                continue
            candidates.append((name, _words(name)))
        ranked = []
        for obligation in semantic.get("obligations", []):
            words = _words(" ".join(str(obligation.get(k, "")) for k in ("subject", "expected_behavior")))
            matches = [(len(words & tokens), name) for name, tokens in candidates if words & tokens]
            ranked.append([name for score, name in sorted(matches, key=lambda item: (-item[0], item[1]))[:4]])
        selected = []
        for rank in range(4):
            for matches in ranked:
                if rank < len(matches) and matches[rank] not in selected and len(selected) < max_files:
                    selected.append(matches[rank])
        for name in selected:
            with (root / name).open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            context["files"].append({"path": name, "sha256": "sha256:" + digest})
        context["status"] = "available"
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        context["status"] = "discovery-unavailable"
        context["files"] = []
    enriched = {**semantic, "repository_path_context": context}
    return {**payload, "input": enriched} if nested else enriched
