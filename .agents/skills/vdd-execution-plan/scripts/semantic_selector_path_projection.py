"""ADR-0041: reconcile redundant snapshot spelling against one explicit script.

No repository search or semantic owner inference. A direct Python command is
the execution target; a singleton snapshot may omit that target's final parent
directory. Explicit source paths, planned files and ambiguous bindings win.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath


def _relative(raw):
    if not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != raw:
        return None
    return path


def _safe(root, relative):
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            return None
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return path


def project_selector_paths(root, source, value):
    """Return a copy and exact changes; leave uncertain or explicit paths intact."""
    root = Path(root)
    changes = []
    hints = value.get("slice_hints")
    if not isinstance(hints, list):
        return value, changes
    frozen = json.dumps(source.get("source_contracts", []), sort_keys=True)
    normalized = deepcopy(value)
    for index, hint in enumerate(normalized["slice_hints"]):
        if not isinstance(hint, dict) or hint.get("planned_new_files") != []:
            continue
        snapshots, commands = hint.get("execution_snapshot_paths"), hint.get("validation_commands")
        if not isinstance(snapshots, list) or len(snapshots) != 1:
            continue
        if not isinstance(commands, list) or len(commands) != 1:
            continue
        argv = commands[0]
        if (not isinstance(argv, list) or len(argv) != 2
                or argv[0] not in {"python", "python3", "python.exe", "python3.exe"}):
            continue
        old, target = _relative(snapshots[0]), _relative(argv[1])
        if old is None or target is None or target.suffix != ".py":
            continue
        # An omitted immediate parent only, with the exact target already in argv.
        if target.parent == PurePosixPath(".") or target.parent.parent / target.name != old:
            continue
        old_path, target_path = _safe(root, old), _safe(root, target)
        if old_path is None or target_path is None or old_path.exists() or not target_path.is_file():
            continue
        if snapshots[0] in frozen:
            continue
        other_fields = {k: v for k, v in hint.items() if k != "execution_snapshot_paths"}
        if snapshots[0] in json.dumps(other_fields, sort_keys=True):
            continue
        hint["execution_snapshot_paths"] = [argv[1]]
        changes.append({"hint_index": index, "obligation_ids": hint.get("obligation_ids", []),
                        "before": snapshots[0], "after": argv[1], "validation_command": argv,
                        "target_sha256": hashlib.sha256(target_path.read_bytes()).hexdigest()})
    return (normalized if changes else value), changes
