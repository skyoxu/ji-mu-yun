using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Text.Json;
using System.Text.Json.Nodes;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeIterationPlanService
{
    private const string EvaluationRunType = "prototype-iteration-plan-evaluation";
    private const int MaxTextAttachments = 5;
    private const int MaxTextAttachmentChars = 12000;
    private static readonly Regex SplitRegex = new(@"[。！？!?]\s*|\r?\n+", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex NumberedGoalRegex = new(
        @"(?:^|\n)\s*(?:step\s*)?\d{1,2}\s*[\.\):\-:：、]?\s*(.+?)(?=(?:\n\s*(?:step\s*)?\d{1,2}\s*[\.\):\-:：、]?\s*)|\z)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.Singleline);
    private static readonly string[] InternalSuggestionKeywords =
    [
        "Day 4",
        "Day 5",
        "Step 04",
        "Step 05",
        "dotnet test",
        "dotnet build",
        "build-server",
        "obj/tmp",
        "文件锁",
        "写权限",
        "环境清理",
        "重跑",
        "工作区",
        "GdUnit",
        "Godot/GdUnit"
    ];
    private static readonly CodexChatClientOptions PlanningCodexOptions = new(
        IgnoreRules: true,
        ReasoningEffort: "minimal");
    private static readonly string PlanningAnalysisSchemaPath = EnsurePlanningAnalysisSchemaFile();
    private static readonly string GoalPlanSchemaPath = EnsureGoalPlanSchemaFile();
    private static readonly string EvaluationSchemaPath = EnsureEvaluationSchemaFile();
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeRouteStateWriter _routeStateWriter;
    private readonly PrototypeContractService _contractService;
    private readonly PrototypeContractFreezeService _contractFreezeService;
    private readonly GameDesignRequirementMapService _requirementMapService;
    private readonly ILlmRouteEngine? _llmRouteEngine;
    private readonly GameTypeTemplateCatalog? _templateCatalog;

    public PrototypeIterationPlanService(PhaseAMetadataStore metadataStore)
        : this(metadataStore, new PrototypeRouteStateWriter(), new PrototypeContractService(), null, null)
    {
    }

    public PrototypeIterationPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeRouteStateWriter routeStateWriter,
        PrototypeContractService? contractService = null,
        ICodexChatClient? codexChatClient = null,
        ILlmRouteEngine? llmRouteEngine = null,
        GameTypeTemplateCatalog? templateCatalog = null,
        PrototypeContractFreezeService? contractFreezeService = null,
        GameDesignRequirementMapService? requirementMapService = null)
    {
        _metadataStore = metadataStore;
        _routeStateWriter = routeStateWriter;
        _contractService = contractService ?? new PrototypeContractService();
        _contractFreezeService = contractFreezeService ?? new PrototypeContractFreezeService(metadataStore);
        _requirementMapService = requirementMapService ?? new GameDesignRequirementMapService(metadataStore);
        _llmRouteEngine = llmRouteEngine ?? (codexChatClient is null ? null : new LlmRouteEngine(codexChatClient));
        _templateCatalog = templateCatalog;
    }

    public async Task<PrototypeIterationPlanResult> CreateAsync(
        string accountId,
        string projectId,
        PrototypeIterationPlanRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        await using var mutationLease = await ProjectMutationLockRegistry.Shared.AcquireAsync(accountId, projectId, cancellationToken);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var newChainGuard = _contractFreezeService.EvaluateNewChainGuard(project);
        if (newChainGuard.NewChainActive && !newChainGuard.Allowed)
        {
            var domainCode = newChainGuard.Status is "contract_missing" ? "requirement_map_missing" : "contract_stale";
            return await RejectPlanBeforeLlmAsync(
                project,
                ToIterationPlanSourceHashes(newChainGuard.ContractStatus),
                domainCode,
                newChainGuard.Summary,
                cancellationToken,
                ["meta/routes/gdd-requirements/latest.json", "routes/prototype-contract/latest.json"]);
        }

        var rawMessage = request.Message?.Trim();
        var message = NormalizePlanningMessage(rawMessage, request.SourceKind);
        var model = PrototypeModelPolicy.Normalize(request.Model);
        if (string.IsNullOrWhiteSpace(message))
        {
            return new PrototypeIterationPlanResult("", "missing_message", "请输入要拆解的优化目标。", [], null, OperationStatus: "rejected");
        }

        if ((request.Attachments?.Count ?? 0) > MaxTextAttachments)
        {
            return new PrototypeIterationPlanResult("", "too_many_attachments", "最多只能导入 5 个 TXT 参考文件。", [], null, OperationStatus: "rejected");
        }

        var attachmentContext = BuildAttachmentPromptBlock(request.Attachments);
        var promptMessage = AppendAttachmentContext(message, attachmentContext);

        var sourceKind = string.IsNullOrWhiteSpace(request.SourceKind) ? "manual_feedback" : request.SourceKind.Trim();
        if (string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase) &&
            IsInternalExecutionSuggestion(message))
        {
            return new PrototypeIterationPlanResult(
                "",
                "suggestion_needs_fix",
                "当前这条建议更像内部执行或环境修复信息，不适合直接拆成游戏模块任务。请先处理需修复项，或重新生成更明确的产品向优化建议。",
                [],
                null,
                OperationStatus: "rejected");
        }
        var sourceHashes = newChainGuard.NewChainActive ? ToIterationPlanSourceHashes(newChainGuard.ContractStatus) : null;
        var styleApplicability = sourceHashes is null ? null : ToIterationStyleApplicability(newChainGuard.ContractStatus);
        GameDesignRequirementMapResult? preflightRequirementMap = null;
        IReadOnlyDictionary<string, string> approvedRequirementDecisions = new Dictionary<string, string>();
        IReadOnlySet<string> verifiedSkeletonRequirementIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (sourceHashes is not null)
        {
            preflightRequirementMap = await _requirementMapService.GetLatestAsync(accountId, projectId, cancellationToken);
            var governance = await ReadLiveGovernanceAsync(project, preflightRequirementMap, cancellationToken);
            if (governance.Blocker is not null)
            {
                return await RejectPlanBeforeLlmAsync(
                    project,
                    sourceHashes,
                    governance.Blocker.DomainCode,
                    governance.Blocker.Summary,
                    cancellationToken,
                    governance.Blocker.EvidenceRefs,
                    governance.Blocker.RequirementIds);
            }
            approvedRequirementDecisions = governance.ApprovedRequirementDecisions;
            if (!IsCurrentRequirementMap(preflightRequirementMap, newChainGuard.ContractStatus, approvedRequirementDecisions))
            {
                return await RejectPlanBeforeLlmAsync(project, sourceHashes, "source_stale", "The frozen Requirement Map does not match the current Prototype Contract authority hashes.", cancellationToken);
            }

            var skeletonAuthority = PrototypeSkeletonAuthorityGate.Evaluate(project, _routeStateWriter, sourceHashes);
            if (!skeletonAuthority.Allowed)
            {
                return await RejectPlanBeforeLlmAsync(
                    project,
                    sourceHashes,
                    skeletonAuthority.DomainCode,
                    skeletonAuthority.Summary,
                    cancellationToken,
                    skeletonAuthority.EvidenceRefs);
            }
            verifiedSkeletonRequirementIds = skeletonAuthority.VerifiedRequirementIds;
        }
        var requestIdentityHash = sourceHashes is null
            ? ""
            : ComputeHash(JsonSerializer.Serialize(new
            {
                account_scope = accountId,
                project_scope = projectId,
                source_hashes = sourceHashes,
                style_applicability = styleApplicability,
                source_kind = sourceKind,
                message = promptMessage,
                model
            }));
        if (sourceHashes is not null)
        {
            var reused = await TryReuseCurrentPlanAsync(project, requestIdentityHash, sourceHashes, cancellationToken);
            if (reused is not null)
            {
                return reused;
            }
        }
        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var routeStrategy = GameTypeRouteStrategies.Resolve(project, routeProfile);

        var previousIterationPlan = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (previousIterationPlan is not null &&
            !string.Equals(sourceKind, "new_iteration_plan", StringComparison.OrdinalIgnoreCase) &&
            IsIterationPlanStarted(previousIterationPlan) &&
            !IsIterationPlanComplete(previousIterationPlan.Goals))
        {
            return new PrototypeIterationPlanResult(
                "",
                "iteration_plan_update_blocked",
                "\u5f53\u524d\u8fed\u4ee3\u8ba1\u5212\u5df2\u7ecf\u5f00\u59cb\u6267\u884c\uff0c\u4e0d\u5141\u8bb8\u66f4\u65b0\u8fed\u4ee3\u8ba1\u5212\u3002",
                [],
                null,
                previousIterationPlan.LatestEvaluation,
                OperationStatus: "rejected");
        }

        var regenerationGuidance = BuildPlanRegenerationGuidance(previousIterationPlan, promptMessage, sourceKind);
        var prototypeContract = _contractService.Read(project);
        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, prototypeContract);
        if (sourceHashes is not null)
        {
            _routeStateWriter.WriteIterationPlanPromptEvidenceState(project, new
            {
                schema_version = "iteration-plan-prompt-evidence.v1",
                route = "iteration-plan",
                source_boundary_enforced = true,
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                source_hashes = ToSourceBoundaryHashMap(sourceHashes),
                authority_sources = SourceBoundaryHashKeys,
                request_identity_hash = requestIdentityHash,
                prompt_transport = "stdin-first-shared-route-engine",
                raw_prompt_persisted = false,
                updated_utc = DateTimeOffset.UtcNow.ToString("O")
            });
        }
        IterationPlanningContext planningContext;
        try
        {
            planningContext = await BuildPlanningContextAsync(project, routeProfile, routeStrategy, prototypeContract, promptMessage, sourceKind, regenerationGuidance, model, cancellationToken);
        }
        catch (PrototypeIterationPlanLlmException ex) when (routeStrategy.RequiresModelBackedIterationPlanning)
        {
            return new PrototypeIterationPlanResult(
                "",
                "llm_failed",
                $"游戏模块生成需要 LLM 成功参与，但当前调用失败：{ex.Message}",
                [],
                null,
                null,
                OperationStatus: "rejected");
        }

        var genericCoreLoopGate = routeStrategy.UsesSpecializedIterationPlanning
            ? GenericCoreLoopGateResult.NotApplicable()
            : AnalyzeGenericCoreLoopForPlanning(promptMessage, planningContext);
        if (genericCoreLoopGate.RequiresCustomRoute)
        {
            return new PrototypeIterationPlanResult(
                "",
                "custom_route_required",
                "当前表单识别出的最小循环已经超过通用游戏模块能力范围，请联系管理员创建定制游戏类型路线后再继续。",
                [],
                ToPlanningAnalysisResult(planningContext),
                null,
                OperationStatus: "rejected");
        }

        IterationGoalBuildResult goalBuild;
        try
        {
            goalBuild = await BuildGoalsForProjectAsync(project, routeProfile, routeStrategy, prototypeContract, promptMessage, sourceKind, planningContext, regenerationGuidance, genericCoreLoopGate, model, cancellationToken);
        }
        catch (PrototypeIterationPlanLlmException ex) when (routeStrategy.RequiresModelBackedIterationPlanning)
        {
            return new PrototypeIterationPlanResult(
                "",
                "llm_failed",
                $"游戏模块生成需要 LLM 成功细化目标，但当前调用失败：{ex.Message}",
                [],
                ToPlanningAnalysisResult(planningContext),
                null,
                OperationStatus: "rejected");
        }

        IReadOnlyList<PrototypeIterationPlanGoalResult> goals = goalBuild.Goals;
        if (routeStrategy.RequiresNonEmptyIterationGoals && goals.Count == 0)
        {
            return new PrototypeIterationPlanResult(
                "",
                "llm_failed",
                "游戏模块生成需要 LLM 成功细化目标，但当前没有得到可用目标。",
                [],
                ToPlanningAnalysisResult(planningContext),
                null,
                OperationStatus: "rejected");
        }

        IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> requiredModules = BuildRequiredModulesForProject(project, routeStrategy, prototypeContract);
        IterationPlanTraceabilityBuildResult? traceability = null;
        if (newChainGuard.NewChainActive)
        {
            var activeSourceHashes = sourceHashes!;
            var requirementMap = await _requirementMapService.GetLatestAsync(accountId, projectId, cancellationToken);
            if (!IsCurrentRequirementMap(requirementMap, newChainGuard.ContractStatus, approvedRequirementDecisions))
            {
                return await RejectPlanBeforeLlmAsync(
                    project,
                    activeSourceHashes,
                    "source_stale",
                    "The frozen Requirement Map changed while the iteration plan was being generated.",
                    cancellationToken);
            }

            traceability = IterationPlanTraceabilityBuilder.Build(
                requirementMap ?? preflightRequirementMap!,
                goals,
                requiredModules,
                activeSourceHashes,
                approvedRequirementDecisions,
                BuildStyleAuthority(newChainGuard.ContractStatus),
                styleApplicability,
                verifiedSkeletonRequirementIds);
            goals = traceability.Goals;
            requiredModules = traceability.RequiredModules;
            var interactionScope = IterationPlanIntegrity.Compute(
                traceability.SourceHashRef,
                goals.Select(ToGoalState).ToArray(),
                requiredModules.Select(ToRequiredModuleState).ToArray(),
                traceability.Blockers.Select(ToBlockerState).ToArray(),
                ToCoverageState(traceability.Coverage));
            goals = goals.Select(goal =>
            {
                if (goal.InteractionRegion is null)
                {
                    return goal;
                }

                var owners = BuildInteractionOwners(goal, requiredModules);
                var geometry = BuildInteractionGeometry(goal, owners);
                return goal with
                {
                    InteractionRegion = goal.InteractionRegion with
                    {
                        ArtifactRef = $"meta/routes/iteration-plan/interaction-regions/{interactionScope}/goal-{goal.GoalIndex:00}.json",
                        OwnerRefs = owners,
                        PlannedGeometry = geometry,
                        ValidRegions = geometry.Select(item => $"geometry:{item.GeometryId}").ToArray()
                    }
                };
            }).ToArray();
            traceability = traceability with
            {
                Goals = goals,
                PlanHash = IterationPlanIntegrity.Compute(
                    traceability.SourceHashRef,
                    goals.Select(ToGoalState).ToArray(),
                    requiredModules.Select(ToRequiredModuleState).ToArray(),
                    traceability.Blockers.Select(ToBlockerState).ToArray(),
                    ToCoverageState(traceability.Coverage))
            };
            if (traceability.Blockers.Count > 0)
            {
                WriteBlockedTraceabilityAttemptState(project, activeSourceHashes, goals, requiredModules, traceability.Blockers, traceability.Coverage, traceability.PlanHash, traceability.SourceHashRef);
                foreach (var blocker in traceability.Blockers)
                {
                    await RecordPlanDiagnosticAsync(project, blocker, traceability.SourceHashRef, cancellationToken);
                }
                return new PrototypeIterationPlanResult(
                    "",
                    "blocked",
                    traceability.Blockers[0].Summary,
                    goals,
                    ToPlanningAnalysisResult(planningContext),
                    null,
                    requiredModules,
                    "rejected",
                    traceability.PlanHash,
                    activeSourceHashes,
                    traceability.Coverage,
                    traceability.Blockers);
            }
        }

        var skeletonGuard = await EvaluatePrototypeSkeletonRegenerationNeedAsync(
            project,
            previousIterationPlan,
            message,
            goals,
            planningContext,
            model,
            cancellationToken);
        if (skeletonGuard.RequiresPrototypeRecreation)
        {
            var recreationMessage = string.IsNullOrWhiteSpace(skeletonGuard.Reason)
                ? "\u6e38\u620f\u529f\u80fd\u8ba1\u5212\u6539\u52a8\u8fc7\u5927\uff0c\u9700\u8981\u65b0\u5efa\u9879\u76ee\u91cd\u65b0\u521b\u5efa\u6e38\u620f\u539f\u578b\u9aa8\u67b6\u3002"
                : skeletonGuard.Reason;
            if (string.Equals(sourceKind, "new_iteration_plan", StringComparison.OrdinalIgnoreCase))
            {
                recreationMessage = $"新一轮游戏模块没有创建：{recreationMessage}";
            }

            return new PrototypeIterationPlanResult(
                "",
                "prototype_recreation_required",
                recreationMessage,
                [],
                ToPlanningAnalysisResult(planningContext),
                null,
                OperationStatus: "rejected");
        }

        foreach (var goal in goals.Where(item => item.InteractionRegion is not null))
        {
            var owners = goal.InteractionRegion!.OwnerRefs;
            var candidate = new
            {
                schema_version = "godot-interaction-region.v1",
                route = "iteration-plan",
                goal_index = goal.GoalIndex,
                requirement_ids = goal.RequirementIds ?? [],
                scene_node_owners = owners,
                artifact_form = "planned-godot-node-map",
                evidence_kind = "pre-execution-design-contract",
                validation_status = "pending",
                validation_method = "",
                runtime_validation_required = true,
                coordinate_semantics = goal.EngineSemantics?.CoordinateSemantics ?? "project-profile-coordinate-semantics",
                devices = goal.InteractionRegion!.Devices,
                valid_regions = goal.InteractionRegion.ValidRegions,
                invalid_regions = goal.InteractionRegion.InvalidRegions,
                state_transitions = goal.InteractionRegion.StateTransitions,
                validation_refs = goal.InteractionRegion.ValidationRefs,
                owner_refs = goal.InteractionRegion.OwnerRefs,
                planned_geometry = goal.InteractionRegion.PlannedGeometry.Select(ToInteractionGeometryState).ToArray(),
                region_map = IterationPlanInteractionArtifactValidator.BuildRegionMap(
                    owners,
                    goal.InteractionRegion.ValidRegions,
                    goal.InteractionRegion.InvalidRegions,
                    goal.InteractionRegion.StateTransitions),
                source_hash_ref = goal.SourceHashRef,
                updated_utc = DateTimeOffset.UtcNow.ToString("O")
            };
            _routeStateWriter.WriteIterationPlanInteractionRegionState(project, goal.GoalIndex, candidate, goal.InteractionRegion!.ArtifactRef);
            var validation = IterationPlanInteractionArtifactValidator.ValidateCandidate(
                project.RepoPath,
                goal.InteractionRegion.ArtifactRef,
                goal.GoalIndex,
                goal.RequirementIds ?? [],
                goal.SourceHashRef,
                owners,
                goal.InteractionRegion.PlannedGeometry,
                goal.EngineSemantics?.CoordinateSemantics ?? "project-profile-coordinate-semantics");
            if (!validation.Allowed || validation.ValidatedPayload is null)
            {
                var blocker = new PrototypeIterationPlanBlockerResult(
                    "interaction_region_validation_failed",
                    "P1",
                    validation.Summary,
                    goal.RequirementIds ?? [],
                    [goal.InteractionRegion.ArtifactRef]);
                await RecordPlanDiagnosticAsync(project, blocker, traceability?.SourceHashRef ?? goal.SourceHashRef, cancellationToken);
                WriteBlockedTraceabilityAttemptState(
                    project,
                    sourceHashes!,
                    goals,
                    requiredModules,
                    [blocker],
                    traceability?.Coverage,
                    traceability?.PlanHash ?? "",
                    traceability?.SourceHashRef ?? goal.SourceHashRef);
                return new PrototypeIterationPlanResult(
                    "",
                    "blocked",
                    validation.Summary,
                    goals,
                    ToPlanningAnalysisResult(planningContext),
                    null,
                    requiredModules,
                    "rejected",
                    traceability?.PlanHash ?? "",
                    sourceHashes,
                    traceability?.Coverage,
                    [blocker]);
            }

            _routeStateWriter.WriteIterationPlanInteractionRegionState(
                project,
                goal.GoalIndex,
                validation.ValidatedPayload,
                goal.InteractionRegion.ArtifactRef);
        }

        var summary = BuildPlanSummary(goals.Count, planningContext, goalBuild.UsedScaffoldFallback);
        var planningAnalysis = ToPlanningAnalysisResult(planningContext, goalBuild.StageTelemetry);
        var llmObservability = BuildIterationPlanObservability(planningContext, goalBuild);
        var sessionId = Guid.NewGuid().ToString("N");
        var routeState = new
        {
            route = "iteration-plan",
            traceability_contract = sourceHashes is null ? null : "iteration-plan-traceability.v2",
            game_type_profile = routeProfile,
            source_boundary = new
            {
                contract_id = HostedRouteRecoveryContract.ContractId,
                enforced = true,
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = SourceBoundaryHashKeys,
                forbidden_source_patterns = new[]
                {
                    "docs/game-type-guides/** raw excerpts",
                    "mutable broad style guide after contract freeze",
                    "assistant summary as acceptance authority"
                },
                prompt_evidence_refs = new[]
                {
                    "meta/routes/iteration-plan/prompt-evidence.json",
                    "meta/routes/iteration-plan/planning-analysis.json",
                    "routes/prototype-contract/latest.json"
                },
                source_hashes = sourceHashes is null ? null : ToSourceBoundaryHashMap(sourceHashes)
            },
            source_boundary_enforced = true,
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            project_execution_guide_present = !string.IsNullOrWhiteSpace(projectExecutionGuide),
            project_execution_guide_path = PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath,
            prototype_contract = prototypeContract.RelativePath,
            prototype_contract_present = !string.IsNullOrWhiteSpace(prototypeContract.Json),
            session_id = sessionId,
            status = "ready",
            source_kind = sourceKind,
            request_identity_hash = requestIdentityHash,
            summary,
            model_plan_degraded = goalBuild.UsedScaffoldFallback ? "scaffold_fallback" : null,
            planning_analysis = planningAnalysis,
            llm_observability = llmObservability,
            selected_capabilities = BuildSelectedCapabilitiesForRoute(routeStrategy, promptMessage, planningContext, prototypeContract, regenerationGuidance),
            source_gdd_hash = sourceHashes?.SourceGddHash,
            source_scene_route_hash = sourceHashes?.SourceSceneRouteHash,
            source_requirement_map_hash = sourceHashes?.SourceRequirementMapHash,
            source_contract_hash = sourceHashes?.SourceContractHash,
            source_contract_snapshot_hash = sourceHashes?.SourceContractSnapshotHash,
            source_godot_ui_contract_hash = sourceHashes?.SourceGodotUiContractHash,
            source_ui_style_contract_hash = sourceHashes?.SourceUiStyleContractHash,
            ui_style_snapshot_hash = sourceHashes?.UiStyleSnapshotHash,
            style_applicability = styleApplicability is null ? null : ToStyleApplicabilityState(styleApplicability),
            source_hash_ref = traceability?.SourceHashRef,
            plan_hash = traceability?.PlanHash,
            coverage = traceability is null ? null : ToCoverageState(traceability.Coverage),
            blockers = traceability?.Blockers.Select(ToBlockerState).ToArray() ?? [],
            required_modules = requiredModules.Select(ToRequiredModuleState).ToArray(),
            goals = goals.Select(ToGoalState).ToArray(),
            confirmation = new { status = "unconfirmed", session_id = sessionId, plan_hash = traceability?.PlanHash ?? "", source_hash_ref = traceability?.SourceHashRef ?? "" },
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        };
        var canonicalRouteStateJson = JsonSerializer.Serialize(
            routeState,
            new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true });
        var overallGoal = BuildOverallGoal(project.GameName, message);
        ProjectIterationSessionSnapshot created;
        try
        {
            created = await _metadataStore.CreateProjectIterationSessionAsync(
                accountId,
                projectId,
                sourceKind,
                message,
                overallGoal,
                goals.Select(goal => new ProjectIterationGoalCreateCommand(
                    goal.GoalIndex,
                    goal.Title,
                    goal.Description,
                    goal.AcceptanceHint)).ToArray(),
                cancellationToken,
                sessionId: sessionId,
                requestIdentityHash: string.IsNullOrWhiteSpace(requestIdentityHash) ? null : requestIdentityHash,
                routeStateJson: canonicalRouteStateJson,
                initialStatus: "ready",
                initialSummary: summary);
        }
        catch (ProjectIterationRequestIdentityConflictException) when (sourceHashes is not null)
        {
            var reused = await TryReuseCurrentPlanAsync(
                project,
                requestIdentityHash,
                sourceHashes,
                cancellationToken,
                requireLatestSession: false);
            if (reused is not null)
            {
                return reused;
            }

            throw;
        }

        _routeStateWriter.WriteIterationPlanAnalysisState(project, new
        {
            route = "iteration-plan",
            session_id = created.SessionId,
            planning_analysis = planningAnalysis,
            llm_observability = llmObservability,
            model_plan_degraded = goalBuild.UsedScaffoldFallback ? "scaffold_fallback" : null,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
        _routeStateWriter.WriteIterationPlanState(project, routeState);
        _routeStateWriter.WriteIterationPlanSessionState(project, created.SessionId, routeState);

        var evaluation = await EvaluateAsync(accountId, projectId, ToPrototypeProgress(planningContext), model, cancellationToken);
        return new PrototypeIterationPlanResult(
            created.SessionId,
            "ready",
            summary,
            goals,
            planningAnalysis,
            evaluation,
            requiredModules,
            OperationStatus: "created_run",
            PlanHash: traceability?.PlanHash ?? "",
            SourceHashes: sourceHashes,
            Coverage: traceability?.Coverage,
            Blockers: traceability?.Blockers ?? [],
            Confirmation: new PrototypeIterationPlanConfirmationResult("unconfirmed", created.SessionId, traceability?.PlanHash ?? "", traceability?.SourceHashRef ?? "", "", ""),
            StyleApplicability: styleApplicability);
    }

    public async Task<PrototypeIterationPlanConfirmationOperationResult> ConfirmAsync(
        string accountId,
        string projectId,
        PrototypeIterationPlanConfirmationRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        await using var mutationLease = await ProjectMutationLockRegistry.Shared.AcquireAsync(accountId, projectId, cancellationToken);
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return new PrototypeIterationPlanConfirmationOperationResult("project_not_found", "project_not_found", "Project not found.", "rejected");
        }

        var guard = _contractFreezeService.EvaluateNewChainGuard(project);
        if (!guard.NewChainActive || !guard.Allowed)
        {
            var code = guard.NewChainActive ? "source_stale" : "legacy_plan_source_unknown";
            return await RejectConfirmationAsync(
                project,
                code,
                "Only a current hash-bound new-chain plan can be confirmed.",
                IterationPlanTraceabilityBuilder.ComputeSourceHashRef(
                    ToIterationPlanSourceHashes(guard.ContractStatus),
                    ToIterationStyleApplicability(guard.ContractStatus)),
                cancellationToken);
        }

        var sessionDetails = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (sessionDetails is null)
        {
            return await RejectConfirmationAsync(
                project,
                "iteration_plan_state_missing",
                "The current database-backed iteration plan is missing.",
                IterationPlanTraceabilityBuilder.ComputeSourceHashRef(
                    ToIterationPlanSourceHashes(guard.ContractStatus),
                    ToIterationStyleApplicability(guard.ContractStatus)),
                cancellationToken);
        }

        var stateText = RestoreCurrentPlanState(
            project,
            sessionDetails,
            _routeStateWriter,
            _routeStateWriter.ReadLatestIterationPlanState(project));
        JsonObject state;
        try
        {
            state = JsonNode.Parse(stateText)?.AsObject() ?? throw new JsonException();
        }
        catch (Exception ex) when (ex is JsonException or InvalidOperationException)
        {
            return await RejectConfirmationAsync(
                project,
                "iteration_plan_state_invalid",
                "The current iteration plan state is invalid.",
                IterationPlanTraceabilityBuilder.ComputeSourceHashRef(
                    ToIterationPlanSourceHashes(guard.ContractStatus),
                    ToIterationStyleApplicability(guard.ContractStatus)),
                cancellationToken);
        }

        var sessionId = ReadNodeString(state, "session_id");
        var planHash = ReadNodeString(state, "plan_hash");
        var sourceHashRef = ReadNodeString(state, "source_hash_ref");
        if (string.IsNullOrWhiteSpace(sessionId) || string.IsNullOrWhiteSpace(planHash) || string.IsNullOrWhiteSpace(sourceHashRef))
        {
            return await RejectConfirmationAsync(project, "legacy_plan_source_unknown", "The current plan does not contain hash-bound confirmation fields.", sourceHashRef, cancellationToken);
        }

        if (!string.Equals(request.SessionId, sessionId, StringComparison.Ordinal))
        {
            return await RejectConfirmationAsync(project, "plan_session_conflict", "The requested session is not the current iteration plan.", sourceHashRef, cancellationToken, "conflict");
        }

        if (!string.Equals(request.PlanHash, planHash, StringComparison.Ordinal))
        {
            return await RejectConfirmationAsync(project, "plan_hash_conflict", "The requested plan hash is not current.", sourceHashRef, cancellationToken, "conflict");
        }

        if (!string.Equals(sessionDetails.Session.SessionId, sessionId, StringComparison.Ordinal))
        {
            return await RejectConfirmationAsync(project, "plan_session_conflict", "The requested session is not the current database-backed iteration plan.", sourceHashRef, cancellationToken, "conflict");
        }

        var confirmationPreflight = IterationPlanExecutionPreflight.EvaluateForConfirmation(
            stateText,
            sessionId,
            ToIterationPlanSourceHashes(guard.ContractStatus),
            ToIterationStyleApplicability(guard.ContractStatus));
        if (!confirmationPreflight.Allowed)
        {
            return await RejectConfirmationAsync(project, confirmationPreflight.DomainCode, confirmationPreflight.Summary, sourceHashRef, cancellationToken);
        }

        var trustedConfirmation = TryReadTraceabilityAnchor(sessionDetails.Session.TraceabilityAnchorJson);
        if (trustedConfirmation is not null)
        {
            if (!string.Equals(trustedConfirmation.SessionId, sessionId, StringComparison.Ordinal) ||
                !string.Equals(trustedConfirmation.PlanHash, planHash, StringComparison.Ordinal) ||
                !string.Equals(trustedConfirmation.SourceHashRef, sourceHashRef, StringComparison.Ordinal))
            {
                return await RejectConfirmationAsync(
                    project,
                    "plan_hash_conflict",
                    "The database-backed confirmation anchor already binds this session to a different plan identity.",
                    sourceHashRef,
                    cancellationToken,
                    "conflict");
            }

            state["confirmation"] = ToConfirmationNode(trustedConfirmation);
            _routeStateWriter.WriteIterationPlanSessionState(project, sessionId, state);
            _routeStateWriter.WriteIterationPlanState(project, state);
            return new PrototypeIterationPlanConfirmationOperationResult(
                "confirmed",
                "",
                "The current hash-bound iteration plan was already confirmed.",
                "returned_existing",
                trustedConfirmation);
        }

        var existing = state["confirmation"] as JsonObject;
        if (existing is not null &&
            string.Equals(ReadNodeString(existing, "status"), "confirmed", StringComparison.Ordinal) &&
            string.Equals(ReadNodeString(existing, "session_id"), sessionId, StringComparison.Ordinal) &&
            string.Equals(ReadNodeString(existing, "plan_hash"), planHash, StringComparison.Ordinal) &&
            string.Equals(ReadNodeString(existing, "source_hash_ref"), sourceHashRef, StringComparison.Ordinal))
        {
            await _metadataStore.SetProjectIterationTraceabilityAnchorAsync(
                sessionId,
                BuildTraceabilityAnchorJson(sessionId, planHash, sourceHashRef, ReadNodeString(existing, "confirmed_by"), ReadNodeString(existing, "confirmed_utc")),
                cancellationToken);
            _routeStateWriter.WriteIterationPlanSessionState(project, sessionId, state);
            return new PrototypeIterationPlanConfirmationOperationResult(
                "confirmed",
                "",
                "The current plan was already confirmed.",
                "returned_existing",
                ReadConfirmation(existing));
        }

        var confirmedUtc = DateTimeOffset.UtcNow.ToString("O");
        var scopeMarker = $"scope-{ComputeHash($"{accountId}|{projectId}")[..16]}";
        var confirmationNode = new JsonObject
        {
            ["status"] = "confirmed",
            ["session_id"] = sessionId,
            ["plan_hash"] = planHash,
            ["source_hash_ref"] = sourceHashRef,
            ["confirmed_by"] = scopeMarker,
            ["confirmed_utc"] = confirmedUtc
        };
        state["confirmation"] = confirmationNode;
        state["updated_utc"] = confirmedUtc;
        await _metadataStore.SetProjectIterationTraceabilityAnchorAsync(
            sessionId,
            BuildTraceabilityAnchorJson(sessionId, planHash, sourceHashRef, scopeMarker, confirmedUtc),
            cancellationToken);
        _routeStateWriter.WriteIterationPlanSessionState(project, sessionId, state);
        _routeStateWriter.WriteIterationPlanState(project, state);
        return new PrototypeIterationPlanConfirmationOperationResult(
            "confirmed",
            "",
            "The current hash-bound plan is confirmed.",
            "created_run",
            ReadConfirmation(confirmationNode));
    }

    private static PrototypeIterationPlanConfirmationResult ReadConfirmation(JsonObject node)
    {
        return new PrototypeIterationPlanConfirmationResult(
            ReadNodeString(node, "status", "unknown"),
            ReadNodeString(node, "session_id"),
            ReadNodeString(node, "plan_hash"),
            ReadNodeString(node, "source_hash_ref"),
            ReadNodeString(node, "confirmed_by"),
            ReadNodeString(node, "confirmed_utc"));
    }

    private static string BuildTraceabilityAnchorJson(
        string sessionId,
        string planHash,
        string sourceHashRef,
        string confirmedBy,
        string confirmedUtc)
    {
        return JsonSerializer.Serialize(new
        {
            status = "confirmed",
            session_id = sessionId,
            plan_hash = planHash,
            source_hash_ref = sourceHashRef,
            confirmed_by = confirmedBy,
            confirmed_utc = confirmedUtc
        });
    }

    private static PrototypeIterationPlanConfirmationResult? TryReadTraceabilityAnchor(string? anchorJson)
    {
        if (string.IsNullOrWhiteSpace(anchorJson))
        {
            return null;
        }
        try
        {
            using var document = JsonDocument.Parse(anchorJson);
            var root = document.RootElement;
            if (!string.Equals(ReadRouteString(root, "status"), "confirmed", StringComparison.Ordinal))
            {
                return null;
            }
            var result = new PrototypeIterationPlanConfirmationResult(
                "confirmed",
                ReadRouteString(root, "session_id"),
                ReadRouteString(root, "plan_hash"),
                ReadRouteString(root, "source_hash_ref"),
                ReadRouteString(root, "confirmed_by"),
                ReadRouteString(root, "confirmed_utc"));
            return new[] { result.SessionId, result.PlanHash, result.SourceHashRef, result.ConfirmedBy, result.ConfirmedUtc }
                .All(value => !string.IsNullOrWhiteSpace(value))
                ? result
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static JsonObject ToConfirmationNode(PrototypeIterationPlanConfirmationResult confirmation)
    {
        return new JsonObject
        {
            ["status"] = confirmation.Status,
            ["session_id"] = confirmation.SessionId,
            ["plan_hash"] = confirmation.PlanHash,
            ["source_hash_ref"] = confirmation.SourceHashRef,
            ["confirmed_by"] = confirmation.ConfirmedBy,
            ["confirmed_utc"] = confirmation.ConfirmedUtc
        };
    }

    private static PrototypeIterationPlanConfirmationResult? ProjectConfirmationFromTrustedAnchor(
        PrototypeIterationPlanConfirmationResult? routeConfirmation,
        string? anchorJson)
    {
        if (routeConfirmation is null)
        {
            return routeConfirmation;
        }
        var trusted = TryReadTraceabilityAnchor(anchorJson);
        if (trusted is not null &&
            string.Equals(trusted.SessionId, routeConfirmation.SessionId, StringComparison.Ordinal) &&
            string.Equals(trusted.PlanHash, routeConfirmation.PlanHash, StringComparison.Ordinal) &&
            string.Equals(trusted.SourceHashRef, routeConfirmation.SourceHashRef, StringComparison.Ordinal))
        {
            return trusted;
        }
        if (!string.Equals(routeConfirmation.Status, "confirmed", StringComparison.Ordinal))
        {
            return routeConfirmation;
        }
        return routeConfirmation with
        {
            Status = "reconfirm_required",
            ConfirmedBy = "",
            ConfirmedUtc = ""
        };
    }

    internal static string ProjectStateFromTrustedAnchor(string stateText, string? anchorJson)
    {
        if (string.IsNullOrWhiteSpace(stateText) || string.IsNullOrWhiteSpace(anchorJson))
        {
            return stateText;
        }
        try
        {
            var state = JsonNode.Parse(stateText)?.AsObject();
            if (state is null)
            {
                return stateText;
            }
            var sessionId = ReadNodeString(state, "session_id");
            var routeConfirmation = state["confirmation"] is JsonObject confirmationNode
                ? ReadConfirmation(confirmationNode)
                : new PrototypeIterationPlanConfirmationResult(
                    "unconfirmed",
                    sessionId,
                    ReadNodeString(state, "plan_hash"),
                    ReadNodeString(state, "source_hash_ref"),
                    "",
                    "");
            var projected = ProjectConfirmationFromTrustedAnchor(routeConfirmation, anchorJson);
            if (projected is null || !string.Equals(projected.Status, "confirmed", StringComparison.Ordinal))
            {
                return stateText;
            }
            state["confirmation"] = ToConfirmationNode(projected);
            return state.ToJsonString(new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true });
        }
        catch (Exception ex) when (ex is JsonException or InvalidOperationException)
        {
            return stateText;
        }
    }

    internal static string RestoreCurrentPlanState(
        ProjectSnapshot project,
        ProjectIterationSessionDetails details,
        PrototypeRouteStateWriter routeStateWriter,
        string stateText)
    {
        var current = TryReadStateForSession(stateText, details.Session.SessionId);
        var databaseState = TryReadStateForSession(details.Session.RouteStateJson ?? "", details.Session.SessionId);
        var restoredFromDatabase = false;
        if (current is null)
        {
            current = databaseState;
            restoredFromDatabase = current is not null;
        }

        if (current is null)
        {
            return stateText;
        }

        var canonical = current.ToJsonString(new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true });
        if (restoredFromDatabase)
        {
            routeStateWriter.WriteIterationPlanSessionState(project, details.Session.SessionId, current);
            routeStateWriter.WriteIterationPlanState(project, current);
        }
        if (databaseState is not null)
        {
            RestoreInteractionArtifacts(project, databaseState, routeStateWriter);
        }
        return canonical;
    }

    private static JsonObject? TryReadStateForSession(string stateText, string sessionId)
    {
        if (string.IsNullOrWhiteSpace(stateText))
        {
            return null;
        }

        try
        {
            var state = JsonNode.Parse(stateText)?.AsObject();
            return state is not null &&
                   string.Equals(ReadNodeString(state, "session_id"), sessionId, StringComparison.Ordinal)
                ? state
                : null;
        }
        catch (Exception ex) when (ex is JsonException or InvalidOperationException)
        {
            return null;
        }
    }

    private static void RestoreInteractionArtifacts(
        ProjectSnapshot project,
        JsonObject state,
        PrototypeRouteStateWriter routeStateWriter)
    {
        var goals = DeserializeRouteValue<IReadOnlyList<PrototypeIterationPlanGoalResult>>(state["goals"]) ?? [];
        foreach (var goal in goals.Where(static item => item.InteractionRegion is not null))
        {
            var interaction = goal.InteractionRegion!;
            var artifactPath = Path.Combine(project.RepoPath, interaction.ArtifactRef.Replace('/', Path.DirectorySeparatorChar));
            var owners = interaction.OwnerRefs;
            if (File.Exists(artifactPath))
            {
                try
                {
                    using var existing = JsonDocument.Parse(File.ReadAllText(artifactPath, Encoding.UTF8));
                    if (IterationPlanInteractionArtifactValidator.IsValidatedArtifact(
                            existing.RootElement,
                            goal.GoalIndex,
                            goal.RequirementIds ?? [],
                            goal.SourceHashRef,
                            owners,
                            interaction.Devices,
                            interaction.ValidRegions,
                            interaction.InvalidRegions,
                            interaction.StateTransitions,
                            interaction.ValidationRefs,
                            interaction.PlannedGeometry,
                            goal.EngineSemantics?.CoordinateSemantics ?? "project-profile-coordinate-semantics"))
                    {
                        continue;
                    }
                }
                catch (Exception ex) when (ex is JsonException or IOException or UnauthorizedAccessException)
                {
                }
            }

            var candidate = new
            {
                schema_version = "godot-interaction-region.v1",
                route = "iteration-plan",
                goal_index = goal.GoalIndex,
                requirement_ids = goal.RequirementIds ?? [],
                scene_node_owners = owners,
                artifact_form = "planned-godot-node-map",
                evidence_kind = "pre-execution-design-contract",
                validation_status = "pending",
                validation_method = "",
                runtime_validation_required = true,
                coordinate_semantics = goal.EngineSemantics?.CoordinateSemantics ?? "project-profile-coordinate-semantics",
                devices = interaction.Devices,
                valid_regions = interaction.ValidRegions,
                invalid_regions = interaction.InvalidRegions,
                state_transitions = interaction.StateTransitions,
                validation_refs = interaction.ValidationRefs,
                owner_refs = owners,
                planned_geometry = interaction.PlannedGeometry.Select(ToInteractionGeometryState).ToArray(),
                region_map = IterationPlanInteractionArtifactValidator.BuildRegionMap(
                    owners,
                    interaction.ValidRegions,
                    interaction.InvalidRegions,
                    interaction.StateTransitions),
                source_hash_ref = goal.SourceHashRef,
                updated_utc = DateTimeOffset.UtcNow.ToString("O")
            };
            routeStateWriter.WriteIterationPlanInteractionRegionState(project, goal.GoalIndex, candidate, interaction.ArtifactRef);
            var validation = IterationPlanInteractionArtifactValidator.ValidateCandidate(
                project.RepoPath,
                interaction.ArtifactRef,
                goal.GoalIndex,
                goal.RequirementIds ?? [],
                goal.SourceHashRef,
                owners,
                interaction.PlannedGeometry,
                goal.EngineSemantics?.CoordinateSemantics ?? "project-profile-coordinate-semantics");
            if (validation.Allowed && validation.ValidatedPayload is not null)
            {
                routeStateWriter.WriteIterationPlanInteractionRegionState(
                    project,
                    goal.GoalIndex,
                    validation.ValidatedPayload,
                    interaction.ArtifactRef);
            }
        }
    }

    private static string ReadNodeString(JsonObject node, string propertyName, string fallback = "")
    {
        return node[propertyName] is JsonValue value && value.TryGetValue<string>(out var text)
            ? text ?? fallback
            : fallback;
    }

    private static string ComputeHash(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private async Task<PrototypeIterationPlanResult?> TryReuseCurrentPlanAsync(
        ProjectSnapshot project,
        string requestIdentityHash,
        PrototypeIterationPlanSourceHashes sourceHashes,
        CancellationToken cancellationToken,
        bool requireLatestSession = true)
    {
        var stateText = _routeStateWriter.ReadLatestIterationPlanState(project);
        JsonObject? state = null;
        var recoveredFromDatabase = false;
        try
        {
            state = JsonNode.Parse(stateText)?.AsObject();
        }
        catch (Exception ex) when (ex is JsonException or InvalidOperationException)
        {
            state = null;
        }

        if (state is null ||
            !string.Equals(ReadNodeString(state, "request_identity_hash"), requestIdentityHash, StringComparison.Ordinal) ||
            !string.Equals(ReadNodeString(state, "status"), "ready", StringComparison.Ordinal))
        {
            var persisted = await _metadataStore.GetProjectIterationSessionByRequestIdentityAsync(
                project.AccountId,
                project.ProjectId,
                requestIdentityHash,
                cancellationToken);
            if (persisted is null || string.IsNullOrWhiteSpace(persisted.Session.RouteStateJson))
            {
                return null;
            }

            stateText = persisted.Session.RouteStateJson;
            try
            {
                state = JsonNode.Parse(stateText)?.AsObject();
            }
            catch (Exception ex) when (ex is JsonException or InvalidOperationException)
            {
                return null;
            }
            if (state is null ||
                !string.Equals(ReadNodeString(state, "request_identity_hash"), requestIdentityHash, StringComparison.Ordinal) ||
                !string.Equals(ReadNodeString(state, "session_id"), persisted.Session.SessionId, StringComparison.Ordinal) ||
                !string.Equals(ReadNodeString(state, "status"), "ready", StringComparison.Ordinal))
            {
                return null;
            }

            recoveredFromDatabase = true;
        }

        var sessionId = ReadNodeString(state, "session_id");
        var details = await _metadataStore.GetProjectIterationSessionAsync(project.ProjectId, sessionId, cancellationToken);
        if (details is null ||
            !string.Equals(details.Session.AccountId, project.AccountId, StringComparison.Ordinal) ||
            !string.Equals(details.Session.RequestIdentityHash, requestIdentityHash, StringComparison.Ordinal))
        {
            return null;
        }

        var latest = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken);
        var isLatestSession = latest is not null &&
            string.Equals(latest.Session.SessionId, sessionId, StringComparison.Ordinal);
        if (requireLatestSession && !isLatestSession)
        {
            return null;
        }
        if (isLatestSession)
        {
            stateText = RestoreCurrentPlanState(project, details, _routeStateWriter, stateText);
            state = JsonNode.Parse(stateText)?.AsObject() ?? state;
        }

        var routeContext = TryReadCurrentIterationRouteContext(stateText, sessionId);
        var confirmation = state["confirmation"] is JsonObject confirmationNode
            ? ReadConfirmation(confirmationNode)
            : new PrototypeIterationPlanConfirmationResult("unconfirmed", sessionId, ReadNodeString(state, "plan_hash"), ReadNodeString(state, "source_hash_ref"), "", "");
        var projectedConfirmation = ProjectConfirmationFromTrustedAnchor(confirmation, details.Session.TraceabilityAnchorJson);
        if (recoveredFromDatabase && isLatestSession && projectedConfirmation is not null)
        {
            state["confirmation"] = ToConfirmationNode(projectedConfirmation);
            stateText = state.ToJsonString(new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true });
            _routeStateWriter.WriteIterationPlanState(project, state);
            _routeStateWriter.WriteIterationPlanSessionState(project, details.Session.SessionId, state);
        }
        var enrichedGoals = DeserializeRouteValue<IReadOnlyList<PrototypeIterationPlanGoalResult>>(state["goals"]) ?? [];
        var coverage = DeserializeRouteValue<PrototypeIterationPlanCoverageResult>(state["coverage"]);
        var blockers = DeserializeRouteValue<IReadOnlyList<PrototypeIterationPlanBlockerResult>>(state["blockers"]) ?? [];
        var styleApplicability = DeserializeRouteValue<PrototypeIterationStyleApplicability>(state["style_applicability"]);
        return new PrototypeIterationPlanResult(
            sessionId,
            "ready",
            details.Session.LatestSummary ?? "Existing iteration plan returned.",
            enrichedGoals,
            routeContext.PlanningAnalysis,
            details.LatestEvaluation,
            routeContext.RequiredModules,
            "returned_existing",
            ReadNodeString(state, "plan_hash"),
            sourceHashes,
            coverage,
            blockers,
            projectedConfirmation,
            styleApplicability);
    }

    private static T? DeserializeRouteValue<T>(JsonNode? node)
    {
        if (node is null)
        {
            return default;
        }
        try
        {
            return JsonSerializer.Deserialize<T>(node.ToJsonString(), new JsonSerializerOptions(JsonSerializerDefaults.Web)
            {
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
                PropertyNameCaseInsensitive = true
            });
        }
        catch (JsonException)
        {
            return default;
        }
    }

    private async Task<IterationGoalBuildResult> BuildGoalsForProjectAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IGameTypeRouteStrategy routeStrategy,
        PrototypeContractSnapshot prototypeContract,
        string message,
        string sourceKind,
        IterationPlanningContext planningContext,
        string? regenerationGuidance,
        GenericCoreLoopGateResult genericCoreLoopGate,
        string model,
        CancellationToken cancellationToken)
    {
        if (routeStrategy.UsesSpecializedIterationPlanning &&
            string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            var scaffold = BuildRpgGoalsFromContext(message, sourceKind, prototypeContract, planningContext, regenerationGuidance);
            if (IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
            {
                return new IterationGoalBuildResult(scaffold, false);
            }

            var refined = await RefineRpgGoalsWithRequiredModelAsync(project, routeProfile, planningContext, message, sourceKind, scaffold, regenerationGuidance, model, cancellationToken);
            return refined with
            {
                Goals = EnsureJrpgExplicitRuleCoverage(refined.Goals, prototypeContract, message, regenerationGuidance)
            };
        }

        if (routeStrategy.UsesSpecializedIterationPlanning &&
            string.Equals(routeStrategy.GameTypeId, "survivorslike", StringComparison.OrdinalIgnoreCase))
        {
            return new IterationGoalBuildResult(BuildSurvivorsLikeFirstLoopGoals(message, prototypeContract, regenerationGuidance), false);
        }

        if (routeStrategy.UsesSpecializedIterationPlanning &&
            string.Equals(routeStrategy.GameTypeId, "deckbuilder", StringComparison.OrdinalIgnoreCase))
        {
            return new IterationGoalBuildResult(BuildDeckbuilderFirstLoopGoals(message, prototypeContract, regenerationGuidance), false);
        }

        var goals = BuildGoals(message, sourceKind);
        return new IterationGoalBuildResult(AppendGenericFinalAcceptanceGoal(goals, message, prototypeContract), false);
    }

    private async Task<IterationPlanningContext> BuildPlanningContextAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IGameTypeRouteStrategy routeStrategy,
        PrototypeContractSnapshot prototypeContract,
        string message,
        string sourceKind,
        string? regenerationGuidance,
        string model,
        CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var latestPrototypeRun = runs
            .FirstOrDefault(run => string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase));
        var latestSuccessfulPrototypeRun = runs
            .FirstOrDefault(run =>
                string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase));
        var draft = await _metadataStore.GetProjectPrototypeDraftAsync(project.ProjectId, cancellationToken);
        var prototypeState = _routeStateWriter.ReadLatestPrototypeState(project);
        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, prototypeContract);
        var template = _templateCatalog?.Find(ResolveCanonicalGameType(project));

        var deterministicFieldCoverage = BuildDeterministicFieldCoverage(draft);
        var fallback = new IterationPlanningContext(
            AnalysisSource: "deterministic_fallback",
            AnalysisSummary: BuildFallbackAnalysisSummary(latestPrototypeRun, latestSuccessfulPrototypeRun, draft),
            LatestPrototypeStatus: latestPrototypeRun?.Status ?? "missing",
            LatestPrototypeCompletionSummary: ReadCompletionSummaryFromRun(latestSuccessfulPrototypeRun ?? latestPrototypeRun),
            DraftCoveragePercent: draft?.CoveragePercent ?? 0,
            DraftCoverageSummary: draft?.CoverageSummary,
            TemplateId: template?.TemplateId,
            FieldCoverage: deterministicFieldCoverage,
            PrototypeStateExcerpt: TrimForPrompt(prototypeState),
            SourceMessage: message,
            SourceKind: sourceKind,
            StageTelemetry: []);

        if (AllowsSoftPlanningAnalysisFallback(routeStrategy))
        {
            return fallback with
            {
                AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, "planning_analysis_skipped_for_rpg_route"),
                StageTelemetry = [BuildSkippedTelemetry("planning-analysis", model, "planning_analysis_skipped_for_rpg_route")]
            };
        }

        if (_llmRouteEngine is null)
        {
            if (routeStrategy.RequiresModelBackedIterationPlanning &&
                !AllowsSoftPlanningAnalysisFallback(routeStrategy) &&
                !IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
            {
                throw new PrototypeIterationPlanLlmException("planning_analysis_llm_client_missing");
            }

            return fallback;
        }

        var modelPrompt = BuildPlanningAnalysisPrompt(project, routeProfile, projectExecutionGuide, prototypeContract, fallback, draft, latestPrototypeRun, latestSuccessfulPrototypeRun);
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "planning-analysis");
        var options = PlanningCodexOptions with { OutputSchemaPath = PlanningAnalysisSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "planning-analysis",
                model,
                modelPrompt,
                options,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            if (routeStrategy.RequiresModelBackedIterationPlanning &&
                !AllowsSoftPlanningAnalysisFallback(routeStrategy) &&
                !IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
            {
                throw new PrototypeIterationPlanLlmException(completion.FailureCode ?? "planning_analysis_llm_failed");
            }

            return fallback with
            {
                AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, completion.FailureCode),
                StageTelemetry = [BuildTelemetry("planning-analysis", completion)]
            };
        }

        var parsed = TryParsePlanningContext(completion.JsonObjectText ?? completion.AssistantMessage, fallback);
        if (parsed is null &&
            routeStrategy.RequiresModelBackedIterationPlanning &&
            !AllowsSoftPlanningAnalysisFallback(routeStrategy) &&
            !IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
        {
            throw new PrototypeIterationPlanLlmException("planning_analysis_parse_failed");
        }

        var telemetry = BuildTelemetry("planning-analysis", completion);
        if (parsed is not null)
        {
            return parsed with { StageTelemetry = [telemetry] };
        }

        return fallback with
        {
            AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, "planning_analysis_parse_failed"),
            StageTelemetry = [telemetry]
        };
    }

    private async Task<IterationGoalBuildResult> RefineRpgGoalsWithRequiredModelAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IterationPlanningContext planningContext,
        string message,
        string sourceKind,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold,
        string? regenerationGuidance,
        string model,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            throw new PrototypeIterationPlanLlmException("goal_plan_llm_client_missing");
        }

        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, _contractService.Read(project));
        var prompt = BuildRpgGoalRefinementPrompt(project, routeProfile, projectExecutionGuide, planningContext, message, scaffold, regenerationGuidance);
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "goal-plan");
        var options = PlanningCodexOptions with { OutputSchemaPath = GoalPlanSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "goal-plan",
                model,
                prompt,
                options,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            throw new PrototypeIterationPlanLlmException(completion.FailureCode ?? "goal_plan_llm_failed");
        }

        var parsed = ParseRefinedRpgGoalPlan(completion.JsonObjectText ?? completion.AssistantMessage, scaffold);
        if (parsed.Goals.Count == 0)
        {
            if (string.Equals(sourceKind, "new_iteration_plan", StringComparison.OrdinalIgnoreCase))
            {
                return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true)
                {
                    StageTelemetry = [BuildTelemetry("goal-plan", completion)]
                };
            }

            throw new PrototypeIterationPlanLlmException("goal_plan_parse_failed");
        }

        return parsed with
        {
            StageTelemetry = [BuildTelemetry("goal-plan", completion)]
        };
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgGoalsFromContext(
        string message,
        string sourceKind,
        PrototypeContractSnapshot prototypeContract,
        IterationPlanningContext planningContext,
        string? regenerationGuidance)
    {
        if (string.Equals(planningContext.LatestPrototypeStatus, "succeeded", StringComparison.OrdinalIgnoreCase))
        {
            return BuildRpgClosureGoals(planningContext, prototypeContract, regenerationGuidance);
        }

        var goals = BuildGoals(message, sourceKind);
        _ = goals;
        return BuildJrpgFirstLoopGoals(message, planningContext, prototypeContract, regenerationGuidance);
    }

    private static bool AllowsSoftPlanningAnalysisFallback(IGameTypeRouteStrategy routeStrategy)
    {
        return routeStrategy.UsesSpecializedIterationPlanning &&
            string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgClosureGoals(IterationPlanningContext planningContext, PrototypeContractSnapshot prototypeContract, string? regenerationGuidance)
    {
        return BuildJrpgFirstLoopGoals(planningContext.SourceMessage, planningContext, prototypeContract, regenerationGuidance);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildNavigationFirstRpgClosureGoals(IterationPlanningContext planningContext, string? regenerationGuidance)
    {
        return BuildJrpgFirstLoopGoals(planningContext.SourceMessage, planningContext, null, regenerationGuidance);
    }

    private static string BuildPlanSummary(int goalCount, IterationPlanningContext planningContext, bool usedScaffoldFallback)
    {
        var prototypeStatus = string.IsNullOrWhiteSpace(planningContext.LatestPrototypeStatus)
            ? "unknown"
            : planningContext.LatestPrototypeStatus;
        var coverage = planningContext.DraftCoveragePercent;
        var degraded = usedScaffoldFallback ? " model_plan_degraded=scaffold_fallback." : "";
        return $"已基于当前原型状态与需求覆盖分析生成 {goalCount} 个游戏模块任务。当前原型状态：{prototypeStatus}；表单覆盖率：{coverage}%。请先执行任务 1，再逐步推进后续任务。{degraded}";
    }

    private static string BuildFallbackAnalysisSummary(RunSnapshot? latestPrototypeRun, RunSnapshot? latestSuccessfulPrototypeRun, ProjectPrototypeDraftSnapshot? draft)
    {
        var prototypeStatus = latestSuccessfulPrototypeRun is not null
            ? "已存在成功原型，可优先做收敛型迭代。"
            : latestPrototypeRun is not null
                ? $"最近一次原型状态为 {latestPrototypeRun.Status}，仍需保留基础收敛步骤。"
                : "尚未发现已完成的原型运行记录。";
        var draftSummary = draft is null
            ? "当前没有草稿覆盖率分析。"
            : $"最近草稿覆盖率约为 {draft.CoveragePercent}%。";
        return $"{prototypeStatus}{draftSummary}";
    }

    private static string AppendFailureNote(string summary, string? failureCode)
    {
        return string.IsNullOrWhiteSpace(failureCode)
            ? summary
            : $"{summary} 模型分析降级为本地规则，原因：{failureCode}。";
    }

    private static string BuildPlanningAnalysisPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        string projectExecutionGuide,
        PrototypeContractSnapshot prototypeContract,
        IterationPlanningContext fallback,
        ProjectPrototypeDraftSnapshot? draft,
        RunSnapshot? latestPrototypeRun,
        RunSnapshot? latestSuccessfulPrototypeRun)
    {
        var draftJson = draft is null
            ? "{}"
            : JsonSerializer.Serialize(new
            {
                draft.PrototypeSlug,
                Hypothesis = CompactForPrompt(draft.Hypothesis, 600),
                CorePlayerFantasy = CompactForPrompt(draft.CorePlayerFantasy, 600),
                MinimumPlayableLoop = CompactForPrompt(draft.MinimumPlayableLoop, 800),
                SuccessCriteria = DeserializeJsonArray(draft.SuccessCriteriaJson).Select(item => CompactForPrompt(item, 300)).Take(6).ToArray(),
                GameFeature = CompactForPrompt(draft.GameFeature, 800),
                CoreGameplayLoop = CompactForPrompt(draft.CoreGameplayLoop, 800),
                WinFailConditions = CompactForPrompt(draft.WinFailConditions, 600),
                draft.CoveragePercent,
                CoverageSummary = CompactForPrompt(draft.CoverageSummary, 600),
                CoverageMissingTopics = DeserializeJsonArray(draft.CoverageMissingTopicsJson).Select(item => CompactForPrompt(item, 220)).Take(8).ToArray()
            });
        var runJson = JsonSerializer.Serialize(new
        {
            latest_run_status = latestPrototypeRun?.Status,
            latest_run_summary = CompactForPrompt(ReadCompletionSummaryFromRun(latestPrototypeRun), 1000),
            latest_successful_status = latestSuccessfulPrototypeRun?.Status,
            latest_successful_summary = CompactForPrompt(ReadCompletionSummaryFromRun(latestSuccessfulPrototypeRun), 1000),
            fallback_analysis = CompactForPrompt(fallback.AnalysisSummary, 800)
        });
        var contractSummary = string.IsNullOrWhiteSpace(prototypeContract.Json)
            ? "{}"
            : JsonSerializer.Serialize(new
            {
                prototypeContract.RelativePath,
                present = true,
                excerpt = CompactForPrompt(prototypeContract.Json, 1000)
            });

        return $"""
            You are analyzing a hosted Godot prototype after prototype creation has already run.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            analysisSummary, fieldCoverage.

            fieldCoverage must be an array of objects with:
            field, status, evidence, missingReason

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - Use Prototype Chapter 3 Lite semantics: split small ordered prototype goals from context without creating Taskmaster triplets, formal task files, overlays, formal acceptance files, or architecture contracts.
            - Treat the Project execution guide below as the project-level /new recovery protocol, especially its Route Recovery Protocol section.
            - Recover route memory in this order: route profile, Project execution guide, prototype contract, latest prototype state, draft/form snapshot, and latest prototype run evidence.
            - Do not use AGENTS.md as hosted game-project recovery memory.
            - status must be one of completed, partial, missing.
            - Judge completion against the current prototype result, not only the form text.
            - Focus on prototype-form fields, the GDD-derived prototype contract, and the current route profile. Do not force template sections that are not implied by the project semantics.
            - Keep evidence and missingReason short and browser-safe.
            - Player-visible text rule for planning: any future goal that creates or changes in-game Godot text should require Chinese player-visible text by default, while preserving English code identifiers, fixed node names, resource paths, tests, logs, and platform validation names.
            - When suggesting implementation work, prefer a lightweight prototype split: PrototypeRoot orchestration, State/Data, gameplay Systems, and View components such as HudView, MapView, BattleView, RewardView, ActorView, or LogView.
            - Treat components as Godot Node/scene responsibility boundaries, not ECS. Do not ask for ECS, EntityComponent, IComponent, or a new framework.
            - Prefer exported NodePath bindings or one local binding pass for stable scene references instead of planning repeated long GetNode("CanvasLayer/...") strings.
            - Prefer direct calls, Godot signals, or C# events inside one prototype; use EventBus only when a goal clearly needs global cross-route notification.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - TemplateId: {fallback.TemplateId}
            - GameTypeProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}
            - SourceBoundary: GDD-derived contract only after GDD generation; do not use route skill documents as gameplay sources.

            Source message:
            {CompactForPrompt(fallback.SourceMessage, 1600)}

            Project execution guide:
            {CompactForPrompt(projectExecutionGuide, 1200)}

            Prototype contract:
            {contractSummary}

            Draft/form snapshot:
            {draftJson}

            Prototype run snapshot:
            {runJson}

            Prototype route state excerpt:
            {CompactForPrompt(fallback.PrototypeStateExcerpt, 1200)}
            """;
    }

    private static string BuildRpgGoalRefinementPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        string projectExecutionGuide,
        IterationPlanningContext planningContext,
        string message,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold,
        string? regenerationGuidance)
    {
        var analysisJson = JsonSerializer.Serialize(new
        {
            planningContext.AnalysisSummary,
            planningContext.LatestPrototypeStatus,
            planningContext.LatestPrototypeCompletionSummary,
            planningContext.DraftCoveragePercent,
            planningContext.DraftCoverageSummary,
            planningContext.TemplateId,
            fieldCoverage = planningContext.FieldCoverage
        });
        var scaffoldJson = JsonSerializer.Serialize(scaffold.Select(goal => new
        {
            goal.GoalIndex,
            goal.Title,
            goal.Description,
            goal.AcceptanceHint
        }).ToArray());

        return $"""
            You are refining a server-generated iteration plan for a JRPG first-loop Godot prototype route.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            goals

            goals must be an array with the exact same number of items as the scaffold, and each object must contain:
            title, description, acceptanceHint

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - Use Prototype Chapter 3 Lite semantics: refine the lightweight iteration plan only, without creating Taskmaster triplets, formal task files, overlays, formal acceptance files, or architecture contracts.
            - Treat the Project execution guide below as the project-level /new recovery protocol, especially its Route Recovery Protocol section.
            - Recover route memory in this order: route profile, Project execution guide, prototype contract, latest prototype state, planning analysis, and scaffold.
            - Do not use AGENTS.md as hosted game-project recovery memory.
            - Do not generate a new plan from scratch.
            - Keep the exact scaffold order.
            - Keep every title exactly unchanged from the scaffold.
            - description and acceptanceHint are browser-facing fields. They must be written in Simplified Chinese by default; English is allowed only for code identifiers, fixed node names, resource paths, tests, logs, route ids, and platform validation names.
            - Only refine description and acceptanceHint so they better reflect the current prototype state, prototype-form coverage, and GDD-derived prototype contract.
            - If the prototype already succeeded once, keep the convergence/closure framing already present in the scaffold.
            - If some user fields are still only partial, mention the most important missing runtime proof in the relevant later steps.
            - Keep each goal narrow enough to execute independently.
            - Treat the GDD-derived prototype contract as the gameplay source of truth, not a fixed DQ-like script or external type guide.
            - If the prototype contract or user fields mention encounter, enemy, monster, boss, combat, battle, fight, challenge, reward, item, experience, level, loot, or return-to-map, preserve those contract-specific capabilities without adding unrelated template requirements.
            - Only omit BattleScene, enemy asset, reward, or return-loop capability when the project contract explicitly negates combat/conflict/reward, such as non-combat, no battle, no encounter, no enemy, or without reward choices.
            - The scaffold is a semantic capability graph. Do not add, remove, or reorder capabilities.
            - If a goal creates or changes any player-visible Godot text, its description or acceptanceHint must preserve this rule: Label, Button, RichTextLabel, HUD, menus, battle logs, quest prompts, result prompts, and win/fail/error prompts default to Chinese; code identifiers, fixed node names, resource paths, tests, logs, and platform validation names remain English.
            - When refining implementation goals, prefer a lightweight prototype split: PrototypeRoot orchestration, State/Data, gameplay Systems, and View components such as HudView, MapView, BattleView, RewardView, ActorView, or LogView.
            - Treat components as Godot Node/scene responsibility boundaries, not ECS. Do not ask for ECS, EntityComponent, IComponent, or a new framework.
            - Prefer exported NodePath bindings or one local binding pass for stable scene references instead of repeated long GetNode("CanvasLayer/...") strings.
            - Prefer direct calls, Godot signals, or C# events inside one prototype; reserve EventBus for true global notifications or future promotion candidates.
            - Final step must remain final first-loop acceptance.
            - If regeneration guidance is provided, treat it as a hard constraint from the previous plan evaluation.
            - When regeneration guidance says the current blocker is Start Adventure, visible MapScene, or stable movement, goal 1 must remain focused on that blocker.
            - When regeneration guidance says the current blocker is encounter entry or encounter trigger, keep conflict entry separate from navigation and battle/challenge resolution.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - GameTypeProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}

            Requested optimization:
            {CompactForPrompt(message, 1800)}

            Regeneration guidance from previous plan evaluation:
            {(string.IsNullOrWhiteSpace(regenerationGuidance) ? "none" : CompactForPrompt(regenerationGuidance, 1200))}

            Project execution guide:
            {CompactForPrompt(projectExecutionGuide, 1800)}

            Planning analysis:
            {analysisJson}

            Goal scaffold that must be preserved:
            {scaffoldJson}
            """;
    }

    private static IterationPlanningContext? TryParsePlanningContext(string? assistantMessage, IterationPlanningContext fallback)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return null;
        }

        try
        {
            var json = LlmRouteEngine.ExtractFirstJsonObject(assistantMessage) ?? assistantMessage;
            using var document = JsonDocument.Parse(json);
            var root = document.RootElement;
            var summary = root.TryGetProperty("analysisSummary", out var summaryElement) && summaryElement.ValueKind == JsonValueKind.String
                ? summaryElement.GetString() ?? fallback.AnalysisSummary
                : fallback.AnalysisSummary;
            var coverage = root.TryGetProperty("fieldCoverage", out var coverageElement) && coverageElement.ValueKind == JsonValueKind.Array
                ? coverageElement.EnumerateArray().Select(item => new PlanningFieldCoverage(
                    item.TryGetProperty("field", out var fieldElement) && fieldElement.ValueKind == JsonValueKind.String ? fieldElement.GetString() ?? "" : "",
                    item.TryGetProperty("status", out var statusElement) && statusElement.ValueKind == JsonValueKind.String ? statusElement.GetString() ?? "missing" : "missing",
                    item.TryGetProperty("evidence", out var evidenceElement) && evidenceElement.ValueKind == JsonValueKind.String ? evidenceElement.GetString() : null,
                    item.TryGetProperty("missingReason", out var missingElement) && missingElement.ValueKind == JsonValueKind.String ? missingElement.GetString() : null))
                    .Where(item => !string.IsNullOrWhiteSpace(item.Field))
                    .ToArray()
                : fallback.FieldCoverage;
            return fallback with
            {
                AnalysisSource = "codex_exec",
                AnalysisSummary = summary,
                FieldCoverage = coverage.Count == 0 ? fallback.FieldCoverage : coverage
            };
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static List<PrototypeIterationPlanGoalResult> ParseGoalPlan(string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return [];
        }

        try
        {
            var json = LlmRouteEngine.ExtractFirstJsonObject(assistantMessage) ?? assistantMessage;
            using var document = JsonDocument.Parse(json);
            if (!document.RootElement.TryGetProperty("goals", out var goalsElement) || goalsElement.ValueKind != JsonValueKind.Array)
            {
                return [];
            }

            var goals = new List<PrototypeIterationPlanGoalResult>();
            var index = 1;
            foreach (var item in goalsElement.EnumerateArray())
            {
                var title = item.TryGetProperty("title", out var titleElement) && titleElement.ValueKind == JsonValueKind.String
                    ? titleElement.GetString()
                    : null;
                var description = item.TryGetProperty("description", out var descriptionElement) && descriptionElement.ValueKind == JsonValueKind.String
                    ? descriptionElement.GetString()
                    : null;
                var acceptance = item.TryGetProperty("acceptanceHint", out var acceptanceElement) && acceptanceElement.ValueKind == JsonValueKind.String
                    ? acceptanceElement.GetString()
                    : null;
                if (string.IsNullOrWhiteSpace(title) || string.IsNullOrWhiteSpace(description) || string.IsNullOrWhiteSpace(acceptance))
                {
                    continue;
                }

                goals.Add(new PrototypeIterationPlanGoalResult(index++, title.Trim(), description.Trim(), acceptance.Trim(), "pending"));
            }

            return goals;
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static IterationGoalBuildResult ParseRefinedRpgGoalPlan(
        string? assistantMessage,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        var parsed = ParseGoalPlan(assistantMessage);
        if (parsed.Count == 0 &&
            !string.IsNullOrWhiteSpace(assistantMessage) &&
            scaffold.All(goal => assistantMessage.Contains(goal.Title, StringComparison.Ordinal)))
        {
            return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
        }

        if (parsed.Count < scaffold.Count)
        {
            if (IsAcceptableJrpgScaffoldSubset(parsed, scaffold))
            {
                return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
            }

            return new IterationGoalBuildResult([], false);
        }

        if (IsRecoverableJrpgScaffoldResponse(parsed, scaffold))
        {
            return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
        }

        var refined = new List<PrototypeIterationPlanGoalResult>(scaffold.Count);
        var parsedByTitle = parsed
            .GroupBy(goal => goal.Title, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
        for (var index = 0; index < scaffold.Count; index++)
        {
            var expected = scaffold[index];
            if (!parsedByTitle.TryGetValue(expected.Title, out var actual) &&
                (index >= parsed.Count || !IsRecoverableRpgGoalRefinementPair(expected, parsed[index])))
            {
                if (IsAcceptableJrpgScaffoldSubset(parsed, scaffold))
                {
                    return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
                }

                return new IterationGoalBuildResult([], false);
            }

            actual ??= parsed[index];

            if (WeakensRpgScaffoldContract(expected, string.Join(" ", actual.Description, actual.AcceptanceHint)))
            {
                return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
            }

            refined.Add(new PrototypeIterationPlanGoalResult(
                expected.GoalIndex,
                expected.Title,
                string.IsNullOrWhiteSpace(actual.Description) ? expected.Description : actual.Description,
                string.IsNullOrWhiteSpace(actual.AcceptanceHint) ? expected.AcceptanceHint : actual.AcceptanceHint,
                "pending"));
        }

        return new IterationGoalBuildResult(refined, false);
    }

    private static bool IsRecoverableRpgGoalRefinementPair(PrototypeIterationPlanGoalResult expected, PrototypeIterationPlanGoalResult actual)
    {
        if (expected.GoalIndex != actual.GoalIndex)
        {
            return false;
        }

        var expectedCapability = ResolveJrpgCapabilityIdFromText(expected.Title);
        var actualCapability = ResolveJrpgCapabilityIdFromText(actual.Title);
        return !string.IsNullOrWhiteSpace(expectedCapability) &&
               string.Equals(expectedCapability, actualCapability, StringComparison.OrdinalIgnoreCase);
    }

    private static List<PrototypeIterationPlanGoalResult> CloneScaffoldGoals(IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        return scaffold
            .Select(goal => new PrototypeIterationPlanGoalResult(goal.GoalIndex, goal.Title, goal.Description, goal.AcceptanceHint, "pending"))
            .ToList();
    }

    private static bool IsAcceptableJrpgScaffoldSubset(
        IReadOnlyList<PrototypeIterationPlanGoalResult> parsed,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        if (parsed.Count < 2 || scaffold.Count < 2)
        {
            return false;
        }

        var firstCapability = ResolveJrpgCapabilityIdFromText(scaffold[0].Title);
        var finalCapability = ResolveJrpgCapabilityIdFromText(scaffold[^1].Title);
        return parsed.Any(goal => string.Equals(ResolveJrpgCapabilityIdFromText(goal.Title), firstCapability, StringComparison.OrdinalIgnoreCase)) &&
               parsed.Any(goal => string.Equals(ResolveJrpgCapabilityIdFromText(goal.Title), finalCapability, StringComparison.OrdinalIgnoreCase)) &&
               parsed.All(goal => IsJrpgScaffoldTitle(goal.Title));
    }

    private static bool IsRecoverableJrpgScaffoldResponse(
        IReadOnlyList<PrototypeIterationPlanGoalResult> parsed,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        if (parsed.Count != scaffold.Count || scaffold.Count < 4)
        {
            return false;
        }

        if (!parsed.All(goal => IsJrpgScaffoldTitle(goal.Title)))
        {
            return false;
        }

        if (!string.Equals(
                ResolveJrpgCapabilityIdFromText(parsed[0].Title),
                ResolveJrpgCapabilityIdFromText(scaffold[0].Title),
                StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var scaffoldCapabilities = scaffold
            .Select(goal => ResolveJrpgCapabilityIdFromText(goal.Title))
            .Where(static value => !string.IsNullOrWhiteSpace(value))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var capabilityMatches = parsed.Count(goal =>
        {
            var capability = ResolveJrpgCapabilityIdFromText(goal.Title);
            return !string.IsNullOrWhiteSpace(capability) && scaffoldCapabilities.Contains(capability);
        });
        return capabilityMatches >= Math.Max(2, scaffold.Count / 2);
    }

    private static bool IsJrpgScaffoldTitle(string title)
    {
        return title.StartsWith("JRPG First Loop:", StringComparison.Ordinal) ||
               ResolveJrpgCapabilityIdFromText(title) is not null ||
               Regex.IsMatch(title, @"^任务\s*\d+\s*[:：]", RegexOptions.CultureInvariant);
    }

    private static bool WeakensRpgScaffoldContract(PrototypeIterationPlanGoalResult expected, string actualText)
    {
        if (string.IsNullOrWhiteSpace(actualText))
        {
            return false;
        }

        var expectedText = string.Join(" ", expected.Title, expected.Description, expected.AcceptanceHint);
        foreach (var group in RequiredRpgScaffoldTerms(expectedText))
        {
            if (!ContainsAny(actualText, group))
            {
                return true;
            }
        }

        return false;
    }

    private static IEnumerable<string[]> RequiredRpgScaffoldTerms(string expectedText)
    {
        if (ContainsAny(expectedText, "Start Adventure", "visible MapScene", "stable movement", "field navigation", "stable control"))
        {
            yield return ["Start Adventure"];
            yield return ["visible MapScene", "visible RPG MapScene", "visible map", "non-empty visible MapScene"];
            yield return ["stable movement", "controllable movement", "move continuously", "movement"];
            yield return ["asset", "assets", "map/player", "map/player/enemy", "map/player runtime"];
        }

        if (ContainsAny(expectedText, "encounter trigger", "guaranteed encounter"))
        {
            yield return ["encounter trigger", "first encounter", "encounter"];
            yield return ["guaranteed", "10 steps", "10-step", "probability", "encounter progress"];
        }

        if (ContainsAny(expectedText, "BattleScene loop", "BattleScene"))
        {
            yield return ["BattleScene"];
            yield return ["settlement", "battle feedback", "complete one readable battle"];
            yield return ["enemy asset", "enemy assets", "enemy asset usage", "enemy"];
        }

        if (ContainsAny(expectedText, "reward 3-choice"))
        {
            yield return ["reward", "3-choice", "three reward", "three choices"];
            yield return ["understandability", "readability", "understandable", "player understanding", "choices are visible"];
        }

        if (ContainsAny(expectedText, "reward application", "return-to-map"))
        {
            yield return ["reward"];
            yield return ["state change", "changes state", "visible state", "application", "apply", "selection"];
            yield return ["return-to-map", "return to MapScene", "return to the map", "returns to MapScene", "returns the player to the map"];
        }

        if (ContainsAny(expectedText, "main loop scene switching", "scene switching"))
        {
            yield return ["scene switching", "scene switch", "switching"];
            yield return ["Start Adventure"];
            yield return ["return-to-map", "return to MapScene", "return to the map"];
        }

        if (ContainsAny(expectedText, "win/fail", "victory", "failure"))
        {
            yield return ["win/fail", "victory", "failure", "defeat"];
            yield return ["encounter", "rule"];
        }

        if (ContainsAny(expectedText, "full playable prototype acceptance", "Final Step", "final first-loop acceptance"))
        {
            yield return ["full playable", "full RPG playable", "full prototype", "final acceptance", "playable end-to-end", "end-to-end", "JRPG first-loop prototype", "first-loop prototype"];
            yield return ["project contract", "contract-specific", "input_traceability", "contract fields"];
            yield return ["asset", "assets", "map/player/enemy"];
        }
    }

    private static PlanningFieldCoverage[] BuildDeterministicFieldCoverage(ProjectPrototypeDraftSnapshot? draft)
    {
        if (draft is null)
        {
            return
            [
                new("hypothesis", "missing", null, "还没有导入或保存需求表单。"),
                new("core_player_fantasy", "missing", null, "还没有导入或保存需求表单。"),
                new("minimum_playable_loop", "missing", null, "还没有导入或保存需求表单。"),
                new("success_criteria", "missing", null, "还没有导入或保存需求表单。"),
                new("game_feature", "missing", null, "还没有导入或保存需求表单。"),
                new("core_gameplay_loop", "missing", null, "还没有导入或保存需求表单。"),
                new("win_fail_conditions", "missing", null, "还没有导入或保存需求表单。"),
                new("reward_loop", "missing", null, "无法从需求表单确认奖励回路。")
            ];
        }

        return
        [
            BuildFieldCoverage("hypothesis", draft.Hypothesis),
            BuildFieldCoverage("core_player_fantasy", draft.CorePlayerFantasy),
            BuildFieldCoverage("minimum_playable_loop", draft.MinimumPlayableLoop),
            BuildFieldCoverage("success_criteria", string.Join(" / ", DeserializeJsonArray(draft.SuccessCriteriaJson))),
            BuildFieldCoverage("game_feature", draft.GameFeature),
            BuildFieldCoverage("core_gameplay_loop", draft.CoreGameplayLoop),
            BuildFieldCoverage("win_fail_conditions", draft.WinFailConditions),
            BuildFieldCoverage("reward_loop", draft.CoreGameplayLoop)
        ];
    }

    private static PlanningFieldCoverage BuildFieldCoverage(string field, string? value)
    {
        return string.IsNullOrWhiteSpace(value)
            ? new PlanningFieldCoverage(field, "missing", null, "需求表单对应字段为空。")
            : new PlanningFieldCoverage(field, "partial", TrimForHint(value, 60), null);
    }

    private static string? ReadCompletionSummaryFromRun(RunSnapshot? run)
    {
        if (run is null || string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_completion", out var completionElement) ||
                completionElement.ValueKind != JsonValueKind.Object ||
                !completionElement.TryGetProperty("completion_summary", out var summaryElement) ||
                summaryElement.ValueKind != JsonValueKind.String)
            {
                return null;
            }

            return summaryElement.GetString();
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string[] DeserializeJsonArray(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return [];
        }

        try
        {
            return JsonSerializer.Deserialize<string[]>(json) ?? [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static PrototypeIterationPlanningAnalysisResult ToPlanningAnalysisResult(
        IterationPlanningContext planningContext,
        IReadOnlyList<PrototypeIterationPlanStageTelemetryResult>? extraStageTelemetry = null)
    {
        var stageTelemetry = planningContext.StageTelemetry
            .Concat(extraStageTelemetry ?? [])
            .ToArray();
        return new PrototypeIterationPlanningAnalysisResult(
            planningContext.AnalysisSource,
            planningContext.AnalysisSummary,
            planningContext.LatestPrototypeStatus,
            planningContext.LatestPrototypeCompletionSummary,
            planningContext.DraftCoveragePercent,
            planningContext.DraftCoverageSummary,
            planningContext.TemplateId,
            planningContext.FieldCoverage.Select(item => new PrototypeIterationPlanningFieldResult(
                item.Field,
                item.Status,
                item.Evidence,
                item.MissingReason)).ToArray(),
            stageTelemetry);
    }

    private static PrototypeIterationPlanStageTelemetryResult BuildTelemetry(string stage, LlmRouteResult completion)
    {
        return new PrototypeIterationPlanStageTelemetryResult(
            stage,
            completion.Model,
            completion.DurationMs,
            completion.PromptLength,
            completion.PromptUtf8Bytes,
            completion.EstimatedPromptTokens,
            completion.FailureCode,
            completion.FailureCategory);
    }

    private static PrototypeIterationPlanStageTelemetryResult BuildSkippedTelemetry(
        string stage,
        string model,
        string reason)
    {
        return new PrototypeIterationPlanStageTelemetryResult(
            stage,
            model,
            0,
            0,
            0,
            0,
            reason,
            "skipped");
    }

    private static object BuildIterationPlanObservability(
        IterationPlanningContext planningContext,
        IterationGoalBuildResult goalBuild)
    {
        var stages = planningContext.StageTelemetry
            .Concat(goalBuild.StageTelemetry ?? [])
            .ToArray();
        return new
        {
            schema = "phase-a.iteration-plan.observability.v1",
            stages,
            totalDurationMs = stages.Sum(stage => stage.DurationMs),
            totalPromptLength = stages.Sum(stage => stage.PromptLength),
            totalPromptUtf8Bytes = stages.Sum(stage => stage.PromptUtf8Bytes),
            totalEstimatedPromptTokens = stages.Sum(stage => stage.EstimatedPromptTokens),
            failedStages = stages
                .Where(stage => !string.IsNullOrWhiteSpace(stage.FailureCode) &&
                    !string.Equals(stage.FailureCategory, "skipped", StringComparison.OrdinalIgnoreCase))
                .Select(stage => new
                {
                    stage.Stage,
                    stage.FailureCode,
                    stage.FailureCategory
                })
                .ToArray()
        };
    }

    private static PrototypeIterationRouteContext TryReadCurrentIterationRouteContext(string stateText, string? expectedSessionId)
    {
        if (string.IsNullOrWhiteSpace(stateText))
        {
            return new PrototypeIterationRouteContext(null, null, null, "", null, null, null, null, null);
        }

        try
        {
            using var document = JsonDocument.Parse(stateText);
            if (!IsCurrentOrLegacyRouteState(document.RootElement, expectedSessionId))
            {
                return new PrototypeIterationRouteContext(null, null, null, "", null, null, null, null, null);
            }

            var requiredModules = TryReadRequiredModules(document.RootElement);
            return new PrototypeIterationRouteContext(
                TryReadPlanningAnalysis(document.RootElement),
                TryReadSelectedCapabilities(document.RootElement),
                requiredModules,
                ReadRouteString(document.RootElement, "plan_hash"),
                TryReadSourceHashes(document.RootElement),
                TryReadConfirmation(document.RootElement),
                TryReadTraceabilityGoals(document.RootElement),
                TryReadBlockers(document.RootElement),
                TryReadStyleApplicability(document.RootElement));
        }
        catch (JsonException)
        {
            return new PrototypeIterationRouteContext(null, null, null, "", null, null, null, null, null);
        }
    }

    private static IReadOnlyList<PrototypeIterationPlanTraceabilityGoalResult>? TryReadTraceabilityGoals(JsonElement root)
    {
        if (!root.TryGetProperty("goals", out var goals) || goals.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        var results = goals.EnumerateArray()
            .Where(goal => goal.ValueKind == JsonValueKind.Object)
            .Select(goal =>
            {
                var uiSurface = goal.TryGetProperty("ui_surface", out var ui) && ui.ValueKind == JsonValueKind.Object
                    ? string.Join(" | ", new[]
                    {
                        ReadRouteString(ui, "scene_owner"),
                        ReadRouteString(ui, "node_owner"),
                        ReadRouteString(ui, "surface_type"),
                        ReadRouteString(ui, "layout"),
                        ReadRouteString(ui, "input_ownership"),
                        ReadRouteString(ui, "focus_policy")
                    }.Where(value => !string.IsNullOrWhiteSpace(value)))
                    : "";
                var style = goal.TryGetProperty("style", out var styleElement) && styleElement.ValueKind == JsonValueKind.Object
                    ? string.Join(" | ", ReadStringArrayAny(styleElement, "style_token_refs", "component_families", "design_dna")
                        .Concat(new[] { ReadRouteString(styleElement, "composition"), ReadRouteString(styleElement, "motion") })
                        .Where(value => !string.IsNullOrWhiteSpace(value)))
                    : "";
                var engineRefs = goal.TryGetProperty("engine_semantics", out var engine) && engine.ValueKind == JsonValueKind.Object
                    ? ReadStringArray(engine, "reading_evidence_refs")
                    : [];
                var interactionArtifact = goal.TryGetProperty("interaction_region", out var interaction) && interaction.ValueKind == JsonValueKind.Object
                    ? ReadRouteString(interaction, "artifact_ref")
                    : "";
                return new PrototypeIterationPlanTraceabilityGoalResult(
                    goal.TryGetProperty("goal_index", out var index) && index.TryGetInt32(out var parsedIndex) ? parsedIndex : 0,
                    ReadStringArray(goal, "requirement_ids"),
                    ReadRouteString(goal, "source_hash_ref"),
                    uiSurface,
                    style,
                    engineRefs,
                    interactionArtifact);
            })
            .Where(goal => goal.GoalIndex > 0)
            .ToArray();
        return results.Length == 0 ? null : results;
    }

    private static IReadOnlyList<PrototypeIterationPlanBlockerResult>? TryReadBlockers(JsonElement root)
    {
        if (!root.TryGetProperty("blockers", out var blockers) || blockers.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        return blockers.EnumerateArray()
            .Where(item => item.ValueKind == JsonValueKind.Object)
            .Select(item => new PrototypeIterationPlanBlockerResult(
                ReadRouteString(item, "domain_code"),
                ReadRouteString(item, "severity"),
                ReadRouteString(item, "summary"),
                ReadStringArray(item, "requirement_ids"),
                ReadStringArray(item, "evidence_refs")))
            .Where(item => !string.IsNullOrWhiteSpace(item.DomainCode))
            .ToArray();
    }

    private static PrototypeIterationPlanSourceHashes? TryReadSourceHashes(JsonElement root)
    {
        var hashes = new PrototypeIterationPlanSourceHashes(
            ReadRouteString(root, "source_gdd_hash"),
            ReadRouteString(root, "source_scene_route_hash"),
            ReadRouteString(root, "source_requirement_map_hash"),
            ReadRouteString(root, "source_contract_hash"),
            ReadRouteString(root, "source_contract_snapshot_hash"),
            ReadRouteString(root, "source_godot_ui_contract_hash"),
            ReadRouteString(root, "source_ui_style_contract_hash"),
            ReadRouteString(root, "ui_style_snapshot_hash"));
        var requiredHashesPresent = new[]
        {
            hashes.SourceGddHash,
            hashes.SourceSceneRouteHash,
            hashes.SourceRequirementMapHash,
            hashes.SourceContractHash,
            hashes.SourceContractSnapshotHash,
            hashes.SourceGodotUiContractHash,
            hashes.SourceUiStyleContractHash
        }.All(value => !string.IsNullOrWhiteSpace(value));
        var applicability = TryReadStyleApplicability(root);
        var styleIdentityPresent = !string.IsNullOrWhiteSpace(hashes.UiStyleSnapshotHash) ||
                                   string.Equals(applicability?.Status, "reviewed_not_applicable", StringComparison.Ordinal);
        return requiredHashesPresent && styleIdentityPresent ? hashes : null;
    }

    private static PrototypeIterationStyleApplicability? TryReadStyleApplicability(JsonElement root)
    {
        if (!root.TryGetProperty("style_applicability", out var applicability) || applicability.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        var result = new PrototypeIterationStyleApplicability(
            ReadRouteString(applicability, "status"),
            ReadRouteString(applicability, "reason"),
            ReadRouteString(applicability, "reviewed_by"),
            ReadRouteString(applicability, "recheck_trigger"),
            ReadRouteString(applicability, "evidence_hash"));
        return new[] { result.Status, result.Reason, result.ReviewedBy, result.RecheckTrigger, result.EvidenceHash }
            .All(value => !string.IsNullOrWhiteSpace(value))
            ? result
            : null;
    }

    private static PrototypeIterationPlanConfirmationResult? TryReadConfirmation(JsonElement root)
    {
        if (!root.TryGetProperty("confirmation", out var confirmation) || confirmation.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        return new PrototypeIterationPlanConfirmationResult(
            ReadRouteString(confirmation, "status"),
            ReadRouteString(confirmation, "session_id"),
            ReadRouteString(confirmation, "plan_hash"),
            ReadRouteString(confirmation, "source_hash_ref"),
            ReadRouteString(confirmation, "confirmed_by"),
            ReadRouteString(confirmation, "confirmed_utc"));
    }

    private static string ReadRouteString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? ""
            : "";
    }

    private static bool IsCurrentOrLegacyRouteState(JsonElement root, string? expectedSessionId)
    {
        if (string.IsNullOrWhiteSpace(expectedSessionId) ||
            !root.TryGetProperty("session_id", out var sessionElement))
        {
            return true;
        }

        return sessionElement.ValueKind == JsonValueKind.String &&
               string.Equals(sessionElement.GetString(), expectedSessionId, StringComparison.Ordinal);
    }

    private static PrototypeIterationPlanningAnalysisResult? TryReadPlanningAnalysisFromState(string stateText)
    {
        if (string.IsNullOrWhiteSpace(stateText))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(stateText);
            return TryReadPlanningAnalysis(document.RootElement);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static PrototypeIterationPlanningAnalysisResult? TryReadPlanningAnalysis(JsonElement root)
    {
        if (!root.TryGetProperty("planning_analysis", out var analysisElement))
        {
            return null;
        }

            var source = analysisElement.TryGetProperty("analysisSource", out var sourceElement) && sourceElement.ValueKind == JsonValueKind.String
                ? sourceElement.GetString() ?? ""
                : "";
            var summary = analysisElement.TryGetProperty("analysisSummary", out var summaryElement) && summaryElement.ValueKind == JsonValueKind.String
                ? summaryElement.GetString() ?? ""
                : "";
            var latestStatus = analysisElement.TryGetProperty("latestPrototypeStatus", out var statusElement) && statusElement.ValueKind == JsonValueKind.String
                ? statusElement.GetString() ?? ""
                : "";
            var latestCompletion = analysisElement.TryGetProperty("latestPrototypeCompletionSummary", out var completionElement) && completionElement.ValueKind == JsonValueKind.String
                ? completionElement.GetString()
                : null;
            var draftCoveragePercent = analysisElement.TryGetProperty("draftCoveragePercent", out var coverageElement) && coverageElement.ValueKind == JsonValueKind.Number
                ? coverageElement.GetInt32()
                : 0;
            var draftCoverageSummary = analysisElement.TryGetProperty("draftCoverageSummary", out var coverageSummaryElement) && coverageSummaryElement.ValueKind == JsonValueKind.String
                ? coverageSummaryElement.GetString()
                : null;
            var templateId = analysisElement.TryGetProperty("templateId", out var templateElement) && templateElement.ValueKind == JsonValueKind.String
                ? templateElement.GetString()
                : null;
            var fieldCoverage = analysisElement.TryGetProperty("fieldCoverage", out var fieldElement) && fieldElement.ValueKind == JsonValueKind.Array
                ? fieldElement.EnumerateArray().Select(item => new PrototypeIterationPlanningFieldResult(
                    item.TryGetProperty("field", out var fieldName) && fieldName.ValueKind == JsonValueKind.String ? fieldName.GetString() ?? "" : "",
                    item.TryGetProperty("status", out var fieldStatus) && fieldStatus.ValueKind == JsonValueKind.String ? fieldStatus.GetString() ?? "missing" : "missing",
                    item.TryGetProperty("evidence", out var evidenceElement) && evidenceElement.ValueKind == JsonValueKind.String ? evidenceElement.GetString() : null,
                    item.TryGetProperty("missingReason", out var missingReasonElement) && missingReasonElement.ValueKind == JsonValueKind.String ? missingReasonElement.GetString() : null))
                    .Where(item => !string.IsNullOrWhiteSpace(item.Field))
                    .ToArray()
                : [];

            return new PrototypeIterationPlanningAnalysisResult(
                source,
                summary,
                latestStatus,
                latestCompletion,
                draftCoveragePercent,
                draftCoverageSummary,
                templateId,
                fieldCoverage);
    }

    private static HashSet<string>? TryReadSelectedCapabilities(JsonElement root)
    {
        if (!root.TryGetProperty("selected_capabilities", out var capabilitiesElement) ||
            capabilitiesElement.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        var capabilities = capabilitiesElement
            .EnumerateArray()
            .Where(item => item.ValueKind == JsonValueKind.String)
            .Select(item => item.GetString())
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Select(item => item!)
            .Where(IsKnownJrpgCapability)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        return capabilities.Count == 0 ? null : capabilities;
    }

    private static IReadOnlyList<PrototypeIterationPlanRequiredModuleResult>? TryReadRequiredModules(JsonElement root)
    {
        if (!root.TryGetProperty("required_modules", out var modulesElement) ||
            modulesElement.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        var modules = modulesElement
            .EnumerateArray()
            .Select(ReadRequiredModule)
            .Where(module => module is not null)
            .Select(module => module!)
            .ToArray();

        return modules.Length == 0 ? null : modules;
    }

    private static PrototypeIterationPlanRequiredModuleResult? ReadRequiredModule(JsonElement moduleElement)
    {
        if (moduleElement.ValueKind == JsonValueKind.String)
        {
            var id = moduleElement.GetString();
            return string.IsNullOrWhiteSpace(id)
                ? null
                : new PrototypeIterationPlanRequiredModuleResult(id, "", "required", "explicit_gdd_conflict", [], null);
        }

        if (moduleElement.ValueKind == JsonValueKind.Object &&
            moduleElement.TryGetProperty("id", out var idElement) &&
            idElement.ValueKind == JsonValueKind.String)
        {
            var id = idElement.GetString();
            if (string.IsNullOrWhiteSpace(id))
            {
                return null;
            }

            return new PrototypeIterationPlanRequiredModuleResult(
                id,
                ReadOptionalString(moduleElement, "source"),
                ReadOptionalString(moduleElement, "status"),
                ReadOptionalStringAny(moduleElement, "applies_unless", "appliesUnless"),
                ReadStringArrayAny(moduleElement, "acceptance_markers", "acceptanceMarkers"),
                ReadOptionalNullableStringAny(moduleElement, "covered_by_goal_capability", "coveredByGoalCapability"),
                ReadStringArrayAny(moduleElement, "requirement_ids", "requirementIds"),
                ReadOptionalStringAny(moduleElement, "source_reason", "sourceReason"),
                ReadStringArrayAny(moduleElement, "source_refs", "sourceRefs"),
                ReadOptionalString(moduleElement, "priority"),
                ReadOptionalStringAny(moduleElement, "coverage_status", "coverageStatus"),
                ReadStringArrayAny(moduleElement, "validation_refs", "validationRefs"));
        }

        return null;
    }

    private static string ReadOptionalString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? ""
            : "";
    }

    private static string? ReadOptionalNullableString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString()
            : null;
    }

    private static string ReadOptionalStringAny(JsonElement element, params string[] propertyNames)
    {
        return propertyNames.Select(name => ReadOptionalString(element, name)).FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    }

    private static string? ReadOptionalNullableStringAny(JsonElement element, params string[] propertyNames)
    {
        return propertyNames.Select(name => ReadOptionalNullableString(element, name)).FirstOrDefault(value => !string.IsNullOrWhiteSpace(value));
    }

    private static IReadOnlyList<string> ReadStringArrayAny(JsonElement element, params string[] propertyNames)
    {
        foreach (var propertyName in propertyNames)
        {
            var values = ReadStringArray(element, propertyName);
            if (values.Count > 0)
            {
                return values;
            }
        }

        return [];
    }

    private static IReadOnlyList<string> ReadStringArray(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var property) || property.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        return property
            .EnumerateArray()
            .Where(item => item.ValueKind == JsonValueKind.String)
            .Select(item => item.GetString())
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Select(item => item!)
            .ToArray();
    }

    private static bool IsKnownJrpgCapability(string capabilityId)
    {
        return JrpgFirstLoopCapabilityIds.Contains(capabilityId);
    }

    private static string? ResolveCanonicalGameType(ProjectSnapshot project)
    {
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        return NormalizeGameType(evidence.MatchedGameTypeId);
    }

    private static string? NormalizeGameType(string? gameTypeSource)
    {
        if (string.IsNullOrWhiteSpace(gameTypeSource))
        {
            return null;
        }

        var lowered = gameTypeSource.Trim().ToLowerInvariant();
        if (lowered.Contains("rpg", StringComparison.Ordinal) ||
            lowered.Contains("角色扮演", StringComparison.Ordinal) ||
            lowered.Contains("勇者斗恶龙", StringComparison.Ordinal))
        {
            return "rpg";
        }

        return lowered;
    }

    private static string TrimForPrompt(string value)
    {
        var trimmed = value.Trim();
        return trimmed.Length <= 5000 ? trimmed : trimmed[..5000];
    }

    private static string CompactForPrompt(string? value, int maxChars)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var trimmed = value.Trim();
        if (trimmed.Length <= maxChars)
        {
            return trimmed;
        }

        return trimmed[..maxChars] + "\n[truncated]";
    }

    private static string AppendAttachmentContext(string message, string attachmentContext)
    {
        if (string.IsNullOrWhiteSpace(attachmentContext) || attachmentContext == "无。")
        {
            return message;
        }

        return $"""
            {message}

            本次导入 TXT 参考资料：
            {attachmentContext}
            """;
    }

    private static string BuildAttachmentPromptBlock(IReadOnlyList<TextAttachment>? attachments)
    {
        if (attachments is null || attachments.Count == 0)
        {
            return "无。";
        }

        var usable = attachments
            .Take(MaxTextAttachments)
            .Where(item => !string.IsNullOrWhiteSpace(item.Content))
            .Select((item, index) =>
            {
                var fileName = string.IsNullOrWhiteSpace(item.FileName) ? $"attachment-{index + 1}.txt" : item.FileName.Trim();
                var content = item.Content!.Trim();
                if (content.Length > MaxTextAttachmentChars)
                {
                    content = content[..MaxTextAttachmentChars] + "\n[truncated]";
                }

                return $"[{index + 1}] {fileName}\n{content}";
            })
            .ToArray();

        return usable.Length == 0 ? "无。" : string.Join("\n\n", usable);
    }

    public async Task<PrototypeIterationPlanDetails?> GetLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (details is null)
        {
            return null;
        }

        var stateText = _routeStateWriter.ReadIterationPlanSessionState(project, details.Session.SessionId);
        if (string.IsNullOrWhiteSpace(stateText))
        {
            stateText = details.Session.RouteStateJson ?? "";
        }
        if (string.IsNullOrWhiteSpace(stateText))
        {
            stateText = _routeStateWriter.ReadLatestIterationPlanState(project);
        }
        var routeContext = TryReadCurrentIterationRouteContext(stateText, details.Session.SessionId);
        return new PrototypeIterationPlanDetails(
            details.Session,
            details.Goals,
            details.GoalRuns,
            details.LatestEvaluation,
            routeContext.PlanningAnalysis,
            routeContext.RequiredModules,
            routeContext.PlanHash,
            routeContext.SourceHashes,
            ProjectConfirmationFromTrustedAnchor(routeContext.Confirmation, details.Session.TraceabilityAnchorJson),
            routeContext.TraceabilityGoals,
            routeContext.Blockers,
            routeContext.StyleApplicability);
    }

    public async Task<IReadOnlyList<PrototypeIterationPlanRoundDetails>> ListAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return [];
        }

        var sessions = FilterDisplayIterationRounds(await _metadataStore.ListProjectIterationSessionsAsync(projectId, cancellationToken));
        return sessions
            .Select((details, index) =>
            {
                var stateText = _routeStateWriter.ReadIterationPlanSessionState(project, details.Session.SessionId);
                if (string.IsNullOrWhiteSpace(stateText))
                {
                    stateText = details.Session.RouteStateJson ?? "";
                }
                if (string.IsNullOrWhiteSpace(stateText))
                {
                    stateText = _routeStateWriter.ReadLatestIterationPlanState(project);
                }
                var routeContext = TryReadCurrentIterationRouteContext(stateText, details.Session.SessionId);
                return new PrototypeIterationPlanRoundDetails(
                    index + 1,
                    details.Session,
                    details.Goals,
                    details.GoalRuns,
                    details.LatestEvaluation,
                    routeContext.PlanningAnalysis,
                    routeContext.RequiredModules,
                    routeContext.PlanHash,
                    routeContext.SourceHashes,
                    ProjectConfirmationFromTrustedAnchor(routeContext.Confirmation, details.Session.TraceabilityAnchorJson),
                    routeContext.TraceabilityGoals,
                    routeContext.Blockers,
                    routeContext.StyleApplicability);
            })
            .ToArray();
    }

    private static IReadOnlyList<ProjectIterationSessionDetails> FilterDisplayIterationRounds(
        IReadOnlyList<ProjectIterationSessionDetails> sessions)
    {
        if (sessions.Count <= 1)
        {
            return sessions;
        }

        var baseRound = sessions
            .Where(details => !string.Equals(details.Session.SourceKind, "new_iteration_plan", StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(details => ParseIsoTimestamp(details.Session.CreatedUtc))
            .FirstOrDefault();
        var newRounds = sessions
            .Where(details => string.Equals(details.Session.SourceKind, "new_iteration_plan", StringComparison.OrdinalIgnoreCase))
            .OrderBy(details => ParseIsoTimestamp(details.Session.CreatedUtc))
            .ToList();
        var rounds = new List<ProjectIterationSessionDetails>();
        if (baseRound is not null)
        {
            rounds.Add(baseRound);
        }

        rounds.AddRange(newRounds);
        return rounds;
    }

    private static long ParseIsoTimestamp(string? value)
    {
        return DateTimeOffset.TryParse(value, out var timestamp) ? timestamp.ToUnixTimeMilliseconds() : 0;
    }

    public async Task<PrototypeIterationPlanDeleteResult> DeleteAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var latest = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (latest is null)
        {
            var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
            if (project is not null && string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
            {
                _routeStateWriter.ClearIterationPlanState(project);
            }

            return new PrototypeIterationPlanDeleteResult("not_found", "当前没有可删除的游戏模块。", 0);
        }

        return await DeleteSessionAsync(accountId, projectId, latest.Session.SessionId, cancellationToken);
    }

    public async Task<PrototypeIterationPlanDeleteResult> DeleteSessionAsync(
        string accountId,
        string projectId,
        string sessionId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);

        await using var mutationLease = await ProjectMutationLockRegistry.Shared.AcquireAsync(accountId, projectId, cancellationToken);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var details = await _metadataStore.GetProjectIterationSessionAsync(projectId, sessionId, cancellationToken);
        if (details is null)
        {
            return new PrototypeIterationPlanDeleteResult("not_found", "当前没有可删除的游戏模块。", 0);
        }

        if (IsIterationPlanComplete(details.Goals))
        {
            return new PrototypeIterationPlanDeleteResult("blocked", "当前轮游戏模块已经全部完成，不可以删除。", 0);
        }

        var latest = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        var wasLatest = latest is not null && string.Equals(latest.Session.SessionId, sessionId, StringComparison.Ordinal);
        var deleted = await _metadataStore.DeleteProjectIterationSessionAsync(projectId, accountId, sessionId, cancellationToken);
        _routeStateWriter.DeleteIterationPlanSessionState(project, sessionId);
        if (wasLatest)
        {
            _routeStateWriter.ClearIterationPlanState(project);
        }

        return new PrototypeIterationPlanDeleteResult("deleted", "当前轮游戏模块已删除。", deleted);
    }

    public async Task<PrototypeIterationPlanEvaluationResult> EvaluateAsync(
        string accountId,
        string projectId,
        PrototypeWorkflowProgress? prototypeProgress,
        string? model = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (details is null)
        {
            var result = new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前项目还没有游戏模块。",
                "还没有可执行的任务列表，无法判断是否适合直接进入下一任务。",
                "请先生成游戏模块。",
                null);
            return result;
        }

        var goals = details.Goals.OrderBy(goal => goal.GoalIndex).ToArray();
        if (goals.Length == 0)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划没有有效任务。",
                "计划会话存在，但没有生成任何可执行任务。",
                "请重新生成游戏模块。",
                BuildRegenerationPrompt(prototypeProgress, details)));
        }

        if (goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)))
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有需要先修复的任务。",
                "至少一个任务已经被标记为 needs_fix，继续执行后续任务只会放大不确定性。",
                "先修复当前任务，再决定是否继续后续任务。",
                null));
        }

        if (goals.Any(goal => string.Equals(goal.Status, "running", StringComparison.Ordinal)))
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有进行中的任务。",
                "已有任务正在执行，暂时不适合重新拆解或继续触发下一任务。",
                "等待当前任务完成后再刷新判断。",
                null));
        }

        var pendingGoals = goals.Where(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)).ToArray();
        if (pendingGoals.Length == 0)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "当前计划已经没有待执行任务。",
                "所有任务都已完成或已停止，不需要继续执行下一任务。",
                "如果还有新需求，请基于新的优化目标重新生成计划。",
                null));
        }

        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var routeStrategy = GameTypeRouteStrategies.Resolve(project, routeProfile);
        if (routeStrategy.UsesSpecializedPlanEvaluation &&
            string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            var routeContext = TryReadCurrentIterationRouteContext(_routeStateWriter.ReadLatestIterationPlanState(project), details.Session.SessionId);
            var prototypeContract = _contractService.Read(project);
            var rpgPlanIssue = FindRpgPlanContractIssue(goals, routeContext.PlanningAnalysis, details.Session.SourceMessage, routeContext.SelectedCapabilities, prototypeContract);
            if (rpgPlanIssue is not null)
            {
                return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                    "should_refine_plan",
                    "当前 RPG 游戏模块缺少类型路由要求的场景、顺序或验收覆盖。",
                    rpgPlanIssue,
                "请按 GDD 派生的项目原型合同重新生成游戏模块：任务 1 只覆盖项目入口、可见地图/场景与稳定移动；后续只选择项目语义实际需要的能力模块，并以最终首轮闭环验收收尾。",
                    BuildRpgRegenerationPrompt(details)));
            }

            var llmEvaluation = await EvaluateRpgPlanWithRequiredModelAsync(project, routeProfile, details, prototypeProgress, PrototypeModelPolicy.Normalize(model), cancellationToken);
            if (IsStaleRpgBoundaryMismatchEvaluation(llmEvaluation, goals))
            {
                llmEvaluation = BuildRpgRouteGuardAcceptedEvaluation(llmEvaluation);
            }

            return await PersistEvaluationAsync(details, llmEvaluation, cancellationToken);
        }

        if (routeStrategy.UsesSpecializedPlanEvaluation &&
            string.Equals(routeStrategy.GameTypeId, "survivorslike", StringComparison.OrdinalIgnoreCase))
        {
            var survivorsLikePlanIssue = FindSurvivorsLikePlanContractIssue(goals);
            if (survivorsLikePlanIssue is not null)
            {
                return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                    "should_refine_plan",
                    "当前吸血鬼幸存者 Like 游戏模块缺少首轮闭环路由覆盖。",
                    survivorsLikePlanIssue,
                    "请按吸血鬼幸存者 Like 首轮闭环路由重新生成游戏模块：开局、场地移动、刷怪压力、自动攻击、伤害/死亡、拾取、升级选择、成长反馈、压力升级，以及本局摘要/重开。",
                    BuildSurvivorsLikeRegenerationPrompt(details)));
            }

            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "当前吸血鬼幸存者 Like 游戏模块符合首轮闭环路由画像。",
                "计划已经按有效顺序覆盖开局、场地移动、刷怪压力、自动攻击、伤害/死亡、拾取、升级选择、成长反馈、压力升级，以及本局摘要/重开。",
                "请先执行下一项待执行任务，再按路由逐项推进。",
                null));
        }

        if (routeStrategy.UsesSpecializedPlanEvaluation &&
            string.Equals(routeStrategy.GameTypeId, "deckbuilder", StringComparison.OrdinalIgnoreCase))
        {
            var routeContext = TryReadCurrentIterationRouteContext(_routeStateWriter.ReadLatestIterationPlanState(project), details.Session.SessionId);
            var deckbuilderPlanIssue = FindDeckbuilderPlanContractIssue(goals, routeContext.RequiredModules);
            if (deckbuilderPlanIssue is not null)
            {
                return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                    "should_refine_plan",
                    "当前卡牌构筑游戏模块缺少首轮闭环路由覆盖。",
                    deckbuilderPlanIssue,
                    "请按卡牌构筑首轮闭环路由重新生成游戏模块：开局语境、初始牌组可读性、费用/回合、敌方意图、出牌结算、牌库循环、战斗结算、战后选牌、牌组变化、必要时的路线选择，以及最终首轮闭环验收。",
                    BuildDeckbuilderRegenerationPrompt(details)));
            }

            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "当前卡牌构筑游戏模块符合首轮闭环路由画像。",
                "计划已经按有效顺序覆盖开局语境、牌组可读性、费用与回合规则、敌方压力、出牌结算、牌库循环、战斗结算、战后奖励、牌组变化反馈、必要时的路线选择，以及最终首轮闭环验收。",
                "请先执行下一项待执行任务，再按路由逐项推进。",
                null));
        }

        var firstPending = pendingGoals[0];
        var firstGoalLooksTooLarge = !IsRecognizedSmallGoal(firstPending) && (LooksTooBroad(firstPending.Title) || LooksTooBroad(firstPending.Description));
        var overallLooksLarge = goals.Length <= 3 && goals.Any(goal => LooksTooBroad(goal.Description));
        var recommendedButStillBroad = string.Equals(prototypeProgress?.NextStepEvaluation, "recommended", StringComparison.OrdinalIgnoreCase)
                                       && goals.Length <= 3
                                       && firstGoalLooksTooLarge;

        if (firstGoalLooksTooLarge || overallLooksLarge || recommendedButStillBroad)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划不适合直接执行，第一任务仍然偏大，需要先重新拆解。",
                $"当前第一个待执行任务“{firstPending.Title}”混合了多个连续实现点，更像总任务而不是单次小任务。",
                "建议先重生成一次更细的游戏模块，再执行下一任务。",
                BuildRegenerationPrompt(prototypeProgress, details)));
        }

        return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "当前计划适合直接执行下一任务。",
            $"当前待执行任务“{firstPending.Title}”边界相对清楚，没有发现明显的 needs_fix 或过粗拆分信号。",
            "可以直接点击“执行下一任务”。",
            null));
    }

    public async Task<PrototypeIterationPlanEvaluationRunResult> EvaluateWithRunAsync(
        string accountId,
        string projectId,
        PrototypeWorkflowProgress? prototypeProgress,
        string? model = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, EvaluationRunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);
        await _metadataStore.UpdateRunProgressAsync(
            runId,
            "running",
            "plan_evaluation",
            "正在评估当前游戏模块。",
            CancellationToken.None);

        try
        {
            var evaluation = await EvaluateAsync(accountId, projectId, prototypeProgress, model, cancellationToken);
            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = EvaluationRunType,
                evaluation,
                evaluated_utc = DateTimeOffset.UtcNow.ToString("O")
            });
            await _metadataStore.CompleteRunAsync(
                runId,
                "succeeded",
                0,
                JsonSerializer.Serialize(evaluation),
                "",
                evidenceJson,
                CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(
                runId,
                "succeeded",
                evaluation.Decision,
                "游戏模块评估已完成。",
                CancellationToken.None);
            return new PrototypeIterationPlanEvaluationRunResult(runId, "succeeded", evaluation);
        }
        catch (OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "cancel", 499, "", "Iteration plan evaluation cancelled.", "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "cancel", "cancelled", "游戏模块评估已取消。", CancellationToken.None);
            throw;
        }
        catch (Exception ex)
        {
            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = EvaluationRunType,
                error = ex.Message
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "游戏模块评估失败。", CancellationToken.None);
            throw;
        }
    }

    private async Task<PrototypeSkeletonRegenerationDecision> EvaluatePrototypeSkeletonRegenerationNeedAsync(
        ProjectSnapshot project,
        ProjectIterationSessionDetails? previousIterationPlan,
        string message,
        IReadOnlyList<PrototypeIterationPlanGoalResult> candidateGoals,
        IterationPlanningContext planningContext,
        string model,
        CancellationToken cancellationToken)
    {
        if (previousIterationPlan is null || _llmRouteEngine is null || candidateGoals.Count == 0)
        {
            return PrototypeSkeletonRegenerationDecision.NotRequired();
        }

        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "prototype-skeleton-regeneration-guard");
        var previousGoals = previousIterationPlan.Goals
            .OrderBy(goal => goal.GoalIndex)
            .Select(goal => $"{goal.GoalIndex}. {goal.Title} - {goal.Description} [{goal.Status}]");
        var newGoals = candidateGoals
            .OrderBy(goal => goal.GoalIndex)
            .Select(goal => $"{goal.GoalIndex}. {goal.Title} - {goal.Description}");
        var prompt = $$"""
            You are the Phase A iteration-plan safety guard.

            Decide whether the newly requested iteration plan can continue from the existing playable prototype skeleton, or whether the gameplay direction changed so much that the user should create a new project and rebuild the prototype skeleton.

            Return one JSON object only:
            {
              "requiresPrototypeRecreation": true,
              "reason": "Chinese user-facing reason"
            }

            Use requiresPrototypeRecreation=true only when the requested plan changes the core genre, camera/control model, primary game loop, required scene topology, or engine-level skeleton beyond what can reasonably be achieved as iteration goals.
            Use false for normal feature additions, UI polish, balance, content expansion, combat improvements, map additions, or second-round iteration on the same core loop.

            Project:
            - Game name: {{project.GameName}}
            - Game type: {{project.GameTypeSource}}
            - Latest prototype status: {{planningContext.LatestPrototypeStatus}}
            - Planning summary: {{planningContext.AnalysisSummary}}

            User update request:
            {{message}}

            Previous iteration plan:
            {{string.Join("\n", previousGoals)}}

            Candidate new iteration plan:
            {{string.Join("\n", newGoals)}}
            """;

        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "prototype-skeleton-regeneration-guard",
                model,
                prompt,
                PlanningCodexOptions,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            return PrototypeSkeletonRegenerationDecision.NotRequired();
        }

        try
        {
            using var document = JsonDocument.Parse(completion.JsonObjectText ?? completion.AssistantMessage ?? "{}");
            var root = document.RootElement;
            var required = root.TryGetProperty("requiresPrototypeRecreation", out var requiredElement) &&
                           requiredElement.ValueKind is JsonValueKind.True or JsonValueKind.False &&
                           requiredElement.GetBoolean();
            var reason = root.TryGetProperty("reason", out var reasonElement) && reasonElement.ValueKind == JsonValueKind.String
                ? reasonElement.GetString()
                : null;
            return required
                ? new PrototypeSkeletonRegenerationDecision(true, string.IsNullOrWhiteSpace(reason)
                    ? "\u6e38\u620f\u529f\u80fd\u8ba1\u5212\u6539\u52a8\u8fc7\u5927\uff0c\u9700\u8981\u65b0\u5efa\u9879\u76ee\u91cd\u65b0\u521b\u5efa\u6e38\u620f\u539f\u578b\u9aa8\u67b6\u3002"
                    : reason!.Trim())
                : PrototypeSkeletonRegenerationDecision.NotRequired();
        }
        catch (JsonException)
        {
            return PrototypeSkeletonRegenerationDecision.NotRequired();
        }
    }

    private static bool IsIterationPlanComplete(IReadOnlyList<ProjectIterationGoalSnapshot> goals)
    {
        return goals.Count > 0 && goals.All(goal =>
            string.Equals(goal.Status, "completed", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(goal.Status, "succeeded", StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsIterationPlanStarted(ProjectIterationSessionDetails details)
    {
        return details.GoalRuns.Count > 0 ||
               details.Session.CurrentGoalIndex > 0 ||
               details.Goals.Any(goal => !string.Equals(goal.Status, "pending", StringComparison.OrdinalIgnoreCase));
    }

    private async Task<PrototypeIterationPlanEvaluationResult> EvaluateRpgPlanWithRequiredModelAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        ProjectIterationSessionDetails details,
        PrototypeWorkflowProgress? prototypeProgress,
        string model,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return BuildLlmFailedEvaluation("plan_evaluation_llm_client_missing");
        }

        var routeContext = TryReadCurrentIterationRouteContext(_routeStateWriter.ReadLatestIterationPlanState(project), details.Session.SessionId);
        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, _contractService.Read(project));
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "plan-evaluation");
        var options = PlanningCodexOptions with { OutputSchemaPath = EvaluationSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "plan-evaluation",
                model,
                BuildRpgPlanEvaluationPrompt(project, routeProfile, projectExecutionGuide, details, prototypeProgress, routeContext.PlanningAnalysis),
                options,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            return BuildLlmFailedEvaluation(completion.FailureCode ?? "plan_evaluation_llm_failed");
        }

        var parsed = ParseModelEvaluation(completion.JsonObjectText ?? completion.AssistantMessage);
        if (parsed is null)
        {
            return BuildLlmFailedEvaluation("plan_evaluation_parse_failed");
        }

        return parsed;
    }

    private static List<PrototypeIterationPlanGoalResult> BuildGoals(string message, string sourceKind)
    {
        var refinedGoals = TryBuildRefinedGoals(message, sourceKind);
        if (refinedGoals.Count > 0)
        {
            return refinedGoals;
        }

        var normalized = message.Replace("\r", "\n");
        var segments = ExtractStructuredGoals(normalized);
        var usedStructuredGoals = segments.Count > 0;
        if (segments.Count == 0)
        {
            segments = SplitRegex
                .Split(normalized)
                .Select(value => value.Trim())
                .Where(IsMeaningfulGoalSegment)
                .Select(NormalizeGoalSegment)
                .Where(IsMeaningfulGoalSegment)
                .Distinct(StringComparer.Ordinal)
                .ToList();
        }

        if (segments.Count == 0)
        {
            segments.Add(NormalizeGoalSegment(message));
        }

        var goals = new List<PrototypeIterationPlanGoalResult>();
        var index = 1;
        foreach (var segment in segments)
        {
            if (goals.Count >= 4)
            {
                break;
            }

            goals.Add(new PrototypeIterationPlanGoalResult(
                index,
                BuildGoalTitle(index, segment),
                segment,
                $"完成并验证：{TrimForHint(segment)}。",
                "pending"));
            index++;
        }

        while (!usedStructuredGoals && goals.Count < 3)
        {
            var title = goals.Count switch
            {
                0 => "任务 1：补齐当前核心缺口",
                1 => "任务 2：收敛关键交互链路",
                _ => "任务 3：完成一次可验证检查"
            };
            var description = goals.Count switch
            {
                0 => "先补齐当前最影响可玩的核心能力，并让结果可见。",
                1 => "把与该能力直接相关的关键交互链路连通。",
                _ => "补一轮最小验证，确认这次改动已经可用。"
            };
            goals.Add(new PrototypeIterationPlanGoalResult(
                goals.Count + 1,
                title,
                description,
                $"完成并验证：{title.Replace("任务 ", "第 ", StringComparison.Ordinal)}。",
                "pending"));
        }

        return goals;
    }

    private static GenericCoreLoopGateResult AnalyzeGenericCoreLoopForPlanning(
        string message,
        IterationPlanningContext planningContext)
    {
        var requestSource = message ?? string.Empty;
        _ = planningContext;
        if (ExtractStructuredGoals(requestSource).Count > 0)
        {
            return GenericCoreLoopGateResult.NotApplicable();
        }

        if (string.IsNullOrWhiteSpace(requestSource))
        {
            return GenericCoreLoopGateResult.NotApplicable();
        }

        var hasCombat = ContainsAny(requestSource, "杀怪", "怪", "战斗", "combat", "battle", "fight", "monster", "enemy", "boss", "Boss");
        var hasLoot = ContainsAny(requestSource, "掉装备", "掉落", "金币", "loot", "drop", "gold", "equipment");
        var hasGrowth = ContainsAny(requestSource, "经验", "升级", "变强", "成长", "exp", "level", "growth", "stronger");
        var hasBossScope = ContainsAny(requestSource, "boss", "Boss", "小Boss", "挑战Boss");
        if ((!hasCombat && !hasBossScope) || (!hasLoot && !hasGrowth && !hasBossScope))
        {
            return GenericCoreLoopGateResult.NotApplicable();
        }

        var optionalLargeSystemsInRequest = CountPresentGroups(
            requestSource,
            ["多职业", "职业", "class", "classes"],
            ["完整商店", "商店", "购买药水", "shop", "merchant"],
            ["多地图", "营地地图", "野外地图", "地图切换", "camp", "field map", "multiple maps"],
            ["boss", "Boss", "小Boss", "挑战Boss"],
            ["复杂词缀", "词缀", "affix", "随机装备"],
            ["剧情", "任务", "npc", "quest", "story"]);

        var coreLoopStepsInRequest = CountPresentGroups(
            requestSource,
            ["进入战斗", "遇敌", "触发战斗", "encounter", "combat entry"],
            ["杀怪", "打怪", "战斗结算", "defeat enemy", "kill"],
            ["掉装备", "掉落", "金币", "loot", "drop", "gold"],
            ["经验", "升级", "level", "exp"],
            ["装备", "穿戴", "equipment", "equip"],
            ["继续", "下一场", "反复", "repeat", "continue"]);

        if (optionalLargeSystemsInRequest >= 4 || coreLoopStepsInRequest >= 6 || (hasBossScope && CountPresentGroups(requestSource, ["购买", "shop", "merchant"], ["地图", "route", "node", "event"], ["任务", "剧情", "npc", "quest"]) >= 2))
        {
            return new GenericCoreLoopGateResult(
                true,
                null,
                "最小循环已经包含过多系统，超过通用游戏模块能力范围，需要定制游戏类型路线。");
        }

        var planningMessage = """
            1. 先完成这个最小循环里最关键的一步
            2. 再补下一步直接相关的反馈
            3. 只保留当前需求真正需要的可玩反馈
            4. 如果当前需求已经明显跨出最小循环，直接转定制路线
            """;
        return new GenericCoreLoopGateResult(false, planningMessage, "generic_loot_combat_core_loop");
    }

    private static int CountPresentGroups(string source, params string[][] groups)
    {
        return groups.Count(group => ContainsAny(source, group));
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgContractGoals(
        string message,
        List<PrototypeIterationPlanGoalResult> existingGoals,
        PrototypeContractSnapshot prototypeContract)
    {
        _ = existingGoals;
        return BuildJrpgFirstLoopGoals(message, null, prototypeContract, null);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildJrpgFirstLoopGoals(
        string message,
        IterationPlanningContext? planningContext,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        var selected = SelectJrpgFirstLoopCapabilities(message, planningContext, prototypeContract, regenerationGuidance);
        var contractInstruction = prototypeContract is null
            ? "Use the project execution guide, current prototype state, and GDD-derived prototype contract as hard acceptance input."
            : BuildContractGoalInstruction(prototypeContract);
        var explicitRules = ExtractExplicitContractRuleClauses(
            JrpgRouteSemantics.ExtractPrototypeContractIntentText(prototypeContract?.Json),
            message,
            regenerationGuidance);
        var hint = TrimForHint(string.Join(" ", message, regenerationGuidance).Trim(), 120);
        var goals = new List<PrototypeIterationPlanGoalResult>(selected.Count);
        var index = 1;
        foreach (var capability in selected)
        {
            var goalIndex = index++;
            var explicitRuleClause = BuildExplicitRuleClauseForCapability(capability.Id, explicitRules);
            var description = capability.DescriptionTemplate
                .Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal)
                .Replace("{sourceHint}", hint, StringComparison.Ordinal) + explicitRuleClause;
            var acceptance = capability.AcceptanceTemplate
                .Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal) + explicitRuleClause;
            goals.Add(new PrototypeIterationPlanGoalResult(
                goalIndex,
                BuildJrpgDisplayGoalTitle(capability),
                description,
                acceptance,
                "pending"));
        }

        return goals;
    }

    private static List<PrototypeIterationPlanGoalResult> BuildSurvivorsLikeFirstLoopGoals(
        string message,
        PrototypeContractSnapshot prototypeContract,
        string? regenerationGuidance)
    {
        var contractInstruction = BuildContractGoalInstruction(prototypeContract);
        var hint = TrimForHint(string.Join(" ", message, regenerationGuidance).Trim(), 120);
        var goals = new List<PrototypeIterationPlanGoalResult>(SurvivorsLikeFirstLoopCapabilities.Length);
        var index = 1;
        foreach (var capability in SurvivorsLikeFirstLoopCapabilities)
        {
            var goalIndex = index++;
            goals.Add(new PrototypeIterationPlanGoalResult(
                goalIndex,
                $"Vampire Survivors-like First Loop: {capability.Title}",
                capability.DescriptionTemplate
                    .Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal)
                    .Replace("{sourceHint}", hint, StringComparison.Ordinal),
                capability.AcceptanceTemplate.Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal),
                "pending"));
        }

        return goals;
    }

    private static List<PrototypeIterationPlanGoalResult> BuildDeckbuilderFirstLoopGoals(
        string message,
        PrototypeContractSnapshot prototypeContract,
        string? regenerationGuidance)
    {
        var contractInstruction = BuildContractGoalInstruction(prototypeContract);
        var hint = TrimForHint(string.Join(" ", message, regenerationGuidance).Trim(), 120);
        var selected = SelectDeckbuilderFirstLoopCapabilities(message, prototypeContract, regenerationGuidance);
        var goals = new List<PrototypeIterationPlanGoalResult>(selected.Count);
        var index = 1;
        foreach (var capability in selected)
        {
            var goalIndex = index++;
            goals.Add(new PrototypeIterationPlanGoalResult(
                goalIndex,
                $"Deckbuilder First Loop: {capability.Title}",
                capability.DescriptionTemplate
                    .Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal)
                    .Replace("{sourceHint}", hint, StringComparison.Ordinal),
                capability.AcceptanceTemplate.Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal),
                "pending"));
        }

        return goals;
    }

    private static IReadOnlyList<JrpgFirstLoopCapability> SelectJrpgFirstLoopCapabilities(
        string message,
        IterationPlanningContext? planningContext,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        var text = BuildJrpgSelectionText(message, planningContext, prototypeContract, regenerationGuidance);
        var selectedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "opening_context",
            "field_navigation"
        };

        var messageText = message ?? string.Empty;
        var guidanceText = regenerationGuidance ?? string.Empty;
        var sourceContractText = JrpgRouteSemantics.ExtractPrototypeContractIntentText(prototypeContract?.Json);
        var sourceContractProbeText = string.Join(" ", messageText, guidanceText, sourceContractText).ToLowerInvariant();
        var explicitlyNoConflict =
            (JrpgRouteSemantics.ContainsBattleNegation(messageText) ||
             JrpgRouteSemantics.ContainsBattleNegation(guidanceText) ||
             JrpgRouteSemantics.ContainsBattleNegation(sourceContractText)) &&
            !JrpgRouteSemantics.RequiresBattleScene(sourceContractProbeText);
        var explicitlyNoReward =
            (JrpgRouteSemantics.ContainsRewardNegation(messageText) ||
             JrpgRouteSemantics.ContainsRewardNegation(guidanceText) ||
             JrpgRouteSemantics.ContainsRewardNegation(sourceContractText)) &&
            !JrpgRouteSemantics.RequiresRewardFlow(sourceContractProbeText);
        var hasConflict = !explicitlyNoConflict && (JrpgRouteSemantics.RequiresBattleScene(sourceContractProbeText) || ContainsAny(sourceContractProbeText, "danger", "首战", "battle", "combat", "fight", "enemy", "monster", "遇敌", "战斗", "冲突", "挑战"));
        var hasReward = !explicitlyNoReward && JrpgRouteSemantics.RequiresRewardFlow(sourceContractProbeText);
        var hasOpeningContext = ContainsAny(text, "opening context", "who they control", "hero/context/objective", "player objective", "开场", "玩家身份", "当前目标");
        var hasStory = ContainsAny(text, "story", "quest", "npc", "dialog", "dialogue", "town", "village", "objective", "cutscene", "narrative", "剧情", "任务", "村庄", "城镇", "对话", "目标", "事件");
        var hasInteraction = hasStory || ContainsAny(text, "chest", "inspect", "talk", "discover", "interaction", "探索", "宝箱", "调查", "交互", "发现");
        var hasPartyState = ContainsAny(text, "party", "character", "hero", "hp", "mp", "stat", "status", "equipment", "job", "角色", "队伍", "主角", "生命", "属性", "装备", "职业");
        var hasReturnLoop = ContainsAny(text, "loop", "return", "continue", "repeat", "map loop", "first loop", "闭环", "返回", "继续", "循环", "首轮");

        if (hasOpeningContext)
        {
            selectedIds.Add("opening_context");
        }

        if (hasInteraction)
        {
            selectedIds.Add("interaction_discovery");
        }

        if (hasConflict)
        {
            selectedIds.Add("conflict_entry");
        }

        if ((ContainsAny(text, "battle", "combat", "fight", "challenge", "battle scene", "battlescene", "战斗", "结算", "挑战") ||
             ContainsAny(sourceContractProbeText, "battle", "combat", "fight", "challenge", "battle scene", "battlescene", "战斗", "结算", "挑战")) &&
            !explicitlyNoConflict)
        {
            selectedIds.Add("battle_or_challenge_resolution");
        }

        if (hasPartyState)
        {
            selectedIds.Add("party_or_character_state");
        }

        if (hasReward)
        {
            selectedIds.Add("growth_feedback");
        }

        if (hasReturnLoop)
        {
            selectedIds.Add("return_or_continue_loop");
        }

        if (hasStory)
        {
            selectedIds.Add("quest_or_story_progress");
        }

        selectedIds.Add("final_first_loop_acceptance");
        return SelectJrpgCapabilitiesInOrder(selectedIds);
    }

    private static IReadOnlyList<JrpgFirstLoopCapability> SelectJrpgCapabilitiesInOrder(params string[] selectedIds)
    {
        return SelectJrpgCapabilitiesInOrder(new HashSet<string>(selectedIds, StringComparer.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<JrpgFirstLoopCapability> SelectJrpgCapabilitiesInOrder(ISet<string> selectedIds)
    {
        return JrpgFirstLoopCapabilities
            .Where(capability => selectedIds.Contains(capability.Id))
            .ToArray();
    }

    private static string[] BuildSelectedCapabilitiesForRoute(
        IGameTypeRouteStrategy routeStrategy,
        string message,
        IterationPlanningContext? planningContext,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        if (string.Equals(routeStrategy.GameTypeId, "deckbuilder", StringComparison.OrdinalIgnoreCase))
        {
            return SelectDeckbuilderFirstLoopCapabilities(message, prototypeContract, regenerationGuidance)
                .Select(capability => capability.Id)
                .ToArray();
        }

        if (!string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            return [];
        }

        return SelectJrpgFirstLoopCapabilities(message, planningContext, prototypeContract, regenerationGuidance)
            .Select(capability => capability.Id)
            .ToArray();
    }

    private static IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> BuildRequiredModulesForProject(
        ProjectSnapshot project,
        IGameTypeRouteStrategy routeStrategy,
        PrototypeContractSnapshot? prototypeContract)
    {
        var modules = BuildRequiredModulesFromContractSnapshot(project).ToDictionary(module => module.Id, StringComparer.OrdinalIgnoreCase);
        foreach (var module in BuildRequiredModulesForRoute(routeStrategy, prototypeContract))
        {
            modules[module.Id] = module;
        }

        return modules.Values.OrderBy(module => module.Id, StringComparer.OrdinalIgnoreCase).ToArray();
    }

    private static IReadOnlyList<string> BuildInteractionOwners(
        PrototypeIterationPlanGoalResult goal,
        IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> requiredModules)
    {
        var owners = new HashSet<string>(StringComparer.Ordinal);
        if (goal.UiSurface is not null)
        {
            if (!string.IsNullOrWhiteSpace(goal.UiSurface.SceneOwner))
            {
                owners.Add($"scene:{goal.UiSurface.SceneOwner}");
            }
            if (!string.IsNullOrWhiteSpace(goal.UiSurface.NodeOwner))
            {
                owners.Add($"node:{goal.UiSurface.NodeOwner}");
            }
        }

        if (goal.GodotThirdPersonCameraProfile is not null)
        {
            if (!string.IsNullOrWhiteSpace(goal.GodotThirdPersonCameraProfile.RigRef))
            {
                owners.Add($"rig:{goal.GodotThirdPersonCameraProfile.RigRef}");
            }
            if (!string.IsNullOrWhiteSpace(goal.GodotThirdPersonCameraProfile.TargetOwner))
            {
                owners.Add($"target:{goal.GodotThirdPersonCameraProfile.TargetOwner}");
            }
        }

        var requirementIds = goal.RequirementIds ?? [];
        foreach (var module in requiredModules.Where(module =>
                     (module.Status is "required" or "covered" or "verified") &&
                     (module.RequirementIds ?? []).Any(requirementId => requirementIds.Contains(requirementId, StringComparer.OrdinalIgnoreCase))))
        {
            owners.Add($"module:{module.Id}:interaction-owner");
            owners.Add($"scene:module:{module.Id}");
            owners.Add($"node:module:{module.Id}:interaction-root");
        }

        return owners.OrderBy(value => value, StringComparer.Ordinal).ToArray();
    }

    private static IReadOnlyList<PrototypeIterationInteractionGeometryResult> BuildInteractionGeometry(
        PrototypeIterationPlanGoalResult goal,
        IReadOnlyList<string> owners)
    {
        var coordinateSpace = goal.EngineSemantics?.CoordinateSemantics ?? "project-profile-coordinate-semantics";
        var geometry = new List<PrototypeIterationInteractionGeometryResult>();
        foreach (var owner in owners.Where(value => value.StartsWith("node:", StringComparison.Ordinal)))
        {
            geometry.Add(new PrototypeIterationInteractionGeometryResult(
                $"goal-{goal.GoalIndex:00}-control-{geometry.Count + 1:00}",
                owner,
                "control_rect",
                coordinateSpace,
                null,
                "rect",
                "interaction_target",
                owner["node:".Length..],
                "control_get_global_rect",
                "runtime_resolved"));
        }

        foreach (var owner in owners.Where(value =>
                     value.StartsWith("module:", StringComparison.Ordinal) &&
                     value.EndsWith(":interaction-owner", StringComparison.Ordinal)))
        {
            var moduleId = owner["module:".Length..(owner.Length - ":interaction-owner".Length)];
            if (string.Equals(moduleId, "hand_card_dragging", StringComparison.OrdinalIgnoreCase))
            {
                geometry.Add(RuntimeControlGeometry(goal.GoalIndex, geometry.Count + 1, owner, coordinateSpace, "drag_source", $"module:{moduleId}:drag-source-node"));
                geometry.Add(RuntimeControlGeometry(goal.GoalIndex, geometry.Count + 1, owner, coordinateSpace, "drop_target", $"module:{moduleId}:drop-target-node"));
            }
            else if (string.Equals(moduleId, "route_map_path_selection", StringComparison.OrdinalIgnoreCase))
            {
                geometry.Add(RuntimeControlGeometry(goal.GoalIndex, geometry.Count + 1, owner, coordinateSpace, "selection_target", $"module:{moduleId}:selectable-node"));
            }
            else
            {
                geometry.Add(new PrototypeIterationInteractionGeometryResult(
                    $"goal-{goal.GoalIndex:00}-collision-{geometry.Count + 1:00}",
                    owner,
                    "collision_shape",
                    coordinateSpace,
                    null,
                    "runtime_shape",
                    "collision_target",
                    $"module:{moduleId}:collision-shape-node",
                    "collision_shape_runtime_bounds",
                    "runtime_resolved"));
            }
        }

        if (geometry.Count == 0)
        {
            if (owners.Count == 0)
            {
                return [];
            }
            var owner = owners.First();
            geometry.Add(new PrototypeIterationInteractionGeometryResult(
                $"goal-{goal.GoalIndex:00}-collision-01",
                owner,
                "collision_shape",
                coordinateSpace,
                null,
                "runtime_shape",
                "interaction_target",
                owner,
                "owner_runtime_bounds",
                "runtime_resolved"));
        }

        return geometry;
    }

    private static PrototypeIterationInteractionGeometryResult RuntimeControlGeometry(
        int goalIndex,
        int geometryIndex,
        string owner,
        string coordinateSpace,
        string interactionRole,
        string locatorRef)
    {
        return new PrototypeIterationInteractionGeometryResult(
            $"goal-{goalIndex:00}-control-{geometryIndex:00}",
            owner,
            "control_rect",
            coordinateSpace,
            null,
            "rect",
            interactionRole,
            locatorRef,
            "control_get_global_rect",
            "runtime_resolved");
    }

    private static PrototypeIterationPlanSourceHashes ToIterationPlanSourceHashes(PrototypeContractStatusResult status)
    {
        return new PrototypeIterationPlanSourceHashes(
            status.SourceGddHash,
            status.SourceSceneRouteHash,
            status.SourceRequirementMapHash,
            status.ContractHash,
            status.SourceContractSnapshotHash,
            status.SourceGodotUiContractHash,
            status.SourceUiStyleContractHash,
            status.UiStyleSnapshotHash);
    }

    private static readonly string[] SourceBoundaryHashKeys =
    [
        "source_gdd_hash",
        "source_scene_route_hash",
        "source_requirement_map_hash",
        "source_contract_hash",
        "source_contract_snapshot_hash",
        "source_godot_ui_contract_hash",
        "source_ui_style_contract_hash",
        "ui_style_snapshot_hash"
    ];

    private static IReadOnlyDictionary<string, string> ToSourceBoundaryHashMap(PrototypeIterationPlanSourceHashes sourceHashes)
    {
        return new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["source_gdd_hash"] = sourceHashes.SourceGddHash,
            ["source_scene_route_hash"] = sourceHashes.SourceSceneRouteHash,
            ["source_requirement_map_hash"] = sourceHashes.SourceRequirementMapHash,
            ["source_contract_hash"] = sourceHashes.SourceContractHash,
            ["source_contract_snapshot_hash"] = sourceHashes.SourceContractSnapshotHash,
            ["source_godot_ui_contract_hash"] = sourceHashes.SourceGodotUiContractHash,
            ["source_ui_style_contract_hash"] = sourceHashes.SourceUiStyleContractHash,
            ["ui_style_snapshot_hash"] = sourceHashes.UiStyleSnapshotHash
        };
    }

    internal static PrototypeIterationStyleApplicability ToIterationStyleApplicability(PrototypeContractStatusResult status)
    {
        var applicability = status.UiStyleApplicability;
        var evidenceHash = ComputeHash(JsonSerializer.Serialize(new
        {
            source_ui_style_contract_hash = status.SourceUiStyleContractHash,
            status = applicability.Status,
            reason = applicability.Reason,
            reviewed_by = applicability.ReviewedBy,
            recheck_trigger = applicability.RecheckTrigger
        }));
        return new PrototypeIterationStyleApplicability(
            applicability.Status,
            applicability.Reason,
            applicability.ReviewedBy,
            applicability.RecheckTrigger,
            evidenceHash);
    }

    private static object ToStyleApplicabilityState(PrototypeIterationStyleApplicability applicability)
    {
        return new
        {
            status = applicability.Status,
            reason = applicability.Reason,
            reviewed_by = applicability.ReviewedBy,
            recheck_trigger = applicability.RecheckTrigger,
            evidence_hash = applicability.EvidenceHash
        };
    }

    private static PrototypeIterationStyleAuthority? BuildStyleAuthority(PrototypeContractStatusResult status)
    {
        if (!string.Equals(status.UiStyleApplicability.Status, "applicable", StringComparison.Ordinal))
        {
            return null;
        }

        var definition = GodotUiStyleCatalog.Styles.FirstOrDefault(style =>
            string.Equals(style.StyleId, status.UiStyleId, StringComparison.Ordinal) &&
            string.Equals(style.Version, status.UiStyleVersion, StringComparison.Ordinal));
        if (definition is null || string.IsNullOrWhiteSpace(status.UiStyleSnapshotHash))
        {
            return null;
        }
        var snapshotPayload = JsonSerializer.Serialize(new
        {
            schema_profile_hash = GodotUiStyleSnapshotSchema.SchemaProfileHash,
            source_ui_style_contract_hash = GodotUiStyleCatalog.CatalogHash,
            definition.StyleId,
            definition.Version,
            definition.GuidePath,
            definition.TriggerTags,
            definition.DesignDna,
            definition.GodotControls,
            definition.GameCompositionTemplates
        }, new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true });
        return !string.Equals(ComputeHash(snapshotPayload), status.UiStyleSnapshotHash, StringComparison.Ordinal)
            ? null
            : new PrototypeIterationStyleAuthority(
                definition.StyleId,
                definition.Version,
                status.UiStyleSnapshotHash,
                definition.GuidePath,
                definition.TriggerTags,
                definition.DesignDna,
                definition.GodotControls,
                definition.GameCompositionTemplates);
    }

    private async Task<IterationPlanLiveGovernanceResult> ReadLiveGovernanceAsync(
        ProjectSnapshot project,
        GameDesignRequirementMapResult? requirementMap,
        CancellationToken cancellationToken)
    {
        var adminRows = await _metadataStore.ListProjectAdminReviewQueueForProjectAsync(
            project.AccountId,
            project.ProjectId,
            "",
            0,
            cancellationToken);
        var unresolvedAdmin = adminRows.FirstOrDefault(row =>
            row.Severity is "P0" or "P1" &&
            ProjectAdminReviewQueuePolicy.IsBlocking(row));
        if (unresolvedAdmin is not null)
        {
            return new IterationPlanLiveGovernanceResult(
                new PrototypeIterationPlanBlockerResult(
                    "admin_review_blocked",
                    unresolvedAdmin.Severity,
                    "Iteration planning is blocked by unresolved admin review.",
                    [unresolvedAdmin.RequirementId],
                    ["admin-review:required"]),
                new Dictionary<string, string>());
        }

        var approved = adminRows
            .Where(row => row.Severity is "P0" or "P1" && ProjectAdminReviewQueuePolicy.IsCleared(row))
            .Where(row => !string.IsNullOrWhiteSpace(row.RequirementId))
            .GroupBy(row => row.RequirementId, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(
                group => group.Key,
                group =>
                {
                    var row = group.OrderByDescending(item => item.DecisionVersion).First();
                    return $"admin-decision:{row.RequirementId}:v{row.DecisionVersion}";
                },
                StringComparer.OrdinalIgnoreCase);
        var allReviewRowsApproved = requirementMap is not null && requirementMap.Requirements
            .Where(row => row.Priority is "P0" or "P1" && row.Status is "needs_review" or "conflict" or "explicitly_deferred")
            .All(row => approved.ContainsKey(row.RequirementId));

        var diagnostics = await _metadataStore.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", project.AccountId, project.ProjectId, null, null, null, 500),
            cancellationToken);
        var unresolvedDiagnostic = diagnostics.FirstOrDefault(row =>
            row.Severity is "P0" or "P1" &&
            IsPlanningBlockingDiagnostic(row.FailureFamily) &&
            !(allReviewRowsApproved && string.Equals(row.FailureFamily, "requirement_map_invalid", StringComparison.Ordinal)));
        if (unresolvedDiagnostic is not null)
        {
            return new IterationPlanLiveGovernanceResult(
                new PrototypeIterationPlanBlockerResult(
                    "diagnostic_blocked",
                    unresolvedDiagnostic.Severity,
                    "Iteration planning is blocked by an unresolved project diagnostic.",
                    [],
                    ["diagnostic:unresolved"]),
                new Dictionary<string, string>());
        }

        return new IterationPlanLiveGovernanceResult(null, approved);
    }

    private static bool IsPlanningBlockingDiagnostic(string failureFamily)
    {
        return failureFamily is not (
            "plan_hash_conflict" or
            "plan_session_conflict" or
            "plan_confirmation_required" or
            "legacy_plan_source_unknown");
    }

    private async Task<PrototypeIterationPlanResult> RejectPlanBeforeLlmAsync(
        ProjectSnapshot project,
        PrototypeIterationPlanSourceHashes sourceHashes,
        string domainCode,
        string summary,
        CancellationToken cancellationToken,
        IReadOnlyList<string>? evidenceRefs = null,
        IReadOnlyList<string>? requirementIds = null)
    {
        var sourceHashRef = ComputeHash(JsonSerializer.Serialize(sourceHashes));
        var blocker = new PrototypeIterationPlanBlockerResult(
            domainCode,
            "P1",
            summary,
            requirementIds ?? [],
            evidenceRefs ?? ["meta/routes/gdd-requirements/latest.json", "routes/prototype-contract/latest.json"]);
        await RecordPlanDiagnosticAsync(project, blocker, sourceHashRef, cancellationToken);
        return new PrototypeIterationPlanResult(
            "",
            "blocked",
            summary,
            [],
            null,
            null,
            [],
            "rejected",
            "",
            sourceHashes,
            new PrototypeIterationPlanCoverageResult(0, 0, 0, 0, 0, []),
            [blocker]);
    }

    private async Task RecordPlanDiagnosticAsync(
        ProjectSnapshot project,
        PrototypeIterationPlanBlockerResult blocker,
        string sourceHashRef,
        CancellationToken cancellationToken)
    {
        var stableSourceHashRef = string.IsNullOrWhiteSpace(sourceHashRef) ? "no-source" : sourceHashRef;
        var existing = await _metadataStore.ListProjectDiagnosticSpoolForAdminAsync(
            new ProjectDiagnosticSpoolQuery("unresolved", project.AccountId, project.ProjectId, "iteration-plan", blocker.DomainCode, blocker.Severity, 100),
            cancellationToken);
        if (existing.Any(row => PrototypeIterationGoalService.HasDiagnosticScope(row.SourceRefsJson, stableSourceHashRef, "no-plan")))
        {
            return;
        }

        var sourceRefsJson = JsonSerializer.Serialize(new[]
        {
            new { kind = "source_hash_ref", @ref = stableSourceHashRef },
            new { kind = "plan_hash", @ref = "no-plan" },
            new { kind = "sidecar", @ref = "meta/routes/iteration-plan/latest.json" }
        });
        await _metadataStore.RecordProjectDiagnosticSpoolEntryAsync(
            new ProjectDiagnosticSpoolCommand(
                project.AccountId,
                project.ProjectId,
                "iteration-plan",
                blocker.DomainCode,
                blocker.Severity,
                blocker.Summary,
                JsonSerializer.Serialize(blocker.EvidenceRefs),
                "meta/routes/iteration-plan/latest.json",
                ProjectNameSnapshot: project.Name,
                SourceRefsJson: sourceRefsJson,
                RetentionClass: "unresolved_blocker",
                RemediationHintId: blocker.DomainCode,
                DedupeScopeKey: ProjectDiagnosticScopeKey.Compute(stableSourceHashRef)),
            cancellationToken);
    }

    private async Task<PrototypeIterationPlanConfirmationOperationResult> RejectConfirmationAsync(
        ProjectSnapshot project,
        string domainCode,
        string summary,
        string sourceHashRef,
        CancellationToken cancellationToken,
        string status = "blocked")
    {
        var blocker = new PrototypeIterationPlanBlockerResult(domainCode, "P1", summary, [], ["meta/routes/iteration-plan/latest.json"]);
        await RecordPlanDiagnosticAsync(project, blocker, sourceHashRef, cancellationToken);
        return new PrototypeIterationPlanConfirmationOperationResult(status, domainCode, summary, "rejected");
    }

    private static bool IsCurrentRequirementMap(
        GameDesignRequirementMapResult? requirementMap,
        PrototypeContractStatusResult contractStatus,
        IReadOnlyDictionary<string, string>? approvedRequirementDecisions = null)
    {
        approvedRequirementDecisions ??= new Dictionary<string, string>();
        var acceptableStatus = requirementMap is not null &&
            (requirementMap.Status == "ready" || requirementMap.Requirements
                .Where(row => row.Priority is "P0" or "P1" && row.Status is "needs_review" or "conflict" or "explicitly_deferred")
                .All(row => approvedRequirementDecisions.ContainsKey(row.RequirementId)));
        return requirementMap is not null &&
               acceptableStatus &&
               string.Equals(requirementMap.SourceGddHash, contractStatus.SourceGddHash, StringComparison.Ordinal) &&
               string.Equals(requirementMap.SourceSceneRouteHash, contractStatus.SourceSceneRouteHash, StringComparison.Ordinal) &&
               string.Equals(requirementMap.SourceRequirementMapHash, contractStatus.SourceRequirementMapHash, StringComparison.Ordinal) &&
               string.Equals(requirementMap.SourceContractSnapshotHash, contractStatus.SourceContractSnapshotHash, StringComparison.Ordinal) &&
               string.Equals(requirementMap.SourceGodotUiContractHash, contractStatus.SourceGodotUiContractHash, StringComparison.Ordinal);
    }

    private void WriteBlockedTraceabilityAttemptState(
        ProjectSnapshot project,
        PrototypeIterationPlanSourceHashes sourceHashes,
        IReadOnlyList<PrototypeIterationPlanGoalResult> goals,
        IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> requiredModules,
        IReadOnlyList<PrototypeIterationPlanBlockerResult> blockers,
        PrototypeIterationPlanCoverageResult? coverage = null,
        string planHash = "",
        string sourceHashRef = "")
    {
        var attemptId = $"{DateTimeOffset.UtcNow:yyyyMMddTHHmmssfffZ}-{Guid.NewGuid():N}";
        _routeStateWriter.WriteIterationPlanAttemptState(project, attemptId, new
        {
            route = "iteration-plan",
            attempt_id = attemptId,
            status = "blocked",
            source_gdd_hash = sourceHashes.SourceGddHash,
            source_scene_route_hash = sourceHashes.SourceSceneRouteHash,
            source_requirement_map_hash = sourceHashes.SourceRequirementMapHash,
            source_contract_hash = sourceHashes.SourceContractHash,
            source_contract_snapshot_hash = sourceHashes.SourceContractSnapshotHash,
            source_godot_ui_contract_hash = sourceHashes.SourceGodotUiContractHash,
            source_ui_style_contract_hash = sourceHashes.SourceUiStyleContractHash,
            ui_style_snapshot_hash = sourceHashes.UiStyleSnapshotHash,
            source_hash_ref = sourceHashRef,
            plan_hash = planHash,
            coverage = coverage is null ? null : ToCoverageState(coverage),
            blockers = blockers.Select(ToBlockerState).ToArray(),
            required_modules = requiredModules.Select(ToRequiredModuleState).ToArray(),
            goals = goals.Select(ToGoalState).ToArray(),
            confirmation = new { status = "blocked", session_id = "", plan_hash = planHash, source_hash_ref = sourceHashRef },
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
    }

    private static object ToCoverageState(PrototypeIterationPlanCoverageResult coverage)
    {
        return new
        {
            p0_p1_requirement_count = coverage.P0P1RequirementCount,
            goal_covered_count = coverage.GoalCoveredCount,
            module_covered_count = coverage.ModuleCoveredCount,
            skeleton_covered_count = coverage.SkeletonCoveredCount,
            explicit_blocker_count = coverage.ExplicitBlockerCount,
            uncovered_requirement_ids = coverage.UncoveredRequirementIds
        };
    }

    private static object ToBlockerState(PrototypeIterationPlanBlockerResult blocker)
    {
        return new
        {
            domain_code = blocker.DomainCode,
            severity = blocker.Severity,
            summary = blocker.Summary,
            requirement_ids = blocker.RequirementIds,
            evidence_refs = blocker.EvidenceRefs
        };
    }

    private static object ToRequiredModuleState(PrototypeIterationPlanRequiredModuleResult module)
    {
        return new
        {
            id = module.Id,
            source = module.Source,
            status = module.Status,
            applies_unless = module.AppliesUnless,
            acceptance_markers = module.AcceptanceMarkers,
            covered_by_goal_capability = module.CoveredByGoalCapability,
            requirement_ids = module.RequirementIds ?? [],
            source_reason = module.SourceReason,
            source_refs = module.SourceRefs ?? [],
            priority = module.Priority,
            coverage_status = module.CoverageStatus,
            validation_refs = module.ValidationRefs ?? []
        };
    }

    private static object ToInteractionGeometryState(PrototypeIterationInteractionGeometryResult geometry)
    {
        return new
        {
            geometry_id = geometry.GeometryId,
            owner_ref = geometry.OwnerRef,
            geometry_kind = geometry.GeometryKind,
            coordinate_space = geometry.CoordinateSpace,
            bounds = geometry.Bounds is null ? null : new
            {
                x = geometry.Bounds.X,
                y = geometry.Bounds.Y,
                width = geometry.Bounds.Width,
                height = geometry.Bounds.Height
            },
            shape = geometry.Shape,
            interaction_role = geometry.InteractionRole,
            locator_ref = geometry.LocatorRef,
            resolution_source = geometry.ResolutionSource,
            bounds_policy = geometry.BoundsPolicy
        };
    }

    private static object ToGoalState(PrototypeIterationPlanGoalResult goal)
    {
        return new
        {
            goal_index = goal.GoalIndex,
            title = goal.Title,
            description = goal.Description,
            acceptance_hint = goal.AcceptanceHint,
            status = goal.Status,
            requirement_ids = goal.RequirementIds ?? [],
            infrastructure_reason = goal.InfrastructureReason is null ? null : new
            {
                code = goal.InfrastructureReason.Code,
                summary = goal.InfrastructureReason.Summary,
                source_refs = goal.InfrastructureReason.SourceRefs
            },
            source_hash_ref = goal.SourceHashRef,
            capability_requirements = goal.CapabilityRequirements is null ? null : new
            {
                dynamic_ui_required = goal.CapabilityRequirements.DynamicUiRequired,
                third_person_camera_required = goal.CapabilityRequirements.ThirdPersonCameraRequired,
                feature_family_reading_required = goal.CapabilityRequirements.FeatureFamilyReadingRequired,
                interaction_region_required = goal.CapabilityRequirements.InteractionRegionRequired
            },
            ui_surface = goal.UiSurface is null ? null : new
            {
                scene_owner = goal.UiSurface.SceneOwner,
                node_owner = goal.UiSurface.NodeOwner,
                surface_type = goal.UiSurface.SurfaceType,
                layout = goal.UiSurface.Layout,
                viewport_mode = goal.UiSurface.ViewportMode,
                canvas_layer = goal.UiSurface.CanvasLayer,
                input_ownership = goal.UiSurface.InputOwnership,
                focus_policy = goal.UiSurface.FocusPolicy,
                feedback_states = goal.UiSurface.FeedbackStates,
                state_boundary = goal.UiSurface.StateBoundary,
                validation_refs = goal.UiSurface.ValidationRefs,
                no_ui_needed_decision_ref = goal.UiSurface.NoUiNeededDecisionRef
            },
            style = goal.Style is null ? null : new
            {
                style_token_refs = goal.Style.StyleTokenRefs,
                component_families = goal.Style.ComponentFamilies,
                design_dna = goal.Style.DesignDna,
                composition = goal.Style.Composition,
                motion = goal.Style.Motion,
                ui_tree_readback = goal.Style.UiTreeReadback,
                visual_evidence_expectations = goal.Style.VisualEvidenceExpectations,
                style_not_applicable_decision_ref = goal.Style.StyleNotApplicableDecisionRef
            },
            engine_semantics = goal.EngineSemantics is null ? null : new
            {
                viewport_semantics = goal.EngineSemantics.ViewportSemantics,
                coordinate_semantics = goal.EngineSemantics.CoordinateSemantics,
                input_semantics = goal.EngineSemantics.InputSemantics,
                layer_semantics = goal.EngineSemantics.LayerSemantics,
                profile_refs = goal.EngineSemantics.ProfileRefs,
                reading_evidence_refs = goal.EngineSemantics.ReadingEvidenceRefs
            },
            interaction_region = goal.InteractionRegion is null ? null : new
            {
                artifact_ref = goal.InteractionRegion.ArtifactRef,
                devices = goal.InteractionRegion.Devices,
                valid_regions = goal.InteractionRegion.ValidRegions,
                invalid_regions = goal.InteractionRegion.InvalidRegions,
                state_transitions = goal.InteractionRegion.StateTransitions,
                validation_refs = goal.InteractionRegion.ValidationRefs,
                owner_refs = goal.InteractionRegion.OwnerRefs,
                planned_geometry = goal.InteractionRegion.PlannedGeometry.Select(ToInteractionGeometryState).ToArray(),
                no_interaction_region_needed_decision_ref = goal.InteractionRegion.NoInteractionRegionNeededDecisionRef
            },
            godot_ui_update_ownership = goal.GodotUiUpdateOwnership is null ? null : new
            {
                construction_owner = goal.GodotUiUpdateOwnership.ConstructionOwner,
                update_mode = goal.GodotUiUpdateOwnership.UpdateMode,
                state_owner = goal.GodotUiUpdateOwnership.StateOwner,
                cleanup_policy = goal.GodotUiUpdateOwnership.CleanupPolicy,
                signal_ownership = goal.GodotUiUpdateOwnership.SignalOwnership,
                stable_item_identity = goal.GodotUiUpdateOwnership.StableItemIdentity
            },
            godot_third_person_camera_profile = goal.GodotThirdPersonCameraProfile is null ? null : new
            {
                rig_ref = goal.GodotThirdPersonCameraProfile.RigRef,
                target_owner = goal.GodotThirdPersonCameraProfile.TargetOwner,
                input_owner = goal.GodotThirdPersonCameraProfile.InputOwner,
                collision_owner = goal.GodotThirdPersonCameraProfile.CollisionOwner,
                validation_method = goal.GodotThirdPersonCameraProfile.ValidationMethod,
                yaw_pitch_ownership = goal.GodotThirdPersonCameraProfile.YawPitchOwnership,
                camera_relative_movement_boundary = goal.GodotThirdPersonCameraProfile.CameraRelativeMovementBoundary,
                camera_state_validation = goal.GodotThirdPersonCameraProfile.CameraStateValidation
            }
        };
    }

    private static IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> BuildRequiredModulesForRoute(
        IGameTypeRouteStrategy routeStrategy,
        PrototypeContractSnapshot? prototypeContract)
    {
        if (string.Equals(routeStrategy.GameTypeId, "deckbuilder", StringComparison.OrdinalIgnoreCase))
        {
            return DeckbuilderRequiredModules
                .Select(module => HasExplicitDeckbuilderRequiredModuleConflict(module.Id, prototypeContract)
                    ? module with { Status = "skipped_by_explicit_gdd_conflict" }
                    : module)
                .ToArray();
        }

        return [];
    }

    private static IReadOnlyList<PrototypeIterationPlanRequiredModuleResult> BuildRequiredModulesFromContractSnapshot(ProjectSnapshot project)
    {
        var snapshot = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson).ContractSnapshot;
        if (!snapshot.HasContract)
        {
            return [];
        }

        return snapshot.RequiredModules
            .Where(module => module.IsAlways)
            .Select(module => new PrototypeIterationPlanRequiredModuleResult(
                module.ModuleId,
                string.IsNullOrWhiteSpace(snapshot.GuidePath) ? "project_contract_snapshot" : snapshot.GuidePath,
                "required",
                "explicit_gdd_conflict",
                [],
                null))
            .ToArray();
    }

    private static bool HasExplicitDeckbuilderRequiredModuleConflict(string moduleId, PrototypeContractSnapshot? prototypeContract)
    {
        var text = BuildDeckbuilderRequiredModuleConflictText(prototypeContract);
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        return moduleId switch
        {
            "route_map_path_selection" => ContainsAny(
                text,
                "no route map",
                "without route map",
                "no route selection",
                "without route selection",
                "no path selection",
                "without path selection",
                "single combat scene only",
                "single battle scene only",
                "battle only prototype",
                "combat only prototype"),
            "hand_card_dragging" => ContainsAny(
                text,
                "no drag",
                "without drag",
                "no dragging",
                "without dragging",
                "button only card play",
                "button-only card play",
                "click only card play",
                "click-to-play only",
                "tap only card play"),
            _ => false
        };
    }

    private static string BuildDeckbuilderRequiredModuleConflictText(PrototypeContractSnapshot? prototypeContract)
    {
        if (string.IsNullOrWhiteSpace(prototypeContract?.Json))
        {
            return "";
        }

        return string.Join(
            " ",
            prototypeContract.Json,
            JrpgRouteSemantics.ExtractPrototypeContractIntentText(prototypeContract.Json)).ToLowerInvariant();
    }

    private static string BuildJrpgSelectionText(
        string message,
        IterationPlanningContext? planningContext,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        return string.Join(
            " ",
            message ?? string.Empty,
            regenerationGuidance ?? string.Empty).ToLowerInvariant();
    }

    private static readonly JrpgFirstLoopCapability[] JrpgFirstLoopCapabilities =
    [
        new(
            "opening_context",
            "opening context and player objective",
            "在扩展系统前先建立 JRPG 短原型的即时语境：玩家必须知道自己操控谁、身处哪里、下一步目标是什么。{contractInstruction} 来源需求：{sourceHint}",
            "只有可玩场景清晰呈现可操控角色、当前语境和目标，并且目标能对应项目合同或明确的需要修复阻塞项时才算通过。"),
        new(
            "field_navigation",
            "field navigation and stable control",
            "把野外或城镇移动层作为独立能力验证：Start Adventure 或项目入口必须进入可见地图（visible MapScene / playable field），显示玩家标记或角色，并支持 stable movement。地图与玩家素材（map/player asset）需要可见。{contractInstruction}",
            "只有入口能打开可见、可玩的野外/地图/城镇场景（visible MapScene / playable field），移动稳定（stable movement），并且玩家与地图素材（asset）使用可见时才算通过。"),
        new(
            "interaction_discovery",
            "interaction and discovery beat",
            "验证第一个有意义的交互节点，例如与 NPC 对话、调查物体、打开宝箱或发现下一目标。除非项目没有交互需求，否则不要把它和战斗结算或最终验收混在一起。{contractInstruction}",
            "只有至少一个项目相关交互可见、可抵达，并能改变反馈、目标状态或玩家理解时才算通过。"),
        new(
            "conflict_entry",
            "conflict entry trigger",
            "验证从导航或交互进入第一次冲突、遭遇、挑战或战斗的过渡。若项目存在概率、脚本接触或固定步数等触发规则，必须纳入验证。{contractInstruction}",
            "只有玩家能清楚触发或到达第一次冲突，并且触发规则可见或已验证时才算通过。"),
        new(
            "battle_or_challenge_resolution",
            "battle or challenge resolution",
            "验证一次可读的 JRPG 冲突结算：战斗/挑战呈现、玩家与敌人或障碍状态、行动反馈、胜利/失败或成功/失败结算都要清楚。除非项目确实没有单独奖励或返回需求，否则不要把成长或返回闭环证明藏进这一步。{contractInstruction}",
            "只有一次冲突或挑战能以可读状态、行动反馈和结算证据完整完成时才算通过。"),
        new(
            "party_or_character_state",
            "party or character state readability",
            "验证首轮循环需要展示给玩家的角色状态，例如 HP、属性、队友、装备、被动技能或状态变化。重点是可读性和规则可追溯，不是完整成长系统。{contractInstruction}",
            "只有相关角色或队伍状态可见、可理解，并且与项目规则一致时才算通过。"),
        new(
            "growth_feedback",
            "growth, reward, or consequence feedback",
            "验证首轮循环的奖励、成长或后果反馈，例如奖励选择、获得道具、属性变化、经验、技能解锁或剧情后果。{contractInstruction}",
            "只有奖励/成长/后果已经展示，玩家能理解含义，并且状态变化可见或已验证时才算通过。"),
        new(
            "return_or_continue_loop",
            "return or continue loop",
            "验证玩家在第一次结算后可以继续：返回地图、前往下一目标、重复循环，或进入明确的下一个可玩状态，同时不能出现视觉叠加或输入失效。{contractInstruction}",
            "只有原型进入预期的下一个可玩状态，并且导航/输入仍可用时才算通过。"),
        new(
            "quest_or_story_progress",
            "quest or story progress",
            "如果项目要求叙事框架、NPC 流程、城镇事件或目标完成，就验证首轮循环里的故事或任务推进。范围只限第一个可玩循环，不做长篇内容生产。{contractInstruction}",
            "只有目标、任务或剧情状态有可见推进，并且能追溯到项目需求时才算通过。"),
        new(
            "final_first_loop_acceptance",
            "final first-loop acceptance",
            "只有已选择能力都有证据后，才执行 JRPG 首轮闭环最终验收。覆盖入口、导航、已选择能力证据、项目专属合同字段、Godot 验证证据和打包准备度。{contractInstruction}",
            "只有已选择 JRPG 首轮能力可以端到端游玩、项目专属合同字段（project-specific contract fields）已呈现或明确阻塞、素材已解析、Godot 验证通过且打包准备度成立时才算通过。")
    ];

    private static readonly HashSet<string> JrpgFirstLoopCapabilityIds = JrpgFirstLoopCapabilities
        .Select(capability => capability.Id)
        .ToHashSet(StringComparer.OrdinalIgnoreCase);

    private sealed record JrpgFirstLoopCapability(
        string Id,
        string Title,
        string DescriptionTemplate,
        string AcceptanceTemplate);

    private static readonly SurvivorsLikeFirstLoopCapability[] SurvivorsLikeFirstLoopCapabilities =
    [
        new(
            "run_start_survival_objective",
            "run start and survival objective",
            "Establish the playable run entry and immediate survival objective before adding systems. The player must know they are starting a survival run, what the short-term objective is, and what initial state they have. {contractInstruction} Source request: {sourceHint}",
            "Pass only when the prototype has a clear run start, visible survival objective or timer/goal, and readable initial player state."),
        new(
            "arena_movement_camera",
            "arena movement and camera readability",
            "Validate the arena control layer independently: the player can move continuously, the camera or viewport keeps the player readable, and the arena/background does not obscure threats. {contractInstruction}",
            "Pass only when movement is stable, the player remains readable, and arena/camera framing supports survival play."),
        new(
            "enemy_spawn_pressure",
            "enemy spawn pressure curve",
            "Validate continuous enemy spawning and a first pressure curve. The prototype must show ongoing spawn pressure rather than a one-time enemy placement. {contractInstruction}",
            "Pass only when enemies spawn repeatedly with readable pressure escalation or wave/timer rules."),
        new(
            "auto_attack_core_weapon",
            "auto-attack or core weapon loop",
            "Validate the core weapon loop: an auto-attack or equivalent repeated attack uses cooldown/range/direction rules, hits enemies, and creates clear hit/kill feedback. {contractInstruction}",
            "Pass only when the core weapon repeatedly attacks, can hit spawned enemies, and produces readable hit or kill feedback."),
        new(
            "damage_health_death",
            "hit, damage, health, and death feedback",
            "Validate the survival risk loop: enemies can threaten the player, health or equivalent durability is readable, damage feedback is visible, and death/failure is understandable. {contractInstruction}",
            "Pass only when player damage, enemy damage/death, health state, and failure feedback are visible or validated."),
        new(
            "pickup_resource_collection",
            "pickup and resource collection",
            "Validate the first collection loop: defeated enemies or arena events produce pickup resources such as experience, coins, gems, or energy, and the player can collect them. {contractInstruction}",
            "Pass only when pickups are visible, collectible, and update a readable resource or progress meter."),
        new(
            "level_up_choice_power_selection",
            "level-up choice or power selection",
            "Validate the first power choice: reaching the resource threshold opens a small set of understandable upgrades, ideally two or three choices, and the player can select one. {contractInstruction}",
            "Pass only when level-up or power selection appears, choices are understandable, and one selected option is applied."),
        new(
            "build_growth_power_fantasy",
            "build growth and power fantasy feedback",
            "Validate that the selected power produces visible growth in the survival loop, such as more damage, larger area, faster cooldown, extra projectile, summon, movement, or defensive change. {contractInstruction}",
            "Pass only when the player can perceive a before/after power increase in runtime behavior, not only text."),
        new(
            "escalation_event_milestone",
            "escalation event or mini-milestone",
            "Validate one short-run escalation beat such as elite spawn, timed wave, chest/event, danger spike, or milestone reward so the loop has a small climax. {contractInstruction}",
            "Pass only when the run reaches a visible escalation event or milestone beyond basic enemy spawning."),
        new(
            "run_end_summary_restart",
            "run end, summary, and restart loop",
            "Validate final first-loop closure: death, timeout, milestone completion, or stage result leads to a summary and restart path. Include selected capability proof, project contract traceability, Godot validation evidence, and package readiness. {contractInstruction}",
            "Pass only when the selected Vampire Survivors-like first-loop capabilities are playable end-to-end, run result/summary is visible, restart works, project-specific contract fields are represented or explicitly blocked, and package readiness is proven.")
    ];

    private sealed record SurvivorsLikeFirstLoopCapability(
        string Id,
        string Title,
        string DescriptionTemplate,
        string AcceptanceTemplate);

    private static IReadOnlyList<DeckbuilderFirstLoopCapability> SelectDeckbuilderFirstLoopCapabilities(
        string message,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        var selectedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "run_context",
            "starter_deck_readability",
            "resource_and_turn_rules",
            "enemy_intent_or_pressure",
            "card_play_resolution",
            "deck_cycle_and_hand_flow",
            "combat_resolution",
            "reward_or_card_draft",
            "deck_mutation_feedback",
            "final_deckbuilder_first_loop_acceptance"
        };

        return DeckbuilderFirstLoopCapabilities
            .Where(capability => selectedIds.Contains(capability.Id))
            .ToArray();
    }

    private static bool RequiresDeckbuilderRouteChoice(string text)
    {
        return ContainsAny(
            text,
            "map",
            "route",
            "node",
            "event",
            "shop",
            "elite",
            "branch",
            "path choice",
            "slay the spire",
            "\u8def\u7ebf",
            "\u8282\u70b9",
            "\u4e8b\u4ef6",
            "\u5546\u5e97",
            "\u7cbe\u82f1",
            "\u5206\u652f",
            "\u722c\u5854");
    }

    private static readonly DeckbuilderFirstLoopCapability[] DeckbuilderFirstLoopCapabilities =
    [
        new(
            "run_context",
            "run context and objective",
            "在扩展系统前建立卡牌构筑的 run 语境：玩家必须知道自己处于哪一局、操控谁或什么、短期目标、失败条件或前进方向。{contractInstruction} 来源需求：{sourceHint}",
            "只有可玩场景呈现清晰的 run 语境、当前角色/阵营、短期目标、失败条件或前进方向时才算通过。"),
        new(
            "starter_deck_readability",
            "starter deck readability",
            "验证初始牌组或工具箱可读性：手牌、抽牌堆、弃牌堆、牌组列表或初始牌组摘要至少一种可见，并且卡牌名称、费用和效果可读。{contractInstruction}",
            "只有卡牌名称、费用/资源和效果对玩家可读，并且至少一个牌组/手牌/牌堆界面可见时才算通过。"),
        new(
            "resource_and_turn_rules",
            "resource and turn rules",
            "验证资源和回合约束层：能量、法力、行动点、蜡烛或项目专属费用必须可见；出牌必须正确消耗资源；玩家可以结束或推进回合。{contractInstruction}",
            "只有资源/费用和回合规则可见且可执行，包括资源消耗和结束回合或等价流程时才算通过。"),
        new(
            "enemy_intent_or_pressure",
            "enemy intent or pressure source",
            "验证玩家为什么需要做战术出牌选择：展示敌方意图、攻击、增益、倒计时、轨道压力、叙事威胁或其他压力源。{contractInstruction}",
            "只有敌方意图或等价压力可见，并且会影响或改变出牌决策时才算通过。"),
        new(
            "card_play_resolution",
            "card play resolution feedback",
            "验证最小出牌手感：玩家至少能打出一张牌，并立刻看到伤害、格挡、召唤、献祭、抽牌、状态或项目专属反馈。{contractInstruction}",
            "只有至少一张牌可以打出，并产生可见的即时结算反馈时才算通过。"),
        new(
            "deck_cycle_and_hand_flow",
            "deck cycle and hand flow",
            "验证卡牌会在牌库系统中流动，而不是静态按钮：抽牌、弃牌、洗牌、消耗或等价手牌流程必须可见且不会卡死。{contractInstruction}",
            "只有至少一个抽牌/弃牌/洗牌/消耗流程可见、可重复且不会死锁时才算通过。"),
        new(
            "combat_resolution",
            "combat win/fail resolution",
            "验证第一次卡牌战斗冲突结果：战斗可以到达胜利或失败，并且在奖励或下一节点工作前结果清晰可读。{contractInstruction}",
            "只有战斗可以胜利或失败，并暴露明确结果状态时才算通过。"),
        new(
            "reward_or_card_draft",
            "post-combat card draft or reward",
            "验证从卡牌战斗进入卡牌构筑的桥梁：胜利后展示至少 2 到 3 个奖励/卡牌选择，允许玩家选择或跳过，并把选择写入牌组状态。{contractInstruction}",
            "只有战后奖励或选牌可见、可选择，并且会影响牌组或 run 状态时才算通过。"),
        new(
            "deck_mutation_feedback",
            "deck mutation feedback",
            "验证构筑选择真的生效：选牌、删牌、升级、获得遗物/神器/图腾或规则变化，必须在牌组或 run 状态反馈中可见。{contractInstruction}",
            "只有构筑选择后牌组或规则状态发生可见变化时才算通过。"),
        new(
            "map_or_route_choice",
            "map or route choice",
            "只在需求明确要求时验证路线选择：玩家可以在路线、节点、事件、商店、精英、下一场战斗或等价下一分支中选择，不强迫所有卡牌构筑都变成地图游戏。{contractInstruction}",
            "只有至少两个下一节点/路线/事件可选择，或非地图项目能清晰进入下一场战斗/事件状态时才算通过。"),
        new(
            "final_deckbuilder_first_loop_acceptance",
            "final deckbuilder first-loop acceptance",
            "在已选择能力都有证据后执行卡牌构筑首轮闭环最终验收。覆盖 run 语境、牌组可读性、费用/回合规则、敌方压力、出牌、牌库循环、战斗结果、奖励/牌组变化、可选路线选择、项目专属合同字段、Godot 验证证据和打包准备度。{contractInstruction}",
            "只有已选择卡牌构筑首轮能力可以端到端游玩、项目专属合同字段已呈现或明确阻塞、素材解析成功、Godot 验证通过且打包准备度成立时才算通过。")
    ];

    private sealed record DeckbuilderFirstLoopCapability(
        string Id,
        string Title,
        string DescriptionTemplate,
        string AcceptanceTemplate);

    private static readonly PrototypeIterationPlanRequiredModuleResult[] DeckbuilderRequiredModules =
    [
        new(
            "route_map_path_selection",
            "docs/game-type-guides/card-game.md",
            "required",
            "explicit_gdd_conflict",
            ["RouteChoice|RouteMap|RouteNode|ChooseNode|SelectRoute|PathSelection"],
            "final_deckbuilder_first_loop_acceptance"),
        new(
            "hand_card_dragging",
            "docs/game-type-guides/card-game.md",
            "required",
            "explicit_gdd_conflict",
            ["DragCard|CardDrag|Dragging|DraggedCard|DragPreview|DropTarget|DropZone|DropArea|PlayZone"],
            "card_play_resolution")
    ];

    private static List<PrototypeIterationPlanGoalResult> AppendGenericFinalAcceptanceGoal(
        List<PrototypeIterationPlanGoalResult> goals,
        string message,
        PrototypeContractSnapshot prototypeContract)
    {
        if (goals.Any(IsFinalAcceptanceGoal))
        {
            return goals;
        }

        var nextIndex = goals.Count == 0 ? 1 : goals.Max(goal => goal.GoalIndex) + 1;
        var summarySource = goals
            .Where(goal => !IsFinalAcceptanceGoal(goal))
            .Select(goal => string.Join(" ", goal.Title, goal.Description))
            .ToArray();
        var scopeLabel = ContainsAny(message, "最小闭环", "最小循环", "minimum loop", "minimal loop")
            ? "最小闭环"
            : "完整可玩切片";
        var genericSummaryActions = ExtractGenericLoopActionList(message);
        var genericSummarySource = genericSummaryActions.Where(item => !ContainsAny(item, "Boss", "boss")).Take(3).ToArray();
        if (genericSummarySource.Length == 0)
        {
            genericSummarySource = summarySource.Take(3).ToArray();
        }
        goals.Add(new PrototypeIterationPlanGoalResult(
            nextIndex,
            "最终任务：完整可玩原型验收",
            $"对{scopeLabel}执行通用原型最终验收，以当前可用的原型技能合同和项目专属原型合同作为检查来源。{BuildContractGoalInstruction(prototypeContract)} 来源需求：{scopeLabel} {BuildGenericLoopSummaryText(genericSummarySource)}",
            $"只有完整可玩原型通过平台验收时才算完成：项目构建、默认原型场景 smoke、主菜单进入、打包准备度、没有待执行或需要修复的游戏模块任务，并且项目专属原型合同字段全部通过。{BuildContractGoalInstruction(prototypeContract)}",
            "pending"));
        return goals;
    }

    private static string BuildContractGoalInstruction(PrototypeContractSnapshot prototypeContract)
    {
        return string.IsNullOrWhiteSpace(prototypeContract.Json)
            ? "如果缺少项目原型合同，不要编造表单值；请把任务标记为 needs_fix，直到合同恢复。"
            : "将项目原型合同和 input_traceability 作为硬性验收输入；每个非空用户字段都必须映射到任务、验证检查或明确的 needs_fix 阻塞项，且用户表单值优先于类型模板默认值。";
    }

    private static ExplicitContractRules ExtractExplicitContractRuleClauses(params string?[] sources)
    {
        var text = string.Join(" ", sources.Where(source => !string.IsNullOrWhiteSpace(source))).ToLowerInvariant();
        return new ExplicitContractRules(
            EncounterProbability: ContainsAny(text, "10%", "10 %"),
            GuaranteedEncounter: ContainsAny(text, "10步", "10 steps", "10-step"),
            FifteenBattleVictory: ContainsAny(text, "15场", "15 battles", "15 battle"),
            AnyLossDefeat: ContainsAny(text, "任一战斗失败", "any battle loss", "any-loss defeat", "game loss"),
            EnemyScaling: ContainsAny(text, "每个怪物", "下一个怪物", "+5", "+2", "5点生命", "5 hp", "+5 hp", "2点攻击", "2 atk", "+2 atk", "enemy scaling"));
    }

    private static string BuildExplicitRuleClauseForCapability(string capabilityId, ExplicitContractRules rules)
    {
        var clauses = new List<string>();
        if (string.Equals(capabilityId, "conflict_entry", StringComparison.OrdinalIgnoreCase))
        {
            if (rules.EncounterProbability)
            {
                clauses.Add("explicit encounter probability rule: 10%");
            }

            if (rules.GuaranteedEncounter)
            {
                clauses.Add("explicit guaranteed encounter rule: 10 steps / 10-step");
            }
        }

        if (string.Equals(capabilityId, "battle_or_challenge_resolution", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(capabilityId, "party_or_character_state", StringComparison.OrdinalIgnoreCase))
        {
            if (rules.FifteenBattleVictory)
            {
                clauses.Add("explicit 15-battle victory rule: 15 battles");
                clauses.Add("15 battles");
            }

            if (rules.AnyLossDefeat)
            {
                clauses.Add("explicit any-loss defeat rule: any battle loss means game loss");
            }

            if (rules.EnemyScaling)
            {
                clauses.Add("explicit enemy scaling rule: +5 HP / +2 ATK or project-specific enemy scaling");
            }
        }

        if (string.Equals(capabilityId, "final_first_loop_acceptance", StringComparison.OrdinalIgnoreCase))
        {
            if (rules.EncounterProbability)
            {
                clauses.Add("10% encounter probability");
            }

            if (rules.GuaranteedEncounter)
            {
                clauses.Add("10-step guaranteed encounter");
            }

            if (rules.FifteenBattleVictory)
            {
                clauses.Add("15-battle victory");
                clauses.Add("15 battles");
            }

            if (rules.AnyLossDefeat)
            {
                clauses.Add("any battle loss");
                clauses.Add("any-loss defeat");
            }

            if (rules.EnemyScaling)
            {
                clauses.Add("enemy scaling: +5 HP / +2 ATK");
            }
        }

        return clauses.Count == 0
            ? string.Empty
            : $" Explicit project rule coverage required here: {string.Join("; ", clauses)}.";
    }

    private static List<PrototypeIterationPlanGoalResult> EnsureJrpgExplicitRuleCoverage(
        IReadOnlyList<PrototypeIterationPlanGoalResult> goals,
        PrototypeContractSnapshot prototypeContract,
        string message,
        string? regenerationGuidance)
    {
        var rules = ExtractExplicitContractRuleClauses(
            JrpgRouteSemantics.ExtractPrototypeContractIntentText(prototypeContract.Json),
            message,
            regenerationGuidance);
        if (!rules.HasAny)
        {
            return goals.ToList();
        }

        return goals.Select(goal =>
        {
            var capabilityId = ResolveJrpgCapabilityIdFromGoalTitle(goal.Title);
            if (string.IsNullOrWhiteSpace(capabilityId))
            {
                return goal;
            }

            var clause = BuildExplicitRuleClauseForCapability(capabilityId, rules);
            if (string.IsNullOrWhiteSpace(clause))
            {
                return goal;
            }

            var existing = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint);
            if (ContainsAny(existing, clause))
            {
                return goal;
            }

            return goal with
            {
                Description = goal.Description + clause,
                AcceptanceHint = goal.AcceptanceHint + clause
            };
        }).ToList();
    }

    private static string? ResolveJrpgCapabilityIdFromGoalTitle(string title)
    {
        foreach (var capability in JrpgFirstLoopCapabilities)
        {
            if (ContainsAny(title, capability.Title, BuildJrpgDisplayGoalTitle(capability), BuildJrpgDisplayTitle(capability)))
            {
                return capability.Id;
            }
        }

        return null;
    }

    private sealed record ExplicitContractRules(
        bool EncounterProbability,
        bool GuaranteedEncounter,
        bool FifteenBattleVictory,
        bool AnyLossDefeat,
        bool EnemyScaling)
    {
        public bool HasAny => EncounterProbability || GuaranteedEncounter || FifteenBattleVictory || AnyLossDefeat || EnemyScaling;
    }

    private static bool IsFinalAcceptanceGoal(PrototypeIterationPlanGoalResult goal)
    {
        var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
        return text.Contains("final", StringComparison.Ordinal) &&
               (text.Contains("acceptance", StringComparison.Ordinal) ||
                text.Contains("full playable", StringComparison.Ordinal) ||
                text.Contains("最终", StringComparison.Ordinal) ||
                text.Contains("验收", StringComparison.Ordinal) ||
                text.Contains("端到端", StringComparison.Ordinal) ||
                text.Contains("全量", StringComparison.Ordinal) ||
                text.Contains("交付验收", StringComparison.Ordinal));
    }

    private static string? FindRpgPlanContractIssue(
        ProjectIterationGoalSnapshot[] goals,
        PrototypeIterationPlanningAnalysisResult? planningAnalysis,
        string? sourceMessage,
        HashSet<string>? selectedCapabilities,
        PrototypeContractSnapshot? prototypeContract)
    {
        var combined = string.Join("\n", goals.Select(goal => string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint))).ToLowerInvariant();
        var requirementSource = BuildRpgRequirementSource(sourceMessage, planningAnalysis, prototypeContract);
        var requiresConflict =
            JrpgRouteSemantics.RequiresBattleScene(requirementSource) ||
            (selectedCapabilities is not null &&
             (selectedCapabilities.Contains("conflict_entry") || selectedCapabilities.Contains("battle_or_challenge_resolution")));
        var requiresReward =
            JrpgRouteSemantics.RequiresRewardFlow(requirementSource) ||
            (selectedCapabilities is not null && selectedCapabilities.Contains("growth_feedback"));
        var missing = new List<string>();
        var boundaryIssue = FindRpgPlanAcceptanceBoundaryIssue(goals);
        if (boundaryIssue is not null)
        {
            return boundaryIssue;
        }

        if (!ContainsAny(combined, "mapscene", "map scene", "mapscene.tscn", "field navigation", "playable field", "playable map", "town scene", "visible map", "地图场景", "可玩地图", "野外", "场域", "城镇") ||
            !ContainsAny(combined, "start adventure", "project entry", "visible map", "visible-map", "opens a valid visible", "entry opens", "可见地图", "可玩地图", "开始冒险", "入口"))
        {
            missing.Add("field navigation and stable control capability");
        }

        if (requiresConflict &&
            !ContainsAny(combined, "battlescene", "battle scene", "battle or challenge", "challenge resolution", "battlescene.tscn", "战斗场景", "战斗", "挑战"))
        {
            missing.Add("battle or challenge resolution capability");
        }

        if (requiresConflict &&
            !ContainsAny(combined, "encounter trigger", "first encounter", "guaranteed encounter", "encounter progress", "conflict entry", "10 steps", "10-step", "冲突入口", "遇敌入口", "第一次冲突", "第一次遇敌", "触发规则"))
        {
            missing.Add("independent conflict entry capability");
        }
        if (requiresReward &&
            !ContainsAny(combined, "reward", "growth", "consequence", "3-choice", "three reward", "three choices", "return-to-map", "return to the map", "奖励", "成长", "后果", "三选一", "3 选 1", "返回地图"))
        {
            missing.Add("growth/reward feedback and return-or-continue capability");
        }

        if (!ContainsAny(combined, "final acceptance", "final first-loop acceptance", "full playable prototype acceptance", "full playable", "package readiness", "end-to-end", "交付验收", "全量验收", "最终验收", "最终首轮闭环验收", "端到端", "打包准备度"))
        {
            missing.Add("final first-loop acceptance capability");
        }

        var explicitContractRuleIssues = FindMissingExplicitContractRules(combined, planningAnalysis, sourceMessage, prototypeContract);
        missing.AddRange(explicitContractRuleIssues);

        if (missing.Count == 0)
        {
            return null;
        }

        return $"Missing RPG contract steps: {string.Join(", ", missing)}.";
    }

    private static string BuildRpgRequirementSource(
        string? sourceMessage,
        PrototypeIterationPlanningAnalysisResult? planningAnalysis,
        PrototypeContractSnapshot? prototypeContract)
    {
        var evidence = planningAnalysis is null
            ? []
            : planningAnalysis.FieldCoverage
                .Where(item => !string.Equals(item.Status, "missing", StringComparison.OrdinalIgnoreCase))
                .Select(item => item.Evidence)
                .Where(item => !string.IsNullOrWhiteSpace(item));

        return string.Join(
            " ",
            sourceMessage ?? string.Empty,
            JrpgRouteSemantics.ExtractPrototypeContractIntentText(prototypeContract?.Json),
            string.Join(" ", evidence)).ToLowerInvariant();
    }

    private static List<string> FindMissingExplicitContractRules(
        string combined,
        PrototypeIterationPlanningAnalysisResult? planningAnalysis,
        string? sourceMessage,
        PrototypeContractSnapshot? prototypeContract)
    {
        var missing = new List<string>();
        var evidenceTexts = new List<(string Field, string Evidence)>();
        if (planningAnalysis is not null && planningAnalysis.FieldCoverage.Count > 0)
        {
            foreach (var item in planningAnalysis.FieldCoverage)
            {
                if (!string.Equals(item.Status, "completed", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(item.Status, "partial", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                var evidence = (item.Evidence ?? string.Empty).Trim();
                if (!string.IsNullOrWhiteSpace(evidence))
                {
                    evidenceTexts.Add((((item.Field ?? string.Empty).Trim().ToLowerInvariant()), evidence));
                }
            }
        }

        if (!string.IsNullOrWhiteSpace(sourceMessage))
        {
            evidenceTexts.Add(("source_message", sourceMessage.Trim()));
        }

        var contractIntentText = JrpgRouteSemantics.ExtractPrototypeContractIntentText(prototypeContract?.Json);
        if (!string.IsNullOrWhiteSpace(contractIntentText))
        {
            evidenceTexts.Add(("prototype_contract", contractIntentText));
        }

        foreach (var (field, evidence) in evidenceTexts)
        {
            var checksWinFail = field is "win_fail_conditions" or "source_message" or "prototype_contract";
            var checksFlowRules = field is "game_feature" or "core_gameplay_loop" or "source_message" or "prototype_contract";

            if (checksWinFail)
            {
                if (ContainsAny(evidence, "15场", "15 battles", "15 battle") &&
                    !ContainsAny(combined, "15场", "15 battles", "15 battle"))
                {
                    missing.Add("explicit 15-battle victory rule coverage");
                }

                if (ContainsAny(evidence, "任一战斗失败", "任一", "any battle loss", "any-loss defeat", "game loss") &&
                    !ContainsAny(combined, "任一战斗失败", "any battle loss", "any-loss defeat", "game loss", "失败即"))
                {
                    missing.Add("explicit any-loss defeat rule coverage");
                }
            }

            if (checksFlowRules)
            {
                if (ContainsAny(evidence, "10%", "10 %") &&
                    !ContainsAny(combined, "10%", "10 %"))
                {
                    missing.Add("explicit encounter probability rule coverage");
                }

                if (ContainsAny(evidence, "10步", "10 steps", "10-step") &&
                    !ContainsAny(combined, "10步", "10 steps", "10-step"))
                {
                    missing.Add("explicit guaranteed encounter rule coverage");
                }

                if (ContainsAny(evidence, "每个怪物", "下一个怪物", "+5", "+2", "enemy", "怪物") &&
                    ContainsAny(evidence, "5点生命", "5 hp", "+5 hp", "2点攻击", "2 atk", "+2 atk") &&
                    !ContainsAny(combined, "5点生命", "5 hp", "+5 hp", "2点攻击", "2 atk", "+2 atk", "enemy scaling", "怪物成长"))
                {
                    missing.Add("explicit enemy scaling rule coverage");
                }
            }
        }

        return missing.Distinct(StringComparer.Ordinal).ToList();
    }

    private static string? FindRpgPlanAcceptanceBoundaryIssue(ProjectIterationGoalSnapshot[] goals)
    {
        var orderedGoals = goals.OrderBy(goal => goal.GoalIndex).ToArray();
        if (orderedGoals.Length == 0)
        {
            return null;
        }

        var fieldGoal = orderedGoals.FirstOrDefault(IsJrpgFieldNavigationGoal);

        if (fieldGoal is null)
        {
            return "GDD-derived plan boundary mismatch: the selected capability graph must include field navigation and stable control when required by the project contract.";
        }

        var fieldGoalText = string.Join(" ", fieldGoal.Title, fieldGoal.Description, fieldGoal.AcceptanceHint);
        if (!ContainsAny(fieldGoalText, "start adventure", "visible map", "visible mapscene", "mapscene", "stable movement", "可见地图", "可玩地图", "稳定移动", "稳定可控移动"))
        {
            return "RPG plan acceptance boundary mismatch: the field navigation capability must target Start Adventure to visible MapScene and stable movement before encounter, BattleScene, reward, polish, package readiness, or final acceptance work.";
        }

        var boundaryProbeText = StripRpgStepOneBoundaryExclusionClauses(fieldGoalText);
        if (ContainsAny(
                boundaryProbeText,
                "encounter entry",
                "encounter trigger",
                "first encounter",
                "battle scene",
                "battlescene",
                "battlescene.tscn",
                "reward",
                "3-choice",
                "three choices",
                "scene switching",
                "scene switch",
                "switch into",
                "return path",
                "full playable",
                "full rpg playable",
                "package readiness",
                "final acceptance"))
        {
            return "RPG plan acceptance boundary mismatch: the field navigation capability must only validate Start Adventure to visible MapScene and stable movement. Encounter trigger, BattleScene, reward, scene switching, package readiness, and final acceptance requirements must be split into later steps.";
        }

        var finalGoalText = string.Join(" ", orderedGoals[^1].Title, orderedGoals[^1].Description, orderedGoals[^1].AcceptanceHint);
        if (!ContainsAny(finalGoalText, "final acceptance", "full playable", "package readiness", "final first-loop acceptance", "first-loop acceptance", "end-to-end", "最终验收", "最终首轮闭环验收", "完整可玩", "端到端", "打包准备度"))
        {
            return "GDD-derived plan boundary mismatch: the final goal must be final first-loop acceptance with selected capability, contract, Godot validation, and package readiness coverage.";
        }

        var selectedCapabilities = ResolveJrpgCapabilitiesFromGoals(orderedGoals);
        if (!selectedCapabilities.Contains("field_navigation", StringComparer.OrdinalIgnoreCase))
        {
            return "GDD-derived plan boundary mismatch: the selected capability graph must include field navigation and stable control when required by the project contract.";
        }

        if (!selectedCapabilities.Contains("final_first_loop_acceptance", StringComparer.OrdinalIgnoreCase))
        {
            return "GDD-derived plan boundary mismatch: the selected capability graph must end with final first-loop acceptance.";
        }

        var hasReward = selectedCapabilities.Contains("growth_feedback", StringComparer.OrdinalIgnoreCase);
        if (hasReward &&
            !selectedCapabilities.Contains("return_or_continue_loop", StringComparer.OrdinalIgnoreCase))
        {
            return "JRPG first-loop plan boundary mismatch: reward or growth plans must include a return-or-continue loop capability.";
        }

        return null;
    }

    private static HashSet<string> ResolveJrpgCapabilitiesFromGoals(ProjectIterationGoalSnapshot[] goals)
    {
        var selected = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var goal in goals)
        {
            AddJrpgCapabilitiesFromText(selected, goal.Title);
        }

        return selected;
    }

    private static bool IsJrpgFieldNavigationGoal(ProjectIterationGoalSnapshot goal)
    {
        var title = goal.Title.ToLowerInvariant();
        if (ContainsAny(title, "field navigation", "stable control", "stable movement", "visible map", "mapscene", "map scene", "town scene", "地图导航", "稳定操控", "地图", "移动"))
        {
            return true;
        }

        var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
        return ContainsAny(text, "start adventure", "visible map", "visible mapscene", "mapscene", "map scene", "playable field", "playable map", "town scene", "stable movement", "controllable movement", "可见地图", "可玩地图", "稳定移动", "稳定可控移动");
    }

    private static void AddJrpgCapabilitiesFromText(HashSet<string> selected, string text)
    {
        text = text.ToLowerInvariant();
        if (ContainsAny(text, "final first-loop acceptance", "final acceptance", "full playable", "package readiness", "end-to-end", "最终验收", "最终首轮闭环验收", "完整可玩", "端到端", "打包准备度", "全量验收"))
        {
            selected.Add("final_first_loop_acceptance");
            return;
        }

        foreach (var capability in JrpgFirstLoopCapabilities)
        {
            if (ContainsAny(text, capability.Title, BuildJrpgDisplayGoalTitle(capability), BuildJrpgDisplayTitle(capability)))
            {
                selected.Add(capability.Id);
            }
        }

        var battleProbeText = JrpgRouteSemantics.NormalizeBattleDetectionText(text);
        var rewardProbeText = JrpgRouteSemantics.NormalizeRewardDetectionText(text);
        var requiresBattle = JrpgRouteSemantics.RequiresBattleScene(text);
        var requiresReward = JrpgRouteSemantics.RequiresRewardFlow(text);
        var explicitlyNoBattle =
            JrpgRouteSemantics.ContainsBattleNegation(text) &&
            !requiresBattle;
        var explicitlyNoReward =
            JrpgRouteSemantics.ContainsRewardNegation(text) &&
            !requiresReward;

        if (ContainsAny(text, "opening context", "player objective", "objective", "hero/context/objective", "目标", "开场"))
        {
            selected.Add("opening_context");
        }

        if (ContainsAny(text, "field navigation", "stable control", "stable movement", "visible map", "mapscene", "map scene", "town scene", "field", "movement", "地图导航", "稳定操控", "地图", "移动", "场景"))
        {
            selected.Add("field_navigation");
        }

        if (ContainsAny(text, "interaction", "discovery", "npc", "dialog", "chest", "inspect", "交互", "发现", "对话", "宝箱", "调查"))
        {
            selected.Add("interaction_discovery");
        }

        if (!explicitlyNoBattle &&
            ContainsAny(battleProbeText, "conflict entry", "encounter", "encounter trigger", "first encounter", "guaranteed encounter", "trigger", "遇敌", "触发"))
        {
            selected.Add("conflict_entry");
        }

        if (!explicitlyNoBattle &&
            ContainsAny(battleProbeText, "battlescene", "battle scene", "battle", "combat", "fight", "boss", "monster", "enemy", "challenge resolution", "combat resolution", "settlement", "战斗", "结算", "挑战"))
        {
            selected.Add("battle_or_challenge_resolution");
        }

        if (ContainsAny(text, "party or character state", "character state", "party", "hp", "stat", "status", "equipment", "角色", "队伍", "属性", "状态", "装备"))
        {
            selected.Add("party_or_character_state");
        }

        if (!explicitlyNoReward &&
            (requiresReward ||
             ContainsAny(rewardProbeText, "growth feedback", "consequence feedback", "story consequence", "item gain", "3-choice", "奖励", "成长", "经验", "升级", "道具")))
        {
            selected.Add("growth_feedback");
        }

        if (ContainsAny(text, "return or continue", "return-to-map", "return to the map", "return to map", "next playable state", "continue loop", "返回地图", "返回", "继续"))
        {
            selected.Add("return_or_continue_loop");
        }

        if (ContainsAny(text, "quest or story", "story progress", "quest", "story", "narrative", "objective completion", "剧情", "任务", "叙事"))
        {
            selected.Add("quest_or_story_progress");
        }
    }

    private static string? ResolveJrpgCapabilityIdFromText(string text)
    {
        var selected = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        AddJrpgCapabilitiesFromText(selected, text);
        return selected.Count == 1 ? selected.Single() : null;
    }

    private static string BuildJrpgDisplayGoalTitle(JrpgFirstLoopCapability capability)
    {
        return $"JRPG 首轮闭环：{BuildJrpgDisplayTitle(capability)}";
    }

    private static string BuildJrpgDisplayTitle(JrpgFirstLoopCapability capability)
    {
        return capability.Id switch
        {
            "opening_context" => "开局语境与玩家目标",
            "field_navigation" => "地图导航与稳定操控",
            "interaction_discovery" => "交互与发现节点",
            "conflict_entry" => "冲突入口触发",
            "battle_or_challenge_resolution" => "战斗或挑战结算",
            "party_or_character_state" => "角色或队伍状态可读性",
            "growth_feedback" => "成长、奖励或后果反馈",
            "return_or_continue_loop" => "返回或继续循环",
            "quest_or_story_progress" => "任务或剧情推进",
            "final_first_loop_acceptance" => "最终首轮闭环验收",
            _ => capability.Title
        };
    }

    private static string? FindSurvivorsLikePlanContractIssue(ProjectIterationGoalSnapshot[] goals)
    {
        if (goals.Length == 0)
        {
            return "Vampire Survivors-like plan boundary mismatch: the plan has no executable goals.";
        }

        var orderedGoals = goals.OrderBy(goal => goal.GoalIndex).ToArray();
        var selected = ResolveSurvivorsLikeCapabilitiesFromGoals(orderedGoals);
        var required = SurvivorsLikeFirstLoopCapabilities.Select(capability => capability.Id).ToArray();
        var missing = required.Where(id => !selected.Contains(id)).ToArray();
        if (missing.Length > 0)
        {
            return "Vampire Survivors-like plan boundary mismatch: missing first-loop capabilities: " + string.Join(", ", missing) + ".";
        }

        var firstText = string.Join(" ", orderedGoals[0].Title, orderedGoals[0].Description, orderedGoals[0].AcceptanceHint).ToLowerInvariant();
        if (!ContainsAny(firstText, "run start", "survival objective", "start", "objective"))
        {
            return "Vampire Survivors-like plan boundary mismatch: step 1 must establish run start and survival objective before arena movement, weapons, pickups, or final acceptance.";
        }

        var finalText = string.Join(" ", orderedGoals[^1].Title, orderedGoals[^1].Description, orderedGoals[^1].AcceptanceHint).ToLowerInvariant();
        if (!ContainsAny(finalText, "run end", "summary", "restart", "final first-loop", "end-to-end", "package readiness"))
        {
            return "Vampire Survivors-like plan boundary mismatch: the final goal must close the run with summary/restart and final first-loop acceptance.";
        }

        return null;
    }

    private static HashSet<string> ResolveSurvivorsLikeCapabilitiesFromGoals(ProjectIterationGoalSnapshot[] goals)
    {
        var selected = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var goal in goals)
        {
            var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
            if (ContainsAny(text, "run start and survival objective", "survival objective", "run start"))
            {
                selected.Add("run_start_survival_objective");
            }

            if (ContainsAny(text, "arena movement and camera", "arena movement", "camera readability"))
            {
                selected.Add("arena_movement_camera");
            }

            if (ContainsAny(text, "enemy spawn pressure", "spawn pressure", "pressure curve"))
            {
                selected.Add("enemy_spawn_pressure");
            }

            if (ContainsAny(text, "auto-attack", "auto attack", "core weapon loop"))
            {
                selected.Add("auto_attack_core_weapon");
            }

            if (ContainsAny(text, "hit, damage, health", "damage, health", "death feedback"))
            {
                selected.Add("damage_health_death");
            }

            if (ContainsAny(text, "pickup and resource collection", "pickup", "resource collection"))
            {
                selected.Add("pickup_resource_collection");
            }

            if (ContainsAny(text, "level-up choice", "level up choice", "power selection"))
            {
                selected.Add("level_up_choice_power_selection");
            }

            if (ContainsAny(text, "build growth", "power fantasy feedback", "power fantasy"))
            {
                selected.Add("build_growth_power_fantasy");
            }

            if (ContainsAny(text, "escalation event", "mini-milestone", "milestone"))
            {
                selected.Add("escalation_event_milestone");
            }

            if (ContainsAny(text, "run end", "summary", "restart loop", "final first-loop acceptance"))
            {
                selected.Add("run_end_summary_restart");
            }
        }

        return selected;
    }

    private static string BuildSurvivorsLikeRegenerationPrompt(ProjectIterationSessionDetails details)
    {
        return $"""
            Regenerate the iteration plan as Vampire Survivors-like first-loop capability steps:
            1. run start and survival objective
            2. arena movement and camera readability
            3. enemy spawn pressure curve
            4. auto-attack or core weapon loop
            5. hit, damage, health, and death feedback
            6. pickup and resource collection
            7. level-up choice or power selection
            8. build growth and power fantasy feedback
            9. escalation event or mini-milestone
            10. run end, summary, and restart loop

            Keep the source request in scope: {TrimForHint(details.Session.SourceMessage, 160)}
            """;
    }

    private static string? FindDeckbuilderPlanContractIssue(
        ProjectIterationGoalSnapshot[] goals,
        IReadOnlyList<PrototypeIterationPlanRequiredModuleResult>? requiredModules)
    {
        if (goals.Length == 0)
        {
            return "Deckbuilder plan boundary mismatch: the plan has no executable goals.";
        }

        var orderedGoals = goals.OrderBy(goal => goal.GoalIndex).ToArray();
        var selected = ResolveDeckbuilderCapabilitiesFromGoals(orderedGoals);
        var required = DeckbuilderFirstLoopCapabilities
            .Where(capability => !string.Equals(capability.Id, "map_or_route_choice", StringComparison.OrdinalIgnoreCase))
            .Select(capability => capability.Id)
            .ToArray();
        var missing = required.Where(id => !selected.Contains(id)).ToArray();
        if (missing.Length > 0)
        {
            return "Deckbuilder plan boundary mismatch: missing first-loop capabilities: " + string.Join(", ", missing) + ".";
        }

        var missingRequiredModules = DeckbuilderRequiredModules
            .Where(module => requiredModules is null || !requiredModules.Any(candidate => string.Equals(candidate.Id, module.Id, StringComparison.OrdinalIgnoreCase)))
            .Select(module => module.Id)
            .ToArray();
        if (missingRequiredModules.Length > 0)
        {
            return "Deckbuilder plan boundary mismatch: missing required game-type modules: " + string.Join(", ", missingRequiredModules) + ".";
        }

        var firstText = string.Join(" ", orderedGoals[0].Title, orderedGoals[0].Description, orderedGoals[0].AcceptanceHint).ToLowerInvariant();
        if (!ContainsAny(firstText, "run context", "objective", "failure condition", "开局目标", "开局语境", "失败条件", "前进方向"))
        {
            return "Deckbuilder plan boundary mismatch: step 1 must establish run context and objective before deck, combat, rewards, route choice, or final acceptance.";
        }

        var finalText = string.Join(" ", orderedGoals[^1].Title, orderedGoals[^1].Description, orderedGoals[^1].AcceptanceHint).ToLowerInvariant();
        if (!ContainsAny(finalText, "final deckbuilder", "final first-loop", "final acceptance", "end-to-end", "package readiness", "最终卡牌构筑", "首轮闭环", "端到端", "打包准备度"))
        {
            return "Deckbuilder plan boundary mismatch: the final goal must be final deckbuilder first-loop acceptance.";
        }

        return null;
    }

    private static HashSet<string> ResolveDeckbuilderCapabilitiesFromGoals(ProjectIterationGoalSnapshot[] goals)
    {
        var selected = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var goal in goals)
        {
            var title = goal.Title.ToLowerInvariant();
            var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
            if (ContainsAny(text, "run context", "opening run context", "failure condition", "开局目标", "开局语境", "失败条件", "前进方向"))
            {
                selected.Add("run_context");
            }

            if (ContainsAny(text, "starter deck readability", "starter deck", "deck readability", "initial deck", "初始牌组"))
            {
                selected.Add("starter_deck_readability");
            }

            if (ContainsAny(text, "resource and turn", "resource rules", "turn rules", "energy", "cost", "费用", "回合规则"))
            {
                selected.Add("resource_and_turn_rules");
            }

            if (ContainsAny(text, "enemy intent", "pressure source", "pressure", "敌方意图", "压力源"))
            {
                selected.Add("enemy_intent_or_pressure");
            }

            if (ContainsAny(text, "card play resolution", "play a card", "card-play", "出牌结算"))
            {
                selected.Add("card_play_resolution");
            }

            if (ContainsAny(text, "deck cycle", "hand flow", "draw", "discard", "shuffle", "牌库循环", "手牌流转"))
            {
                selected.Add("deck_cycle_and_hand_flow");
            }

            if (ContainsAny(text, "combat win/fail", "combat resolution", "victory", "defeat", "战斗胜负", "胜负结算"))
            {
                selected.Add("combat_resolution");
            }

            if (ContainsAny(text, "post-combat card draft", "card draft", "reward", "draft", "战后选牌", "奖励"))
            {
                selected.Add("reward_or_card_draft");
            }

            if (ContainsAny(text, "deck mutation", "deck change", "upgrade", "remove", "牌组变化", "删牌", "升级"))
            {
                selected.Add("deck_mutation_feedback");
            }

            if (ContainsAny(title, "map or route choice", "route choice", "node choice", "路线选择") ||
                ContainsAny(text, "selected route choice capability", "route/node choice", "routes, nodes, events, shops, elites", "事件节点", "商店节点", "精英节点"))
            {
                selected.Add("map_or_route_choice");
            }

            if (ContainsAny(text, "final deckbuilder first-loop acceptance", "final deckbuilder", "final first-loop acceptance", "最终卡牌构筑", "首轮闭环验收"))
            {
                selected.Add("final_deckbuilder_first_loop_acceptance");
            }
        }

        return selected;
    }

    private static string BuildDeckbuilderRegenerationPrompt(ProjectIterationSessionDetails details)
    {
        return $"""
            Regenerate the iteration plan as deckbuilder first-loop capability steps:
            1. run context and objective
            2. starter deck readability
            3. resource and turn rules
            4. enemy intent or pressure source
            5. card play resolution feedback
            6. deck cycle and hand flow
            7. combat win/fail resolution
            8. post-combat card draft or reward
            9. deck mutation feedback
            10. final deckbuilder first-loop acceptance

            Add a separate required_modules block with route_map_path_selection and hand_card_dragging. Treat these modules as required unless the GDD records an explicit conflict; do not add route_map_path_selection as a normal iteration goal.

            Keep the source request in scope: {TrimForHint(details.Session.SourceMessage, 160)}
            """;
    }

    private static string StripRpgStepOneBoundaryExclusionClauses(string value)
    {
        var clauses = Regex.Split(value, @"(?<=[.;??])\s+|\s+(?=\bPass only when\b)", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        return string.Join(" ", clauses.Where(clause => !IsRpgStepOneBoundaryExclusionClause(clause)));
    }

    private static bool IsRpgStepOneBoundaryExclusionClause(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var text = value.ToLowerInvariant();
        if (ContainsAny(
            text,
            "later battle",
            "later battles",
            "later boss battle",
            "later reward",
            "later rewards",
            "keep later battle",
            "keep later boss battle",
            "keep the later battle",
            "keep the later boss battle",
            "后续战斗",
            "之后战斗",
            "后面战斗",
            "后续奖励",
            "之后奖励",
            "后面奖励"))
        {
            return false;
        }

        var battleProbeText = JrpgRouteSemantics.NormalizeBattleDetectionText(text);
        var rewardProbeText = JrpgRouteSemantics.NormalizeRewardDetectionText(text);
        var mentionsLaterCapability = ContainsAny(
            text,
            "conflict",
            "encounter",
            "first encounter",
            "encounter trigger",
            "battle",
            "battlescene",
            "reward",
            "rewards",
            "3-choice",
            "three choices",
            "polish",
            "scene switching",
            "package readiness",
            "final acceptance",
            "full playable") ||
            JrpgRouteSemantics.RequiresBattleScene(text) ||
            JrpgRouteSemantics.RequiresRewardFlow(text) ||
            ContainsAny(battleProbeText, "conflict entry", "encounter trigger", "challenge resolution") ||
            ContainsAny(rewardProbeText, "growth feedback", "consequence feedback", "3-choice");
        if (!mentionsLaterCapability)
        {
            return false;
        }

        return ContainsAny(
            text,
            "before",
            "without",
            "independent of",
            "separate from",
            "not include",
            "not cover",
            "do not",
            "don't",
            "must not",
            "should not",
            "exclude",
            "excluding",
            "only validate",
            "only covers",
            "keep this scoped",
            "keep this focused",
            "focused on",
            "limited to",
            "mixed in");
    }

    private static bool IsStaleRpgBoundaryMismatchEvaluation(
        PrototypeIterationPlanEvaluationResult evaluation,
        ProjectIterationGoalSnapshot[] goals)
    {
        if (!string.Equals(evaluation.Decision, "should_refine_plan", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (FindRpgPlanAcceptanceBoundaryIssue(goals) is not null)
        {
            return false;
        }

        var evaluationText = string.Join(
            " ",
            evaluation.Summary ?? string.Empty,
            evaluation.Reason ?? string.Empty,
            evaluation.SuggestedAction ?? string.Empty,
            evaluation.SuggestedPromptForRegeneration ?? string.Empty);
        if (string.IsNullOrWhiteSpace(evaluationText))
        {
            return false;
        }

        return
            ContainsAny(evaluationText, "acceptance boundary mismatch", "step 1 must only", "step one must only", "first step must only") &&
            ContainsAny(evaluationText, "BattleScene", "battle scene", "reward", "scene switching", "package readiness", "final acceptance", "full playable") &&
            ContainsAny(evaluationText, "Start Adventure", "visible MapScene", "visible map", "stable movement");
    }

    private static PrototypeIterationPlanEvaluationResult BuildRpgRouteGuardAcceptedEvaluation(PrototypeIterationPlanEvaluationResult staleEvaluation)
    {
        return new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "RPG route guard accepted the saved iteration plan.",
            $"The model requested RPG acceptance-boundary refinement, but the saved final goals already cover the JRPG first-loop capability graph with the first executable capability limited to Start Adventure, visible MapScene, and stable movement. Stale model reason: {TrimForHint(staleEvaluation.Reason, 240)}",
            "Execute the next goal.",
            null);
    }

    private static string BuildRpgRegenerationPrompt(ProjectIterationSessionDetails details)
    {
        var sourceMessage = details.Session.SourceMessage?.Trim();
        if (string.IsNullOrWhiteSpace(sourceMessage))
        {
            sourceMessage = details.Session.OverallGoal?.Trim();
        }

        var guidance = "Regenerate the iteration plan from the GDD-derived prototype contract only. Select only the capabilities implied by the project semantics: opening context, field navigation, interaction/discovery, conflict entry, battle/challenge resolution, party or character state, growth/reward/consequence feedback, return/continue loop, quest/story progress, and final first-loop acceptance. Do not force a fixed 7-step DQ-like route or external type-guide requirements. For combat-oriented project semantics, preserve only the contract-implied capabilities. Omit battle/reward when the project explicitly negates combat, encounter, enemy, or reward.";
        return string.IsNullOrWhiteSpace(sourceMessage)
            ? guidance
            : $"{guidance} Source request: {sourceMessage}";
    }

    private static string BuildRpgPlanEvaluationPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        string projectExecutionGuide,
        ProjectIterationSessionDetails details,
        PrototypeWorkflowProgress? prototypeProgress,
        PrototypeIterationPlanningAnalysisResult? planningAnalysis)
    {
        var goalsJson = JsonSerializer.Serialize(details.Goals.OrderBy(goal => goal.GoalIndex).Select(goal => new
        {
            goal.GoalIndex,
            goal.Title,
            goal.Description,
            goal.AcceptanceHint,
            goal.Status
        }).ToArray());
        var progressJson = JsonSerializer.Serialize(prototypeProgress);
        var planningJson = JsonSerializer.Serialize(planningAnalysis);

        return $"""
            You are evaluating whether a prototype iteration plan is accurate enough to execute as-is against the GDD-derived prototype contract.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            decision, summary, reason, suggestedAction, suggestedPromptForRegeneration

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - Use Prototype Chapter 3 Lite / Chapter 6 Lite boundaries: evaluate whether the lightweight prototype goals are executable, not whether formal Chapter 3/6 task artifacts exist.
            - Treat the Project execution guide below as the project-level /new recovery protocol, especially its Route Recovery Protocol section.
            - Recover route memory in this order: route profile, Project execution guide, prototype contract/state inside the guide, current iteration goals, prototype progress, and planning analysis.
            - Do not use AGENTS.md as hosted game-project recovery memory.
            - decision must be one of: ready_to_execute, should_refine_plan.
            - Use the current prototype result, planning analysis, and GDD-derived prototype contract requirements.
            - Treat the route as a project-specific first-loop contract, not a fixed DQ-like 7-step script or external type guide.
            - For combat-oriented project semantics, evaluate only the capabilities implied by the GDD-derived contract: field navigation, conflict entry, battle/challenge resolution, reward or growth feedback, return-or-continue loop, win/fail or character-state readability, and final first-loop acceptance.
            - A plan that omits battle/reward/return capability despite explicit encounter, enemy, monster, boss, combat, battle, fight, reward, item, experience, level, loot, or return-to-map semantics should_refine_plan.
            - Omit BattleScene/reward requirements only when the source semantics explicitly negates combat/conflict/reward.
            - If the plan is generic, misses the selected capability coverage, lacks field navigation, lacks final first-loop acceptance, or merges unrelated boundaries, return should_refine_plan.
            - If the latest prototype gap is navigation or visible-map related, prefer should_refine_plan unless the first executable capability clearly targets Start Adventure or the project entry into a visible playable field/map/town with stable movement.
            - Conflict-oriented projects should split conflict entry from battle/challenge resolution only when a single goal mixes both boundaries; do not reject a plan just because it has both capabilities across different goals.
            - Reward or growth projects should include growth/reward/consequence feedback and a return-or-continue loop, unless the project explicitly ends after the reward.
            - Story or town-first JRPGs do not need BattleScene/reward steps unless the source semantics asks for conflict or growth.
            - A plan should_refine_plan if its goals require new player-visible Godot text but allow that text to default to English instead of Chinese. Do not treat English code identifiers, fixed node names, resource paths, tests, logs, or platform validation names as localization failures.
            - suggestedPromptForRegeneration should be null only when decision is ready_to_execute.
            - Keep output browser-safe.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - GameTypeProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}
            - EvaluatorId: {routeProfile.EvaluatorId}
            - Rule: evaluate only against this same game-type route profile; do not invent requirements outside this route set.

            Project execution guide:
            {TrimForPrompt(projectExecutionGuide)}

            Iteration goals:
            {goalsJson}

            Prototype progress:
            {progressJson}

            Planning analysis:
            {planningJson}
            """;
    }

    private static PrototypeIterationPlanEvaluationResult? ParseModelEvaluation(string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(LlmRouteEngine.ExtractFirstJsonObject(assistantMessage) ?? assistantMessage);
            var root = document.RootElement;
            var decision = root.TryGetProperty("decision", out var decisionElement) && decisionElement.ValueKind == JsonValueKind.String
                ? decisionElement.GetString()?.Trim()
                : null;
            if (!string.Equals(decision, "ready_to_execute", StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(decision, "should_refine_plan", StringComparison.OrdinalIgnoreCase))
            {
                return null;
            }

            var summary = root.TryGetProperty("summary", out var summaryElement) && summaryElement.ValueKind == JsonValueKind.String
                ? summaryElement.GetString()?.Trim()
                : null;
            var reason = root.TryGetProperty("reason", out var reasonElement) && reasonElement.ValueKind == JsonValueKind.String
                ? reasonElement.GetString()?.Trim()
                : null;
            var suggestedAction = root.TryGetProperty("suggestedAction", out var actionElement) && actionElement.ValueKind == JsonValueKind.String
                ? actionElement.GetString()?.Trim()
                : null;
            string? suggestedPrompt = null;
            if (root.TryGetProperty("suggestedPromptForRegeneration", out var promptElement) && promptElement.ValueKind == JsonValueKind.String)
            {
                suggestedPrompt = promptElement.GetString()?.Trim();
            }

            if (string.IsNullOrWhiteSpace(summary) || string.IsNullOrWhiteSpace(reason) || string.IsNullOrWhiteSpace(suggestedAction))
            {
                return null;
            }

            return new PrototypeIterationPlanEvaluationResult(
                decision!,
                summary!,
                reason!,
                suggestedAction!,
                string.Equals(decision, "ready_to_execute", StringComparison.OrdinalIgnoreCase) ? null : suggestedPrompt);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string? BuildPlanRegenerationGuidance(
        ProjectIterationSessionDetails? previousIterationPlan,
        string message,
        string sourceKind)
    {
        if (string.Equals(sourceKind, "new_iteration_plan", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var candidates = new List<string>();
        if (previousIterationPlan?.LatestEvaluation is not null &&
            string.Equals(previousIterationPlan.LatestEvaluation.Decision, "should_refine_plan", StringComparison.OrdinalIgnoreCase))
        {
            if (!string.IsNullOrWhiteSpace(previousIterationPlan.LatestEvaluation.SuggestedPromptForRegeneration))
            {
                candidates.Add(previousIterationPlan.LatestEvaluation.SuggestedPromptForRegeneration!);
            }

            candidates.Add(previousIterationPlan.LatestEvaluation.SuggestedAction);
            candidates.Add(previousIterationPlan.LatestEvaluation.Reason);
        }

        if (string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase) &&
            LooksLikeRegenerationGuidance(message))
        {
            candidates.Add(message);
        }

        var guidance = string.Join("\n", candidates.Where(value => !string.IsNullOrWhiteSpace(value)).Select(value => value.Trim()));
        return string.IsNullOrWhiteSpace(guidance) ? null : guidance;
    }

    private static bool LooksLikeRegenerationGuidance(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        return ContainsAny(
            value,
            "重写 RPG 游戏模块",
            "重拆",
            "Regenerate the RPG iteration plan",
            "Start Adventure",
            "visible MapScene",
            "可见 MapScene",
            "稳定移动");
    }

    private static bool IsDeterministicRpgRegenerationRequest(string sourceKind, string message, string? regenerationGuidance)
    {
        if (!string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var combined = string.Join("\n", message ?? string.Empty, regenerationGuidance ?? string.Empty);
        if (string.IsNullOrWhiteSpace(combined))
        {
            return false;
        }

        return ContainsAny(
            combined,
            "strict 7 route-profile",
            "RPG iteration plan as strict 7",
            "JRPG first-loop capability steps",
            "RPG iteration plan as JRPG first-loop capabilities",
            "visible MapScene with stable movement first",
            "reward 3-choice understandability fourth",
            "full playable acceptance seventh",
            "final first-loop acceptance");
    }

    private static bool RequiresNavigationFirstRpgPlan(string? regenerationGuidance)
    {
        if (string.IsNullOrWhiteSpace(regenerationGuidance))
        {
            return false;
        }

        var guidance = regenerationGuidance.Trim();
        return ContainsAny(guidance, "Start Adventure", "visible MapScene", "可见 MapScene", "稳定移动") &&
               ContainsAny(guidance, "第一优先级", "首要阻塞", "first priority", "first blocker", "Step 1", "第一阶段", "先解决");
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.OrdinalIgnoreCase));
    }

    private static List<PrototypeIterationPlanGoalResult> TryBuildRefinedGoals(string message, string sourceKind)
    {
        var normalized = message.Trim();
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return [];
        }

        var genericLoopGoals = TryBuildGenericLoopGoalsFromActionList(normalized);
        if (genericLoopGoals.Count > 0)
        {
            return genericLoopGoals;
        }

        if (!string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase))
        {
            return [];
        }

        var looksLikeRpgClosure =
            normalized.Contains("RPG", StringComparison.OrdinalIgnoreCase) &&
            normalized.Contains("完整首轮闭环", StringComparison.Ordinal) &&
            normalized.Contains("移动", StringComparison.Ordinal) &&
            normalized.Contains("遇敌", StringComparison.Ordinal) &&
            normalized.Contains("战斗", StringComparison.Ordinal) &&
            normalized.Contains("奖励 3 选 1", StringComparison.Ordinal);
        if (looksLikeRpgClosure)
        {
            return
            [
                new PrototypeIterationPlanGoalResult(
                    1,
                    "任务 1：补稳地图移动与可见遇敌触发",
                    "先让玩家能稳定移动，并且能清楚看到或明确触发第一次遇敌，不要把战斗、奖励和胜负提示一起塞进这一步。",
                    "完成并验证：玩家能稳定移动，并能明确进入第一次遇敌。",
                    "pending"),
                new PrototypeIterationPlanGoalResult(
                    2,
                    "任务 2：补通单场战斗与基础结算",
                    "在首次遇敌后完成一场可读、可结束的战斗，至少让玩家能看到战斗开始、行动结果和胜利结算，不要在这一步同时处理奖励理解问题。",
                    "完成并验证：玩家能完整打完一场战斗，并看到明确的胜利结算。",
                    "pending"),
                new PrototypeIterationPlanGoalResult(
                    3,
                    "任务 3：补通奖励 3 选 1 并返回地图",
                    "战斗胜利后展示奖励 3 选 1，并在选择后正确返回地图继续流程，重点保证奖励含义可理解、选择后状态变化可见。",
                    "完成并验证：奖励 3 选 1 可理解、可选择，且选择后能正确返回地图。",
                    "pending"),
                new PrototypeIterationPlanGoalResult(
                    4,
                    "任务 4：补齐胜负目标提示与最小验证",
                    "把“打赢 15 场胜利、任一战斗失败即失败”的规则做成玩家一眼能看懂的提示，并补一轮最小验证，确认首轮闭环与目标提示能一起工作。",
                    "完成并验证：玩家能清楚理解胜负条件，且首轮闭环在提示存在时仍可正常工作。",
                    "pending"),
            ];
        }

        return [];
    }

    private static List<PrototypeIterationPlanGoalResult> TryBuildGenericLoopGoalsFromActionList(string message)
    {
        var actionList = ExtractGenericLoopActionList(message);
        if (actionList.Count < 3)
        {
            return [];
        }

        var goals = new List<PrototypeIterationPlanGoalResult>();
        var maxActionGoals = Math.Min(actionList.Count, 4);
        for (var index = 0; index < maxActionGoals; index++)
        {
            var action = actionList[index];
            var normalizedAction = NormalizeGenericActionSummary(action);
            var previous = index == 0 ? null : actionList[index - 1];
            var next = index + 1 < actionList.Count ? actionList[index + 1] : null;
            var title = index == 0
                ? $"任务 1：验证玩家能{action}"
                : $"任务 {index + 1}：补通{action}反馈";
            var description = index == 0
                ? $"只处理“{normalizedAction}”这个最小动作：让玩家能触发该动作，并看到明确反馈。不要在这一步同时实现{string.Join("、", actionList.Skip(1).Take(3).Select(NormalizeGenericActionSummary))}等后续动作。"
                : $"在前一步“{NormalizeGenericActionSummary(previous ?? string.Empty)}”已经成立的基础上，只补通“{normalizedAction}”及其必要状态变化和可见反馈。{(next is null ? "不要扩大到完整闭环之外的新系统。" : $"不要同时处理后续“{NormalizeGenericActionSummary(next)}”。")}";
            goals.Add(new PrototypeIterationPlanGoalResult(
                index + 1,
                title,
                description,
                $"完成并验证：玩家能{normalizedAction}，且反馈和状态变化清楚可见。",
                "pending"));
        }

        return goals;
    }

    private static string BuildGenericLoopSummaryText(IEnumerable<string> actions)
    {
        var normalized = actions.Select(NormalizeGenericActionSummary).Where(value => !string.IsNullOrWhiteSpace(value)).ToArray();
        return normalized.Length == 0 ? "本轮最小闭环" : string.Join(" -> ", normalized);
    }

    private static string NormalizeGenericActionSummary(string value)
    {
        var text = value.Trim();
        if (ContainsAny(text, "杀怪", "打怪", "战斗", "combat", "battle", "fight", "怪"))
        {
            return "进入一次战斗并击败一个普通敌人";
        }

        if (ContainsAny(text, "掉装备", "掉落", "金币", "loot", "drop", "gold"))
        {
            return "获得掉落或金币";
        }

        if (ContainsAny(text, "经验", "升级", "变强", "growth", "level", "exp", "stronger"))
        {
            return "展示玩家状态变化";
        }

        if (ContainsAny(text, "继续", "下一场", "repeat", "continue"))
        {
            return "继续下一轮操作";
        }

        return text;
    }

    private static List<string> ExtractGenericLoopActionList(string message)
    {
        var rawItems = ExtractDelimitedLoopItems(message);
        if (string.IsNullOrWhiteSpace(rawItems))
        {
            return [];
        }

        rawItems = Regex.Replace(rawItems, @"补齐.*$", "", RegexOptions.CultureInvariant).Trim();
        return Regex.Split(rawItems, @"[、,，/／]+|\s*->\s*|\s+then\s+", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)
            .Select(NormalizeGoalSegment)
            .Select(RemoveGenericActionNoise)
            .Where(IsMeaningfulLoopActionSegment)
            .Where(item => item.Length <= 20)
            .Distinct(StringComparer.Ordinal)
            .Take(8)
            .ToList();
    }

    private static string ExtractDelimitedLoopItems(string message)
    {
        var source = message.Trim();
        var marker = new[] { "围绕", "包括", "包含", "核心循环", "最小循环" }
            .Select(value => new { Marker = value, Index = source.IndexOf(value, StringComparison.Ordinal) })
            .FirstOrDefault(item => item.Index >= 0);
        if (marker is null)
        {
            return string.Empty;
        }

        var start = marker.Index + marker.Marker.Length;
        while (start < source.Length && (source[start] == ':' || source[start] == '：' || char.IsWhiteSpace(source[start])))
        {
            start++;
        }

        if (start >= source.Length)
        {
            return string.Empty;
        }

        var quotePairs = new Dictionary<char, char>
        {
            ['“'] = '”',
            ['"'] = '"',
            ['\''] = '\''
        };
        if (quotePairs.TryGetValue(source[start], out var closingQuote))
        {
            var endQuote = source.IndexOf(closingQuote, start + 1);
            return endQuote > start ? source[(start + 1)..endQuote].Trim() : string.Empty;
        }

        var end = source.IndexOfAny(['。', '.', '！', '!', '？', '?', '\r', '\n'], start);
        return (end < 0 ? source[start..] : source[start..end]).Trim(' ', '。', '.', '；', ';');
    }

    private static string RemoveGenericActionNoise(string value)
    {
        return value
            .Replace("尝试", "", StringComparison.Ordinal)
            .Replace("玩家能", "", StringComparison.Ordinal)
            .Trim();
    }

    private static bool IsMeaningfulLoopActionSegment(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var trimmed = value.Trim();
        if (trimmed.Length < 2)
        {
            return false;
        }

        return trimmed.Count(char.IsLetterOrDigit) >= 2;
    }

    private static List<string> ExtractStructuredGoals(string message)
    {
        return NumberedGoalRegex.Matches(message)
            .Select(match => match.Groups[1].Value.Trim())
            .Select(NormalizeGoalSegment)
            .Where(IsMeaningfulGoalSegment)
            .Distinct(StringComparer.Ordinal)
            .ToList();
    }

    private static string NormalizeGoalSegment(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        return value
            .Replace("\r", "\n")
            .Trim()
            .Trim(';', '；', ',', '，', '.', '。', ':', '：', '-', ' ')
            .Replace("\n", " ")
            .Trim();
    }

    private static bool IsMeaningfulGoalSegment(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var trimmed = value.Trim();
        if (trimmed.Length < 4)
        {
            return false;
        }

        var letterOrDigitCount = trimmed.Count(char.IsLetterOrDigit);
        return letterOrDigitCount >= 3;
    }
    private static string BuildOverallGoal(string gameName, string message)
    {
        var prefix = string.IsNullOrWhiteSpace(gameName) ? "当前项目" : gameName.Trim();
        return $"{prefix}：{TrimForHint(message, 120)}";
    }

    private static bool IsInternalExecutionSuggestion(string message)
    {
        return InternalSuggestionKeywords.Any(keyword => message.Contains(keyword, StringComparison.OrdinalIgnoreCase));
    }

    private static string BuildGoalTitle(int index, string segment)
    {
        return $"任务 {index}：{TrimForHint(segment, 24)}";
    }

    private static string TrimForHint(string value, int maxLength = 32)
    {
        var trimmed = value.Trim();
        return trimmed.Length <= maxLength ? trimmed : $"{trimmed[..maxLength]}...";
    }

    private static string BuildRegenerationPrompt(PrototypeWorkflowProgress? prototypeProgress, ProjectIterationSessionDetails details)
    {
        var sourceMessage = details.Session.SourceMessage?.Trim();
        if (!string.IsNullOrWhiteSpace(sourceMessage))
        {
            return $"请把这条原型优化建议重拆成 4 个更小、能单独执行的任务，不要把多个连续实现点塞进同一个任务里：{sourceMessage}";
        }

        if (!string.IsNullOrWhiteSpace(prototypeProgress?.CompletionSummary))
        {
            return "请根据当前 prototype completion report，把下一步优化拆成 4 个更小的任务：先补地图稳定移动和可见遇敌触发，再补完成一场战斗并正常结算，再补胜利后奖励 3 选 1 并返回地图，最后补胜负条件提示与验证。";
        }

        return "请把当前优化目标重拆成 4 个更小的连续任务，每个任务都要足够小，适合一次单独执行。";
    }

    private static bool LooksTooBroad(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var text = value.Trim();
        var separators = new[] { "，", "、", "并", "然后", "同时", "再", "后", " and ", "," };
        var separatorHits = separators.Count(text.Contains);
        return text.Length >= 36 || separatorHits >= 2;
    }

    private static bool IsRecognizedSmallGoal(ProjectIterationGoalSnapshot goal)
    {
        var title = goal.Title?.Trim() ?? string.Empty;
        var description = goal.Description?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(title) || string.IsNullOrWhiteSpace(description))
        {
            return false;
        }

        return
            (title.Contains("JRPG 首轮闭环：开局语境与玩家目标", StringComparison.Ordinal) &&
             description.Contains("player", StringComparison.OrdinalIgnoreCase)) ||
            (title.Contains("JRPG 首轮闭环：地图导航与稳定操控", StringComparison.Ordinal) &&
             description.Contains("MapScene", StringComparison.OrdinalIgnoreCase)) ||
            (title.Contains("JRPG 首轮闭环：交互与发现节点", StringComparison.Ordinal) &&
             (description.Contains("dialogue", StringComparison.OrdinalIgnoreCase) || description.Contains("interaction", StringComparison.OrdinalIgnoreCase))) ||
            (title.Contains("JRPG 首轮闭环：冲突入口触发", StringComparison.Ordinal) &&
             (description.Contains("encounter", StringComparison.OrdinalIgnoreCase) || description.Contains("触发", StringComparison.Ordinal))) ||
            (title.Contains("JRPG 首轮闭环：战斗或挑战结算", StringComparison.Ordinal) &&
             (description.Contains("BattleScene", StringComparison.OrdinalIgnoreCase) || description.Contains("battle", StringComparison.OrdinalIgnoreCase))) ||
            (title.Contains("JRPG 首轮闭环：成长、奖励或后果反馈", StringComparison.Ordinal) &&
             (description.Contains("reward", StringComparison.OrdinalIgnoreCase) || description.Contains("growth", StringComparison.OrdinalIgnoreCase))) ||
            (title.Contains("JRPG 首轮闭环：返回或继续循环", StringComparison.Ordinal) &&
             (description.Contains("return", StringComparison.OrdinalIgnoreCase) || description.Contains("continue", StringComparison.OrdinalIgnoreCase))) ||
            (title.Contains("JRPG 首轮闭环：角色或队伍状态可读性", StringComparison.Ordinal) &&
             (description.Contains("win", StringComparison.OrdinalIgnoreCase) || description.Contains("fail", StringComparison.OrdinalIgnoreCase))) ||
            (title.Contains("JRPG 首轮闭环：最终首轮闭环验收", StringComparison.Ordinal) &&
             (description.Contains("acceptance", StringComparison.OrdinalIgnoreCase) || description.Contains("package readiness", StringComparison.OrdinalIgnoreCase))) ||
            (title.Contains("补稳地图移动与可见遇敌触发", StringComparison.Ordinal) &&
             description.Contains("稳定移动", StringComparison.Ordinal) &&
             description.Contains("第一次遇敌", StringComparison.Ordinal)) ||
            (title.Contains("补通单场战斗与基础结算", StringComparison.Ordinal) &&
             description.Contains("首次遇敌后完成一场可读、可结束的战斗", StringComparison.Ordinal)) ||
            (title.Contains("补通奖励 3 选 1 并返回地图", StringComparison.Ordinal) &&
             description.Contains("奖励 3 选 1", StringComparison.Ordinal) &&
             description.Contains("返回地图", StringComparison.Ordinal)) ||
            (title.Contains("补齐胜负目标提示与最小验证", StringComparison.Ordinal) &&
             description.Contains("打赢 15 场胜利", StringComparison.Ordinal) &&
             description.Contains("任一战斗失败即失败", StringComparison.Ordinal)) ||
            (description.Contains("进入一次战斗", StringComparison.Ordinal) &&
             description.Contains("战斗入口", StringComparison.Ordinal)) ||
            (description.Contains("击败一个普通敌人", StringComparison.Ordinal) &&
             description.Contains("战斗结果反馈", StringComparison.Ordinal)) ||
            ((title.StartsWith("目标 ", StringComparison.Ordinal) || title.StartsWith("任务 ", StringComparison.Ordinal)) &&
             (title.Contains("验证玩家能", StringComparison.Ordinal) || title.Contains("补通", StringComparison.Ordinal)) &&
             description.Contains("只", StringComparison.Ordinal) &&
             (description.Contains("可见反馈", StringComparison.Ordinal) || description.Contains("明确反馈", StringComparison.Ordinal))) ||
            (title.Contains("最小闭环回归验收", StringComparison.Ordinal) &&
             description.Contains("只做验收和必要修补", StringComparison.Ordinal)) ||
            (description.Contains("获得一个明确奖励", StringComparison.Ordinal) &&
             description.Contains("三选一", StringComparison.Ordinal)) ||
            (description.Contains("展示玩家状态变化", StringComparison.Ordinal) &&
             (description.Contains("变强", StringComparison.Ordinal) || description.Contains("资源增加", StringComparison.Ordinal))) ||
            (description.Contains("返回或继续到下一场战斗", StringComparison.Ordinal) &&
             description.Contains("最小循环验收", StringComparison.Ordinal));
    }

    private static PrototypeIterationPlanEvaluationResult BuildLlmFailedEvaluation(string failureCode)
    {
        var code = string.IsNullOrWhiteSpace(failureCode) ? "llm_failed" : failureCode.Trim();
        return new PrototypeIterationPlanEvaluationResult(
            "llm_failed",
            "游戏模块评估需要 LLM 成功参与，但当前调用失败。",
            $"LLM 调用失败：{code}。系统不会使用本地规则假装评估成功。",
            "请先修复 LLM 调用，再重新评估当前游戏模块。",
            null);
    }

    private async Task<PrototypeIterationPlanEvaluationResult> PersistEvaluationAsync(
        ProjectIterationSessionDetails details,
        PrototypeIterationPlanEvaluationResult evaluation,
        CancellationToken cancellationToken = default)
    {
        var serialized = JsonSerializer.Serialize(evaluation);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(
            details.Session.SessionId,
            details.Session.Status,
            details.Session.CurrentGoalIndex,
            details.Session.LatestSummary,
            serialized,
            details.Session.CompletedUtc,
            cancellationToken);
        return evaluation;
    }

    private static PrototypeWorkflowProgress ToPrototypeProgress(IterationPlanningContext context)
    {
        return new PrototypeWorkflowProgress(
            context.LatestPrototypeStatus,
            context.LatestPrototypeStatus,
            "",
            "done",
            null,
            null,
            null,
            context.LatestPrototypeCompletionSummary,
            "system",
            "recommended",
            context.AnalysisSummary);
    }

    private static string NormalizePlanningMessage(string? message, string? sourceKind)
    {
        var value = message?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var kind = sourceKind?.Trim() ?? string.Empty;
        if (!string.Equals(kind, "completion_suggestion", StringComparison.OrdinalIgnoreCase))
        {
            return value;
        }

        return UnwrapRegenerationPrompt(value);
    }

    private static string UnwrapRegenerationPrompt(string message)
    {
        var value = message.Trim();
        var prefixes = new[]
        {
            "请把这条原型优化建议重拆成 4 个更小、能单独执行的目标，不要把多个连续实现点塞进同一个目标里：",
            "请把这条原型优化建议重拆成 4 个更小、能单独执行的任务，不要把多个连续实现点塞进同一个任务里：",
            "请根据当前 prototype completion report，把下一步优化拆成 4 个更小的目标：",
            "请根据当前 prototype completion report，把下一步优化拆成 4 个更小的任务：",
            "请把当前优化目标重拆成 4 个更小的连续目标，每个目标都要足够小，适合一次单独执行。",
            "请把当前优化目标重拆成 4 个更小的连续任务，每个任务都要足够小，适合一次单独执行。"
        };

        var changed = true;
        while (changed)
        {
            changed = false;
            foreach (var prefix in prefixes)
            {
                if (!value.StartsWith(prefix, StringComparison.Ordinal))
                {
                    continue;
                }

                var remainder = value[prefix.Length..].Trim();
                if (string.IsNullOrWhiteSpace(remainder))
                {
                    return value;
                }

                value = remainder;
                changed = true;
                break;
            }
        }

        return value;
    }

    private sealed record PlanningFieldCoverage(
        string Field,
        string Status,
        string? Evidence,
        string? MissingReason);

    private sealed record PrototypeIterationRouteContext(
        PrototypeIterationPlanningAnalysisResult? PlanningAnalysis,
        HashSet<string>? SelectedCapabilities,
        IReadOnlyList<PrototypeIterationPlanRequiredModuleResult>? RequiredModules,
        string PlanHash,
        PrototypeIterationPlanSourceHashes? SourceHashes,
        PrototypeIterationPlanConfirmationResult? Confirmation,
        IReadOnlyList<PrototypeIterationPlanTraceabilityGoalResult>? TraceabilityGoals,
        IReadOnlyList<PrototypeIterationPlanBlockerResult>? Blockers,
        PrototypeIterationStyleApplicability? StyleApplicability);

    private sealed record IterationPlanLiveGovernanceResult(
        PrototypeIterationPlanBlockerResult? Blocker,
        IReadOnlyDictionary<string, string> ApprovedRequirementDecisions);

    private sealed record IterationPlanningContext(
        string AnalysisSource,
        string AnalysisSummary,
        string LatestPrototypeStatus,
        string? LatestPrototypeCompletionSummary,
        int DraftCoveragePercent,
        string? DraftCoverageSummary,
        string? TemplateId,
        IReadOnlyList<PlanningFieldCoverage> FieldCoverage,
        string PrototypeStateExcerpt,
        string SourceMessage,
        string SourceKind,
        IReadOnlyList<PrototypeIterationPlanStageTelemetryResult> StageTelemetry);

    private static string EnsurePlanningAnalysisSchemaFile()
    {
        var schemaDir = Path.Combine(Path.GetTempPath(), "phase-a-platform-schemas");
        Directory.CreateDirectory(schemaDir);
        var schemaPath = Path.Combine(schemaDir, "prototype-iteration-planning-analysis.schema.json");
        var schema = new JsonObject
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["properties"] = new JsonObject
            {
                ["analysisSummary"] = new JsonObject
                {
                    ["type"] = "string",
                    ["minLength"] = 1
                },
                ["fieldCoverage"] = new JsonObject
                {
                    ["type"] = "array",
                    ["items"] = new JsonObject
                    {
                        ["type"] = "object",
                        ["additionalProperties"] = false,
                        ["properties"] = new JsonObject
                        {
                            ["field"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                            ["status"] = new JsonObject { ["type"] = "string", ["enum"] = new JsonArray("completed", "partial", "missing") },
                            ["evidence"] = new JsonObject { ["type"] = new JsonArray("string", "null") },
                            ["missingReason"] = new JsonObject { ["type"] = new JsonArray("string", "null") }
                        },
                        ["required"] = new JsonArray("field", "status", "evidence", "missingReason")
                    }
                }
            },
            ["required"] = new JsonArray("analysisSummary", "fieldCoverage")
        };

        File.WriteAllText(schemaPath, schema.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return schemaPath;
    }

    private static string EnsureGoalPlanSchemaFile()
    {
        var schemaDir = Path.Combine(Path.GetTempPath(), "phase-a-platform-schemas");
        Directory.CreateDirectory(schemaDir);
        var schemaPath = Path.Combine(schemaDir, "prototype-iteration-goal-plan.schema.json");
        var schema = new JsonObject
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["properties"] = new JsonObject
            {
                ["goals"] = new JsonObject
                {
                    ["type"] = "array",
                    ["minItems"] = 3,
                    ["maxItems"] = 8,
                    ["items"] = new JsonObject
                    {
                        ["type"] = "object",
                        ["additionalProperties"] = false,
                        ["properties"] = new JsonObject
                        {
                            ["title"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                            ["description"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                            ["acceptanceHint"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 }
                        },
                        ["required"] = new JsonArray("title", "description", "acceptanceHint")
                    }
                }
            },
            ["required"] = new JsonArray("goals")
        };

        File.WriteAllText(schemaPath, schema.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return schemaPath;
    }

    private static string EnsureEvaluationSchemaFile()
    {
        var schemaDir = Path.Combine(Path.GetTempPath(), "phase-a-platform-schemas");
        Directory.CreateDirectory(schemaDir);
        var schemaPath = Path.Combine(schemaDir, "prototype-iteration-evaluation.schema.json");
        var schema = new JsonObject
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["properties"] = new JsonObject
            {
                ["decision"] = new JsonObject { ["type"] = "string", ["enum"] = new JsonArray("ready_to_execute", "should_refine_plan") },
                ["summary"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                ["reason"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                ["suggestedAction"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                ["suggestedPromptForRegeneration"] = new JsonObject { ["type"] = new JsonArray("string", "null") }
            },
            ["required"] = new JsonArray("decision", "summary", "reason", "suggestedAction", "suggestedPromptForRegeneration")
        };

        File.WriteAllText(schemaPath, schema.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return schemaPath;
    }

    private static string EnsureIterationPlanPromptWorkspace(ProjectSnapshot project, string purpose)
    {
        var repoParent = Path.GetDirectoryName(project.RepoPath);
        var workspaceRoot = string.IsNullOrWhiteSpace(repoParent) ? project.RepoPath : repoParent;
        var root = Path.Combine(workspaceRoot, "_phasea_llm", purpose);
        Directory.CreateDirectory(root);
        return root;
    }

    private sealed record IterationGoalBuildResult(
        List<PrototypeIterationPlanGoalResult> Goals,
        bool UsedScaffoldFallback,
        IReadOnlyList<PrototypeIterationPlanStageTelemetryResult>? StageTelemetry = null);

    private sealed record GenericCoreLoopGateResult(
        bool RequiresCustomRoute,
        string? PlanningMessage,
        string? Reason)
    {
        public static GenericCoreLoopGateResult NotApplicable()
        {
            return new GenericCoreLoopGateResult(false, null, null);
        }
    }
}

public sealed record PrototypeIterationPlanDetails(
    ProjectIterationSessionSnapshot Session,
    IReadOnlyList<ProjectIterationGoalSnapshot> Goals,
    IReadOnlyList<ProjectIterationGoalRunSnapshot> GoalRuns,
    PrototypeIterationPlanEvaluationResult? LatestEvaluation = null,
    PrototypeIterationPlanningAnalysisResult? PlanningAnalysis = null,
    IReadOnlyList<PrototypeIterationPlanRequiredModuleResult>? RequiredModules = null,
    string PlanHash = "",
    PrototypeIterationPlanSourceHashes? SourceHashes = null,
    PrototypeIterationPlanConfirmationResult? Confirmation = null,
    IReadOnlyList<PrototypeIterationPlanTraceabilityGoalResult>? TraceabilityGoals = null,
    IReadOnlyList<PrototypeIterationPlanBlockerResult>? Blockers = null,
    PrototypeIterationStyleApplicability? StyleApplicability = null);

public sealed record PrototypeIterationPlanRoundDetails(
    int RoundIndex,
    ProjectIterationSessionSnapshot Session,
    IReadOnlyList<ProjectIterationGoalSnapshot> Goals,
    IReadOnlyList<ProjectIterationGoalRunSnapshot> GoalRuns,
    PrototypeIterationPlanEvaluationResult? LatestEvaluation = null,
    PrototypeIterationPlanningAnalysisResult? PlanningAnalysis = null,
    IReadOnlyList<PrototypeIterationPlanRequiredModuleResult>? RequiredModules = null,
    string PlanHash = "",
    PrototypeIterationPlanSourceHashes? SourceHashes = null,
    PrototypeIterationPlanConfirmationResult? Confirmation = null,
    IReadOnlyList<PrototypeIterationPlanTraceabilityGoalResult>? TraceabilityGoals = null,
    IReadOnlyList<PrototypeIterationPlanBlockerResult>? Blockers = null,
    PrototypeIterationStyleApplicability? StyleApplicability = null);

public sealed record PrototypeIterationPlanTraceabilityGoalResult(
    int GoalIndex,
    IReadOnlyList<string> RequirementIds,
    string SourceHashRef,
    string UiSurfaceSummary,
    string StyleSummary,
    IReadOnlyList<string> EngineReadingRefs,
    string InteractionArtifactRef);

internal sealed class PrototypeIterationPlanLlmException : Exception
{
    public PrototypeIterationPlanLlmException(string message)
        : base(message)
    {
    }
}
