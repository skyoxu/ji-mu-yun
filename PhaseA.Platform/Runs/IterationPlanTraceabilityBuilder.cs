using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

internal static class IterationPlanTraceabilityBuilder
{
    public static IterationPlanTraceabilityBuildResult Build(
        GameDesignRequirementMapResult requirementMap,
        IReadOnlyList<PrototypeIterationPlanGoalResult> goals,
        IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> requiredModules,
        PrototypeIterationPlanSourceHashes sourceHashes,
        IReadOnlyDictionary<string, string>? approvedRequirementDecisions = null,
        PrototypeIterationStyleAuthority? styleAuthority = null,
        PrototypeIterationStyleApplicability? styleApplicability = null,
        IReadOnlySet<string>? verifiedSkeletonRequirementIds = null)
    {
        ArgumentNullException.ThrowIfNull(requirementMap);
        ArgumentNullException.ThrowIfNull(goals);
        ArgumentNullException.ThrowIfNull(requiredModules);
        ArgumentNullException.ThrowIfNull(sourceHashes);
        approvedRequirementDecisions ??= new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        verifiedSkeletonRequirementIds ??= new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        var blockers = new List<PrototypeIterationPlanBlockerResult>();
        var requirementRows = new Dictionary<string, GameDesignRequirementRow>(StringComparer.OrdinalIgnoreCase);
        foreach (var row in requirementMap.Requirements)
        {
            var requirementId = NormalizeRequirementId(row.RequirementId);
            if (requirementId.Length == 0)
            {
                AddBlocker(blockers, "requirement_id_empty", "P0", "Requirement Map contains an empty requirement ID.", [], requirementMap.EvidenceRefs.Select(item => item.Path));
                continue;
            }

            if (!requirementRows.TryAdd(requirementId, row with { RequirementId = requirementId }))
            {
                AddBlocker(blockers, "requirement_id_duplicate", "P0", $"Requirement Map contains duplicate requirement ID {requirementId}.", [requirementId], requirementMap.EvidenceRefs.Select(item => item.Path));
            }
        }

        foreach (var issue in requirementMap.BlockingIssues)
        {
            var issueSegments = issue.IssueId.Split(':', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if (approvedRequirementDecisions.Keys.Any(requirementId => issueSegments.Contains(requirementId, StringComparer.OrdinalIgnoreCase)))
            {
                continue;
            }
            AddBlocker(blockers, issue.DomainCode, issue.Severity, issue.Summary, [], issue.EvidenceRefs.Select(item => item.Path));
        }

        var reviewedRequirementRows = requirementRows.Values
            .Where(IsP0P1)
            .Where(row => IsReviewedBlocker(row, approvedRequirementDecisions, out _))
            .ToArray();
        var reviewedRequirementIds = reviewedRequirementRows.Select(row => row.RequirementId).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var activeRequirementRows = requirementRows.Values.Where(row => !reviewedRequirementIds.Contains(row.RequirementId)).ToArray();

        foreach (var row in activeRequirementRows.Where(IsP0P1))
        {
            if (RequiresDynamicUiOwnership(row) && !HasCompleteUiOwnership(row.GodotUiUpdateOwnership))
            {
                AddBlocker(blockers, "ui_update_ownership_missing", row.Priority, "Dynamic UI ownership evidence is incomplete.", [row.RequirementId], ["meta/routes/gdd-requirements/latest.json"]);
            }

            if (RequiresThirdPersonCamera(row) && !HasCompleteThirdPersonCamera(row.GodotThirdPersonCameraProfile))
            {
                AddBlocker(blockers, "third_person_camera_profile_missing", row.Priority, "Third-person camera profile evidence is incomplete.", [row.RequirementId], ["meta/routes/gdd-requirements/latest.json"]);
            }
        }

        var nextSyntheticGoalIndex = goals.Count == 0 ? 1 : goals.Max(goal => goal.GoalIndex) + 1;
        var syntheticGoals = activeRequirementRows
            .Where(IsP0P1)
            .Where(row => row.MappedIterationGoalIds.Count == 0 && row.MappedRequiredModuleIds.Count > 0)
            .Where(row => RequiresDynamicUiOwnership(row) || RequiresThirdPersonCamera(row) || RequiresInteractionRegion(row))
            .OrderBy(row => row.RequirementId, StringComparer.Ordinal)
            .Select(row => new { Row = row, ModuleId = ResolveExecutableMappedModuleId(row, requiredModules) })
            .Where(candidate => candidate.ModuleId.Length > 0)
            .Select(candidate => new PrototypeIterationPlanGoalResult(
                nextSyntheticGoalIndex++,
                $"Implement {candidate.ModuleId}",
                $"Implement the requirement-mapped module {candidate.ModuleId} with its capability and validation contract.",
                string.Join("; ", candidate.Row.AcceptanceMarkers),
                "pending",
                [candidate.Row.RequirementId]))
            .ToArray();
        if (syntheticGoals.Length > 0)
        {
            goals = goals.Concat(syntheticGoals).ToArray();
        }

        var reviewedGoalIndexes = reviewedRequirementRows.SelectMany(row => ResolveMappedGoals(row, goals)).Select(goal => goal.GoalIndex).ToHashSet();
        var activeGoalIndexes = activeRequirementRows.SelectMany(row => ResolveMappedGoals(row, goals)).Select(goal => goal.GoalIndex).ToHashSet();
        goals = goals.Where(goal =>
            !reviewedGoalIndexes.Contains(goal.GoalIndex) ||
            activeGoalIndexes.Contains(goal.GoalIndex) ||
            (goal.RequirementIds ?? []).Any(requirementId => !reviewedRequirementIds.Contains(requirementId))).ToArray();

        var reviewedModuleIds = reviewedRequirementRows.SelectMany(row => row.MappedRequiredModuleIds).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var activeModuleIds = activeRequirementRows.SelectMany(row => row.MappedRequiredModuleIds).ToHashSet(StringComparer.OrdinalIgnoreCase);
        requiredModules = requiredModules.Select(module =>
        {
            if (!reviewedModuleIds.Contains(module.Id) || activeModuleIds.Contains(module.Id))
            {
                return module;
            }

            var reviewedRows = reviewedRequirementRows
                .Where(row => row.MappedRequiredModuleIds.Contains(module.Id, StringComparer.OrdinalIgnoreCase))
                .ToArray();
            var evidenceRefs = reviewedRows
                .Select(row => approvedRequirementDecisions.TryGetValue(row.RequirementId, out var evidence) ? evidence : "")
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.Ordinal)
                .ToArray();
            return module with
            {
                Status = "reviewed_not_applicable",
                RequirementIds = reviewedRows.Select(row => row.RequirementId).ToArray(),
                SourceReason = "admin_approved_conflict_suppression",
                SourceRefs = evidenceRefs,
                CoverageStatus = "reviewed_not_applicable",
                ValidationRefs = evidenceRefs
            };
        }).ToArray();
        foreach (var module in requiredModules.Where(module =>
                     string.Equals(module.Status, "skipped_by_explicit_gdd_conflict", StringComparison.OrdinalIgnoreCase) &&
                     !(module.SourceRefs ?? []).Any(reference => reference.StartsWith("admin-review:", StringComparison.OrdinalIgnoreCase))))
        {
            AddBlocker(
                blockers,
                "admin_decision_evidence_missing",
                "P1",
                $"Module {module.Id} cannot be suppressed without admin-approved decision evidence.",
                module.RequirementIds ?? [],
                module.SourceRefs ?? []);
        }

        var invalidGoalIndexes = goals.Where(goal => goal.GoalIndex <= 0).Select(goal => goal.GoalIndex).ToArray();
        var duplicateGoalIndexes = goals.GroupBy(goal => goal.GoalIndex).Where(group => group.Count() > 1).Select(group => group.Key).ToArray();
        if (invalidGoalIndexes.Length > 0 || duplicateGoalIndexes.Length > 0)
        {
            if (invalidGoalIndexes.Length > 0)
            {
                AddBlocker(blockers, "goal_index_invalid", "P0", "Iteration goals contain a non-positive goal index.", [], ["iteration-plan-goals"]);
            }
            if (duplicateGoalIndexes.Length > 0)
            {
                AddBlocker(blockers, "goal_index_duplicate", "P0", "Iteration goals contain duplicate goal indexes.", [], ["iteration-plan-goals"]);
            }
            var invalidSourceHashRef = ComputeHash(JsonSerializer.Serialize(sourceHashes));
            var invalidCoverage = new PrototypeIterationPlanCoverageResult(0, 0, 0, 0, 0, []);
            var invalidPlanHash = IterationPlanIntegrity.Compute(invalidSourceHashRef, goals, requiredModules, blockers, invalidCoverage);
            return new IterationPlanTraceabilityBuildResult(
                goals,
                requiredModules,
                new PrototypeIterationPlanCoverageResult(0, 0, 0, 0, 0, []),
                blockers,
                invalidSourceHashRef,
                invalidPlanHash);
        }

        var effectiveModules = requiredModules
            .Concat(activeRequirementRows
                .SelectMany(row => row.MappedRequiredModuleIds)
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Where(id => requiredModules.All(module => !string.Equals(module.Id, id, StringComparison.OrdinalIgnoreCase)))
                .Select(id => new PrototypeIterationPlanRequiredModuleResult(
                    id.Trim(),
                    "requirement_map",
                    "required",
                    "admin_approved_conflict",
                    [],
                    null)))
            .Concat(reviewedRequirementRows
                .Where(row => row.Status is "explicitly_deferred" or "conflict")
                .Where(row => row.MappedRequiredModuleIds.Count == 0)
                .Where(row => approvedRequirementDecisions.TryGetValue(row.RequirementId, out var evidenceRef) && !string.IsNullOrWhiteSpace(evidenceRef))
                .Select(row => new PrototypeIterationPlanRequiredModuleResult(
                    $"decision_disposition_{row.RequirementId.ToLowerInvariant()}",
                    "admin_review_queue",
                    "reviewed_not_applicable",
                    "approved_decision_only",
                    [],
                    null,
                    [row.RequirementId],
                    "admin_approved_conflict_suppression",
                    [approvedRequirementDecisions[row.RequirementId]],
                    row.Priority,
                    "reviewed_not_applicable",
                    [approvedRequirementDecisions[row.RequirementId]])))
            .GroupBy(module => module.Id, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .OrderBy(module => module.Id, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        var knownRequirementIds = requirementRows.Keys.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var goalRequirements = goals.ToDictionary(goal => goal.GoalIndex, _ => new HashSet<string>(StringComparer.OrdinalIgnoreCase));
        var moduleRequirements = effectiveModules.ToDictionary(module => module.Id, _ => new HashSet<string>(StringComparer.OrdinalIgnoreCase), StringComparer.OrdinalIgnoreCase);

        foreach (var goal in goals)
        {
            ValidateDeclaredRequirementIds(goal.RequirementIds, knownRequirementIds, goalRequirements[goal.GoalIndex], blockers, $"goal-{goal.GoalIndex}");
        }

        foreach (var module in effectiveModules)
        {
            ValidateDeclaredRequirementIds(module.RequirementIds, knownRequirementIds, moduleRequirements[module.Id], blockers, module.Id);
        }

        var goalCovered = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var moduleCovered = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var skeletonCovered = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var explicitBlockers = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var row in requirementRows.Values.Where(IsP0P1))
        {
            if (IsReviewedBlocker(row, approvedRequirementDecisions, out var decisionEvidenceRef))
            {
                explicitBlockers.Add(row.RequirementId);
                continue;
            }

            var resolvedGoal = ResolveMappedGoals(row, goals);
            var resolvedModules = ResolveMappedModules(row, effectiveModules);
            if ((RequiresDynamicUiOwnership(row) || RequiresThirdPersonCamera(row) || RequiresInteractionRegion(row)) &&
                resolvedGoal.Count == 0 &&
                !verifiedSkeletonRequirementIds.Contains(row.RequirementId))
            {
                AddBlocker(blockers, "capability_goal_missing", row.Priority, "Capability-heavy requirements must map to an executable goal with equivalent preflight evidence.", [row.RequirementId], ["meta/routes/gdd-requirements/latest.json"]);
            }
            foreach (var goal in resolvedGoal)
            {
                goalRequirements[goal.GoalIndex].Add(row.RequirementId);
                goalCovered.Add(row.RequirementId);
            }

            foreach (var module in resolvedModules)
            {
                moduleRequirements[module.Id].Add(row.RequirementId);
                moduleCovered.Add(row.RequirementId);
            }

            if (verifiedSkeletonRequirementIds.Contains(row.RequirementId))
            {
                skeletonCovered.Add(row.RequirementId);
            }

        }

        var p0P1Ids = requirementRows.Values.Where(IsP0P1).Select(row => row.RequirementId).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var covered = goalCovered.Concat(moduleCovered).Concat(skeletonCovered).Concat(explicitBlockers).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var uncovered = p0P1Ids.Where(id => !covered.Contains(id)).OrderBy(id => id, StringComparer.Ordinal).ToArray();
        if (uncovered.Length > 0)
        {
            AddBlocker(blockers, "coverage_gap", "P0", "One or more P0/P1 requirements are not covered by a goal, required module, verified skeleton capability, or explicit blocker.", uncovered, ["meta/routes/gdd-requirements/latest.json"]);
        }

        var styledRequirementIds = requirementRows.Values
            .Where(IsP0P1)
            .Where(row => string.Equals(row.Kind, "ui", StringComparison.OrdinalIgnoreCase) || row.CapabilityDomainIds.Any(id => id.StartsWith("ui_", StringComparison.OrdinalIgnoreCase)))
            .Select(row => row.RequirementId)
            .ToArray();
        var reviewedStyleNotApplicable = string.Equals(styleApplicability?.Status, "reviewed_not_applicable", StringComparison.Ordinal) &&
                                         !string.IsNullOrWhiteSpace(styleApplicability!.EvidenceHash);
        if (styledRequirementIds.Length > 0 && styleAuthority is null && !reviewedStyleNotApplicable)
        {
            AddBlocker(blockers, "ui_style_snapshot_missing", "P1", "UI-facing requirements do not have a valid frozen style authority.", styledRequirementIds, ["routes/prototype-contract/latest.json"]);
        }

        foreach (var goal in goals)
        {
            var linkedRows = goalRequirements[goal.GoalIndex].Select(id => requirementRows[id]).ToArray();
            var ownershipProfiles = linkedRows
                .Where(row => row.GodotUiUpdateOwnership is not null)
                .Select(row => JsonSerializer.Serialize(row.GodotUiUpdateOwnership))
                .Distinct(StringComparer.Ordinal)
                .ToArray();
            if (ownershipProfiles.Length > 1)
            {
                AddBlocker(blockers, "ui_update_ownership_conflict", "P1", "A single goal cannot collapse multiple dynamic UI ownership profiles.", linkedRows.Select(row => row.RequirementId), ["meta/routes/gdd-requirements/latest.json"]);
            }

            var cameraProfiles = linkedRows
                .Where(row => row.GodotThirdPersonCameraProfile is not null)
                .Select(row => JsonSerializer.Serialize(row.GodotThirdPersonCameraProfile))
                .Distinct(StringComparer.Ordinal)
                .ToArray();
            if (cameraProfiles.Length > 1)
            {
                AddBlocker(blockers, "third_person_camera_profile_conflict", "P1", "A single goal cannot collapse multiple third-person camera profiles.", linkedRows.Select(row => row.RequirementId), ["meta/routes/gdd-requirements/latest.json"]);
            }
        }

        var sourceHashRef = ComputeSourceHashRef(sourceHashes, styleApplicability);
        var enrichedGoals = goals.Select(goal => EnrichGoal(goal, goalRequirements[goal.GoalIndex], requirementRows, sourceHashRef, styleAuthority, styleApplicability)).ToArray();
        var enrichedModules = effectiveModules.Select(module => EnrichModule(module, moduleRequirements[module.Id], requirementRows)).ToArray();
        var coverage = new PrototypeIterationPlanCoverageResult(
            p0P1Ids.Count,
            goalCovered.Count,
            moduleCovered.Count,
            skeletonCovered.Count,
            explicitBlockers.Count,
            uncovered);
        var planHash = IterationPlanIntegrity.Compute(sourceHashRef, enrichedGoals, enrichedModules, blockers, coverage);

        return new IterationPlanTraceabilityBuildResult(enrichedGoals, enrichedModules, coverage, blockers, sourceHashRef, planHash);
    }

    internal static string ComputeSourceHashRef(
        PrototypeIterationPlanSourceHashes sourceHashes,
        PrototypeIterationStyleApplicability? styleApplicability)
    {
        return ComputeHash(JsonSerializer.Serialize(new
        {
            source_hashes = sourceHashes,
            style_applicability = styleApplicability
        }));
    }

    private static PrototypeIterationPlanGoalResult EnrichGoal(
        PrototypeIterationPlanGoalResult goal,
        IReadOnlySet<string> requirementIds,
        IReadOnlyDictionary<string, GameDesignRequirementRow> rows,
        string sourceHashRef,
        PrototypeIterationStyleAuthority? styleAuthority,
        PrototypeIterationStyleApplicability? styleApplicability)
    {
        var linked = requirementIds.Select(id => rows[id]).ToArray();
        var uiRows = linked.Where(row => string.Equals(row.Kind, "ui", StringComparison.OrdinalIgnoreCase) || row.CapabilityDomainIds.Any(id => id.StartsWith("ui_", StringComparison.OrdinalIgnoreCase))).ToArray();
        var dynamicUiRequired = linked.Any(RequiresDynamicUiOwnership);
        var thirdPersonCameraRequired = linked.Any(RequiresThirdPersonCamera);
        var featureFamilyReadingRequired = linked.Any(RequiresFeatureFamilyReading);
        var interactionRegionRequired = linked.Any(RequiresInteractionRegion);
        var uiSurface = uiRows.Length == 0
            ? null
            : new PrototypeIterationUiSurfaceResult(
                string.Join(",", uiRows.SelectMany(row => row.MappedSceneIds).Distinct(StringComparer.OrdinalIgnoreCase)),
                $"iteration-goal-{goal.GoalIndex}",
                "godot_control_surface",
                "requirement_map_defined",
                "canvas_layer_ui",
                "ui",
                "scene_owned",
                "explicit_focus_order",
                uiRows.SelectMany(row => row.AcceptanceMarkers).Distinct(StringComparer.OrdinalIgnoreCase).ToArray(),
                "gameplay_state_to_ui_projection",
                uiRows.SelectMany(row => row.AcceptanceMarkers).Distinct(StringComparer.OrdinalIgnoreCase).ToArray());
        var style = uiRows.Length == 0
            ? null
            : styleAuthority is null
                ? string.Equals(styleApplicability?.Status, "reviewed_not_applicable", StringComparison.Ordinal)
                    ? new PrototypeIterationStyleResult([], [], [], "not_applicable", "not_applicable", "not_applicable", [], styleApplicability!.EvidenceHash)
                    : null
                : new PrototypeIterationStyleResult(
                    [$"style:{styleAuthority.StyleId}@{styleAuthority.Version}", $"snapshot:{styleAuthority.SnapshotHash}", styleAuthority.GuidePath],
                    styleAuthority.ComponentFamilies,
                    styleAuthority.DesignDna,
                    string.Join("; ", styleAuthority.CompositionTemplates),
                    string.Join("; ", styleAuthority.TriggerTags),
                    "required",
                    ["ui_tree_readback", "visual_evidence_matrix"]);
        var engineSemantics = featureFamilyReadingRequired
            ? new PrototypeIterationEngineSemanticsResult(
                "project_viewport_contract",
                "godot_canvas_and_world_coordinates",
                "godot_input_event_ownership",
                "canvas_layer_and_world_layer_boundary",
                ["repo-owned-feature-profile"],
                ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"])
            : null;
        var interactionRegion = interactionRegionRequired
            ? new PrototypeIterationInteractionRegionResult(
                $"meta/routes/iteration-plan/interaction-regions/goal-{goal.GoalIndex:00}.json",
                ["mouse", "keyboard", "gamepad", "touch"],
                linked.SelectMany(row => row.MappedSceneIds.Select(id => $"scene:{id}:interaction-region")
                    .Concat(row.MappedRequiredModuleIds.Select(id => $"module:{id}:interaction-region")))
                    .Distinct(StringComparer.OrdinalIgnoreCase).ToArray(),
                ["outside_owned_control_or_collision_region"],
                linked.SelectMany(row => row.AcceptanceMarkers).Distinct(StringComparer.OrdinalIgnoreCase).ToArray(),
                ["interaction-region-contract-validation"])
            : null;

        return goal with
        {
            RequirementIds = requirementIds.OrderBy(id => id, StringComparer.Ordinal).ToArray(),
            InfrastructureReason = requirementIds.Count == 0
                ? new PrototypeIterationInfrastructureReason("route_strategy_scaffold", "Goal is retained from the game-type route strategy and does not claim P0/P1 requirement coverage.", ["game-type-route-strategy"])
                : null,
            SourceHashRef = sourceHashRef,
            UiSurface = uiSurface,
            Style = style,
            EngineSemantics = engineSemantics,
            InteractionRegion = interactionRegion,
            GodotUiUpdateOwnership = linked.Select(row => row.GodotUiUpdateOwnership).FirstOrDefault(item => item is not null),
            GodotThirdPersonCameraProfile = linked.Select(row => row.GodotThirdPersonCameraProfile).FirstOrDefault(item => item is not null),
            CapabilityRequirements = new PrototypeIterationCapabilityRequirements(
                dynamicUiRequired,
                thirdPersonCameraRequired,
                featureFamilyReadingRequired,
                interactionRegionRequired)
        };
    }

    private static PrototypeIterationPlanRequiredModuleResult EnrichModule(
        PrototypeIterationPlanRequiredModuleResult module,
        IReadOnlySet<string> requirementIds,
        IReadOnlyDictionary<string, GameDesignRequirementRow> rows)
    {
        if (string.Equals(module.CoverageStatus, "reviewed_not_applicable", StringComparison.Ordinal))
        {
            return module;
        }
        var linked = requirementIds.Select(id => rows[id]).ToArray();
        return module with
        {
            RequirementIds = requirementIds.OrderBy(id => id, StringComparer.Ordinal).ToArray(),
            SourceReason = linked.Length == 0 ? "route_strategy_required_module" : "requirement_map_module_mapping",
            SourceRefs = linked.Length == 0 ? [module.Source] : linked.Select(row => $"requirement:{row.RequirementId}").ToArray(),
            Priority = HighestPriority(linked.Select(row => row.Priority)),
            CoverageStatus = linked.Length == 0 ? "infrastructure" : "covered",
            ValidationRefs = linked.SelectMany(row => row.AcceptanceMarkers).Distinct(StringComparer.OrdinalIgnoreCase).ToArray()
        };
    }

    private static IReadOnlyList<PrototypeIterationPlanGoalResult> ResolveMappedGoals(GameDesignRequirementRow row, IReadOnlyList<PrototypeIterationPlanGoalResult> goals)
    {
        return goals.Where(goal =>
            (goal.RequirementIds?.Contains(row.RequirementId, StringComparer.OrdinalIgnoreCase) ?? false) ||
            row.MappedIterationGoalIds.Any(mapped =>
                string.Equals(mapped, $"goal-{goal.GoalIndex}", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(mapped, goal.GoalIndex.ToString(), StringComparison.OrdinalIgnoreCase) ||
                string.Equals(mapped, goal.Title, StringComparison.OrdinalIgnoreCase))).ToArray();
    }

    private static IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> ResolveMappedModules(GameDesignRequirementRow row, IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> modules)
    {
        return modules.Where(module =>
            row.MappedRequiredModuleIds.Contains(module.Id, StringComparer.OrdinalIgnoreCase) &&
            module.Status is "required" or "covered" or "verified").ToArray();
    }

    private static void ValidateDeclaredRequirementIds(
        IReadOnlyList<string>? declared,
        IReadOnlySet<string> known,
        ISet<string> target,
        ICollection<PrototypeIterationPlanBlockerResult> blockers,
        string owner)
    {
        if (declared is null)
        {
            return;
        }

        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var raw in declared)
        {
            var id = NormalizeRequirementId(raw);
            if (id.Length == 0)
            {
                AddBlocker(blockers, "requirement_id_empty", "P0", $"{owner} contains an empty requirement ID.", [], [owner]);
                continue;
            }

            if (!seen.Add(id))
            {
                AddBlocker(blockers, "requirement_id_duplicate", "P0", $"{owner} contains duplicate requirement ID {id}.", [id], [owner]);
                continue;
            }

            if (!known.Contains(id))
            {
                AddBlocker(blockers, "requirement_id_unknown", "P0", $"{owner} references unknown requirement ID {id}.", [id], [owner]);
                continue;
            }

            target.Add(id);
        }
    }

    private static bool IsP0P1(GameDesignRequirementRow row) => row.Priority is "P0" or "P1";

    private static string ResolveExecutableMappedModuleId(
        GameDesignRequirementRow row,
        IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> requiredModules)
    {
        return row.MappedRequiredModuleIds.FirstOrDefault(moduleId =>
            !requiredModules.Any(module => string.Equals(module.Id, moduleId, StringComparison.OrdinalIgnoreCase)) ||
            requiredModules.Any(module =>
                string.Equals(module.Id, moduleId, StringComparison.OrdinalIgnoreCase) &&
                module.Status is "required" or "covered" or "verified")) ?? "";
    }

    private static bool RequiresDynamicUiOwnership(GameDesignRequirementRow row)
    {
        return row.GodotUiUpdateOwnership is not null ||
               row.CapabilityDomainIds.Contains("dynamic_item_factory", StringComparer.OrdinalIgnoreCase) ||
               (row.Kind == "ui" && row.NormalizedRequirement.Contains("dynamic", StringComparison.OrdinalIgnoreCase));
    }

    private static bool RequiresThirdPersonCamera(GameDesignRequirementRow row)
    {
        return row.GodotThirdPersonCameraProfile is not null ||
               row.NormalizedRequirement.Contains("third-person", StringComparison.OrdinalIgnoreCase) ||
               row.NormalizedRequirement.Contains("third person", StringComparison.OrdinalIgnoreCase);
    }

    private static bool RequiresFeatureFamilyReading(GameDesignRequirementRow row)
    {
        return row.Kind is "ui" or "input" or "camera" or "mechanic" or "scene" or "rendering" or "procedural" or "geometry";
    }

    private static bool RequiresInteractionRegion(GameDesignRequirementRow row)
    {
        var mapInteraction = row.Kind == "scene" && new[] { "map", "path", "tile", "move", "navigation", "select" }
            .Any(term => row.NormalizedRequirement.Contains(term, StringComparison.OrdinalIgnoreCase));
        return row.Kind is "ui" or "input" or "camera" or "mechanic" or "geometry" or "procedural" ||
               mapInteraction ||
               row.MappedRequiredModuleIds.Any(id => id is "route_map_path_selection" or "hand_card_dragging");
    }

    private static bool HasCompleteUiOwnership(GodotUiUpdateOwnership? ownership)
    {
        return ownership is
        {
            ConstructionOwner.Length: > 0,
            UpdateMode.Length: > 0,
            StateOwner.Length: > 0,
            CleanupPolicy.Length: > 0,
            StableItemIdentity.Length: > 0,
            SignalOwnership.Length: > 0
        };
    }

    private static bool HasCompleteThirdPersonCamera(GodotThirdPersonCameraProfile? profile)
    {
        return profile is
        {
            RigRef.Length: > 0,
            TargetOwner.Length: > 0,
            InputOwner.Length: > 0,
            CollisionOwner.Length: > 0,
            YawPitchOwnership.Length: > 0,
            CameraRelativeMovementBoundary.Length: > 0,
            CameraStateValidation.Length: > 0
        };
    }

    private static bool IsReviewedBlocker(
        GameDesignRequirementRow row,
        IReadOnlyDictionary<string, string> approvedRequirementDecisions,
        out string decisionEvidenceRef)
    {
        if (row.Status is "explicitly_deferred" or "conflict" &&
            approvedRequirementDecisions.TryGetValue(row.RequirementId, out var evidenceRef) &&
            !string.IsNullOrWhiteSpace(evidenceRef))
        {
            decisionEvidenceRef = evidenceRef;
            return true;
        }

        decisionEvidenceRef = "";
        return false;
    }

    private static string HighestPriority(IEnumerable<string> priorities)
    {
        var values = priorities.ToArray();
        return values.Contains("P0", StringComparer.OrdinalIgnoreCase) ? "P0" :
            values.Contains("P1", StringComparer.OrdinalIgnoreCase) ? "P1" : "P2";
    }

    private static string NormalizeRequirementId(string? value) => (value ?? "").Trim().ToUpperInvariant();

    private static void AddBlocker(
        ICollection<PrototypeIterationPlanBlockerResult> blockers,
        string domainCode,
        string severity,
        string summary,
        IEnumerable<string> requirementIds,
        IEnumerable<string> evidenceRefs)
    {
        var normalizedIds = requirementIds.Where(id => !string.IsNullOrWhiteSpace(id)).Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(id => id, StringComparer.Ordinal).ToArray();
        var normalizedRefs = evidenceRefs.Where(item => !string.IsNullOrWhiteSpace(item)).Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        if (blockers.Any(item => item.DomainCode == domainCode && item.RequirementIds.SequenceEqual(normalizedIds, StringComparer.OrdinalIgnoreCase)))
        {
            return;
        }

        blockers.Add(new PrototypeIterationPlanBlockerResult(domainCode, severity, summary, normalizedIds, normalizedRefs));
    }

    private static string ComputeHash(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }
}

internal sealed record IterationPlanTraceabilityBuildResult(
    IReadOnlyList<PrototypeIterationPlanGoalResult> Goals,
    IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> RequiredModules,
    PrototypeIterationPlanCoverageResult Coverage,
    IReadOnlyList<PrototypeIterationPlanBlockerResult> Blockers,
    string SourceHashRef,
    string PlanHash);

internal sealed record PrototypeIterationStyleAuthority(
    string StyleId,
    string Version,
    string SnapshotHash,
    string GuidePath,
    IReadOnlyList<string> TriggerTags,
    IReadOnlyList<string> DesignDna,
    IReadOnlyList<string> ComponentFamilies,
    IReadOnlyList<string> CompositionTemplates);
