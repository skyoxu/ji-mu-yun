from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_STATUSES = {
    "verified",
    "partial",
    "missing",
    "not_applicable",
    "explicitly_deferred",
    "blocked",
}
ALLOWED_OWNERS = {"backend", "frontend", "database", "scripts", "standards", "delivery-review"}
COMMIT_READINESS_STATUSES = {"not_evaluated", "failed", "stale", "passed"}
REQUIRED_COMMIT_RESULT_BINDINGS = [
    "implementation_acceptance_matrix_sha256",
    "implementation_acceptance_markdown_sha256",
    "proposed_commit_set_manifest_sha256",
    "git_tree_or_commit_sha",
]

PLAN_DIR = Path("execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening")
PHASE_SOURCE = PLAN_DIR / "08-implementation-phases.md"
CAPABILITY_SOURCE = PLAN_DIR / "schemas/gdd-to-module-capability-inventory.v1.json"
ACCEPTANCE_REGISTRY = PLAN_DIR / "schemas/split-added-acceptance-registry.v1.json"
SPLIT_ADDED_LEDGER = PLAN_DIR / "97-split-added-requirements-ledger.md"
PHASE1_EXIT = Path(
    "logs/phase-a-innernet/reviews/gdd-to-module-hardening/"
    "phase-1-exit-review-20260711T104735Z.json"
)
OUTPUT_JSON = PLAN_DIR / "schemas/implementation-acceptance-matrix.v1.json"
OUTPUT_MARKDOWN = PLAN_DIR / "100-implementation-acceptance-matrix.md"
EVIDENCE_INDEX = PLAN_DIR / "schemas/implementation-acceptance-evidence-index.v1.json"
REBUILD_IDS = False

LOCAL_ACCEPTANCE_FILES = [
    "01-overview-workflow.md",
    "02a-route-state-artifacts.md",
    "02b-backend-api-contracts.md",
    "02c-frontend-migration-compatibility.md",
    "03-testing-observability-admin.md",
    "04a-route-contracts-and-guards.md",
    "04b-route-readback-recovery-and-freshness.md",
    "04c-route-operation-governance.md",
    "04d-godot-engine-semantics-and-reference-examples.md",
    "05-godot-ui-capability-contract.md",
    "06a-ui-style-migration-overview-and-catalog.md",
    "06b-ui-style-snapshot-schema.md",
    "06c-style-aware-ui-closure.md",
    "06d-ui-style-schema-acceptance.md",
    "07-godot-diagnostics-quality-gates.md",
]

PHASE_SECTIONS = {
    "Phase 0A": ("Phase 0A exit criteria:", "Phase 0B exit criteria:"),
    "Phase 0B": ("Phase 0B exit criteria:", "### Phase 1:"),
    "Phase 1": ("### Phase 1:", "### Phase 2:"),
    "Phase 2": ("### Phase 2:", "### Phase 3:"),
    "Phase 3": ("### Phase 3:", "### Phase 4:"),
    "Phase 4": ("### Phase 4:", "### Phase 5:"),
    "Phase 5": ("### Phase 5:", "### Phase 6:"),
    "Phase 6": ("### Phase 6:", None),
}

PHASE_EVIDENCE = {
    "Phase 0A": [
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-exit-review-20260711T071611Z.json",
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-post-review-smoke-20260711T065851Z/summary.json",
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-post-review-governance-20260711T065851Z/summary.json",
    ],
    "Phase 0B": [
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-exit-review-20260711T071611Z.json",
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-post-review-smoke-20260711T065851Z/summary.json",
    ],
    "Phase 1": [
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-review-20260711T104735Z.json",
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-smoke-20260711T104735Z/summary.json",
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-governance-20260711T104735Z/summary.json",
    ],
    "Phase 2": [
        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase2-exit-final-20260712T005219Z/phase2-exit-evidence.md",
        "logs/ci/2026-07-12/phase-a-iteration-plan-e2e/20260712T005255Z-93efdf61/summary.json",
        "logs/phase-a-gdd-to-module-hardening/20260712T005219Z-phase2-exit-final/summary.json",
        "logs/phase-a-gdd-to-module-governance-audit/20260712T005219Z-phase2-exit-final/summary.json",
    ],
}

PHASE_REFS = {
    "Phase 0A": {
        "code": [
            "PhaseA.Platform/Workflow/RouteModuleContracts.cs",
            "PhaseA.Platform/Workflow/RouteActionDescriptors.cs",
            "PhaseA.Platform/Workflow/RouteFreshnessPolicy.cs",
            "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
            "PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Workflow/GddToModuleSplitAddedRequirementsTests.cs",
            "PhaseA.Platform.Tests/Workflow/RouteModuleContractsTests.cs",
            "PhaseA.Platform.Tests/Workflow/RouteActionDescriptorsTests.cs",
        ],
    },
    "Phase 0B": {
        "code": [
            "docs/standards/godot-engine-semantics.md",
            "docs/standards/godot-ui-capability-contract.md",
            "docs/standards/godot-ui-style-contract.md",
            "docs/standards/godot-diagnostics-quality-gates.md",
            "PhaseA.Platform/Workflow/GodotUiCapabilityContract.cs",
            "PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Workflow/GodotEngineSemanticsTests.cs",
            "PhaseA.Platform.Tests/Workflow/GodotUiCapabilityContractTests.cs",
            "PhaseA.Platform.Tests/Workflow/GodotUiStyleSnapshotSchemaTests.cs",
            "PhaseA.Platform.Tests/Workflow/GodotDiagnosticsQualityGateTests.cs",
        ],
    },
    "Phase 1": {
        "code": [
            "PhaseA.Platform/Runs/GameDesignRequirementMapService.cs",
            "PhaseA.Platform/Runs/GddToModulePhase1StateService.cs",
            "PhaseA.Platform/Runs/PrototypeContractFreezeService.cs",
            "PhaseA.Platform/Runs/GddMilestoneStepService.cs",
            "PhaseA.Platform/Runs/PrototypeWorkflowService.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs",
            "PhaseA.Platform.Tests/Workflow/RouteModuleContractsTests.cs",
            "PhaseA.Platform.Tests/Workflow/RouteFreshnessPolicyTests.cs",
        ],
    },
    "Phase 2": {
        "code": [
            "PhaseA.Platform/Runs/PrototypeIterationPlanService.cs",
            "PhaseA.Platform/Runs/IterationPlanTraceabilityBuilder.cs",
            "PhaseA.Platform/Runs/IterationPlanExecutionPreflight.cs",
            "PhaseA.Platform/Runs/PrototypeSkeletonAuthorityGate.cs",
            "PhaseA.Platform/Browser/BrowserUiRenderer.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs",
            "PhaseA.Platform.Tests/Runs/IterationPlanTraceabilityBuilderTests.cs",
            "PhaseA.Platform.Tests/Runs/IterationPlanExecutionPreflightTests.cs",
            "PhaseA.Platform.Tests/Browser/BrowserUiRendererTests.cs",
            "scripts/python/tests/test_phase_a_iteration_plan_e2e.py",
        ],
    },
    "Phase 3": {
        "code": [
            "PhaseA.Platform/Runs/ProjectWorkflowRouteService.cs",
            "PhaseA.Platform/Workflow/RouteActionDescriptors.cs",
            "PhaseA.Platform/Browser/BrowserUiRenderer.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Runs/ProjectWorkflowRouteServiceTests.cs",
            "PhaseA.Platform.Tests/Workflow/RouteActionDescriptorsTests.cs",
            "PhaseA.Platform.Tests/Browser/BrowserUiRendererTests.cs",
        ],
    },
    "Phase 4": {
        "code": [
            "PhaseA.Platform/Runs/PrototypeIterationGoalService.cs",
            "PhaseA.Platform/Runs/PrototypeNeedsFixRouteService.cs",
            "PhaseA.Platform/Runs/IterationPlanExecutionPreflight.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Runs/PrototypeIterationGoalServiceTests.cs",
            "PhaseA.Platform.Tests/Runs/PrototypeNeedsFixRouteServiceTests.cs",
            "PhaseA.Platform.Tests/Runs/IterationPlanExecutionPreflightTests.cs",
        ],
    },
    "Phase 5": {
        "code": [
            "PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs",
            "PhaseA.Platform/Workflow/GodotUiCapabilityContract.cs",
            "PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs",
            "PhaseA.Platform/Browser/BrowserUiRenderer.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Runs/ProjectRouteStateArtifactServiceTests.cs",
            "PhaseA.Platform.Tests/Browser/BrowserUiRendererTests.cs",
            "PhaseA.Platform.Tests/Workflow/GodotUiCapabilityContractTests.cs",
        ],
    },
    "Phase 6": {
        "code": [
            "PhaseA.Platform/Workflow/RouteModuleContracts.cs",
            "PhaseA.Platform/Workflow/RouteActionDescriptors.cs",
            "PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs",
            "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
        ],
        "tests": [
            "PhaseA.Platform.Tests/Workflow/RouteModuleContractsTests.cs",
            "PhaseA.Platform.Tests/Workflow/RouteActionDescriptorsTests.cs",
            "PhaseA.Platform.Tests/Runs/ProjectRouteStateArtifactServiceTests.cs",
            "PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs",
        ],
    },
}

PHASE2_TRIGGERED_CAPABILITIES = {
    "ui_theme_token_system",
    "ui_lifecycle_ownership",
    "ui_overlays_feedback",
    "ui_diagnostics_visual_evidence",
    "ui_runtime_environment_identity",
    "ui_theme_resource_contract",
    "ui_visual_evidence_contract",
    "godot_interaction_region_gate",
}

SPLIT_ADDED_RULES = [
    ("import_gdd_form", "split_added_workflow_action_import_gdd_form"),
    ("repair", "split_added_repair_action_alias_boundary"),
    ("delete_project", "split_added_delete_project_action_placement"),
    ("project-delete", "split_added_delete_project_action_placement"),
    ("prototype-skeleton", "split_added_prototype_alias_boundary"),
    ("status vocabulary", "split_added_status_subset_contract"),
    ("metadata db", "split_added_metadata_db_table_contracts"),
    ("schema contract profile", "split_added_style_schema_contract_profile"),
    ("machine-readable contract", "split_added_style_schema_contract_profile"),
    ("full-target", "split_added_full_target_capability_schedule"),
    ("durable standards", "split_added_durable_standards_destination_matrix"),
    ("dod", "split_added_dod_layering"),
    ("engine semantic", "split_added_godot_engine_semantics_reference_examples"),
    ("reference-example", "split_added_godot_engine_semantics_reference_examples"),
    ("reading evidence", "split_added_godot_feature_family_reading_gate"),
    ("example copy", "split_added_godot_reference_example_copy_manifest"),
    ("geometry", "split_added_godot_geometry_size_material_profiles"),
    ("material", "split_added_godot_geometry_size_material_profiles"),
    ("rendering", "split_added_godot_rendering_animation_profiles"),
    ("animation", "split_added_godot_rendering_animation_profiles"),
    ("dynamic ui", "split_added_godot_ui_update_ownership"),
    ("update ownership", "split_added_godot_ui_update_ownership"),
    ("third-person camera", "split_added_godot_third_person_camera_profile"),
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_phase_criteria(lines: list[str], phase: str, start_marker: str, end_marker: str | None) -> list[tuple[int, str]]:
    start = next(i for i, line in enumerate(lines) if start_marker in line)
    if phase in {"Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5", "Phase 6"}:
        start = next(i for i in range(start, len(lines)) if lines[i].strip() == "Exit criteria:")
    end = len(lines) if end_marker is None else next(i for i in range(start + 1, len(lines)) if end_marker in lines[i])
    return [
        (i + 1, lines[i][2:].strip())
        for i in range(start + 1, end)
        if lines[i].startswith("- ")
    ]


def owner_for(requirement: str) -> str:
    value = requirement.lower()
    if any(token in value for token in ("review records", "phase exit review", "unresolved p0/p1/p2")):
        return "delivery-review"
    if any(token in value for token in ("frontend", "browser", "user sees", "ui closure panel")):
        return "frontend"
    if any(token in value for token in ("metadata db", "diagnostic spool", "admin review queue", "tombstone")):
        return "database"
    if any(token in value for token in ("script", "preflight", "local dependencies")):
        return "scripts"
    if any(token in value for token in ("standards", "linked from", "template", "taxonomy", "policy", "adr")):
        return "standards"
    return "backend"


def split_added_for(requirement: str) -> list[str]:
    value = requirement.lower()
    result = {split_id for token, split_id in SPLIT_ADDED_RULES if token in value}
    if "prototype-skeleton" in value and ("phase 0b" in value or "semantic" in value):
        result.add("split_added_phase0b_skeleton_guard_dependency")
    return sorted(result)


def refs_for(phase: str, requirement: str) -> dict[str, list[str]]:
    value = requirement.lower()
    code_refs: list[str] = []
    test_refs: list[str] = []

    def add(token: str, code: list[str], tests: list[str]) -> None:
        if token in value:
            code_refs.extend(code)
            test_refs.extend(tests)

    if phase == "Phase 0A":
        add("no-store", ["PhaseA.Platform/Program.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("route action", ["PhaseA.Platform/Workflow/RouteActionDescriptors.cs"], ["PhaseA.Platform.Tests/Workflow/RouteActionDescriptorsTests.cs"])
        add("workflow recommendation", ["PhaseA.Platform/Runs/ProjectWorkflowRouteService.cs", "PhaseA.Platform/Workflow/RouteActionDescriptors.cs"], ["PhaseA.Platform.Tests/Runs/ProjectWorkflowRouteServiceTests.cs"])
        add("prototype-contract", ["PhaseA.Platform/Runs/PrototypeContractFreezeService.cs", "PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("source-boundary", ["PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs", "PhaseA.Platform/Workflow/RouteModuleContracts.cs"], ["PhaseA.Platform.Tests/Runs/ProjectRouteStateArtifactServiceTests.cs"])
        add("admin review queue", ["PhaseA.Platform/Data/PhaseAMetadataStore.cs", "PhaseA.Platform/Data/SqliteMetadataSchema.cs"], ["PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs", "PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("diagnostic", ["PhaseA.Platform/Data/PhaseAMetadataStore.cs", "PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs"], ["PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs", "PhaseA.Platform.Tests/Workflow/GodotDiagnosticsQualityGateTests.cs"])
        add("structured game-type", ["PhaseA.Platform/Prototypes/ProjectGameTypeMatchService.cs", "PhaseA.Platform/Prototypes/SteamGameTypeMetadataProvider.cs"], ["PhaseA.Platform.Tests/Prototypes/ProjectGameTypeMatchServiceTests.cs", "PhaseA.Platform.Tests/Prototypes/SteamGameTypeMetadataProviderTests.cs"])
        add("secret redaction", ["PhaseA.Platform/Workflow/SecretRedactionPolicy.cs"], ["PhaseA.Platform.Tests/Workflow/RouteOperationGovernanceTests.cs"])
        add("shared entrypoint", ["PhaseA.Platform/Llm/LlmRouteEngine.cs", "PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs", "scripts/sc/_llm_backend.py"], ["PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs", "PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs", "scripts/sc/tests/test_llm_backend.py"])
        add("phase adr", ["docs/architecture/ADR_INDEX_PHASE.md"], ["PhaseA.Platform.Tests/Workflow/GddToModuleSplitAddedRequirementsTests.cs"])
        add("phase exit", ["_bmad-output/implementation-artifacts/1-1-phase0-governance-baseline.md"], ["PhaseA.Platform.Tests/Workflow/GddToModuleImplementationPhasesTests.cs"])
        add("path/readback", ["PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs"], ["PhaseA.Platform.Tests/Runs/ProjectRouteStateArtifactServiceTests.cs"])
        add("status vocabulary", ["PhaseA.Platform/Workflow/RouteFreshnessPolicy.cs", "PhaseA.Platform/Workflow/RouteActionDescriptors.cs"], ["PhaseA.Platform.Tests/Workflow/RouteFreshnessPolicyTests.cs"])
    elif phase == "Phase 0B":
        add("ui capability", ["docs/standards/godot-ui-capability-contract.md", "PhaseA.Platform/Workflow/GodotUiCapabilityContract.cs"], ["PhaseA.Platform.Tests/Workflow/GodotUiCapabilityContractTests.cs"])
        add("engine semantic", ["docs/standards/godot-engine-semantics.md", "PhaseA.Platform/Workflow/GodotEngineSemantics.cs"], ["PhaseA.Platform.Tests/Workflow/GodotEngineSemanticsTests.cs"])
        add("reference-example", ["docs/reference/godot-official-examples-index.md"], ["PhaseA.Platform.Tests/Workflow/GodotEngineSemanticsTests.cs"])
        add("ui style", ["docs/standards/godot-ui-style-contract.md", "PhaseA.Platform/Workflow/GodotUiStyleSnapshotSchema.cs"], ["PhaseA.Platform.Tests/Workflow/GodotUiStyleSnapshotSchemaTests.cs"])
        add("styled ui", ["docs/standards/godot-ui-style-contract.md", "PhaseA.Platform/Workflow/GodotUiStyleSnapshotSchema.cs"], ["PhaseA.Platform.Tests/Workflow/GodotUiStyleSnapshotSchemaTests.cs"])
        add("diagnostic", ["docs/standards/godot-diagnostics-quality-gates.md", "PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs"], ["PhaseA.Platform.Tests/Workflow/GodotDiagnosticsQualityGateTests.cs"])
        add("failure-family", ["PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs"], ["PhaseA.Platform.Tests/Workflow/GodotDiagnosticsQualityGateTests.cs"])
    elif phase == "Phase 1":
        add("scene route", ["PhaseA.Platform/Runs/GameDesignSceneRouteService.cs", "PhaseA.Platform/Runs/GddToModulePhase1StateService.cs"], ["PhaseA.Platform.Tests/Runs/GameDesignSceneRouteServiceTests.cs", "PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("gdd document", ["PhaseA.Platform/Runs/GddMilestoneStepService.cs", "PhaseA.Platform/Runs/GddToModulePhase1StateService.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("requirement map", ["PhaseA.Platform/Runs/GameDesignRequirementMapService.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("contract", ["PhaseA.Platform/Runs/PrototypeContractFreezeService.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("skeleton", ["PhaseA.Platform/Runs/PrototypeWorkflowService.cs", "PhaseA.Platform/Runs/PrototypeSkeletonAuthorityGate.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("double-click", ["PhaseA.Platform/Runs/ProjectMutationLockRegistry.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])
        add("shared phase service", ["PhaseA.Platform/Llm/LlmRouteEngine.cs", "PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs"], ["PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs", "PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs"])
        add("workflow recommendation", ["PhaseA.Platform/Runs/ProjectWorkflowRouteService.cs", "PhaseA.Platform/Workflow/RouteActionDescriptors.cs"], ["PhaseA.Platform.Tests/Runs/ProjectWorkflowRouteServiceTests.cs"])
    elif phase == "Phase 2":
        add("covered by plan", ["PhaseA.Platform/Runs/IterationPlanTraceabilityBuilder.cs"], ["PhaseA.Platform.Tests/Runs/IterationPlanTraceabilityBuilderTests.cs"])
        add("traceability", ["PhaseA.Platform/Runs/IterationPlanTraceabilityBuilder.cs", "PhaseA.Platform/Browser/BrowserUiRenderer.cs"], ["PhaseA.Platform.Tests/Runs/IterationPlanTraceabilityBuilderTests.cs", "PhaseA.Platform.Tests/Browser/BrowserUiRendererTests.cs"])
        add("deckbuilder", ["PhaseA.Platform/Runs/IterationPlanTraceabilityBuilder.cs"], ["PhaseA.Platform.Tests/Runs/IterationPlanTraceabilityBuilderTests.cs"])
        add("ui-facing", ["PhaseA.Platform/Runs/IterationPlanTraceabilityBuilder.cs"], ["PhaseA.Platform.Tests/Runs/IterationPlanTraceabilityBuilderTests.cs"])
        add("interaction-region", ["PhaseA.Platform/Runs/IterationPlanInteractionArtifactValidator.cs"], ["PhaseA.Platform.Tests/Runs/IterationPlanExecutionPreflightTests.cs"])
        add("dynamic ui", ["PhaseA.Platform/Runs/IterationPlanExecutionPreflight.cs"], ["PhaseA.Platform.Tests/Runs/IterationPlanExecutionPreflightTests.cs"])
        add("third-person camera", ["PhaseA.Platform/Runs/IterationPlanExecutionPreflight.cs"], ["PhaseA.Platform.Tests/Runs/IterationPlanExecutionPreflightTests.cs"])
        add("route governance", ["PhaseA.Platform/Runs/PrototypeIterationPlanService.cs", "PhaseA.Platform/Program.cs"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs", "scripts/python/tests/test_phase_a_iteration_plan_e2e.py"])
        add("review records", ["_bmad-output/implementation-artifacts/1-3-phase2-iteration-plan-traceability-gate.md"], ["PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs"])

    return {
        "code": list(dict.fromkeys(code_refs)),
        "tests": list(dict.fromkeys(test_refs)),
    }


def phase_status(phase: str, requirement: str) -> tuple[str, str]:
    if phase == "Phase 0A":
        return (
            "partial",
            "Phase 0A has implementation and historical evidence, but the current clause-level review still has unresolved findings and no evidence artifact explicitly enumerates this check_id as verified.",
        )
    return (
        "blocked",
        "No current reviewed check-ID evidence accepts this requirement. Existing implementation or historical evidence is retained only as supporting context.",
    )


def _non_empty_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def _has_valid_recheck_condition(deferral: dict, now: datetime | None = None) -> bool:
    trigger = deferral.get("recheck_trigger")
    if isinstance(trigger, str) and trigger.strip():
        return True
    expires_utc = deferral.get("expires_utc")
    if not isinstance(expires_utc, str) or not expires_utc.strip():
        return False
    try:
        expiry = datetime.fromisoformat(expires_utc.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    if expiry.tzinfo is None:
        return False
    return expiry.astimezone(timezone.utc) > (now or datetime.now(timezone.utc))


def _phase6_closure_test_exists(repo_root: Path, reference: object) -> bool:
    if not isinstance(reference, str) or "::" not in reference:
        return False
    relative_path, symbol = (part.strip() for part in reference.split("::", 1))
    if not relative_path or not symbol:
        return False
    test_path = repo_root / relative_path
    if not test_path.is_file():
        return False
    return re.search(rf"\b{re.escape(symbol)}\b", test_path.read_text(encoding="utf-8")) is not None


def is_exit_permitted_deferral(
    row: dict,
    repo_root: Path | None = None,
    now: datetime | None = None,
) -> bool:
    deferral = row.get("deferral", {})
    root = (repo_root or Path.cwd()).resolve()
    return (
        row.get("status") == "explicitly_deferred"
        and row.get("owner") in ALLOWED_OWNERS
        and _non_empty_string_list(row.get("evidence_refs"))
        and "recheck=" in row.get("gap", "")
        and isinstance(deferral.get("owner"), str)
        and bool(deferral.get("owner", "").strip())
        and _non_empty_string_list(deferral.get("affected_routes"))
        and deferral.get("severity") in {"P0", "P1", "P2"}
        and isinstance(deferral.get("current_scope_non_impact_proof"), str)
        and bool(deferral.get("current_scope_non_impact_proof", "").strip())
        and _phase6_closure_test_exists(root, deferral.get("phase6_closure_test"))
        and _has_valid_recheck_condition(deferral, now)
    )


def phase0a_exit_satisfied(rows: list[dict], repo_root: Path | None = None) -> bool:
    phase_rows = [row for row in rows if row.get("phase") == "Phase 0A"]
    return bool(phase_rows) and all(
        row.get("status") in {"verified", "not_applicable"}
        or is_exit_permitted_deferral(row, repo_root=repo_root)
        for row in phase_rows
    )


def apply_phase0a_predecessor_gate(rows: list[dict], repo_root: Path | None = None) -> list[dict]:
    if phase0a_exit_satisfied(rows, repo_root=repo_root):
        return rows

    blocker = (
        "Blocked by sequential prerequisite: Phase 0A has not satisfied its audited phase-exit "
        "dispositions; every Phase 0A row must be verified, not applicable with evidence, or an "
        "owned and evidenced explicit deferral with a recheck condition."
    )
    for row in rows:
        if row.get("phase") == "Phase 0A":
            continue
        prior_gap = row.get("gap", "").strip()
        row["status"] = "blocked"
        row["gap"] = f"{blocker} {prior_gap}".strip()
    return rows


def existing_ids() -> dict[tuple[str, str], str]:
    if REBUILD_IDS or not OUTPUT_JSON.exists():
        return {}
    document = read_json(OUTPUT_JSON)
    return {
        (row["phase"], row["requirement"]): row["check_id"]
        for row in document.get("checks", [])
        if row.get("acceptance_kind") == "phase_exit"
    }


def next_check_id(phase: str, ordinal: int) -> str:
    phase_token = phase.replace("Phase ", "P").replace(" ", "")
    return f"GTM-AC-{phase_token}-{ordinal:03d}"


def build_phase_rows(lines: list[str]) -> list[dict]:
    previous = existing_ids()
    reused_previous: set[tuple[str, str]] = set()
    rows: list[dict] = []
    for phase, (start_marker, end_marker) in PHASE_SECTIONS.items():
        criteria = extract_phase_criteria(lines, phase, start_marker, end_marker)
        for ordinal, (line_number, requirement) in enumerate(criteria, start=1):
            status, gap = phase_status(phase, requirement)
            refs = refs_for(phase, requirement)
            check_id = previous.get((phase, requirement), next_check_id(phase, ordinal))
            if (phase, requirement) in previous:
                reused_previous.add((phase, requirement))
            rows.append(
                {
                    "check_id": check_id,
                    "acceptance_kind": "phase_exit",
                    "phase": phase,
                    "source_ref": f"{PHASE_SOURCE.as_posix()}:{line_number}",
                    "requirement": requirement,
                    "owner": owner_for(requirement),
                    "code_refs": refs["code"],
                    "test_refs": refs["tests"],
                    "evidence_refs": PHASE_EVIDENCE.get(phase, []),
                    "split_added_ids": split_added_for(requirement),
                    "status": status,
                    "gap": gap,
                }
            )
    removed_or_changed = set(previous) - reused_previous
    if removed_or_changed:
        changed_ids = [previous[key] for key in sorted(removed_or_changed)]
        raise SystemExit(
            "Acceptance clauses changed or disappeared; preserve or explicitly migrate stable IDs: "
            + ", ".join(changed_ids)
        )
    return rows


def local_file_token(file_name: str) -> str:
    prefix = file_name.split("-", 1)[0].upper()
    return prefix.replace(".", "")


def local_existing_ids() -> dict[tuple[str, str, str], str]:
    if REBUILD_IDS or not OUTPUT_JSON.exists():
        return {}
    document = read_json(OUTPUT_JSON)
    return {
        (row["phase"], row["source_ref"].split(":", 1)[0], row["requirement"]): row["check_id"]
        for row in document.get("checks", [])
        if row.get("acceptance_kind") == "local_acceptance"
    }


def infer_route_phase(requirement: str, default_phase: str) -> str:
    value = requirement.lower()
    if any(token in value for token in ("status vocabulary", "action descriptor", "source_boundary", "source-boundary", "secret redaction", "shared llm", "shared phase service", "path/readback")):
        return "Phase 0A"
    if any(token in value for token in ("ui closure", "ui-wiring", "final readiness")):
        return "Phase 5"
    if any(token in value for token in ("execute-next", "execute next", "needs-fix", "needs_fix", "repair")):
        return "Phase 4"
    if "workflow recommendation" in value or "recommendedaction" in value or "recommended_action" in value:
        return "Phase 3"
    if any(token in value for token in ("iteration plan", "iteration-plan", "module plan", "interaction-region", "interaction region")):
        return "Phase 2"
    if any(token in value for token in ("requirement map", "requirement-map", "scene route", "scene-route", "gdd document", "gdd-document", "contract freeze", "prototype contract", "prototype-contract", "prototype-skeleton")):
        return "Phase 1"
    if any(token in value for token in ("preview", "package download", "package readiness")):
        return "Phase 5"
    if any(token in value for token in ("godot ui", "ui style", "engine semantic", "reference example", "failure-family", "diagnostic taxonomy")):
        return "Phase 0B"
    if any(token in value for token in ("project-delete", "project delete", "admin/backfill", "all remaining route")):
        return "Phase 6"
    return default_phase


def local_phase(file_name: str, marker_line: int, requirement: str) -> str:
    if file_name == "01-overview-workflow.md":
        return "Phase 0A"
    if file_name == "02a-route-state-artifacts.md":
        mapping = {63: "Phase 0A", 143: "Phase 1", 262: "Phase 1", 318: "Phase 1", 416: "Phase 0A", 471: "Phase 1", 538: "Phase 3", 572: "Phase 1", 701: "Phase 5"}
        return mapping[marker_line]
    if file_name == "02b-backend-api-contracts.md":
        mapping = {20: "Phase 0A", 40: "Phase 1", 62: "Phase 1", 87: "Phase 1", 106: "Phase 2", 130: "Phase 4", 160: "Phase 3", 187: "Phase 0A"}
        return mapping.get(marker_line, infer_route_phase(requirement, "Phase 6"))
    if file_name == "02c-frontend-migration-compatibility.md":
        mapping = {34: "Phase 0A", 56: "Phase 3", 82: "Phase 1", 93: "Phase 1", 106: "Phase 2", 117: "Phase 5", 131: "Phase 5", 171: "Phase 6"}
        return mapping[marker_line]
    if file_name == "03-testing-observability-admin.md":
        default = "Phase 0A" if marker_line in {22, 101, 118, 242} else "Phase 0B" if marker_line in {149, 176, 206} else "Phase 6"
        return infer_route_phase(requirement, default)
    if file_name == "04a-route-contracts-and-guards.md":
        return "Phase 6" if marker_line == 180 else "Phase 0A"
    if file_name == "04b-route-readback-recovery-and-freshness.md":
        return "Phase 6" if marker_line == 41 else "Phase 0A"
    if file_name == "04c-route-operation-governance.md":
        return "Phase 6" if marker_line == 51 else "Phase 0A"
    if file_name == "04d-godot-engine-semantics-and-reference-examples.md":
        return "Phase 0B"
    if file_name == "05-godot-ui-capability-contract.md":
        return infer_route_phase(requirement, "Phase 0B") if marker_line == 236 else "Phase 0B"
    if file_name in {"06a-ui-style-migration-overview-and-catalog.md", "06b-ui-style-snapshot-schema.md", "06d-ui-style-schema-acceptance.md"}:
        return "Phase 0B"
    if file_name == "06c-style-aware-ui-closure.md":
        return "Phase 5"
    if file_name == "07-godot-diagnostics-quality-gates.md":
        mapping = {20: "Phase 0B", 67: "Phase 0B", 136: "Phase 0B", 198: "Phase 0B", 219: "Phase 2", 239: "Phase 4"}
        return mapping[marker_line]
    raise ValueError(f"No local phase mapping for {file_name}:{marker_line}")


def local_acceptance_sections(path: Path) -> list[tuple[int, str, list[tuple[int, str]]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    sections: list[tuple[int, str, list[tuple[int, str]]]] = []
    for index, line in enumerate(lines):
        normalized = line.lower().strip()
        heading_normalized = normalized.lstrip("# ").strip()
        if normalized not in {"acceptance criteria:", "destination acceptance:", "ledger acceptance:"} and heading_normalized != "acceptance criteria":
            continue
        parent = next((lines[j] for j in range(index - 1, -1, -1) if lines[j].startswith("#")), path.name)
        end_candidates = [j for j in range(index + 1, len(lines)) if lines[j].startswith("#")]
        end_candidates.extend(
            j
            for j in range(index + 1, len(lines))
            if lines[j].lower().strip() in {"acceptance criteria:", "destination acceptance:", "ledger acceptance:"}
        )
        end = min(end_candidates, default=len(lines))
        bullets = [
            (j + 1, lines[j][2:].strip())
            for j in range(index + 1, end)
            if lines[j].startswith("- ")
        ]
        sections.append((index + 1, parent, bullets))
    return sections


def build_local_acceptance_rows() -> list[dict]:
    previous = local_existing_ids()
    reused_previous: set[tuple[str, str, str]] = set()
    rows: list[dict] = []
    for file_name in LOCAL_ACCEPTANCE_FILES:
        source_path = PLAN_DIR / file_name
        ordinal = 0
        for marker_line, _, bullets in local_acceptance_sections(source_path):
            for line_number, requirement in bullets:
                ordinal += 1
                phase = local_phase(file_name, marker_line, requirement)
                source_file = source_path.as_posix()
                key = (phase, source_file, requirement)
                check_id = previous.get(key, f"GTM-LAC-{local_file_token(file_name)}-{ordinal:03d}")
                if key in previous:
                    reused_previous.add(key)
                status, gap = phase_status(phase, requirement)
                refs = refs_for(phase, requirement)
                rows.append(
                    {
                        "check_id": check_id,
                        "acceptance_kind": "local_acceptance",
                        "phase": phase,
                        "source_ref": f"{source_file}:{line_number}",
                        "requirement": requirement,
                        "owner": owner_for(requirement),
                        "code_refs": refs["code"],
                        "test_refs": refs["tests"],
                        "evidence_refs": PHASE_EVIDENCE.get(phase, []),
                        "split_added_ids": split_added_for(requirement),
                        "status": status,
                        "gap": gap,
                    }
                )
    removed_or_changed = set(previous) - reused_previous
    if removed_or_changed:
        changed_ids = [previous[key] for key in sorted(removed_or_changed)]
        raise SystemExit(
            "Local acceptance clauses changed or disappeared; preserve or explicitly migrate stable IDs: "
            + ", ".join(changed_ids)
        )
    return rows


def capability_phase(value: str) -> str:
    match = re.search(r"Phase\s+(0A|0B|[1-6])", value)
    return f"Phase {match.group(1)}" if match else "Phase 0B"


def capability_owner(owner_id: str) -> str:
    if "DIAGNOSTICS" in owner_id:
        return "database"
    if "STYLE" in owner_id or "CAPABILITY" in owner_id or "ENGINE" in owner_id:
        return "standards"
    return "backend"


def build_capability_rows(repo_root: Path) -> list[dict]:
    inventory = read_json(CAPABILITY_SOURCE)
    phase1_exit = read_json(PHASE1_EXIT)
    coverage_rows = phase1_exit.get("full_target_capability_rows", phase1_exit.get("full_target_capability_coverage", []))
    exit_rows = {
        row["capability_id"]: row
        for row in coverage_rows
    }
    rows: list[dict] = []
    for index, capability in enumerate(inventory["capabilities"]):
        capability_id = capability["capability_id"]
        coverage = exit_rows[capability_id]
        if coverage["coverage_status"] == "covered":
            status = "blocked"
            gap = "Historical capability coverage is retained only as supporting evidence; this capability row lacks current reviewed check-ID acceptance."
            evidence_refs = [PHASE1_EXIT.as_posix()]
        elif capability_id in PHASE2_TRIGGERED_CAPABILITIES:
            status = "blocked"
            gap = (
                "The Phase 1 deferral recheck trigger fired during Phase 2, but no canonical full-target closure ledger or current reviewed check-ID acceptance exists."
            )
            evidence_refs = [
                PHASE1_EXIT.as_posix(),
                "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase2-exit-final-20260712T005219Z/phase2-exit-evidence.md",
            ]
        else:
            status = "blocked"
            gap = (
                "This capability row lacks current reviewed check-ID acceptance. "
                f"Historical deferral owner={coverage['owner']}; reason={coverage['reason']}; "
                f"recheck={coverage['recheck_phase']}; trigger={coverage['trigger']}"
            )
            evidence_refs = coverage["validation_evidence_refs"]
        owner_doc = PLAN_DIR / coverage["owner_doc"]
        rows.append(
            {
                "check_id": "GTM-AC-CAP-" + capability_id.upper().replace("_", "-"),
                "acceptance_kind": "full_target_capability",
                "phase": capability_phase(capability["first_required_phase"]),
                "source_ref": f"{CAPABILITY_SOURCE.as_posix()}#/capabilities/{index}",
                "requirement": (
                    f"Capability `{capability_id}` is covered before its trigger is consumed, or has an auditable owner and recheck condition. Trigger: {capability['trigger']}"
                ),
                "owner": capability_owner(capability["owner_id"]),
                "code_refs": [owner_doc.as_posix()],
                "test_refs": coverage["validation_evidence_refs"]
                if coverage["coverage_status"] == "covered"
                else ["PhaseA.Platform.Tests/Workflow/GddToModuleFirstSliceTests.cs"],
                "evidence_refs": evidence_refs,
                "split_added_ids": ["split_added_full_target_capability_schedule"],
                "status": status,
                "gap": gap,
            }
        )
    return rows


def split_owner(owner_id: str) -> str:
    if "DELIVERY-REVIEW" in owner_id:
        return "delivery-review"
    if "METADATA" in owner_id:
        return "database"
    if any(token in owner_id for token in ("STYLE", "CAPABILITY", "ENGINE", "REFERENCE", "STANDARDS", "VOCABULARY", "PHASE-GATES")):
        return "standards"
    return "backend"


def build_split_added_rows() -> list[dict]:
    rows: list[dict] = []
    for line_number, line in enumerate(SPLIT_ADDED_LEDGER.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.startswith("| `split_added_"):
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        split_id = columns[0].strip("`")
        requirement = columns[1]
        owner_id = columns[2].strip("`")
        first_phase = columns[3]
        phase = capability_phase(first_phase)
        refs = refs_for(phase, requirement)
        if phase == "Phase 0A":
            status = "partial"
            gap = "Phase 0A split-added requirement awaits explicit check-ID verification in the current phase-exit evidence."
            evidence_refs = PHASE_EVIDENCE.get(phase, [])
        elif split_id == "split_added_full_target_capability_schedule":
            status = "blocked"
            gap = "Consumed Phase 2 capability rows lack a refreshed canonical full-target closure ledger and current reviewed check-ID acceptance."
            evidence_refs = [
                "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-review-20260711T104735Z.json",
                "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase2-exit-final-20260712T005219Z/phase2-exit-evidence.md",
            ]
        else:
            status = "blocked"
            gap = "No current reviewed check-ID evidence accepts this split-added requirement."
            evidence_refs = PHASE_EVIDENCE.get(phase, PHASE_EVIDENCE["Phase 0B"])
        rows.append(
            {
                "check_id": "GTM-SAR-" + split_id.removeprefix("split_added_").upper().replace("_", "-"),
                "acceptance_kind": "split_added_requirement",
                "phase": phase,
                "source_ref": f"{SPLIT_ADDED_LEDGER.as_posix()}:{line_number}",
                "requirement": requirement,
                "owner": split_owner(owner_id),
                "code_refs": refs["code"],
                "test_refs": refs["tests"],
                "evidence_refs": evidence_refs,
                "split_added_ids": [split_id],
                "status": status,
                "gap": gap,
            }
        )
    return rows


def validate_rows(repo_root: Path, rows: list[dict]) -> None:
    required_fields = {
        "check_id",
        "phase",
        "source_ref",
        "requirement",
        "owner",
        "code_refs",
        "test_refs",
        "evidence_refs",
        "split_added_ids",
        "status",
        "gap",
    }
    acceptance_registry = read_json(ACCEPTANCE_REGISTRY)
    valid_split_ids = set(acceptance_registry["expected_split_added_requirements"])
    seen: set[str] = set()
    failures: list[str] = []
    for row in rows:
        missing = required_fields - set(row)
        if missing:
            failures.append(f"{row.get('check_id', '<missing>')}: missing fields {sorted(missing)}")
        if row["check_id"] in seen:
            failures.append(f"duplicate check_id: {row['check_id']}")
        seen.add(row["check_id"])
        if row["status"] not in ALLOWED_STATUSES:
            failures.append(f"{row['check_id']}: invalid status {row['status']}")
        if row["owner"] not in ALLOWED_OWNERS:
            failures.append(f"{row['check_id']}: invalid owner {row['owner']}")
        unknown_split_ids = set(row["split_added_ids"]) - valid_split_ids
        if unknown_split_ids:
            failures.append(f"{row['check_id']}: unknown split_added_ids {sorted(unknown_split_ids)}")
        if row["status"] == "verified" and not all(
            row[field] for field in ("code_refs", "test_refs", "evidence_refs")
        ):
            failures.append(f"{row['check_id']}: verified row lacks implementation, test, or evidence refs")
        if row["status"] in {"partial", "missing", "blocked", "explicitly_deferred"} and not row["gap"]:
            failures.append(f"{row['check_id']}: non-verified row lacks a gap explanation")
        if row["status"] == "explicitly_deferred" and "recheck=" not in row["gap"]:
            failures.append(f"{row['check_id']}: deferred row lacks a recheck condition")
        if row["status"] == "explicitly_deferred" and not is_exit_permitted_deferral(row):
            failures.append(f"{row['check_id']}: deferred row lacks the complete exit-permitted deferral contract")
        if row["status"] in {"verified", "not_applicable", "explicitly_deferred"} and not row["evidence_refs"]:
            failures.append(f"{row['check_id']}: status requires durable evidence refs")
        for ref in row["code_refs"] + row["test_refs"]:
            path_text = ref.split("#", 1)[0]
            if not (repo_root / path_text).exists():
                failures.append(f"{row['check_id']}: missing implementation/test ref {ref}")
        for ref in row["evidence_refs"]:
            if re.match(r"^[a-z]+://", ref):
                failures.append(f"{row['check_id']}: external evidence refs require imported local evidence {ref}")
            elif not (repo_root / ref.split("#", 1)[0]).exists():
                failures.append(f"{row['check_id']}: missing evidence ref {ref}")
    if failures:
        raise SystemExit("\n".join(failures))


def markdown_table(rows: list[dict]) -> str:
    def cell(value: object) -> str:
        if isinstance(value, list):
            text = "<br>".join(f"`{item}`" for item in value) if value else "-"
        else:
            text = str(value) if value else "-"
        return text.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| check_id | phase | source_ref | requirement | owner | code_refs | test_refs | evidence_refs | split_added_ids | status | gap |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join(
                cell(row[field])
                for field in (
                    "check_id",
                    "phase",
                    "source_ref",
                    "requirement",
                    "owner",
                    "code_refs",
                    "test_refs",
                    "evidence_refs",
                    "split_added_ids",
                    "status",
                    "gap",
                )
            ) + " |"
        )
    return "\n".join(lines)


def apply_evidence_index(rows: list[dict]) -> list[dict]:
    if not EVIDENCE_INDEX.exists():
        return rows
    document = read_json(EVIDENCE_INDEX)
    raw_entries = document.get("entries", [])
    entry_ids = [entry["check_id"] for entry in raw_entries]
    duplicates = sorted(check_id for check_id, count in Counter(entry_ids).items() if count > 1)
    if duplicates:
        raise SystemExit(f"Evidence index contains duplicate check IDs: {duplicates}")
    entries = {entry["check_id"]: entry for entry in raw_entries}
    known = {row["check_id"] for row in rows}
    unknown = sorted(set(entries) - known)
    if unknown:
        raise SystemExit(f"Evidence index contains unknown check IDs: {unknown}")
    for row in rows:
        entry = entries.get(row["check_id"])
        if entry is None:
            continue
        row["status"] = entry["status"]
        row["code_refs"] = entry.get("code_refs", [])
        row["test_refs"] = entry.get("test_refs", [])
        row["evidence_refs"] = entry.get("evidence_refs", [])
        row["gap"] = entry.get("gap", "")
        if row["status"] == "explicitly_deferred":
            row["deferral"] = {
                "owner": entry.get("defer_owner", ""),
                "affected_routes": entry.get("defer_affected_routes", []),
                "severity": entry.get("defer_severity", ""),
                "expires_utc": entry.get("defer_expires_utc", ""),
                "recheck_trigger": entry.get("defer_recheck_trigger", ""),
                "current_scope_non_impact_proof": entry.get("defer_current_scope_non_impact_proof", ""),
                "phase6_closure_test": entry.get("defer_phase6_closure_test", ""),
                "acceptance_refs": entry.get("defer_acceptance_refs", []),
            }
    return rows


def source_inputs_hash(repo_root: Path) -> str:
    inputs = {
        PHASE_SOURCE,
        PLAN_DIR / "00-index.md",
        PLAN_DIR / "10-recommended-first-slice.md",
        CAPABILITY_SOURCE,
        ACCEPTANCE_REGISTRY,
        SPLIT_ADDED_LEDGER,
        PHASE1_EXIT,
        EVIDENCE_INDEX,
        *(PLAN_DIR / file_name for file_name in LOCAL_ACCEPTANCE_FILES),
    }
    digest = hashlib.sha256()
    for relative in sorted(inputs, key=lambda path: path.as_posix()):
        path = repo_root / relative
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_commit_readiness_evaluation(repo_root: Path, evaluation: dict) -> None:
    status = evaluation.get("status", "not_evaluated")
    if status != "not_evaluated":
        raise SystemExit(
            "Embedded Phase 0A commit-readiness status must remain not_evaluated; "
            "evaluated results belong in the external predecessor-gate artifact"
        )
    bindings = evaluation.get("required_result_bindings")
    if bindings != REQUIRED_COMMIT_RESULT_BINDINGS:
        raise SystemExit(
            "Phase 0A commit-readiness required_result_bindings must exactly match the four hash/tree bindings"
        )
    result_path_pattern = evaluation.get("result_path_pattern")
    if (
        not isinstance(result_path_pattern, str)
        or not result_path_pattern.strip()
        or "<run_id>" not in result_path_pattern
    ):
        raise SystemExit(
            "Phase 0A commit-readiness result_path_pattern must be non-empty and contain <run_id>"
        )
    evidence_refs = evaluation.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        raise SystemExit("Phase 0A commit-readiness evidence_refs must be an array")
    for ref in evidence_refs:
        if not isinstance(ref, str) or not ref.strip() or not (repo_root / ref).exists():
            raise SystemExit(f"Missing Phase 0A commit-readiness evidence ref: {ref}")


def build_document(repo_root: Path, rows: list[dict], generated_utc: str | None = None) -> dict:
    counts = Counter(row["status"] for row in rows)
    evidence_index = read_json(EVIDENCE_INDEX)
    commit_evaluation = evidence_index.get("phase0a_commit_readiness_evaluation", {})
    commit_status = commit_evaluation.get("status", "not_evaluated")
    validate_commit_readiness_evaluation(repo_root, commit_evaluation)
    row_dispositions_passed = phase0a_exit_satisfied(rows, repo_root=repo_root)
    phase1_authorized = row_dispositions_passed and commit_status == "passed"
    phase_counts = {
        phase: dict(Counter(row["status"] for row in rows if row["phase"] == phase))
        for phase in PHASE_SECTIONS
    }
    return {
        "schema_version": "gdd-to-module-implementation-acceptance-matrix.v1",
        "generated_utc": generated_utc or datetime.now(timezone.utc).isoformat(),
        "source_inputs_hash": source_inputs_hash(repo_root),
        "authority": {
            "phase_exit_source": PHASE_SOURCE.as_posix(),
            "capability_inventory": CAPABILITY_SOURCE.as_posix(),
            "split_added_registry": ACCEPTANCE_REGISTRY.as_posix(),
            "split_added_ledger": SPLIT_ADDED_LEDGER.as_posix(),
        },
        "phase0a_predecessor_gate": {
            "evaluation_mode": "post_generation_external_result",
            "effective_commit_readiness_status_values": sorted(COMMIT_READINESS_STATUSES),
            "row_disposition_status": "passed" if row_dispositions_passed else "blocked",
            "commit_readiness_status": commit_status,
            "complete_predecessor_status": "passed" if phase1_authorized else "blocked",
            "phase1_authorized": phase1_authorized,
            "row_disposition_requirement": "Every Phase 0A row is verified, evidenced not_applicable, or explicitly_deferred with the complete deferral contract.",
            "matrix_row_dispositions_alone_are_sufficient": False,
            "additional_required_checks": [
                {
                    "check_id": "GTM-GATE-P0A-COMMIT-READINESS",
                    "source_refs": [
                        f"{(PLAN_DIR / '00-index.md').as_posix()}:26",
                        f"{(PLAN_DIR / '10-recommended-first-slice.md').as_posix()}:9",
                    ],
                    "validator_refs": [
                        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/capture_commit_set.py",
                        "logs/phase-a-innernet/reviews/gdd-to-module-hardening/review_harness.py#COMMIT-PROPOSED-SET-COMPLETE",
                    ],
                    "required_result": "passed",
                    "evaluation": commit_evaluation,
                    "effective_result_authority": commit_evaluation.get("result_path_pattern", ""),
                    "required_result_bindings": commit_evaluation.get("required_result_bindings", []),
                    "requirement": "The complete split directory and schemas are included in the proposed commit/PR, no split-plan file is untracked, and monolithic-source changes comply with the source-history policy.",
                }
            ],
        },
        "allowed_statuses": sorted(ALLOWED_STATUSES),
        "summary": {
            "check_count": len(rows),
            "status_counts": {status: counts.get(status, 0) for status in sorted(ALLOWED_STATUSES)},
            "phase_status_counts": phase_counts,
        },
        "checks": rows,
    }


def write_outputs(repo_root: Path, rows: list[dict]) -> None:
    document = build_document(repo_root, rows)
    counts = Counter(row["status"] for row in rows)
    gate = document["phase0a_predecessor_gate"]
    commit_evaluation = gate["additional_required_checks"][0]["evaluation"]
    OUTPUT_JSON.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown = f"""# GDD-To-Module Implementation Acceptance Matrix

This view is generated from the machine-readable authority at
`schemas/implementation-acceptance-matrix.v1.json`. Checks are acceptance-clause based, not document based.

## Status Contract

- `verified`: implementation, automated tests, and evidence all satisfy the check.
- `partial`: some implementation exists, but the complete acceptance condition is not met.
- `missing`: no implementation or closure evidence exists.
- `not_applicable`: an auditable reason and evidence prove the check does not apply.
- `explicitly_deferred`: a named owner and recheck condition defer the check.
- `blocked`: a prerequisite prevents the check from being accepted.

No other status value is allowed.

## Current Summary

- Total checks: `{len(rows)}`
{chr(10).join(f'- `{status}`: `{counts.get(status, 0)}`' for status in sorted(ALLOWED_STATUSES))}

## Phase 0A Predecessor Gate

- Evaluation mode: `{gate['evaluation_mode']}`.
- Row-disposition gate: `{gate['row_disposition_status']}`.
- Commit-readiness gate: `{gate['commit_readiness_status']}` (`{commit_evaluation.get('reason_code', 'not_evaluated')}`).
- Complete predecessor gate: `{gate['complete_predecessor_status']}`.
- Phase 1 authorized: `{str(gate['phase1_authorized']).lower()}`.
- Commit-readiness evidence: {', '.join(f'`{ref}`' for ref in commit_evaluation.get('evidence_refs', [])) or '-'}
- External result authority: `{gate['additional_required_checks'][0]['effective_result_authority']}`.
- Required result bindings: {', '.join(f'`{item}`' for item in gate['additional_required_checks'][0]['required_result_bindings'])}.
- Recheck condition: {commit_evaluation.get('recheck_condition', 'Run the commit-readiness validator before Phase 1.')}

## Matrix

{markdown_table(rows)}
"""
    OUTPUT_MARKDOWN.write_text(markdown, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Phase 0A-6 implementation acceptance matrix.")
    parser.add_argument("--repository-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--rebuild-ids", action="store_true", help="Rebuild IDs only during initial uncommitted matrix authoring.")
    args = parser.parse_args()
    repo_root = Path(args.repository_root).resolve()
    os.chdir(repo_root)
    global REBUILD_IDS
    REBUILD_IDS = args.rebuild_ids

    lines = PHASE_SOURCE.read_text(encoding="utf-8").splitlines()
    rows = build_phase_rows(lines) + build_local_acceptance_rows() + build_split_added_rows() + build_capability_rows(repo_root)
    rows = apply_evidence_index(rows)
    rows = apply_phase0a_predecessor_gate(rows, repo_root=repo_root)
    validate_rows(repo_root, rows)
    if args.check_only:
        current = read_json(OUTPUT_JSON)
        expected = build_document(repo_root, rows, generated_utc=current.get("generated_utc", ""))
        if current != expected:
            raise SystemExit("Committed matrix document is stale; regenerate the matrix.")
        print(json.dumps({"status": "ok", "check_count": len(rows)}, ensure_ascii=False))
        return 0
    write_outputs(repo_root, rows)
    print(json.dumps({"status": "ok", "check_count": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
