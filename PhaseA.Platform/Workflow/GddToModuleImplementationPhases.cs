using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GddToModuleImplementationPhases
{
    public const string PlanId = "phase-a-gdd-to-module-hardening-implementation-phases";
    public const string PlanVersion = "v1";
    public const string StandardPath = "docs/workflows/phase-a-gdd-to-module-implementation-phases.md";
    public const string PhaseExitReviewSchemaPath = "docs/schemas/gdd-to-module-phase-exit-review.v1.example.json";
    public const string DefaultReviewEvidenceRoot = "logs/phase-a-innernet/reviews/gdd-to-module-hardening";

    public static readonly IReadOnlyList<string> RequiredPhaseExitReviewFields =
    [
        "phase",
        "run_id",
        "reviewed_utc",
        "reviewer",
        "implemented_items",
        "consumed_phase0a_items",
        "required_phase0b_items",
        "routes",
        "artifacts",
        "api_surfaces",
        "browser_surfaces",
        "scripts",
        "evidence_refs",
        "durable_decision_refs",
        "unresolved_findings_by_severity",
        "regression_checks"
    ];

    public static readonly IReadOnlyList<string> Phase0AItems =
    [
        "route_module_contract_template",
        "path_readback_policy",
        "route_action_exposure_classes",
        "context_boundary_dto_hygiene",
        "no_store_workflow_evidence_readback",
        "duplicate_run_idempotency_convention",
        "dimensioned_status_vocabulary",
        "source_boundary_schema",
        "canonical_prototype_contract_path_policy",
        "route_action_descriptor_registry",
        "admin_review_queue_metadata_owner",
        "minimum_diagnostic_index_schema",
        "structured_game_type_metadata_hash_policy",
        "complete_workflow_action_descriptor_mapping",
        "secret_redaction_validator_baseline",
        "local_deterministic_preflight",
        "phase_review_evidence_template",
        "phase_adr_decision_log_gate",
        "shared_llm_codex_entrypoint_guard"
    ];

    public static readonly IReadOnlyList<string> Phase0BItems =
    [
        "godot_engine_semantic_baseline",
        "godot_ui_capability_contract_template",
        "godot_ui_style_contract_template",
        "godot_ui_style_snapshot_schema",
        "godot_ui_style_closure_contract",
        "godot_diagnostics_quality_gate_contract",
        "visual_evidence_fixture_seed",
        "full_taptapmarker_non_technology_ui_capability_coverage"
    ];

    public static readonly IReadOnlyList<ImplementationPhase> Phases =
    [
        new(
            "0A",
            "Cross-cutting governance blocking baseline",
            "governance",
            Phase0AItems,
            [],
            [
                "workflow-recommendation",
                "project-delete",
                "structured-game-type-analysis"
            ],
            "Phase 1 cannot start until Phase 0A review records zero unresolved P0/P1/P2 findings."),
        new(
            "0B",
            "Expanded Godot capability baseline",
            "capability",
            [],
            Phase0BItems,
            [
                "gdd-document-generation",
                "gdd-requirements",
                "prototype-contract",
                "prototype-skeleton-guard",
                "preview-package",
                "ui-wiring-closure"
            ],
            "Touched routes must consume required Phase 0B packages before implementation."),
        new(
            "1",
            "Requirement map and contract freshness",
            "route",
            [
                "route_module_contract_template",
                "path_readback_policy",
                "route_action_descriptor_registry",
                "admin_review_queue_metadata_owner",
                "minimum_diagnostic_index_schema",
                "shared_llm_codex_entrypoint_guard"
            ],
            [
                "godot_engine_semantic_baseline",
                "godot_ui_capability_contract_template",
                "godot_ui_style_contract_template",
                "godot_diagnostics_quality_gate_contract"
            ],
            [
                "structured-game-type-analysis",
                "scene-route-confirmation",
                "gdd-document-generation",
                "gdd-requirements",
                "prototype-contract",
                "prototype-skeleton-guard"
            ],
            "Requirement map, scene route, contract freshness, skeleton guard, and source hash tests pass."),
        new(
            "2",
            "Iteration plan traceability gate",
            "route",
            ["route_module_contract_template", "source_boundary_schema", "duplicate_run_idempotency_convention"],
            ["godot_ui_capability_contract_template", "godot_ui_style_contract_template", "godot_diagnostics_quality_gate_contract"],
            ["iteration-plan"],
            "Every P0/P1 requirement is covered by plan, explicit blocker, or reviewed non-applicability."),
        new(
            "3",
            "Workflow recommendation",
            "route",
            ["complete_workflow_action_descriptor_mapping", "dimensioned_status_vocabulary", "context_boundary_dto_hygiene"],
            [],
            ["workflow-recommendation"],
            "Recommendation exposes one allowed primary next step and maps forbidden actions to disabled reasons."),
        new(
            "4",
            "Execute goal freshness and needs-fix tightening",
            "route",
            ["source_boundary_schema", "secret_redaction_validator_baseline", "shared_llm_codex_entrypoint_guard"],
            ["godot_engine_semantic_baseline", "godot_ui_capability_contract_template", "godot_ui_style_contract_template", "godot_diagnostics_quality_gate_contract"],
            ["execute-next-goal", "needs-fix", "repair"],
            "Codex execution is blocked by stale sources, missing diagnostics, or missing frozen capability/style contracts."),
        new(
            "5",
            "UI wiring closure",
            "route",
            ["path_readback_policy", "duplicate_run_idempotency_convention", "admin_review_queue_metadata_owner"],
            ["godot_ui_capability_contract_template", "godot_ui_style_contract_template", "godot_ui_style_closure_contract", "godot_diagnostics_quality_gate_contract"],
            ["ui-wiring-closure", "preview-package"],
            "UI closure and preview readiness cannot pass with unresolved UI, style, diagnostics, source-boundary, or admin-review blockers."),
        new(
            "6",
            "Route governance guardrails",
            "consolidation",
            Phase0AItems,
            Phase0BItems,
            [
                "structured-game-type-analysis",
                "gdd-requirements",
                "gdd-document-generation",
                "scene-route-confirmation",
                "prototype-contract",
                "prototype-skeleton-guard",
                "workflow-recommendation",
                "iteration-plan",
                "execute-next-goal",
                "needs-fix",
                "repair",
                "project-delete",
                "ui-wiring-closure",
                "preview-package"
            ],
            "Phase 0 primitives are reused across all covered routes and final readiness remains distinct from package download.")
    ];

    public static readonly string PlanHash = ComputeHash();

    public static ImplementationPhase? Find(string phase)
    {
        return Phases.FirstOrDefault(item => string.Equals(item.Phase, phase, StringComparison.Ordinal));
    }

    public static bool HasZeroBlockingFindings(IDictionary<string, int> unresolvedFindingsBySeverity)
    {
        return unresolvedFindingsBySeverity.TryGetValue("P0", out var p0) && p0 == 0 &&
               unresolvedFindingsBySeverity.TryGetValue("P1", out var p1) && p1 == 0 &&
               unresolvedFindingsBySeverity.TryGetValue("P2", out var p2) && p2 == 0;
    }

    public static string ReviewFileName(string phase, string runId)
    {
        if (string.IsNullOrWhiteSpace(phase) || string.IsNullOrWhiteSpace(runId))
        {
            throw new ArgumentException("Phase and run id are required.");
        }

        return $"phase-{phase}-exit-review-{runId}.json";
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n", Phases.Select(phase => string.Join(
            "|",
            phase.Phase,
            phase.Title,
            phase.PhaseKind,
            string.Join(",", phase.ConsumedPhase0AItems),
            string.Join(",", phase.RequiredPhase0BItems),
            string.Join(",", phase.Routes),
            phase.ExitCriterion)));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }
}

public sealed record ImplementationPhase(
    string Phase,
    string Title,
    string PhaseKind,
    IReadOnlyList<string> ConsumedPhase0AItems,
    IReadOnlyList<string> RequiredPhase0BItems,
    IReadOnlyList<string> Routes,
    string ExitCriterion);
