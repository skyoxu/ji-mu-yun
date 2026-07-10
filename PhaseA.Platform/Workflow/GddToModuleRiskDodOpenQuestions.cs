using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GddToModuleRiskDodOpenQuestions
{
    public const string RegisterId = "phase-a-gdd-to-module-risk-dod-open-questions";
    public const string RegisterVersion = "v1";
    public const string StandardPath = "docs/workflows/phase-a-gdd-to-module-risk-dod-open-questions.md";
    public const string ClosureReviewSchemaPath = "docs/schemas/gdd-to-module-dod-closure-review.v1.example.json";

    public static readonly IReadOnlyList<string> DodLayers =
    [
        "program",
        "phase_exit",
        "first_slice"
    ];

    public static readonly IReadOnlyList<RiskRegisterRow> Risks =
    [
        Risk("too_many_stages", "Too many new stages overwhelm users", "Use recommendation-driven primary action and hide advanced controls.", "User always sees one recommended next action."),
        Risk("llm_requirement_map_misses_details", "LLM requirement map misses details", "Add coverage validation and needs-review fallback.", "Empty map is invalid unless GDD has no requirements."),
        Risk("contract_stale_blocks_legacy", "Contract stale blocks old users unexpectedly", "Treat legacy as unknown; allow explicit refresh and hash-bound continuation only.", "Existing preview/package works; new execution from unknown-source legacy plans remains blocked."),
        Risk("strictness_slows_prototype_creation", "Too much strictness slows prototype creation", "P0/P1 block runtime by default; tracked P2 can be advisory for ordinary execution only.", "Fast path remains usable and implementation acceptance has zero unresolved P0/P1/P2 findings."),
        Risk("ui_closure_delays_playability", "UI closure delays early playability", "UI closure is late-stage final-readiness gate, not skeleton gate.", "Prototype creation does not require UI closure."),
        Risk("formatting_hash_churn", "Formatting-only GDD changes cause hash churn", "Normalize text before hashing or classify formatting-only stale as advisory.", "Formatting-only changes can avoid hard stale if normalized hash is unchanged."),
        Risk("taptap_patterns_copied_literally", "Borrowed TapTap patterns are copied too literally", "Adapt boundary and guard patterns only; keep Phase A C# architecture.", "No TypeScript/MCP feature layout is required."),
        Risk("brittle_guard_snapshots", "Guard tests become brittle string snapshots", "Guard stable names, enums, source-boundary markers, and contract fields.", "Tests fail on real contract drift, not harmless copy changes."),
        Risk("hidden_admin_mutation_paths", "Admin scripts become hidden mutation paths", "Require explicit admin intent, idempotency notes, and append-only evidence.", "Bulk maintenance stays auditable."),
        Risk("diagnostic_spool_leaks_private_evidence", "Project diagnostic spool leaks private evidence", "Store spool outside workspaces with redaction status, account ownership, admin-only raw access, and user-safe summaries.", "Normal-user readback cannot expose cross-account diagnostics, raw host paths, raw prompts, token material, provider secrets, or admin-only evidence."),
        Risk("project_delete_removes_diagnostics", "Project deletion accidentally removes diagnostics", "Keep diagnostic spool outside hosted workspaces and make deletion cleanup ignore preserved diagnostics.", "Deleted-project admin lookup still finds unresolved diagnostics."),
        Risk("package_download_mistaken_for_final_readiness", "Package download is mistaken for final readiness", "Separate ordinary package download compatibility from final readiness labels.", "Download can remain available while final readiness remains blocked."),
        Risk("diagnostic_cleanup_erases_repair_evidence", "Diagnostic cleanup erases repair evidence", "Preserve unresolved blockers and keep replacement evidence for eligible compaction/redaction.", "Unresolved P0/P1/P2 diagnostics survive deletion and cleanup.")
    ];

    public static readonly IReadOnlyList<DodItem> DodItems =
    [
        Dod(1, "full_stage_flow_visible", "A new project can complete the full stage flow from GDD form to package with visible stage statuses.", "program"),
        Dod(2, "requirement_map_coverage", "GDD requirements are represented in meta/routes/gdd-requirements/latest.json with coverage status.", "phase_exit"),
        Dod(6, "canonical_contract_path", "routes/prototype-contract/latest.json records source hashes and stale status can be read back.", "phase_exit"),
        Dod(8, "execute_refuses_stale_source", "Execute-next-goal refuses stale/missing source state before executable Codex work.", "phase_exit"),
        Dod(12, "api_backward_compatibility", "No existing public/browser API field is removed or renamed.", "phase_exit"),
        Dod(19, "zero_p0_p1_p2", "Final review records zero unresolved P0, P1, or P2 findings.", "phase_exit"),
        Dod(24, "diagnostics_quality_gate_consumed", "Godot diagnostics quality-gate contract is linked, consumed by route diagnostics, and covered by guard tests.", "phase_exit"),
        Dod(25, "diagnostic_spool_retention", "Project diagnostic spool preserves unresolved P0/P1/P2 diagnostics outside hosted workspaces with deleted-project admin lookup and triage.", "phase_exit"),
        Dod(27, "ui_style_contract_consumed", "Godot UI style contract is frozen into prototype contracts and consumed by downstream UI/style routes.", "phase_exit"),
        Dod(35, "download_vs_final_readiness", "Ordinary package download compatibility is separate from final package readiness.", "phase_exit"),
        Dod(40, "split_primary_source", "The split directory is committed as primary plan and source-history maintenance is recorded when needed.", "first_slice"),
        Dod(43, "phase_exit_review_evidence", "Each phase exit review writes append-only structured JSON under the agreed logs path.", "phase_exit"),
        Dod(44, "full_target_closure_ledger", "Full non-technology UI target has a closure ledger with covered, reviewed_not_applicable, or explicitly_deferred rows.", "program"),
        Dod(49, "split_added_requirements_classified", "Split-added hardening requirements are classified in phase exit evidence.", "first_slice")
    ];

    public static readonly IReadOnlyList<DecisionMatrixRow> DecisionMatrix =
    [
        Decision("api_auth_db_llm_retention_runtime", "New or changed public/browser API semantics, auth behavior, account isolation, metadata DB ownership, shared LLM/Codex invocation behavior, diagnostic retention policy, or runtime/protected-path behavior", "adr_or_update"),
        Decision("route_contract_action_status_readiness_admin_style_diagnostic", "New route module contract, action descriptor, source-boundary rule, readiness label policy, admin review queue behavior, or style/diagnostic standard without architecture ownership change", "decision_log_or_standards"),
        Decision("execution_plan_sequence", "Pure execution-plan sequencing, first-slice ordering, or non-binding implementation notes", "execution_plan_only"),
        Decision("phase_service_standards_sync", "Phase service standards update for API/status/error/readback/no-store semantics introduced by this plan", "standards_update")
    ];

    public static readonly IReadOnlyList<OpenQuestionRow> OpenQuestions =
    [
        Question("requirement_map_manual_edits", "Should users manually edit requirement map rows?", "Product + Phase A platform", "Phase 1 forbids normal-user direct edits and regenerates from GDD/scene route."),
        Question("contract_stale_continuation", "Should contract_stale block execute-next-goal for all statuses?", "Phase A platform", "Phase 1 blocks new execution and allows only hash-bound old session continuation."),
        Question("ui_closure_package_gate", "Should UI closure become mandatory before package download?", "Product + Phase A platform", "Phase 1 keeps ordinary package download non-blocking and final readiness blocked."),
        Question("requirement_map_generation_architecture", "Should requirement mapping stay hybrid deterministic plus structured LLM?", "Phase A platform", "Phase 1 uses deterministic collection/validation plus structured LLM and fallback rows."),
        Question("hash_normalization_scope", "Should source hash normalization ignore more Markdown changes?", "Phase A platform", "Phase 1 normalizes line endings/trailing whitespace and keeps raw diagnostic hashes."),
        Question("ui_style_selection_ux", "Should users choose UI style manually during GDD?", "Product + Phase A platform", "Phase 1 starts with workflow recommendation plus explicit override.")
    ];

    public static readonly IReadOnlyList<string> Phase1DefaultDecisions =
    [
        "requirement_map_rows_not_user_editable",
        "contract_stale_blocks_new_iteration_plan",
        "ui_closure_not_required_for_ordinary_package_download",
        "hybrid_deterministic_structured_llm_requirement_mapping",
        "workflow_recommended_ui_style_with_override",
        "normalized_markdown_and_canonical_json_source_hashes"
    ];

    public static readonly string RegisterHash = ComputeHash();

    public static bool CanClaimDodLayer(string requestedLayer, IReadOnlySet<string> completedItemIds, IReadOnlySet<string> unresolvedConsumedCapabilities)
    {
        if (!DodLayers.Contains(requestedLayer, StringComparer.Ordinal))
        {
            return false;
        }

        if (requestedLayer == "program" && unresolvedConsumedCapabilities.Count > 0)
        {
            return false;
        }

        return DodItems
            .Where(item => item.Layer == requestedLayer || requestedLayer == "program")
            .All(item => completedItemIds.Contains(item.ItemId));
    }

    public static bool IsValidDecisionClassification(string classification)
    {
        return DecisionMatrix.Any(row => string.Equals(row.RequiredEvidence, classification, StringComparison.Ordinal));
    }

    private static RiskRegisterRow Risk(string id, string risk, string mitigation, string acceptance)
    {
        return new RiskRegisterRow(id, risk, mitigation, acceptance);
    }

    private static DodItem Dod(int number, string itemId, string text, string layer)
    {
        return new DodItem(number, itemId, text, layer);
    }

    private static DecisionMatrixRow Decision(string id, string changeType, string requiredEvidence)
    {
        return new DecisionMatrixRow(id, changeType, requiredEvidence);
    }

    private static OpenQuestionRow Question(string id, string question, string owner, string phase1Proof)
    {
        return new OpenQuestionRow(id, question, owner, phase1Proof);
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n",
            Risks.Select(row => $"{row.RiskId}|{row.Risk}|{row.Mitigation}|{row.Acceptance}")
                .Concat(DodItems.Select(row => $"{row.Number}|{row.ItemId}|{row.Layer}|{row.Text}"))
                .Concat(DecisionMatrix.Select(row => $"{row.RowId}|{row.ChangeType}|{row.RequiredEvidence}"))
                .Concat(OpenQuestions.Select(row => $"{row.QuestionId}|{row.Question}|{row.Owner}|{row.Phase1NonBlockingProof}"))
                .Concat(Phase1DefaultDecisions));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }
}

public sealed record RiskRegisterRow(string RiskId, string Risk, string Mitigation, string Acceptance);

public sealed record DodItem(int Number, string ItemId, string Text, string Layer);

public sealed record DecisionMatrixRow(string RowId, string ChangeType, string RequiredEvidence);

public sealed record OpenQuestionRow(string QuestionId, string Question, string Owner, string Phase1NonBlockingProof);
