namespace PhaseA.Platform.Runs;

public sealed record ProjectBusinessChainStatus(string Status, IReadOnlyList<string> BlockingReasons,
    string Scope = "current_stored_business_chain", bool RoutesExecuted = false)
{
    // ADR-0036/0038: consume the existing validated readback, never run a second
    // acceptance workflow or trust historical green status after activation.
    public static ProjectBusinessChainStatus Evaluate(ProjectRouteStateArtifactReadback readback,
        IReadOnlyList<ProjectWorkflowRouteStep> steps, bool restoreValidationRequired)
    {
        var reasons = new List<string>();
        if (readback.Status != "ready" || readback.BlockingIssues.Count != 0)
            reasons.Add("workflow:route_artifacts_blocked");
        foreach (var route in new[] { "gdd-question-form", "scene-route-confirmation", "gdd-document-generation",
            "gdd-requirements", "prototype-contract", "prototype-skeleton", "ui-wiring" })
        {
            var matches = readback.Artifacts.Where(item => item.Route == route).ToArray();
            if (matches.Length != 1) reasons.Add($"route:{route}:missing_or_duplicate");
            else if (matches[0].Freshness != "fresh" || matches[0].BlockingIssueIds.Count != 0 ||
                     matches[0].Status is not ("ready" or "confirmed" or "succeeded" or "fresh"))
                reasons.Add($"route:{route}:not_current_and_complete");
        }
        var ui = readback.Artifacts.FirstOrDefault(item => item.Route == "ui-wiring");
        if (ui is not null && (ui.Status != "succeeded" || new[] { ui.SourceContractHash, ui.SourceRequirementMapHash,
            ui.SourceGodotUiContractHash, ui.SourceUiStyleContractHash, ui.UiStyleSnapshotHash,
            ui.SourceIterationSessionHash, ui.SourceValidationInputHash }.Any(hash => hash is null ||
                hash.Length != 64 || hash.Any(ch => ch is not (>= '0' and <= '9' or >= 'a' and <= 'f')))))
            reasons.Add("ui:machine_evidence_missing");
        foreach (var id in new[] { "iteration-plan", "module-execution", "prototype-acceptance", "preview-package" })
        {
            var matches = steps.Where(step => step.Id == id).ToArray();
            if (matches.Length != 1 || matches[0].Status != "done" || string.IsNullOrWhiteSpace(matches[0].Evidence))
                reasons.Add($"execution:{id}:not_complete");
        }
        if (steps.Any(step => step.Id == "needs-fix-or-repair" && step.Status is "fix" or "blocked" or "continue"))
            reasons.Add("execution:repair_not_closed");
        if (restoreValidationRequired) reasons.Add("workspace:restore_revalidation_required");
        return new(reasons.Count == 0 ? "passed" : "blocked", reasons.Distinct().OrderBy(value => value).ToArray());
    }
}
