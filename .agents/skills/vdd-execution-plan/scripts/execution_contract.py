"""ADR-0041: shared path and ownerless-guard rules, without owner inference."""
from pathlib import PurePosixPath


def selector_file_path(value):
    """A pytest node is a selector; only its file belongs in path sets."""
    return value.split("::", 1)[0]


def is_test_path(value):
    if not isinstance(value, str) or "\\" in value or ":" in value:
        return False
    parts = PurePosixPath(value).parts
    if not parts or value.startswith("/") or ".." in parts:
        return False
    return (value.startswith(("tests/", "scripts/sc/tests/", "PhaseA.Platform.Tests/"))
            or (value.startswith(".agents/skills/") and "tests" in parts[3:-1]))


def test_only_surface(item, failures):
    """Execution half of the guard rule; semantic kind is checked separately."""
    paths = [*item.get("allowed_write_paths", []), *item.get("planned_new_files", []),
             *item.get("execution_snapshot_paths", []),
             *(item.get("rollback_scope") or {}).get("production_paths", [])]
    return bool(item.get("production_owners") == [] and item.get("allowed_write_paths")
                and paths and all(is_test_path(p) for p in paths)
                and all(f.get("failure_family") != "expected-red" for f in failures))


def ownerless_guard(item, obligations, failures):
    return bool(test_only_surface(item, failures) and obligations
                and all(o.get("obligation_kind") in {"governance", "constraint"}
                        for o in obligations))
