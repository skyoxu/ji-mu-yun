using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

public sealed class ProjectRouteStateArtifactService
{
    private static readonly IReadOnlyList<string> RouteReadbackStatuses = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback).ToArray();

    private static readonly IReadOnlyList<string> RequirementMapStatuses = ["ready", "needs_review", "blocked", "stale", "unknown"];

    private static readonly IReadOnlyList<string> RequirementStatuses = RouteStatusVocabulary.Values(RouteStatusVocabulary.RequirementCoverage).ToArray();

    private static readonly IReadOnlyList<string> UiClosureStatuses = ["ready", "needs_fix", "succeeded", "blocked", "stale", "unknown"];

    public ProjectRouteStateArtifactReadback Read(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);

        var context = ProjectRouteStateContext.Load(project);
        var summaries = new List<ProjectRouteStateArtifactSummary>
        {
            BuildSummary(context, RouteArtifactKind.GddQuestionForm),
            BuildSummary(context, RouteArtifactKind.SceneRoute),
            BuildSummary(context, RouteArtifactKind.GddDocument),
            BuildSummary(context, RouteArtifactKind.GddRequirements),
            BuildSummary(context, RouteArtifactKind.PrototypeContract),
            BuildSummary(context, RouteArtifactKind.PrototypeSkeleton),
            BuildSummary(context, RouteArtifactKind.UiWiring)
        };

        var issues = BuildBlockingIssues(project, context, summaries);
        var status = issues.Any(issue => issue.Severity is "P0" or "P1") ? "blocked" : "ready";
        return new ProjectRouteStateArtifactReadback(
            status,
            status == "blocked" ? "Route-state artifacts have blocking source, freshness, or admin-review gaps." : "Route-state artifacts are readable for the current phase.",
            summaries,
            issues);
    }

    public ProjectWorkflowRecommendation BuildRecommendation(
        ProjectSnapshot project,
        ProjectRouteStateArtifactReadback artifacts,
        ProjectWorkflowNextAction currentAction)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(artifacts);
        ArgumentNullException.ThrowIfNull(currentAction);

        var now = DateTimeOffset.UtcNow.ToString("O");
        var descriptor = DescriptorRef();
        var recommended = ResolveRecommendedAction(artifacts, currentAction);
        var blockingIssues = artifacts.BlockingIssues;
        var status = blockingIssues.Any(issue => issue.Severity is "P0" or "P1")
            ? "blocked"
            : "ready";
        var allowed = new List<ProjectWorkflowRecommendationAction>();
        var forbidden = new List<ProjectWorkflowRecommendationAction>();

        foreach (var actionId in RouteActionDescriptors.CanonicalActionIds)
        {
            var descriptorHash = descriptor.DescriptorHash;
            var descriptorAction = BuildActionDescriptor(actionId, descriptorHash, project.ProjectId);
            if (RouteActionDescriptors.IsPhase1Action(actionId) &&
                (actionId == recommended || actionId == "inspect_first" || status == "ready"))
            {
                allowed.Add(descriptorAction with { PhaseEligibility = "active" });
                continue;
            }

            var domainCode = RouteActionDescriptors.IsPhase1Action(actionId)
                ? "phase_gate_blocked"
                : "route_contract_not_active";
            forbidden.Add(descriptorAction with
            {
                PhaseEligibility = "blocked",
                DisabledReason = actionId == recommended
                    ? "The action is blocked by current route-state artifact gaps."
                    : "Route contract is not active for the current phase.",
                DisabledDomainCode = domainCode,
                RequiredPhase = RouteActionDescriptors.Get(actionId).RequiredPhase,
                BlockingIssueRefs = blockingIssues.Select(issue => issue.IssueId).ToArray()
            });
        }

        if (allowed.All(action => action.ActionId != recommended))
        {
            var descriptorAction = BuildActionDescriptor(recommended, descriptor.DescriptorHash, project.ProjectId);
            allowed.Insert(0, descriptorAction with
            {
                PhaseEligibility = "active",
                BlockingIssueRefs = blockingIssues.Select(issue => issue.IssueId).ToArray()
            });
        }

        return new ProjectWorkflowRecommendation(
            "project-workflow-recommendation.v1",
            descriptor,
            recommended,
            BuildReason(recommended, artifacts),
            "route_readback",
            ["ready", "blocked", "stale", "needs_fix"],
            status,
            "workflow_recommendation",
            status == "blocked" ? "Resolve blocking route-state artifacts before downstream execution." : "",
            blockingIssues,
            allowed,
            forbidden,
            artifacts.Artifacts.Where(artifact => artifact.Freshness == "stale").Select(artifact => artifact.CanonicalPath).ToArray(),
            now,
            [new ProjectRouteStateEvidenceRef("sidecar", "meta/routes/workflow-recommendation/latest.json", "Structured read model from ProjectWorkflowRouteService.")]);
    }

    public static ProjectWorkflowActionDescriptorRef DescriptorRef()
    {
        return new ProjectWorkflowActionDescriptorRef(
            RouteActionDescriptors.DescriptorId,
            RouteActionDescriptors.DescriptorVersion,
            RouteActionDescriptors.DescriptorHash);
    }

    private static ProjectWorkflowRecommendationAction BuildActionDescriptor(string actionId, string descriptorHash, string projectId)
    {
        var descriptor = RouteActionDescriptors.Get(actionId);
        return new ProjectWorkflowRecommendationAction(
            actionId,
            descriptorHash,
            descriptor.ExposureClass,
            descriptor.DefaultPhaseEligibility,
            RouteActionDescriptors.ResolveTemplate(descriptor.ApiRouteTemplate, projectId),
            descriptor.BrowserActionId,
            descriptor.DisplayLabelKey,
            descriptor.OperationScope,
            RouteActionDescriptors.ResolveTemplate(descriptor.ReadbackUrlTemplate, projectId),
            []);
    }

    private static string ResolveRecommendedAction(ProjectRouteStateArtifactReadback artifacts, ProjectWorkflowNextAction currentAction)
    {
        var byRoute = artifacts.Artifacts.ToDictionary(artifact => artifact.Route, StringComparer.OrdinalIgnoreCase);
        if (MissingOrBlocked(byRoute, "gdd-question-form"))
        {
            return HasArtifact(byRoute, "gdd-document-generation") ? "import_gdd_form" : "create_gdd";
        }

        if (MissingOrBlocked(byRoute, "scene-route-confirmation"))
        {
            return "confirm_scene_route";
        }

        if (MissingOrBlocked(byRoute, "gdd-document-generation"))
        {
            return "generate_gdd_document";
        }

        if (MissingOrBlocked(byRoute, "gdd-requirements"))
        {
            return artifacts.BlockingIssues.Any(issue => issue.DomainCode is "requirement_p0_gap" or "admin_review_blocked")
                ? "inspect_first"
                : "generate_requirement_map";
        }

        if (MissingOrBlocked(byRoute, "prototype-contract"))
        {
            return ArtifactFreshness(byRoute, "prototype-contract") == "stale" ? "refresh_contract" : "freeze_contract";
        }

        return currentAction.ActionId switch
        {
            "create-prototype" => "create_prototype",
            "create-iteration-plan" or "create-next-iteration-plan" => "create_iteration_plan",
            "execute-iteration-goal" => "execute_next_goal",
            "needs-fix-route" or "create-repair-plan" or "execute-repair-step" => "run_needs_fix",
            "asset-inventory" or "download-project" => "preview_package",
            _ => "inspect_first"
        };
    }

    private static string BuildReason(string actionId, ProjectRouteStateArtifactReadback artifacts)
    {
        return actionId switch
        {
            "create_gdd" => "GDD inputs are missing; start the GDD question-form workflow.",
            "import_gdd_form" => "A legacy GDD document exists without the canonical question-form sidecar; import or confirm the GDD form before continuing.",
            "confirm_scene_route" => "Scene route confirmation is missing, stale, or blocked.",
            "generate_gdd_document" => "GDD document route state is missing, stale, or not aligned with the confirmed scene route.",
            "generate_requirement_map" => "Generate a GDD requirement map before contract freeze.",
            "inspect_first" => artifacts.BlockingIssues.Count == 0 ? "Inspect the workflow route-state readback before continuing." : "Inspect blocking requirement, admin-review, or freshness issues before continuing.",
            "freeze_contract" => "Freeze the prototype contract from current GDD, scene route, and requirement-map sources.",
            "refresh_contract" => "Refresh the stale prototype contract before downstream execution.",
            _ => "Continue with the current workflow recommendation."
        };
    }

    private static bool MissingOrBlocked(IReadOnlyDictionary<string, ProjectRouteStateArtifactSummary> byRoute, string route)
    {
        return !byRoute.TryGetValue(route, out var artifact) ||
               artifact.Status is "missing" or "blocked" or "failed" or "needs_review" ||
               artifact.Freshness is "stale" or "unknown";
    }

    private static bool HasArtifact(IReadOnlyDictionary<string, ProjectRouteStateArtifactSummary> byRoute, string route)
    {
        return byRoute.TryGetValue(route, out var artifact) && artifact.Status != "missing";
    }

    private static string ArtifactFreshness(IReadOnlyDictionary<string, ProjectRouteStateArtifactSummary> byRoute, string route)
    {
        return byRoute.TryGetValue(route, out var artifact) ? artifact.Freshness : "unknown";
    }

    private static ProjectRouteStateArtifactSummary BuildSummary(ProjectRouteStateContext context, RouteArtifactKind kind)
    {
        var spec = ArtifactSpec.For(kind);
        var canonical = context.Read(spec.CanonicalPath);
        var mirror = spec.MirrorPath is null ? null : context.Read(spec.MirrorPath);
        var status = canonical.Status;
        var freshness = canonical.Freshness;
        var issues = canonical.Issues.ToList();
        if (spec.Kind == RouteArtifactKind.GddDocument &&
            canonical.Status == "missing" &&
            mirror is not null &&
            mirror.Status != "missing")
        {
            status = mirror.Status;
            freshness = "unknown";
            issues.Add($"{spec.Route}:sidecar_missing_for_existing_gdd");
        }

        if (mirror is not null && mirror.Status != "missing" && canonical.Status != "missing")
        {
            var canonicalHash = canonical.Hash;
            var mirrorHash = mirror.Hash;
            if (!string.Equals(canonicalHash, mirrorHash, StringComparison.Ordinal))
            {
                freshness = "stale";
                issues.Add($"{spec.Route}:mirror_hash_mismatch");
            }
        }

        return new ProjectRouteStateArtifactSummary(
            spec.Route,
            spec.CanonicalPath,
            spec.MirrorPath,
            spec.Authority,
            status,
            spec.StatusDimension,
            spec.AllowedStatuses,
            freshness,
            issues,
            spec.Kind == RouteArtifactKind.GddRequirements && canonical.Json.HasValue ? ReadRequirementRows(canonical.Json.Value) : null,
            canonical.Json.HasValue ? ReadString(canonical.Json.Value, "source_gdd_hash") : null,
            canonical.Json.HasValue ? ReadString(canonical.Json.Value, "source_scene_route_hash") : null,
            canonical.Json.HasValue ? ReadString(canonical.Json.Value, "source_requirement_map_hash") : null,
            canonical.Json.HasValue ? ReadString(canonical.Json.Value, "source_godot_ui_contract_hash") : null,
            canonical.Json.HasValue ? ReadString(canonical.Json.Value, "source_ui_style_contract_hash") : null,
            canonical.Json.HasValue ? ReadString(canonical.Json.Value, "ui_style_snapshot_hash") : null);
    }

    private static IReadOnlyList<GameDesignRequirementRow> ReadRequirementRows(JsonElement root)
    {
        return ReadArray(root, "requirements")
            .Select(requirement => new GameDesignRequirementRow(
                ReadString(requirement, "requirement_id"),
                ReadString(requirement, "source_section"),
                ReadString(requirement, "normalized_source_summary"),
                ReadString(requirement, "source_language"),
                ReadString(requirement, "source_excerpt_policy"),
                ReadString(requirement, "normalized_requirement"),
                ReadString(requirement, "priority"),
                ReadString(requirement, "kind"),
                ReadStringArray(requirement, "mapped_scene_ids"),
                ReadStringArray(requirement, "mapped_required_module_ids"),
                ReadStringArray(requirement, "mapped_iteration_goal_ids"),
                ReadString(requirement, "status"),
                ReadString(requirement, "defer_reason"),
                ReadString(requirement, "conflict_reason"),
                ReadString(requirement, "decision_by"),
                ReadString(requirement, "decision_role"),
                ReadString(requirement, "decision_utc"),
                ReadString(requirement, "decision_reason"),
                ReadStringArray(requirement, "affected_requirement_ids"),
                ReadStringArray(requirement, "acceptance_markers")))
            .ToArray();
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> BuildBlockingIssues(
        ProjectSnapshot project,
        ProjectRouteStateContext context,
        IReadOnlyList<ProjectRouteStateArtifactSummary> summaries)
    {
        var issues = new List<ProjectWorkflowBlockingIssue>();
        foreach (var summary in summaries)
        {
            foreach (var issueId in summary.BlockingIssueIds)
            {
                issues.Add(new ProjectWorkflowBlockingIssue(
                    issueId,
                    DomainCode(issueId),
                    Severity(issueId),
                    $"Route-state artifact issue: {issueId}.",
                    [new ProjectRouteStateEvidenceRef("sidecar", summary.CanonicalPath)]));
            }
        }

        var requirementMap = context.Read("meta/routes/gdd-requirements/latest.json");
        if (requirementMap.Json.HasValue)
        {
            issues.AddRange(ValidateRequirementMap(project, requirementMap.Json.Value));
        }

        var uiWiring = context.Read("meta/routes/ui-wiring/latest.json");
        if (uiWiring.Json.HasValue)
        {
            issues.AddRange(ValidateUiWiring(uiWiring.Json.Value));
        }

        return issues
            .GroupBy(issue => issue.IssueId, StringComparer.Ordinal)
            .Select(group => group.First())
            .ToArray();
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> ValidateRequirementMap(ProjectSnapshot project, JsonElement root)
    {
        var issues = new List<ProjectWorkflowBlockingIssue>();
        foreach (var requirement in ReadArray(root, "requirements"))
        {
            var id = ReadString(requirement, "requirement_id");
            var priority = ReadString(requirement, "priority");
            var status = ReadString(requirement, "status");
            if (!RequirementStatuses.Contains(status, StringComparer.Ordinal))
            {
                issues.Add(Issue($"gdd-requirements:{id}:invalid_status", "route_state_invalid", "P1", "meta/routes/gdd-requirements/latest.json"));
                continue;
            }

            if (priority is "P0" or "P1" && status is "missing_scene" or "missing_module" or "needs_review" or "conflict")
            {
                issues.Add(Issue($"gdd-requirements:{id}:requirement_p0_gap", "requirement_p0_gap", priority, "meta/routes/gdd-requirements/latest.json"));
            }

            if (status is "explicitly_deferred" or "conflict")
            {
                var role = ReadString(requirement, "decision_role");
                var hasDecision = !string.IsNullOrWhiteSpace(ReadString(requirement, "decision_by")) &&
                                  !string.IsNullOrWhiteSpace(ReadString(requirement, "decision_utc")) &&
                                  !string.IsNullOrWhiteSpace(ReadString(requirement, "decision_reason")) &&
                                  ReadArray(requirement, "affected_requirement_ids").Any();
                if (!hasDecision)
                {
                    issues.Add(Issue($"gdd-requirements:{id}:decision_metadata_missing", "admin_review_blocked", priority is "P0" or "P1" ? priority : "P2", "meta/routes/gdd-requirements/latest.json"));
                }

                if (priority is "P0" or "P1" && status == "explicitly_deferred" && role != "admin")
                {
                    issues.Add(Issue($"gdd-requirements:{id}:admin_decision_required", "admin_review_blocked", priority, "meta/routes/gdd-requirements/latest.json"));
                }
            }
        }

        return issues;
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> ValidateUiWiring(JsonElement root)
    {
        var issues = new List<ProjectWorkflowBlockingIssue>();
        foreach (var surface in ReadArray(root, "ui_surface_matrix"))
        {
            var feature = ReadString(surface, "feature");
            var status = ReadString(surface, "status");
            var priority = ReadString(surface, "priority");
            var capabilityDomainIds = ReadStringArray(surface, "capability_domain_ids");
            foreach (var domainId in capabilityDomainIds)
            {
                if (!GodotUiCapabilityContract.IsKnownCapabilityDomain(domainId))
                {
                    issues.Add(Issue($"ui-wiring:{feature}:godot_ui_capability_missing", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
                }
            }

            if (ContainsForbiddenTechnologyTerm(surface))
            {
                issues.Add(Issue($"ui-wiring:{feature}:technology_stack_leakage", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }

            if (status == "no_ui_needed")
            {
                if (priority is "P0" or "P1" && !HasReviewedExemption(surface))
                {
                    issues.Add(Issue($"ui-wiring:{feature}:godot_ui_no_ui_needed_review_missing", "admin_review_blocked", priority, "meta/routes/ui-wiring/latest.json"));
                }
                continue;
            }

            var missingCoreFields =
                string.IsNullOrWhiteSpace(ReadString(surface, "godot_scene_path")) &&
                string.IsNullOrWhiteSpace(ReadString(surface, "godot_node_path"));
            missingCoreFields |= string.IsNullOrWhiteSpace(ReadString(surface, "godot_surface_type"));
            missingCoreFields |= string.IsNullOrWhiteSpace(ReadString(surface, "layout_strategy"));
            missingCoreFields |= !ReadArray(surface, "input_paths").Any();
            missingCoreFields |= !ReadArray(surface, "feedback_states").Any();
            missingCoreFields |= string.IsNullOrWhiteSpace(ReadString(surface, "camera_layer_boundary"));
            missingCoreFields |= string.IsNullOrWhiteSpace(ReadString(surface, "viewport_mode"));
            missingCoreFields |= string.IsNullOrWhiteSpace(ReadString(surface, "ui_update_ownership_mode"));
            missingCoreFields |= string.IsNullOrWhiteSpace(ReadString(surface, "state_boundary"));
            if (missingCoreFields)
            {
                issues.Add(Issue($"ui-wiring:{feature}:godot_ui_surface_incomplete", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }

            if (!GodotEngineSemantics.ViewportModes.Any(mode => string.Equals(mode.ModeId, ReadString(surface, "viewport_mode"), StringComparison.Ordinal)))
            {
                issues.Add(Issue($"ui-wiring:{feature}:godot_ui_semantic_mode_missing", "diagnostic_blocked", priority is "P0" or "P1" ? priority : "P2", "meta/routes/ui-wiring/latest.json"));
            }

            var updateMode = ReadString(surface, "ui_update_ownership_mode");
            if (!string.IsNullOrWhiteSpace(updateMode) && !GodotUiCapabilityContract.IsKnownUpdateOwnershipMode(updateMode))
            {
                issues.Add(Issue($"ui-wiring:{feature}:ui_update_ownership_missing", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }

            ValidateProfile(surface, feature, "material_profile", GodotUiCapabilityContract.IsKnownMaterialProfile, "material_profile_missing", issues);
            ValidateProfile(surface, feature, "rendering_profile", GodotUiCapabilityContract.IsKnownRenderingProfile, "rendering_profile_missing", issues);
            ValidateProfile(surface, feature, "animation_profile", GodotUiCapabilityContract.IsKnownAnimationProfile, "animation_state_profile_missing", issues);

            if (ReadBoolean(surface, "third_person_camera_required") &&
                string.IsNullOrWhiteSpace(ReadString(surface, "camera_controller_profile")))
            {
                issues.Add(Issue($"ui-wiring:{feature}:third_person_camera_profile_missing", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }
        }

        issues.AddRange(ValidateStyleGapRows(root));
        issues.AddRange(ValidateStyleRepairPromptInputs(root));
        issues.AddRange(ValidateFullTargetClosureLedger(root));
        return issues;
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> ValidateStyleGapRows(JsonElement root)
    {
        var issues = new List<ProjectWorkflowBlockingIssue>();
        foreach (var gap in ReadArray(root, "style_gap_rows"))
        {
            var gapId = ReadString(gap, "gap_id");
            var family = ReadString(gap, "style_drift_family");
            var severity = ReadString(gap, "severity");
            var status = ReadString(gap, "status");
            if (string.IsNullOrWhiteSpace(gapId))
            {
                gapId = "unknown";
            }

            foreach (var field in GodotUiStyleClosureContract.GapRowRequiredFields)
            {
                if (!HasRequiredValue(gap, field))
                {
                    issues.Add(Issue($"ui-wiring:style-gap:{gapId}:missing_{field}", "diagnostic_blocked", severity is "P0" or "P1" ? severity : "P2", "meta/routes/ui-wiring/latest.json"));
                }
            }

            if (!GodotUiStyleClosureContract.IsKnownGapFamily(family))
            {
                issues.Add(Issue($"ui-wiring:style-gap:{gapId}:style_gap_family_unknown", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }

            if (GodotUiStyleClosureContract.IsFinalReadinessBlockingSeverity(severity) &&
                status is not "resolved" and not "reviewed_not_applicable")
            {
                issues.Add(Issue($"ui-wiring:style-gap:{gapId}:unresolved_final_readiness_blocker", "diagnostic_blocked", severity, "meta/routes/ui-wiring/latest.json"));
            }
        }

        return issues;
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> ValidateStyleRepairPromptInputs(JsonElement root)
    {
        if (!root.TryGetProperty("style_repair_prompt_inputs", out var inputs) ||
            inputs.ValueKind != JsonValueKind.Object)
        {
            return [];
        }

        var issues = new List<ProjectWorkflowBlockingIssue>();
        foreach (var field in GodotUiStyleClosureContract.RepairPromptRequiredInputs)
        {
            if (!HasRequiredValue(inputs, field))
            {
                issues.Add(Issue($"ui-wiring:style-repair-prompt:missing_{field}", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }
        }

        return issues;
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> ValidateFullTargetClosureLedger(JsonElement root)
    {
        var issues = new List<ProjectWorkflowBlockingIssue>();
        foreach (var row in ReadArray(root, "full_target_closure_ledger"))
        {
            var capabilityId = ReadString(row, "capability_id");
            var status = ReadString(row, "status");
            if (GodotUiStyleClosureContract.CapabilityIds.Contains(capabilityId, StringComparer.Ordinal) &&
                !GodotUiStyleClosureContract.IsFullTargetClosureStatus(status))
            {
                issues.Add(Issue($"ui-wiring:full-target:{capabilityId}:invalid_final_readiness_status", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }

            if (GodotUiStyleClosureContract.InterimOnlyCoverageStatuses.Contains(status, StringComparer.Ordinal))
            {
                issues.Add(Issue($"ui-wiring:full-target:{capabilityId}:interim_status_not_final", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
            }
        }

        return issues;
    }

    private static bool HasRequiredValue(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out var value))
        {
            return false;
        }

        return value.ValueKind switch
        {
            JsonValueKind.String => !string.IsNullOrWhiteSpace(value.GetString()),
            JsonValueKind.Array => value.GetArrayLength() > 0,
            JsonValueKind.Object => value.EnumerateObject().Any(),
            JsonValueKind.True => true,
            JsonValueKind.False => true,
            JsonValueKind.Number => true,
            _ => false
        };
    }

    private static void ValidateProfile(
        JsonElement surface,
        string feature,
        string propertyName,
        Func<string, bool> isKnown,
        string diagnosticCode,
        List<ProjectWorkflowBlockingIssue> issues)
    {
        if (!surface.TryGetProperty(propertyName, out var _))
        {
            return;
        }

        var value = ReadString(surface, propertyName);
        if (string.IsNullOrWhiteSpace(value) || !isKnown(value))
        {
            issues.Add(Issue($"ui-wiring:{feature}:{diagnosticCode}", "diagnostic_blocked", "P1", "meta/routes/ui-wiring/latest.json"));
        }
    }

    private static bool HasReviewedExemption(JsonElement surface)
    {
        return !string.IsNullOrWhiteSpace(ReadString(surface, "decision_by")) &&
               !string.IsNullOrWhiteSpace(ReadString(surface, "decision_role")) &&
               !string.IsNullOrWhiteSpace(ReadString(surface, "decision_utc")) &&
               !string.IsNullOrWhiteSpace(ReadString(surface, "decision_reason")) &&
               ReadArray(surface, "affected_requirement_ids").Any() &&
               ReadArray(surface, "evidence_refs").Any();
    }

    private static bool ContainsForbiddenTechnologyTerm(JsonElement surface)
    {
        var text = surface.GetRawText();
        return GodotUiCapabilityContract.ForbiddenTechnologyTerms.Any(term =>
            text.Contains(term, StringComparison.OrdinalIgnoreCase));
    }

    private static bool ReadBoolean(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.True;
    }

    private static ProjectWorkflowBlockingIssue Issue(string issueId, string domainCode, string severity, string path)
    {
        return new ProjectWorkflowBlockingIssue(
            issueId,
            domainCode,
            severity,
            $"Route-state artifact issue: {issueId}.",
            [new ProjectRouteStateEvidenceRef("sidecar", path)]);
    }

    private static string DomainCode(string issueId)
    {
        if (issueId.Contains("source_boundary", StringComparison.Ordinal)) return "source_stale";
        if (issueId.Contains("admin", StringComparison.Ordinal) || issueId.Contains("decision", StringComparison.Ordinal)) return "admin_review_blocked";
        if (issueId.Contains("status", StringComparison.Ordinal)) return "route_state_invalid";
        if (issueId.Contains("freshness", StringComparison.Ordinal) || issueId.Contains("stale", StringComparison.Ordinal)) return "source_stale";
        if (issueId.Contains("ui", StringComparison.Ordinal)) return "diagnostic_blocked";
        return "phase_gate_blocked";
    }

    private static string Severity(string issueId)
    {
        if (issueId.Contains("prototype-contract", StringComparison.Ordinal) ||
            issueId.Contains("source_boundary", StringComparison.Ordinal))
        {
            return "P0";
        }

        if (issueId.Contains("requirement_p0_gap", StringComparison.Ordinal))
        {
            return "P1";
        }

        return "P2";
    }

    private static IEnumerable<JsonElement> ReadArray(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out var value) || value.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        return value.EnumerateArray();
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? ""
            : "";
    }

    private static IReadOnlyList<string> ReadStringArray(JsonElement root, string propertyName)
    {
        return ReadArray(root, propertyName)
            .Where(item => item.ValueKind == JsonValueKind.String)
            .Select(item => item.GetString() ?? "")
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToArray();
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private enum RouteArtifactKind
    {
        GddQuestionForm,
        SceneRoute,
        GddDocument,
        GddRequirements,
        PrototypeContract,
        PrototypeSkeleton,
        UiWiring
    }

    private sealed record ArtifactSpec(
        RouteArtifactKind Kind,
        string Route,
        string CanonicalPath,
        string? MirrorPath,
        string Authority,
        string StatusDimension,
        IReadOnlyList<string> AllowedStatuses)
    {
        public static ArtifactSpec For(RouteArtifactKind kind)
        {
            return kind switch
            {
                RouteArtifactKind.GddQuestionForm => new(kind, "gdd-question-form", "meta/routes/gdd-question-form/latest.json", "meta/routes/gdd-question-form/legacy-import/latest.json", "readback", "route_readback", RouteReadbackStatuses),
                RouteArtifactKind.SceneRoute => new(kind, "scene-route-confirmation", "meta/routes/scene-route/latest.json", "meta/routes/gdd-scene-route/latest.json", "authority", RouteStatusVocabulary.SceneRouteConfirmation, RouteStatusVocabulary.Values(RouteStatusVocabulary.SceneRouteConfirmation).ToArray()),
                RouteArtifactKind.GddDocument => new(kind, "gdd-document-generation", "meta/routes/gdd-document/latest.json", "docs/gdd/GDD.md", "authority", "route_readback", RouteReadbackStatuses),
                RouteArtifactKind.GddRequirements => new(kind, "gdd-requirements", "meta/routes/gdd-requirements/latest.json", null, "authority", "route_readback", RequirementMapStatuses),
                RouteArtifactKind.PrototypeContract => new(kind, "prototype-contract", "routes/prototype-contract/latest.json", "meta/routes/prototype-contract/latest.json", "authority", "route_readback", ["fresh", "stale", "unknown", "ready", "blocked"]),
                RouteArtifactKind.PrototypeSkeleton => new(kind, "prototype-skeleton", "meta/routes/prototype-skeleton/latest.json", "meta/routes/prototype/latest.json", "readback", "route_readback", RouteReadbackStatuses),
                RouteArtifactKind.UiWiring => new(kind, "ui-wiring", "meta/routes/ui-wiring/latest.json", "meta/routes/ui-closure/latest.json", "authority", "route_readback", UiClosureStatuses),
                _ => throw new ArgumentOutOfRangeException(nameof(kind), kind, null)
            };
        }
    }

    private sealed record ProjectRouteStateContext(ProjectSnapshot Project)
    {
        public static ProjectRouteStateContext Load(ProjectSnapshot project)
        {
            return new ProjectRouteStateContext(project);
        }

        public ArtifactRead Read(string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath))
            {
                return ArtifactRead.Missing();
            }

            var fullPath = Resolve(relativePath);
            if (fullPath is null || !File.Exists(fullPath))
            {
                return ArtifactRead.Missing();
            }

            try
            {
                var text = File.ReadAllText(fullPath, Encoding.UTF8);
                var hash = Sha256(NormalizeText(text));
                if (!relativePath.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
                {
                    return new ArtifactRead("ready", "fresh", hash, null, []);
                }

                using var document = JsonDocument.Parse(text);
                var root = document.RootElement.Clone();
                var status = ReadArtifactStatus(root);
                var issues = ValidateCommon(relativePath, root).ToList();
                return new ArtifactRead(status, ReadFreshness(root), hash, root, issues);
            }
            catch (JsonException)
            {
                return new ArtifactRead("failed", "unknown", "", null, [$"{relativePath}:invalid_json"]);
            }
            catch (IOException)
            {
                return new ArtifactRead("failed", "unknown", "", null, [$"{relativePath}:read_failed"]);
            }
            catch (UnauthorizedAccessException)
            {
                return new ArtifactRead("failed", "unknown", "", null, [$"{relativePath}:read_forbidden"]);
            }
        }

        private static string ReadArtifactStatus(JsonElement root)
        {
            var status = ReadString(root, "status");
            if (string.IsNullOrWhiteSpace(status))
            {
                status = ReadString(root, "freshness", "status");
            }

            return string.IsNullOrWhiteSpace(status) ? "unknown" : status;
        }

        private static string ReadFreshness(JsonElement root)
        {
            var freshness = ReadString(root, "freshness", "status");
            if (!string.IsNullOrWhiteSpace(freshness))
            {
                return freshness;
            }

            var status = ReadString(root, "status");
            return status is "stale" ? "stale" : "fresh";
        }

        private static IEnumerable<string> ValidateCommon(string relativePath, JsonElement root)
        {
            var statusDimension = ReadString(root, "status_dimension");
            var status = ReadArtifactStatus(root);
            if (!string.IsNullOrWhiteSpace(statusDimension))
            {
                var allowed = ReadArray(root, "status_allowed_values")
                    .Where(item => item.ValueKind == JsonValueKind.String)
                    .Select(item => item.GetString() ?? "")
                    .ToArray();
                if (!RouteStatusVocabulary.IsKnownDimension(statusDimension))
                {
                    yield return $"{relativePath}:status_dimension_unknown";
                }

                if (allowed.Length == 0)
                {
                    yield return $"{relativePath}:status_allowed_values_missing";
                }

                if (allowed.Length > 0 && !RouteStatusVocabulary.IsSubset(statusDimension, allowed))
                {
                    yield return $"{relativePath}:status_allowed_values_outside_dimension";
                }

                if (allowed.Length > 0 && !allowed.Contains(status, StringComparer.Ordinal))
                {
                    yield return $"{relativePath}:status_outside_declared_subset";
                }

                if (!RouteStatusVocabulary.Contains(statusDimension, status))
                {
                    yield return $"{relativePath}:status_outside_dimension";
                }
            }

            if (root.TryGetProperty("source_boundary_enforced", out var enforced) &&
                enforced.ValueKind == JsonValueKind.False &&
                !root.TryGetProperty("source_boundary_not_applicable", out _))
            {
                yield return $"{relativePath}:source_boundary_not_applicable_missing";
            }

            if (root.TryGetProperty("source_boundary_enforced", out enforced) &&
                enforced.ValueKind == JsonValueKind.True)
            {
                if (!root.TryGetProperty("source_boundary", out var boundary) ||
                    !boundary.TryGetProperty("authority_sources", out _) ||
                    !boundary.TryGetProperty("forbidden_source_patterns", out _))
                {
                    yield return $"{relativePath}:source_boundary_incomplete";
                }

                if (boundary.ValueKind == JsonValueKind.Object &&
                    ReadString(boundary, "recovery_source_order_ref") is not "" and not "hosted-route-recovery-order.v1")
                {
                    yield return $"{relativePath}:recovery_source_order_ref_invalid";
                }
            }

            foreach (var evidenceRef in ReadEvidenceRefs(root))
            {
                var kind = ReadString(evidenceRef, "kind");
                if (string.IsNullOrWhiteSpace(kind) || !RouteEvidenceRefKinds.Contains(kind))
                {
                    yield return $"{relativePath}:evidence_ref_kind_invalid";
                }
            }
        }

        private static IEnumerable<JsonElement> ReadEvidenceRefs(JsonElement root)
        {
            foreach (var item in ReadArray(root, "evidence_refs"))
            {
                yield return item;
            }

            foreach (var item in ReadArray(root, "evidenceRefs"))
            {
                yield return item;
            }
        }

        private string? Resolve(string relativePath)
        {
            var normalized = relativePath.Replace('\\', Path.DirectorySeparatorChar).Replace('/', Path.DirectorySeparatorChar);
            if (Path.IsPathRooted(normalized) ||
                normalized.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).Any(part => part == ".."))
            {
                return null;
            }

            var primaryRoot = relativePath.StartsWith("routes/", StringComparison.OrdinalIgnoreCase)
                ? Project.RepoPath
                : Project.RepoPath;
            return SafeCombine(primaryRoot, normalized) ?? SafeCombine(Project.MetaPath, normalized);
        }

        private static string? SafeCombine(string root, string relativePath)
        {
            if (string.IsNullOrWhiteSpace(root))
            {
                return null;
            }

            var rootFullPath = Path.GetFullPath(root);
            var fullPath = Path.GetFullPath(Path.Combine(rootFullPath, relativePath));
            var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
            return fullPath.StartsWith(rootFullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar, comparison)
                ? fullPath
                : null;
        }

        private static string NormalizeText(string text)
        {
            return text.Replace("\r\n", "\n").Trim();
        }

        private static string ReadString(JsonElement root, string propertyName)
        {
            return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
                ? value.GetString()?.Trim() ?? ""
                : "";
        }

        private static string ReadString(JsonElement root, string propertyName, string nestedPropertyName)
        {
            return root.TryGetProperty(propertyName, out var nested) && nested.ValueKind == JsonValueKind.Object
                ? ReadString(nested, nestedPropertyName)
                : "";
        }

    }

    private sealed record ArtifactRead(
        string Status,
        string Freshness,
        string Hash,
        JsonElement? Json,
        IReadOnlyList<string> Issues)
    {
        public static ArtifactRead Missing()
        {
            return new ArtifactRead("missing", "unknown", "", null, []);
        }
    }
}
