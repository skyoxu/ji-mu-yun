#!/usr/bin/env python3
"""Build deterministic source-derived inventories for shared LLM/Codex entrypoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Iterator


PLAN_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ROOT = PLAN_DIR.parents[1]
SCANNER_REVISION = "hosted-inventory-scanner.v1"
EXCLUSION_POLICY_REVISION = "phase-production-source-scope.v1"
GENERATED_BY = f"tools/build_hosted_inventory.py@{SCANNER_REVISION}"

INVENTORY_FILENAMES = {
    "codex-hosted": "codex-hosted-callers.v1.json",
    "llm-route-engine": "llm-route-engine-callers.v1.json",
    "python-backend": "python-llm-backend-callers.v1.json",
}

ALLOWED_DIRECT_IMPLEMENTATIONS = {
    "PhaseA.Platform/Llm/CodexCliChatClient.cs": "shared-read-only-llm-client",
    "PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs": "shared-codex-command-factory",
    "PhaseA.Platform/Runs/HostedProcessRunner.cs": "shared-process-runner",
    "scripts/sc/_llm_backend.py": "shared-python-llm-backend",
}

CODEX_FACTORY_RE = re.compile(
    r"\bCodexHostedProcessCommandFactory\s*\.\s*Build(?:Async)?\s*\(", re.MULTILINE
)
LLM_ENGINE_DECL_RE = re.compile(
    r"\b(?:ILlmRouteEngine|LlmRouteEngine)\??\s+([A-Za-z_]\w*)"
)
PYTHON_BACKEND_RE = re.compile(r"\brun_llm_exec\s*\(", re.MULTILINE)

DIRECT_PATTERNS = (
    ("process_start_info", re.compile(r"\bnew\s+ProcessStartInfo\b")),
    (
        "provider_endpoint",
        re.compile(r"(?i)\bapi\.(?:openai|anthropic)\.com\b"),
    ),
    (
        "provider_client",
        re.compile(r"\b(?:OpenAIClient|AnthropicClient)\b"),
    ),
    (
        "codex_exec_literal",
        re.compile(
            r"(?i)[\"']codex(?:\.exe)?[\"']\s*,\s*[\"']exec[\"']"
        ),
    ),
)


def stable_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_relative(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def is_generated_or_test_path(relative_path: str) -> bool:
    parts = tuple(part.casefold() for part in Path(relative_path).parts)
    name = Path(relative_path).name.casefold()
    return (
        any(part in {"bin", "obj", "__pycache__", ".venv", "node_modules"} for part in parts)
        or "tests" in parts
        or name.startswith("test_")
    )


def iter_production_sources(repo_root: Path) -> Iterator[Path]:
    candidates: list[Path] = []
    phase_root = repo_root / "PhaseA.Platform"
    scripts_root = repo_root / "scripts"
    if phase_root.is_dir():
        candidates.extend(phase_root.rglob("*.cs"))
    if scripts_root.is_dir():
        candidates.extend(scripts_root.rglob("*.py"))

    normalized: list[tuple[str, Path]] = []
    for path in candidates:
        relative = normalized_relative(repo_root, path)
        if not is_generated_or_test_path(relative):
            normalized.append((relative, path))
    for _relative, path in sorted(normalized, key=lambda item: (item[0].casefold(), item[0])):
        yield path


def build_source_snapshot(repo_root: Path, sources: Iterable[Path]) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for path in sources:
        content = path.read_bytes()
        files.append(
            {
                "path": normalized_relative(repo_root, path),
                "sha256": sha256_bytes(content),
                "size_bytes": len(content),
            }
        )
    identity_input = {
        "scanner_revision": SCANNER_REVISION,
        "exclusion_policy_revision": EXCLUSION_POLICY_REVISION,
        "files": files,
    }
    return {
        "schema_version": "jimuyun.knowledge-source-snapshot.v1",
        "snapshot_mode": "working-tree",
        "scanner_revision": SCANNER_REVISION,
        "exclusion_policy_revision": EXCLUSION_POLICY_REVISION,
        "files": files,
        "source_snapshot_id": sha256_bytes(stable_json_bytes(identity_input)),
    }


def line_and_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    return line, offset - line_start + 1


def callsite(
    family: str,
    symbol: str,
    repo_root: Path,
    path: Path,
    text: str,
    offset: int,
) -> dict[str, object]:
    relative = normalized_relative(repo_root, path)
    line, column = line_and_column(text, offset)
    source_sha256 = sha256_bytes(path.read_bytes())
    fingerprint_input = {
        "family": family,
        "path": relative,
        "line": line,
        "column": column,
        "symbol": symbol,
        "source_sha256": source_sha256,
    }
    fingerprint = sha256_bytes(stable_json_bytes(fingerprint_input))
    return {
        "callsite_id": f"{family}:{fingerprint[:20]}",
        "path": relative,
        "line": line,
        "column": column,
        "symbol": symbol,
        "source_sha256": source_sha256,
        "callsite_fingerprint": fingerprint,
        "reachability_status": "unassessed",
        "migration_status": "unassessed",
        "context_envelope_status": "unassessed",
    }


def sorted_callsites(items: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        items,
        key=lambda item: (
            str(item["path"]).casefold(),
            str(item["path"]),
            int(item["line"]),
            int(item["column"]),
            str(item.get("symbol", "")),
        ),
    )


def scan_codex_hosted(repo_root: Path, sources: Iterable[Path]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    callers: list[dict[str, object]] = []
    for path in sources:
        if path.suffix.casefold() != ".cs":
            continue
        text = path.read_text(encoding="utf-8")
        for match in CODEX_FACTORY_RE.finditer(text):
            callers.append(
                callsite(
                    "codex-hosted",
                    "CodexHostedProcessCommandFactory.Build/BuildAsync",
                    repo_root,
                    path,
                    text,
                    match.start(),
                )
            )
    return sorted_callsites(callers), []


def scan_llm_route_engine(repo_root: Path, sources: Iterable[Path]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    callers: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for path in sources:
        if path.suffix.casefold() != ".cs":
            continue
        text = path.read_text(encoding="utf-8")
        identifiers = sorted(set(LLM_ENGINE_DECL_RE.findall(text)))
        for identifier in identifiers:
            invocation = re.compile(
                rf"\b{re.escape(identifier)}\s*\.\s*CompleteAsync\s*\(", re.MULTILINE
            )
            for match in invocation.finditer(text):
                key = (normalized_relative(repo_root, path), match.start())
                if key in seen:
                    continue
                seen.add(key)
                callers.append(
                    callsite(
                        "llm-route-engine",
                        f"{identifier}.CompleteAsync",
                        repo_root,
                        path,
                        text,
                        match.start(),
                    )
                )
    return sorted_callsites(callers), []


def scan_python_backend(repo_root: Path, sources: Iterable[Path]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    callers: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    backend_path = "scripts/sc/_llm_backend.py"
    for path in sources:
        if path.suffix.casefold() != ".py":
            continue
        relative = normalized_relative(repo_root, path)
        text = path.read_text(encoding="utf-8")
        for match in PYTHON_BACKEND_RE.finditer(text):
            item = callsite(
                "python-backend", "run_llm_exec", repo_root, path, text, match.start()
            )
            line_start = text.rfind("\n", 0, match.start()) + 1
            prefix = text[line_start : match.start()].strip()
            if relative == backend_path and prefix.startswith("def"):
                item["reason"] = "entrypoint-definition"
                excluded.append(item)
            else:
                callers.append(item)
    return sorted_callsites(callers), sorted_callsites(excluded)


def scan_direct_invocations(repo_root: Path, sources: Iterable[Path]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    violations: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for path in sources:
        relative = normalized_relative(repo_root, path)
        text = path.read_text(encoding="utf-8")
        for rule_id, pattern in DIRECT_PATTERNS:
            for match in pattern.finditer(text):
                key = (relative, match.start(), rule_id)
                if key in seen:
                    continue
                seen.add(key)
                item = callsite(
                    "direct-llm-invocation",
                    rule_id,
                    repo_root,
                    path,
                    text,
                    match.start(),
                )
                item["rule_id"] = rule_id
                allowed_reason = ALLOWED_DIRECT_IMPLEMENTATIONS.get(relative)
                if allowed_reason:
                    item["reason"] = allowed_reason
                    excluded.append(item)
                else:
                    item["failure_code"] = "direct_llm_invocation_bypass"
                    violations.append(item)
    return sorted_callsites(violations), sorted_callsites(excluded)


def inventory_envelope(
    family: str,
    snapshot_id: str,
    callers: list[dict[str, object]],
    excluded: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "jimuyun.hosted-caller-inventory.v1",
        "entrypoint_family": family,
        "source_snapshot_id": snapshot_id,
        "generated_by": GENERATED_BY,
        "callers": callers,
        "excluded_candidates": excluded,
    }


def build_outputs(repo_root: Path) -> dict[str, dict[str, object]]:
    sources = list(iter_production_sources(repo_root))
    snapshot = build_source_snapshot(repo_root, sources)
    snapshot_id = str(snapshot["source_snapshot_id"])

    codex_callers, codex_excluded = scan_codex_hosted(repo_root, sources)
    llm_callers, llm_excluded = scan_llm_route_engine(repo_root, sources)
    python_callers, python_excluded = scan_python_backend(repo_root, sources)
    violations, direct_excluded = scan_direct_invocations(repo_root, sources)

    return {
        "source-snapshot.v1.json": snapshot,
        INVENTORY_FILENAMES["codex-hosted"]: inventory_envelope(
            "codex-hosted", snapshot_id, codex_callers, codex_excluded
        ),
        INVENTORY_FILENAMES["llm-route-engine"]: inventory_envelope(
            "llm-route-engine", snapshot_id, llm_callers, llm_excluded
        ),
        INVENTORY_FILENAMES["python-backend"]: inventory_envelope(
            "python-backend", snapshot_id, python_callers, python_excluded
        ),
        "direct-llm-invocation-violations.v1.json": {
            "schema_version": "jimuyun.direct-llm-invocation-violations.v1",
            "source_snapshot_id": snapshot_id,
            "generated_by": GENERATED_BY,
            "violations": violations,
            "excluded_candidates": direct_excluded,
        },
    }


def write_outputs(output_dir: Path, outputs: dict[str, dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, value in sorted(outputs.items()):
        rendered = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"
        (output_dir / filename).write_text(rendered, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=PLAN_DIR / "inventories")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if not (repo_root / "PhaseA.Platform").is_dir() or not (repo_root / "scripts").is_dir():
        raise SystemExit(f"ERROR invalid repository root: {repo_root}")
    outputs = build_outputs(repo_root)
    write_outputs(args.output_dir.resolve(), outputs)

    counts = {
        "codex-hosted": len(outputs[INVENTORY_FILENAMES["codex-hosted"]]["callers"]),
        "llm-route-engine": len(outputs[INVENTORY_FILENAMES["llm-route-engine"]]["callers"]),
        "python-backend": len(outputs[INVENTORY_FILENAMES["python-backend"]]["callers"]),
        "direct-violations": len(outputs["direct-llm-invocation-violations.v1.json"]["violations"]),
    }
    snapshot_id = outputs["source-snapshot.v1.json"]["source_snapshot_id"]
    print(
        "INVENTORY_BUILD PASS "
        + " ".join(f"{key}={value}" for key, value in counts.items())
        + f" snapshot={snapshot_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
