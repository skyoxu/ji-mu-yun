using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GddToModuleFirstSlice
{
    public const string SliceId = "phase-a-gdd-to-module-recommended-first-slice";
    public const string SliceVersion = "v1";
    public const string WorkflowDocPath = "docs/workflows/phase-a-gdd-to-module-first-slice.md";
    public const string FirstSliceReviewSchemaPath = "docs/schemas/gdd-to-module-first-slice-review.v1.example.json";
    public const string FullTargetLedgerSchemaPath = "docs/schemas/full-target-ui-closure-ledger.v1.example.json";
    public const string FullTargetLedgerRuntimePath = "logs/phase-a-innernet/reviews/gdd-to-module-hardening/full-target-ui-closure-ledger.json";

    public const string InterimCoverageStatus = "not_consumed_by_first_slice";

    public static readonly IReadOnlyList<FirstSlicePlanItem> Phase0AMandatoryBaseline =
    [
        Item("0A-01", "route_module_contract_template_and_action_descriptor_registry", "Phase 0 route module contract template and route action descriptor registry baseline."),
        Item("0A-02", "path_readback_no_store_exposure_context_account_boundary", "Path/readback policy, no-store workflow readback, exposure classes, context boundary, and account-boundary tests."),
        Item("0A-03", "duplicate_run_idempotency_active_run_reused_preflight", "Duplicate-run/idempotency convention, active_run_reused response contract, and local preflight checklist."),
        Item("0A-04", "canonical_prototype_contract_path_policy", "routes/prototype-contract/latest.json is authority and stale mirror mismatch fails validation."),
        Item("0A-05", "common_source_boundary_schema_prompt_evidence", "Common source-boundary schema, prompt evidence guard, and structured source_boundary_not_applicable object."),
        Item("0A-06", "dimensioned_status_vocabulary", "Central dimensioned status vocabulary with fixture parity tests."),
        Item("0A-07", "admin_review_queue_metadata_owner", "Admin review queue sidecar/API/readback/mutation contract with metadata DB as query owner."),
        Item("0A-08", "complete_workflow_action_mapping", "Complete canonical workflow action mapping across API and browser catalogs."),
        Item("0A-09", "package_download_final_readiness_boundary", "Ordinary package download compatibility is separate from final package readiness."),
        Item("0A-10", "exemption_semantics_reviewed_system_exemptions", "no_ui_needed and style_not_applicable remain scoped exemptions, with review for system-created P0/P1 exemptions."),
        Item("0A-11", "diagnostic_spool_minimum_schema_retention", "Diagnostic spool metadata DB ownership, minimum schema, failure-family seed, and retention rules."),
        Item("0A-12", "evidence_ref_kind_fixture_parity", "Evidence ref kind fixture mirrors phase-service standards across sidecars, DTOs, and browser readback."),
        Item("0A-13", "secret_redaction_validator_phase_review_template", "Secret redaction validator baseline, fixture coverage, and phase review evidence template."),
        Item("0A-14", "adr_decision_log_gate", "ADR/decision-log gate for durable cross-cutting standards and architecture contracts."),
        Item("0A-15", "shared_llm_codex_entrypoint_guard", "Shared LLM/Codex entrypoint guard and tests for C#, Codex command, and Python backend."),
        Item("0A-16", "structured_game_type_metadata_hash_policy", "Structured game-type metadata ownership, normalized fields, hash policy, and stale blocker tests."),
        Item("0A-17", "phase_service_standards_sync_checklist", "Phase-service standards sync checklist for status, readback, readiness, diagnostics, delete, and game-type maintenance.")
    ];

    public static readonly IReadOnlyList<FirstSlicePlanItem> Phase0BRouteDependentBaseline =
    [
        Item("0B-18", "godot_engine_semantic_baseline", "Godot engine semantic baseline, viewport and feature-family rules, reference examples, and missing-reference diagnostics."),
        Item("0B-19", "godot_ui_capability_contract_template", "Godot UI capability contract template, version/hash rule, leakage denylist, and initial fixtures."),
        Item("0B-20", "godot_ui_style_contract_template", "Godot UI style contract, built-in style seed, style taxonomy, component defaults, token mapping, and fixtures."),
        Item("0B-21", "godot_diagnostics_quality_gate_contract", "Godot diagnostics and quality-gate contract, diagnostic spool schema, interaction-region, preview, and lifecycle rules."),
        Item("0B-22", "durable_review_evidence", "Durable review evidence under logs."),
        Item("0B-23", "phase0b_dependency_matrix_in_phase_review", "Phase 0B dependency matrix in phase review evidence for every touched Phase 1 route.")
    ];

    public static readonly IReadOnlyList<FirstSlicePlanItem> SmallestPhase1Slice =
    [
        Item("P1-23", "game_design_requirement_map_service", "GameDesignRequirementMapService through ILlmRouteEngine for structured output."),
        Item("P1-24", "gdd_document_generation_write_through_hash", "GDD document generation records matching source_generated_gdd_hash in scene route state."),
        Item("P1-25", "requirement_map_api_readback", "Requirement map API and browser-safe readback."),
        Item("P1-26", "artifact_local_source_hashes", "Artifact-local contract and source hash fields with API/readback projections."),
        Item("P1-27", "artifact_local_ui_contract_style_source_boundary_fields", "Artifact-local Godot UI contract/style version and source-boundary projections."),
        Item("P1-28", "stale_detection_and_frontend_banners", "Stale detection for GDD, scene, requirement map, contract, game-type, UI capability, style, and snapshot hashes with frontend banners."),
        Item("P1-29", "route_module_contract_template_application", "Route module contract template application for game-type, scene, GDD document, requirement map, and prototype contract routes."),
        Item("P1-30", "prototype_skeleton_compatibility_guard", "Prototype skeleton compatibility guard for new-chain projects."),
        Item("P1-31", "workflow_recommendation_phase_eligibility_tests", "Workflow recommendation phase-eligibility tests for forbidden downstream actions."),
        Item("P1-32", "phase1_guard_test_matrix", "Guard tests for paths, hashes, source boundaries, statuses, evidence kinds, UI/style/diagnostic fields, readiness, exemptions, redaction, LLM/Codex usage, and source history."),
        Item("P1-33", "minimum_deckbuilder_chain_tests", "Minimum deckbuilder GDD to requirement map to fresh contract chain tests.")
    ];

    public static readonly IReadOnlyList<CapabilityScheduleRow> CapabilitySchedule =
    [
        Schedule(
            [
                "ui_component_system",
                "ui_theme_token_system",
                "ui_layout_scale_coordinates",
                "ui_input_pointer_gesture",
                "ui_state_data_binding",
                "ui_style_snapshot_schema",
                "ui_runtime_environment_identity",
                "ui_theme_resource_contract",
                "ui_style_schema_acceptance_gate",
                "godot_failure_family_taxonomy",
                "godot_diagnostic_spool_contract"
            ],
            "Phase 0B / Phase 1 touched routes",
            "Any visible UI project, requirement map, scene confirmation, GDD document generation, or contract freeze",
            "Standards templates, style fixture/profile, phase exit evidence, route/style capability matrix"),
        Schedule(
            [
                "ui_lifecycle_ownership",
                "ui_overlays_feedback",
                "ui_diagnostics_visual_evidence",
                "ui_visual_evidence_contract",
                "godot_prebuild_preview_quality_gate",
                "godot_interaction_region_gate",
                "godot_resource_lifecycle_gate"
            ],
            "Phase 2-5 when consumed by iteration, execution, repair, UI closure, preview, or package",
            "Dynamic UI nodes, overlays, player feedback, diagnostics, preview/package, interaction-heavy goals, resource-owning helpers",
            "Route contracts, diagnostic spool records, visual evidence, interaction-region artifact, lifecycle cleanup evidence"),
        Schedule(
            [
                "ui_scroll_virtualization",
                "ui_style_closure_gap_taxonomy",
                "ui_style_repair_prompt_contract",
                "ui_final_readiness_style_gate"
            ],
            "Phase 5-6 or earlier if consumed by a touched route",
            "Large lists/grids, style-aware repair, UI closure, final readiness",
            "UI closure readback, style gap rows, repair prompt evidence, full-target closure ledger"),
        Schedule(
            [
                "ui_security_gated_tooling"
            ],
            "Only when security-gated admin/tooling UI is implemented",
            "File upload, raw diagnostic viewers, account/admin-only asset tooling",
            "Phase service security policy, account-boundary tests, redacted admin evidence, explicit normal-user non-applicability rows")
    ];

    public static readonly IReadOnlyList<string> RequiredLedgerFields =
    [
        "capability_id",
        "owner_doc",
        "firstRequiredPhase",
        "trigger",
        "ownerEvidence",
        "currentCoverageStatus",
        "closure_status",
        "affected_routes",
        "owner",
        "expiry_or_recheck_trigger",
        "validation_evidence_refs",
        "defer_reason",
        "phase_exit_review_ref"
    ];

    public static readonly IReadOnlyList<string> FinalClosureStatuses = GodotUiStyleClosureContract.FullTargetClosureStatuses;

    public static readonly string SliceHash = ComputeHash();

    public static IReadOnlyList<string> CapabilityIds =>
        CapabilitySchedule.SelectMany(row => row.CapabilityIds).Distinct(StringComparer.Ordinal).ToArray();

    public static bool CanStartPhase1(IReadOnlySet<string> completedPhase0AItemIds, IDictionary<string, int> unresolvedFindingsBySeverity)
    {
        return Phase0AMandatoryBaseline.All(item => completedPhase0AItemIds.Contains(item.ItemId)) &&
               GddToModuleImplementationPhases.HasZeroBlockingFindings(unresolvedFindingsBySeverity);
    }

    public static IReadOnlyList<CapabilityScheduleViolation> ValidateConsumedCapabilitySchedule(
        IEnumerable<FullTargetCapabilityLedgerRow> ledgerRows,
        IReadOnlySet<string> consumedCapabilityIds)
    {
        var rowsById = ledgerRows.ToDictionary(row => row.CapabilityId, StringComparer.Ordinal);
        var violations = new List<CapabilityScheduleViolation>();

        foreach (var capabilityId in consumedCapabilityIds)
        {
            if (!CapabilityIds.Contains(capabilityId, StringComparer.Ordinal))
            {
                violations.Add(new CapabilityScheduleViolation(capabilityId, "unknown_capability_id"));
                continue;
            }

            if (!rowsById.TryGetValue(capabilityId, out var row))
            {
                violations.Add(new CapabilityScheduleViolation(capabilityId, "missing_ledger_row"));
                continue;
            }

            if (!string.Equals(row.CurrentCoverageStatus, InterimCoverageStatus, StringComparison.Ordinal))
            {
                continue;
            }

            var hasReviewedEscape = string.Equals(row.ClosureStatus, "reviewed_not_applicable", StringComparison.Ordinal) ||
                                    string.Equals(row.ClosureStatus, "explicitly_deferred", StringComparison.Ordinal);
            if (!hasReviewedEscape)
            {
                violations.Add(new CapabilityScheduleViolation(capabilityId, "consumed_capability_left_not_consumed_by_first_slice"));
            }
            else if (!HasRequiredFinalMetadata(row))
            {
                violations.Add(new CapabilityScheduleViolation(capabilityId, "reviewed_escape_missing_owner_expiry_or_evidence"));
            }
        }

        return violations;
    }

    public static IReadOnlyList<CapabilityScheduleViolation> ValidateFinalClosureLedger(IEnumerable<FullTargetCapabilityLedgerRow> ledgerRows)
    {
        var rows = ledgerRows.ToArray();
        var violations = new List<CapabilityScheduleViolation>();
        var duplicateIds = rows
            .GroupBy(row => row.CapabilityId, StringComparer.Ordinal)
            .Where(group => group.Count() > 1)
            .Select(group => group.Key);

        foreach (var capabilityId in duplicateIds)
        {
            violations.Add(new CapabilityScheduleViolation(capabilityId, "duplicate_ledger_row"));
        }

        foreach (var capabilityId in CapabilityIds)
        {
            if (rows.All(row => !string.Equals(row.CapabilityId, capabilityId, StringComparison.Ordinal)))
            {
                violations.Add(new CapabilityScheduleViolation(capabilityId, "missing_ledger_row"));
            }
        }

        foreach (var row in rows)
        {
            if (!CapabilityIds.Contains(row.CapabilityId, StringComparer.Ordinal))
            {
                violations.Add(new CapabilityScheduleViolation(row.CapabilityId, "orphan_ledger_row"));
            }

            if (!FinalClosureStatuses.Contains(row.ClosureStatus, StringComparer.Ordinal))
            {
                violations.Add(new CapabilityScheduleViolation(row.CapabilityId, "invalid_final_closure_status"));
            }

            if (string.Equals(row.CurrentCoverageStatus, InterimCoverageStatus, StringComparison.Ordinal))
            {
                violations.Add(new CapabilityScheduleViolation(row.CapabilityId, "interim_status_not_final"));
            }

            if (!HasRequiredFinalMetadata(row))
            {
                violations.Add(new CapabilityScheduleViolation(row.CapabilityId, "missing_owner_expiry_or_validation_evidence"));
            }
        }

        return violations;
    }

    public static bool IsCommitReady(FirstSliceCommitReadiness review)
    {
        return review.SplitDirectoryIncluded &&
               review.SchemaFixturesIncluded &&
               review.NoUntrackedSplitPlanFiles &&
               !review.MonolithicSourceUsedAsLiveMirror &&
               (!review.MonolithicSourceChanged || review.MonolithicSourceChangeRecordedAsHistoryMaintenance);
    }

    private static bool HasRequiredFinalMetadata(FullTargetCapabilityLedgerRow row)
    {
        return !string.IsNullOrWhiteSpace(row.Owner) &&
               row.AffectedRoutes.Count > 0 &&
               !string.IsNullOrWhiteSpace(row.ExpiryOrRecheckTrigger) &&
               row.ValidationEvidenceRefs.Count > 0 &&
               !string.IsNullOrWhiteSpace(row.PhaseExitReviewRef);
    }

    private static FirstSlicePlanItem Item(string itemId, string title, string acceptance)
    {
        return new FirstSlicePlanItem(itemId, title, acceptance);
    }

    private static CapabilityScheduleRow Schedule(IReadOnlyList<string> capabilityIds, string firstRequiredPhase, string trigger, string ownerEvidence)
    {
        return new CapabilityScheduleRow(capabilityIds, firstRequiredPhase, trigger, ownerEvidence);
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n",
            Phase0AMandatoryBaseline.Select(item => $"{item.ItemId}|{item.Title}|{item.Acceptance}")
                .Concat(Phase0BRouteDependentBaseline.Select(item => $"{item.ItemId}|{item.Title}|{item.Acceptance}"))
                .Concat(SmallestPhase1Slice.Select(item => $"{item.ItemId}|{item.Title}|{item.Acceptance}"))
                .Concat(CapabilitySchedule.Select(row => $"{string.Join(",", row.CapabilityIds)}|{row.FirstRequiredPhase}|{row.Trigger}|{row.OwnerEvidence}"))
                .Concat(RequiredLedgerFields));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }
}

public sealed record FirstSlicePlanItem(string ItemId, string Title, string Acceptance);

public sealed record CapabilityScheduleRow(
    IReadOnlyList<string> CapabilityIds,
    string FirstRequiredPhase,
    string Trigger,
    string OwnerEvidence);

public sealed record FullTargetCapabilityLedgerRow(
    string CapabilityId,
    string OwnerDoc,
    string FirstRequiredPhase,
    string Trigger,
    string OwnerEvidence,
    string CurrentCoverageStatus,
    string ClosureStatus,
    IReadOnlyList<string> AffectedRoutes,
    string Owner,
    string ExpiryOrRecheckTrigger,
    IReadOnlyList<string> ValidationEvidenceRefs,
    string DeferReason,
    string PhaseExitReviewRef);

public sealed record CapabilityScheduleViolation(string CapabilityId, string Reason);

public sealed record FirstSliceCommitReadiness(
    bool SplitDirectoryIncluded,
    bool SchemaFixturesIncluded,
    bool NoUntrackedSplitPlanFiles,
    bool MonolithicSourceUsedAsLiveMirror,
    bool MonolithicSourceChanged,
    bool MonolithicSourceChangeRecordedAsHistoryMaintenance);
