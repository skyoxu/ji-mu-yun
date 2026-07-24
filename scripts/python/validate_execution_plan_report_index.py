from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


INDEX_NAME = "95-implementation-report-index.v1.json"
SCHEMA_VERSION = "jimuyun.execution-plan-95-report-index.v1"
REPORT_NAME_PATTERN = re.compile(r"^95-[^\\/]+\.md$")


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def is_simple_name(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
    )


def is_contained(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def validate_index(repository_root: Path) -> list[str]:
    plans_root = repository_root / "execution-plans"
    index_path = plans_root / INDEX_NAME
    try:
        document = json.loads(
            index_path.read_text(encoding="utf-8"), parse_constant=reject_json_constant
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot read index: {exc}"]
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "entries"}
        or document.get("schema_version") != SCHEMA_VERSION
        or not isinstance(document.get("entries"), list)
    ):
        return ["index envelope is invalid"]

    entries = document["entries"]
    if entries != sorted(
        entries,
        key=lambda item: str(item.get("plan_directory", "")).casefold()
        if isinstance(item, dict)
        else "",
    ):
        return ["entries are not case-insensitively sorted"]

    errors: list[str] = []
    seen: set[str] = set()
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"plan_directory", "report_filename"}:
            errors.append(f"entry {position} has an invalid shape")
            continue
        plan_directory = entry["plan_directory"]
        report_filename = entry["report_filename"]
        if not is_simple_name(plan_directory):
            errors.append(f"entry {position} has an unsafe plan_directory")
            continue
        folded = plan_directory.casefold()
        if folded in seen:
            errors.append(f"entry {position} duplicates plan_directory {plan_directory!r}")
            continue
        seen.add(folded)
        if not isinstance(report_filename, str) or not REPORT_NAME_PATTERN.fullmatch(report_filename):
            errors.append(f"entry {position} has an unsafe report_filename")
            continue
        plan_root = plans_root / plan_directory
        report_path = plan_root / report_filename
        if not plan_root.is_dir() or not is_contained(plan_root, plans_root):
            errors.append(f"entry {position} references a missing or escaping plan directory")
            continue
        if not report_path.is_file() or not is_contained(report_path, plan_root):
            errors.append(f"entry {position} references a missing or escaping report")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the repository implementation-report index."
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    args = parser.parse_args(argv)
    errors = validate_index(args.repository_root.resolve())
    print(
        json.dumps(
            {
                "schema_version": "jimuyun.execution-plan-95-report-index-validation.v1",
                "ok": not errors,
                "errors": errors,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
