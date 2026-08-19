"""Build deterministic repository knowledge layers from committed main facts.

The derived catalog implements ADR-0044, ADR-0048, and ADR-0057. Source bytes are read
only from the pinned Git ref; the worktree is never promoted as fact.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from fnmatch import fnmatchcase
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


DOMAINS = ("toolchain", "phase", "workspace", "marketplace")
HARD_EXCLUDED_PREFIXES = ("docs/migration/",)
ADR_ID = re.compile(r"ADR-\d{4}")
MARKDOWN_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
STATUS_LINE = re.compile(r"^(?:-\s*)?status\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def prefixed_sha256(value: bytes) -> str:
    return "sha256:" + sha256(value)


def normalized_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("invalid_repository_path")
    return path.as_posix()


def select_versioned_plan_resource(
    directory: str,
    paths: Iterable[str],
    stems: tuple[str, ...],
) -> str | None:
    direct_depth = directory.count("/") + 1
    candidates: list[tuple[int, int, str]] = []
    for path in paths:
        if path.count("/") != direct_depth:
            continue
        name = PurePosixPath(path).name
        for priority, stem in enumerate(stems):
            matched = re.fullmatch(rf"{re.escape(stem)}\.v(\d+)\.json", name, re.IGNORECASE)
            if matched:
                candidates.append((int(matched.group(1)), -priority, path))
                break
    return max(candidates)[2] if candidates else None


def is_hard_excluded(path: str) -> bool:
    normalized = normalized_path(path)
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in HARD_EXCLUDED_PREFIXES)


def excluded_source_prefixes(exclusions: dict[str, Any]) -> tuple[str, ...]:
    """Return source-snapshot exclusions declared by the current policy."""
    prefixes = list(HARD_EXCLUDED_PREFIXES)
    for rule in exclusions.get("rules", []):
        if (
            isinstance(rule, dict)
            and rule.get("disposition") == "excluded"
            and "source-snapshot" in rule.get("applies_to", [])
            and isinstance(rule.get("path_prefix"), str)
        ):
            prefixes.append(normalized_path(rule["path_prefix"]).rstrip("/") + "/")
    return tuple(sorted(set(prefixes)))


def is_policy_excluded(path: str, exclusions: dict[str, Any]) -> bool:
    normalized = normalized_path(path)
    if any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in excluded_source_prefixes(exclusions)
    ):
        return True
    return any(
        isinstance(rule, dict)
        and rule.get("disposition") == "excluded"
        and "source-snapshot" in rule.get("applies_to", [])
        and isinstance(rule.get("path_pattern"), str)
        and fnmatchcase(normalized, rule["path_pattern"])
        for rule in exclusions.get("rules", [])
    )


@dataclass
class MainSnapshot:
    repository_root: Path
    authority_ref: str = "refs/heads/main"
    commit: str = field(init=False)
    paths: tuple[str, ...] = field(init=False)
    _bytes: dict[str, bytes] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.repository_root = self.repository_root.resolve()
        self.commit = self._git_text("rev-parse", self.authority_ref).strip()
        if not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ValueError("invalid_main_commit")
        listed = self._git_text("ls-tree", "-r", "--name-only", self.commit).splitlines()
        self.paths = tuple(sorted(normalized_path(path) for path in listed if path))

    def _git_text(self, *arguments: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.repository_root), *arguments],
            text=True,
            encoding="utf-8",
        )

    def contains(self, path: str) -> bool:
        return normalized_path(path) in self.paths

    def read_bytes(self, path: str) -> bytes:
        normalized = normalized_path(path)
        if is_hard_excluded(normalized):
            raise ValueError("hard_excluded_source")
        if normalized not in self._bytes:
            self._bytes[normalized] = subprocess.check_output(
                ["git", "-C", str(self.repository_root), "show", f"{self.commit}:{normalized}"]
            )
        return self._bytes[normalized]

    def read_text(self, path: str) -> str:
        return self.read_bytes(path).decode("utf-8-sig")

    def digest(self, path: str) -> str:
        return sha256(self.read_bytes(path))

    def under(self, prefix: str) -> list[str]:
        normalized = normalized_path(prefix).rstrip("/") + "/"
        return [path for path in self.paths if path.startswith(normalized)]


def _slug(value: str) -> str:
    lowered = value.casefold().replace("_", "-")
    return re.sub(r"[^a-z0-9.-]+", "-", lowered).strip("-")


def _title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        match = MARKDOWN_HEADING.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    frontmatter = re.search(r"^title\s*:\s*(.+?)\s*$", content, re.IGNORECASE | re.MULTILINE)
    return frontmatter.group(1).strip(" '\"") if frontmatter else fallback


def _anchors(content: str, fallback: str) -> list[dict[str, Any]]:
    lines = content.splitlines()
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines, 1):
        match = MARKDOWN_HEADING.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    if not headings:
        return [{"anchor": fallback, "line_start": 1, "line_end": max(1, len(lines))}]
    values: list[dict[str, Any]] = []
    for position, (line, level, heading) in enumerate(headings):
        end = len(lines)
        for next_line, next_level, _ in headings[position + 1 :]:
            if next_level <= level:
                end = next_line - 1
                break
        values.append({"anchor": heading, "line_start": line, "line_end": max(line, end)})
    return values


def _status(content: str) -> str:
    match = STATUS_LINE.search(content)
    return match.group(1).strip().strip("`'").casefold() if match else "unmarked"


def _visibility(primary_domain: str, *, dependencies: Iterable[str] = ()) -> dict[str, str]:
    dependency_set = set(dependencies)
    return {
        domain: "active" if domain == primary_domain else "dependency" if domain in dependency_set else "excluded"
        for domain in DOMAINS
    }


def _consumer_ids(primary_domain: str) -> list[str]:
    if primary_domain == "marketplace":
        return ["vdd", "bootstrap", "refactor-acceptance"]
    return ["vdd", "bootstrap", "refactor-acceptance"]


def _domain_for_adr(identifier: str, title: str) -> tuple[str, tuple[str, ...]]:
    number = int(identifier.split("-")[1])
    if number >= 41 or number in {12, 17}:
        return "toolchain", ("phase",)
    if 32 <= number <= 40:
        return "phase", ("toolchain", "workspace")
    return "workspace", ("toolchain", "phase")


def _domain_for_plan(path: str, title: str) -> tuple[str, tuple[str, ...]]:
    value = f"{path} {title}".casefold()
    if any(token in value for token in ("knowledge", "review", "adapter", "acceptance-skill")):
        return "toolchain", ("phase", "workspace")
    return "phase", ("toolchain", "workspace")


def _plan_catalog_status(raw_status: str, content: str = "") -> str:
    normalized = raw_status.replace("_", "-").replace(" ", "-")
    if any(value in normalized for value in ("implementation-complete", "acceptance-passed", "archived")) or normalized in {"complete", "completed"}:
        return "historical"
    if any(value in normalized for value in ("paused", "draft", "plan-ready", "proposed")) or normalized == "unmarked":
        return "conditional"
    folded = content.casefold()
    if "strictly downstream" in folded and "may start until" in folded:
        return "conditional"
    return "active"


def _adr_catalog_status(raw_status: str) -> tuple[str, bool]:
    normalized = raw_status.replace("_", "-").replace(" ", "-")
    if normalized == "accepted":
        return "active", True
    if normalized == "proposed":
        return "conditional", True
    if normalized == "superseded":
        return "historical", True
    return "excluded", False


class CatalogBuilder:
    def __init__(self, snapshot: MainSnapshot, policy: dict[str, Any], exclusions: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.policy = policy
        self.exclusions = exclusions
        self.modules: list[dict[str, Any]] = []
        self.sources: dict[str, dict[str, Any]] = {}
        self.routes: list[dict[str, Any]] = []

    def add_source(self, path: str, source_role: str) -> dict[str, Any] | None:
        normalized = normalized_path(path)
        if is_policy_excluded(normalized, self.exclusions) or not self.snapshot.contains(normalized):
            return None
        existing = self.sources.get(normalized)
        if existing is None:
            existing = {
                "path": normalized,
                "sha256": self.snapshot.digest(normalized),
                "source_role": source_role,
            }
            self.sources[normalized] = existing
        elif existing["source_role"] in {"integrity-only", "supporting-source"}:
            existing["source_role"] = source_role
        return existing

    def add_module(
        self,
        *,
        module_id: str,
        kind: str,
        source_path: str,
        source_role: str,
        primary_domain: str,
        dependencies: Iterable[str] = (),
        status: str = "active",
        semantic_eligible: bool = True,
        resources: Iterable[tuple[str, str]] = (),
        relations: Iterable[dict[str, str]] = (),
        consumer_ids: Iterable[str] | None = None,
    ) -> dict[str, Any] | None:
        source = self.add_source(source_path, source_role)
        if source is None:
            return None
        content = self.snapshot.read_text(source_path)
        title = _title(content, PurePosixPath(source_path).name)
        bound_resources: list[dict[str, Any]] = []
        seen_paths = {source_path}
        for role, path in resources:
            normalized = normalized_path(path)
            if normalized in seen_paths:
                continue
            item = self.add_source(normalized, role)
            if item is not None:
                bound_resources.append({"role": role, "path": normalized, "source_sha256": item["sha256"]})
                seen_paths.add(normalized)
        module = {
            "module_id": module_id,
            "entry_id": module_id,
            "kind": kind,
            "title": title,
            "primary_domain": primary_domain,
            "visibility": _visibility(primary_domain, dependencies=dependencies),
            "lifecycle": "repository-source",
            "enforcement_level": "E1",
            "authority_class": "derived_cache",
            "instruction_authority": False,
            "may_override_source": False,
            "source_role": source_role,
            "status": status,
            "source_path": source_path,
            "source_sha256": source["sha256"],
            "anchor": title,
            "anchors": _anchors(content, title),
            "relations": sorted(list(relations), key=lambda item: (item["type"], item["target"])),
            "consumer_ids": sorted(set(consumer_ids or _consumer_ids(primary_domain))),
            "semantic_eligible": semantic_eligible,
            "resources": sorted(bound_resources, key=lambda item: (item["role"], item["path"])),
            "content": content,
        }
        self.modules.append(module)
        return module

    def add_repository_modules(self) -> None:
        self.add_module(
            module_id="repository-rules",
            kind="repository-guide",
            source_path="AGENTS.md",
            source_role="repository-authority",
            primary_domain="toolchain",
            dependencies=("phase", "workspace"),
        )
        self.add_module(
            module_id="repository.overview",
            kind="repository-overview",
            source_path="README.md",
            source_role="repository-overview",
            primary_domain="phase",
            dependencies=("toolchain", "workspace"),
        )

    def add_adrs(self) -> None:
        for path in self.snapshot.under("docs/adr"):
            if not path.endswith(".md"):
                continue
            role = "decision-support" if "/addenda/" in path else "navigation" if path.endswith("/guide.md") else "decision"
            self.add_source(path, role)
            filename_match = ADR_ID.search(PurePosixPath(path).name)
            if filename_match is None or "/addenda/" in path:
                continue
            content = self.snapshot.read_text(path)
            identifier = filename_match.group(0)
            title = _title(content, identifier)
            primary_domain, dependencies = _domain_for_adr(identifier, title)
            status, eligible = _adr_catalog_status(_status(content))
            referenced = sorted(set(ADR_ID.findall(content)) - {identifier})
            relations = [{"type": "references", "target": f"adr.{value}"} for value in referenced]
            self.add_module(
                module_id=f"adr.{identifier}",
                kind="adr",
                source_path=path,
                source_role="decision",
                primary_domain=primary_domain,
                dependencies=dependencies,
                status=status,
                semantic_eligible=eligible,
                relations=relations,
            )

    def accepted_adr_ids(self, content: str) -> list[str]:
        active_ids = {
            module["module_id"].removeprefix("adr.")
            for module in self.modules
            if module.get("kind") == "adr" and module.get("status") == "active"
        }
        return sorted(set(ADR_ID.findall(content)) & active_ids)

    def add_architecture(self) -> None:
        paths = self.snapshot.under("docs/architecture")
        for path in paths:
            if path.endswith(".feature"):
                self.add_source(path, "acceptance-fixture")
                continue
            if not path.endswith(".md"):
                continue
            name = PurePosixPath(path).name
            lower = name.casefold()
            if lower.startswith("zzz-") or "checklist" in lower or lower == "front-matter-standardization-example.md":
                self.add_source(path, "integrity-only")
                continue
            if name.startswith("ADR_INDEX_"):
                scope = "phase" if "PHASE" in name else "godot"
                domain = "phase" if scope == "phase" else "workspace"
                self.add_module(
                    module_id=f"adr-index.{scope}",
                    kind="adr-scope-index",
                    source_path=path,
                    source_role="collection-index",
                    primary_domain=domain,
                    dependencies=("toolchain",),
                )
                continue
            if "/phase-service/" in path:
                module_id = "architecture.phase-service." + ("index" if name == "_index.md" else _slug(name.removesuffix(".md")))
                kind = "architecture-collection" if name == "_index.md" else "architecture-module"
                domain, dependencies = "phase", ("toolchain", "workspace")
            elif "/base/" in path:
                module_id = "architecture.base." + ("index" if name == "00-README.md" else _slug(name.removesuffix(".md")))
                kind = "architecture-collection" if name == "00-README.md" else "architecture-module"
                domain, dependencies = "workspace", ("toolchain", "phase")
            elif "/overlays/" in path:
                parts = PurePosixPath(path).parts
                overlay = _slug(parts[3])
                module_id = f"architecture.overlay.{overlay}." + ("index" if name == "_index.md" else _slug(name.removesuffix(".md")))
                kind = "architecture-collection" if name == "_index.md" else "architecture-overlay"
                domain, dependencies = ("phase", ("toolchain", "workspace")) if "PHASE-A" in path else ("workspace", ("toolchain",))
            else:
                self.add_source(path, "integrity-only")
                continue
            content = self.snapshot.read_text(path)
            governed = self.accepted_adr_ids(content)
            relations = [{"type": "governed_by", "target": f"adr.{value}"} for value in governed]
            self.add_module(
                module_id=module_id,
                kind=kind,
                source_path=path,
                source_role="collection-index" if kind == "architecture-collection" else "architecture-module",
                primary_domain=domain,
                dependencies=dependencies,
                relations=relations,
            )

    def add_standards(self) -> None:
        for path in self.snapshot.under("docs/standards"):
            if not path.endswith(".md"):
                continue
            name = PurePosixPath(path).name
            stem = name.removesuffix(".md")
            if name == "_index.md":
                domain, dependencies, kind = "toolchain", ("phase", "workspace"), "standards-collection"
                module_id = "standards.index"
            elif stem.startswith("godot-"):
                domain, dependencies, kind = "workspace", ("toolchain", "phase"), "standard"
                module_id = "standard." + _slug(stem)
            elif stem == "phase-service":
                domain, dependencies, kind = "phase", ("toolchain", "workspace"), "standard"
                module_id = "standard.phase-service"
            else:
                domain, dependencies, kind = "toolchain", ("phase", "workspace"), "standard"
                module_id = "standard." + _slug(stem)
            content = self.snapshot.read_text(path)
            relations = [
                {"type": "governed_by", "target": f"adr.{value}"}
                for value in self.accepted_adr_ids(content)
            ]
            self.add_module(
                module_id=module_id,
                kind=kind,
                source_path=path,
                source_role="collection-index" if kind.endswith("collection") else "standard",
                primary_domain=domain,
                dependencies=dependencies,
                relations=relations,
            )

    def add_governance_components(self) -> None:
        components = (
            {
                "id": "governance.vdd-execution-plan",
                "title": "VDD execution plan",
                "primary": ".agents/skills/vdd-execution-plan/SKILL.md",
                "resources": (
                    ("cli", ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py"),
                    ("orchestrator", ".agents/skills/vdd-execution-plan/scripts/prepare_knowledge_context.py"),
                    ("route-registry", ".agents/skills/vdd-execution-plan/scripts/skill-contract.json"),
                ),
                "consumer": "vdd",
                "operations": ["locate", "consume", "freeze-plan-context"],
                "freeze_point": "before-plan-source-freeze",
                "locator_mode": "query-and-freeze",
            },
            {
                "id": "governance.quick-dev-tdd-adapter",
                "title": "Quick Dev TDD adapter",
                "primary": ".agents/skills/quick-dev-tdd-adapter/SKILL.md",
                "resources": (
                    ("cli", ".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"),
                    ("orchestrator", ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py"),
                    ("validator", ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py"),
                    ("knowledge-contract", ".agents/skills/quick-dev-tdd-adapter/references/knowledge-consumption.md"),
                    ("implementation-contract", ".agents/skills/quick-dev-tdd-adapter/references/implementation-backend-contract.md"),
                ),
                "consumer": "quick-dev",
                "operations": ["verify-bound", "execute-slice"],
                "freeze_point": "vdd-owned-context",
                "locator_mode": "frozen-context-only",
            },
            {
                "id": "governance.bootstrap-review",
                "title": "Bootstrap Review",
                "primary": ".agents/skills/run-phase-bootstrap-review/SKILL.md",
                "resources": (
                    ("cli", ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"),
                    ("orchestrator", ".agents/skills/run-phase-bootstrap-review/scripts/_control_plane.py"),
                    ("route-registry", ".agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json"),
                ),
                "consumer": "bootstrap",
                "operations": ["locate", "prepare", "review", "gate", "seal", "finalize"],
                "freeze_point": "artifact-view-prepare",
                "locator_mode": "pre-prepare-query-and-freeze",
            },
            {
                "id": "governance.refactor-implementation-acceptance",
                "title": "Refactor implementation acceptance",
                "primary": ".agents/skills/run-refactor-implementation-acceptance/SKILL.md",
                "resources": (
                    ("cli", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"),
                    ("knowledge-adapter", ".agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py"),
                    ("knowledge-validator", ".agents/skills/run-refactor-implementation-acceptance/scripts/knowledge_context.py"),
                    ("orchestrator", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_core.py"),
                    ("route-registry", ".agents/skills/run-refactor-implementation-acceptance/policies/phase-service-code-review.v1.json"),
                    ("acceptance-matrix-contract", ".agents/skills/run-refactor-implementation-acceptance/schemas/implementation-acceptance-matrix.v1.schema.json"),
                    ("phase-graph-contract", ".agents/skills/run-refactor-implementation-acceptance/schemas/phase-graph.v1.schema.json"),
                    ("knowledge-maintenance-route-contract", ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-knowledge-maintenance-route.v1.schema.json"),
                ),
                "consumer": "refactor-acceptance",
                "operations": ["inspect", "build-matrix", "bootstrap-gate", "finalize"],
                "freeze_point": "acceptance-run-input",
                "locator_mode": "query-and-freeze",
            },
            {
                "id": "governance.knowledge-locator",
                "title": "Repository Knowledge Locator",
                "primary": "scripts/python/knowledge_locator.py",
                "resources": (
                    ("core", "scripts/python/_knowledge_locator_core.py"),
                    ("catalog-core", "scripts/python/_knowledge_catalog_builder.py"),
                    ("catalog-builder", "scripts/python/build_knowledge_catalog.py"),
                    ("index-builder", "scripts/python/build_knowledge_index.py"),
                    ("publication-gate", "scripts/python/publish_knowledge_catalog.py"),
                    ("generation-pruner", "scripts/python/prune_knowledge_generations.py"),
                    ("query-evaluator", "scripts/python/evaluate_knowledge_queries.py"),
                    ("contract", "knowledge/contracts/knowledge-locator-request.v1.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-locator-result.v1.schema.json"),
                    ("contract", "knowledge/contracts/repository-knowledge-catalog.v2.schema.json"),
                    ("contract", "knowledge/contracts/repository-source-snapshot.v1.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-consumer-projections.v1.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-consumer-context.v1.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-publication-generation.v1.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-index-pointer.v2.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-publication-report.v1.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-publication-request.v1.schema.json"),
                    ("contract", "knowledge/contracts/knowledge-generation-retention-policy.v1.schema.json"),
                    ("evaluation-suite", "knowledge/evaluation/repository-knowledge-query-suite.v1.json"),
                    ("policy", "knowledge/policies/consumer-policies.v1.json"),
                    ("policy", "knowledge/policies/consumer-policies.v2.json"),
                    ("policy", "knowledge/policies/source-exclusions.v1.json"),
                    ("policy", "knowledge/policies/generation-retention.v1.json"),
                ),
                "consumer": "server-registry",
                "operations": ["locate", "rank", "verify-snapshot", "verify-source-hash", "restore-lkg", "prune-generations"],
                "freeze_point": "consumer-owned",
                "locator_mode": "deterministic-service",
            },
            {
                "id": "governance.knowledge-maintenance",
                "title": "Repository knowledge maintenance",
                "primary": ".agents/skills/maintain-knowledge-base/SKILL.md",
                "resources": (
                    ("cli", ".agents/skills/maintain-knowledge-base/scripts/maintain_knowledge.py"),
                    ("publication-authorizer", ".agents/skills/maintain-knowledge-base/scripts/prepare_publication_request.py"),
                    ("catalog-builder", "scripts/python/build_knowledge_catalog.py"),
                    ("publication-gate", "scripts/python/publish_knowledge_catalog.py"),
                    ("publication-request-contract", "knowledge/contracts/knowledge-publication-request.v1.schema.json"),
                    ("generation-pruner", "scripts/python/prune_knowledge_generations.py"),
                    ("retention-policy", "knowledge/policies/generation-retention.v1.json"),
                ),
                "consumer": "maintainer",
                "operations": ["existing-only", "targeted", "refresh-derived-index", "authorize-publication", "restore-lkg", "prune-generations"],
                "freeze_point": "pinned-main-at-run-start",
                "locator_mode": "maintenance-only",
            },
            {
                "id": "skill-input-execution",
                "title": "Typed Skill Input execution",
                "primary": "scripts/python/skill_input_consumption.py",
                "resources": (
                    ("consumer", "scripts/python/skill_input_consumption.py"),
                    ("launcher", "scripts/python/launch_skill_input_consumer.py"),
                    ("validator", "scripts/python/validate_skill_input_consumption.py"),
                    ("contract", ".agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json"),
                ),
                "consumer": "vdd",
                "operations": ["prepare", "launch", "validate", "replay"],
                "freeze_point": "candidate-input",
                "locator_mode": "deterministic-service",
            },
            {
                "id": "knowledge-execution-gates",
                "title": "Knowledge execution gates",
                "primary": "scripts/python/knowledge_context_validation.py",
                "resources": (
                    ("validator", "scripts/python/knowledge_context_validation.py"),
                    ("locator", "scripts/python/knowledge_locator.py"),
                    ("contract", "knowledge/contracts/knowledge-consumer-context.v1.schema.json"),
                    ("policy", "knowledge/policies/consumer-policies.v2.json"),
                ),
                "consumer": "vdd",
                "operations": ["validate", "freshness", "source-hash", "replay"],
                "freeze_point": "context-consumption",
                "locator_mode": "deterministic-service",
            },
        )
        for component in components:
            module = self.add_module(
                module_id=component["id"],
                kind="governance-component",
                source_path=component["primary"],
                source_role="skill-entrypoint" if component["primary"].endswith("SKILL.md") else "cli-entrypoint",
                primary_domain="toolchain",
                dependencies=("phase", "workspace"),
                resources=component["resources"],
                relations=(
                    {"type": "governed_by", "target": "adr.ADR-0044"},
                    {"type": "governed_by", "target": "adr.ADR-0048"},
                    *(
                        ({"type": "governed_by", "target": "adr.ADR-0050"},)
                        if component["id"] in {"governance.knowledge-locator", "governance.knowledge-maintenance"}
                        else ()
                    ),
                    *(
                        ({"type": "governed_by", "target": "adr.ADR-0057"},)
                        if component["id"] in {
                            "governance.vdd-execution-plan",
                            "governance.refactor-implementation-acceptance",
                            "governance.knowledge-locator",
                            "governance.knowledge-maintenance",
                        }
                        else ()
                    ),
                ),
                consumer_ids=("vdd", "bootstrap", "refactor-acceptance"),
            )
            if module is None:
                continue
            resource_by_role = {item["role"]: item["path"] for item in module["resources"]}
            self.routes.append(
                {
                    "route_id": component["id"] + ".route",
                    "component_id": component["id"],
                    "consumer_id": component["consumer"],
                    "cli_path": resource_by_role.get("cli", component["primary"]),
                    "orchestrator_path": resource_by_role.get("orchestrator"),
                    "route_registry_path": resource_by_role.get("route-registry"),
                    "operations": component["operations"],
                    "required_modules": ["repository-rules", "adr.ADR-0044", "adr.ADR-0048"],
                    "path_policy_id": self.policy.get("policy_revision"),
                    "freeze_point": component["freeze_point"],
                    "gate_mode": "enforce",
                    "locator_mode": component["locator_mode"],
                }
            )

    def add_execution_plans(self) -> None:
        plan_indexes = [path for path in self.snapshot.under("execution-plans") if path.endswith("/00-index.md")]
        for index_path in plan_indexes:
            directory = index_path.rsplit("/", 1)[0]
            directory_paths = [path for path in self.snapshot.paths if path.startswith(directory + "/")]
            resource_candidates: list[tuple[str, str]] = []
            versioned = (
                ("requirements-ledger", ("requirements-ledger", "requirements")),
                ("implementation-contract", ("implementation-contract",)),
                ("plan-state", ("plan-state",)),
                ("command-registry", ("command-registry",)),
            )
            for role, stems in versioned:
                path = select_versioned_plan_resource(directory, directory_paths, stems)
                if path is not None:
                    resource_candidates.append((role, path))
            if not any(role == "requirements-ledger" for role, _ in resource_candidates):
                canonical_markdown = f"{directory}/01-requirements-and-acceptance.md"
                if canonical_markdown in directory_paths:
                    resource_candidates.append(("requirements-ledger", canonical_markdown))
            if not any(role == "requirements-ledger" for role, _ in resource_candidates):
                fallback = next(
                    (
                        path
                        for path in directory_paths
                        if path.count("/") == directory.count("/") + 1 and "requirements-ledger" in PurePosixPath(path).name.casefold()
                    ),
                    None,
                )
                if fallback:
                    resource_candidates.append(("requirements-ledger", fallback))
            content = self.snapshot.read_text(index_path)
            title = _title(content, PurePosixPath(directory).name)
            domain, dependencies = _domain_for_plan(index_path, title)
            self.add_module(
                module_id="plan." + _slug(PurePosixPath(directory).name),
                kind="execution-plan",
                source_path=index_path,
                source_role="plan-index",
                primary_domain=domain,
                dependencies=dependencies,
                status=_plan_catalog_status(_status(content), content),
                resources=resource_candidates,
                relations=[
                    {"type": "references", "target": f"adr.{identifier}"}
                    for identifier in sorted(set(ADR_ID.findall(content)))
                ],
            )

    def add_runtime_entrypoints(self) -> None:
        self.add_module(
            module_id="runtime.phase-a.startup",
            kind="runtime-entrypoint",
            source_path="runtime/phase-a/start-phasea.ps1",
            source_role="runtime-config",
            primary_domain="phase",
            dependencies=("toolchain",),
            consumer_ids=("vdd", "bootstrap", "refactor-acceptance"),
        )

    def source_snapshot(self) -> dict[str, Any]:
        sources = sorted(self.sources.values(), key=lambda item: item["path"])
        identity = {
            "ref": self.snapshot.authority_ref,
            "commit": self.snapshot.commit,
            "exclusion_policy_revision": self.exclusions.get("policy_revision"),
            "sources": sources,
        }
        return {
            "schema_version": "jimuyun.repository-source-snapshot.v1",
            **identity,
            "snapshot_id": prefixed_sha256(canonical_bytes(identity)),
        }

    def collections(self) -> list[dict[str, Any]]:
        module_ids = {module["module_id"] for module in self.modules}
        all_adrs = sorted(module_id for module_id in module_ids if module_id.startswith("adr.ADR-"))
        phase_ids = {
            f"adr.{identifier}"
            for identifier in ADR_ID.findall(self.snapshot.read_text("docs/architecture/ADR_INDEX_PHASE.md"))
        }
        godot_ids = {
            f"adr.{identifier}"
            for identifier in ADR_ID.findall(self.snapshot.read_text("docs/architecture/ADR_INDEX_GODOT.md"))
        }
        definitions = {
            "adr.global": all_adrs,
            "adr.phase": sorted(module_id for module_id in phase_ids if module_id in module_ids),
            "adr.godot-workspace": sorted(module_id for module_id in godot_ids if module_id in module_ids),
            "adr.toolchain-governance": sorted(
                module["module_id"]
                for module in self.modules
                if module["kind"] == "adr" and module["primary_domain"] == "toolchain"
            ),
            "adr.unscoped": sorted(module_id for module_id in all_adrs if module_id not in phase_ids | godot_ids),
            "architecture.phase-service": sorted(
                module_id for module_id in module_ids if module_id.startswith("architecture.phase-service.")
            ),
            "architecture.base": sorted(module_id for module_id in module_ids if module_id.startswith("architecture.base.")),
            "architecture.overlays": sorted(module_id for module_id in module_ids if module_id.startswith("architecture.overlay.")),
            "governance.components": sorted(module_id for module_id in module_ids if module_id.startswith("governance.")),
            "execution-plans.directories": sorted(module_id for module_id in module_ids if module_id.startswith("plan.")),
        }
        return [
            {"collection_id": collection_id, "member_module_ids": members}
            for collection_id, members in sorted(definitions.items())
        ]

    def build(self) -> tuple[dict[str, Any], dict[str, Any]]:
        self.add_repository_modules()
        self.add_adrs()
        self.add_architecture()
        self.add_standards()
        self.add_governance_components()
        self.add_execution_plans()
        self.add_runtime_entrypoints()
        modules = sorted(self.modules, key=lambda item: item["module_id"])
        source_snapshot = self.source_snapshot()
        catalog = {
            "schema_version": "jimuyun.repository-knowledge-catalog.v2",
            "authority_ref": self.snapshot.authority_ref,
            "authority_class": "derived_cache",
            "instruction_authority": False,
            "may_override_source": False,
            "source_snapshot": source_snapshot,
            "exclusion_policy": {
                "policy_revision": self.exclusions.get("policy_revision"),
                "excluded_path_prefixes": list(excluded_source_prefixes(self.exclusions)),
                "targeted_discovery": "forbidden",
            },
            "collections": self.collections(),
            "routes": sorted(self.routes, key=lambda item: item["route_id"]),
            "modules": modules,
        }
        return source_snapshot, catalog


def compatibility_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for module in catalog["modules"]:
        compact_content = " ".join(
            [module["title"]]
            + [item.get("anchor", "") for item in module.get("anchors", []) if isinstance(item, dict)]
            + [item.get("path", "") for item in module.get("resources", []) if isinstance(item, dict)]
        )
        entries.append(
            {
                "entry_id": module["entry_id"],
                "source_path": module["source_path"],
                "source_sha256": module["source_sha256"],
                "anchor": module["anchor"],
                "content": compact_content,
            }
        )
    return {
        "schema_version": "jimuyun.repository-knowledge-catalog.v1",
        "authority_ref": catalog["authority_ref"],
        "source_snapshot": catalog["source_snapshot"],
        "entries": entries,
    }


def _module_allowed(module: dict[str, Any], policy: dict[str, Any]) -> bool:
    if not module.get("semantic_eligible") or module.get("consumer_ids") and policy.get("consumer") not in module["consumer_ids"]:
        return False
    if module.get("lifecycle") not in policy.get("lifecycles", ["repository-source"]):
        return False
    prefixes = policy.get("path_prefixes", [])
    exact_paths = policy.get("exact_paths", [])
    path = module.get("source_path", "")
    if path not in exact_paths and not any(path.startswith(prefix) for prefix in prefixes):
        return False
    allowed_visibility = set(policy.get("visibility", ["active", "dependency", "conditional"]))
    return any(
        module.get("visibility", {}).get(domain) in allowed_visibility
        for domain in policy.get("domains", [])
    )


def build_consumer_projections(catalog: dict[str, Any], policies: dict[str, Any]) -> dict[str, Any]:
    policy_bytes = canonical_bytes(policies)
    catalog_bytes = canonical_bytes(catalog)
    projections = []
    for policy in policies.get("policies", []):
        max_candidates = policy.get("max_candidates", 0)
        eligible = [] if max_candidates == 0 else [
            module["module_id"] for module in catalog["modules"] if _module_allowed(module, policy)
        ]
        projections.append(
            {
                "consumer": policy["consumer"],
                "eligible_module_ids": sorted(eligible),
                "required_modules": policy.get("required_modules", []),
                "optional_modules": policy.get("optional_modules", []),
                "max_candidates": max_candidates,
                "freeze_point": policy.get("freeze_point"),
            }
        )
    return {
        "schema_version": "jimuyun.knowledge-consumer-projections.v1",
        "source_snapshot_id": catalog["source_snapshot"]["snapshot_id"],
        "catalog_sha256": prefixed_sha256(catalog_bytes),
        "policy_revision": policies.get("policy_revision"),
        "policy_sha256": prefixed_sha256(policy_bytes),
        "projections": sorted(projections, key=lambda item: item["consumer"]),
    }


def build_layers(
    repository_root: Path,
    *,
    policy: dict[str, Any],
    exclusions: dict[str, Any],
    authority_ref: str = "refs/heads/main",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    snapshot = MainSnapshot(repository_root, authority_ref=authority_ref)
    builder = CatalogBuilder(snapshot, policy, exclusions)
    source_snapshot, catalog = builder.build()
    projections = build_consumer_projections(catalog, policy)
    return source_snapshot, catalog, projections, compatibility_catalog(catalog)
