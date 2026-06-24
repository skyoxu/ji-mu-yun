using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeNeedsFixRouteService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeQuickFixService _quickFixService;
    private readonly PrototypeRouteStateWriter _stateWriter;
    private readonly PrototypeContractService _contractService;

    public PrototypeNeedsFixRouteService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService,
        PrototypeRouteStateWriter stateWriter,
        PrototypeContractService? contractService = null)
    {
        _metadataStore = metadataStore;
        _quickFixService = quickFixService;
        _stateWriter = stateWriter;
        _contractService = contractService ?? new PrototypeContractService();
    }

    public async Task<PrototypeNeedsFixRouteResult> RunAsync(
        string accountId,
        string projectId,
        PrototypeNeedsFixRouteRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken);
        if (details is null)
        {
            return new PrototypeNeedsFixRouteResult("", "missing_plan", "当前项目还没有游戏模块。请先使用固定的“生成游戏模块”按钮创建计划；提交反馈不会自动生成计划。", 0, null, null, []);
        }

        var goal = ResolveGoal(details, request);
        if (goal is null)
        {
            return await RunProjectLevelNeedsFixAsync(project, details, request, cancellationToken);
        }

        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeNeedsFixRouteResult("", routeSkill.FailureCode, routeSkill.FailureMessage, goal.GoalIndex, details.Session.Status, goal.Status, []);
        }

        var readme = _stateWriter.ReadProjectReadme(project);
        var prototypeContract = _contractService.Read(project);
        var projectExecutionGuide = _stateWriter.ReadOrCreateProjectExecutionGuide(project, prototypeContract);
        var rawStepState = _stateWriter.ReadLatestNeedsFixState(project, goal.GoalIndex);
        var rawExecuteNextGoalState = _stateWriter.ReadLatestExecuteNextGoalState(project, goal.GoalIndex);
        var stepState = SelectCurrentNeedsFixState(rawStepState, rawExecuteNextGoalState, details.Session.SessionId, goal);
        var executeNextGoalState = string.IsNullOrWhiteSpace(stepState)
            ? SelectCurrentExecuteNextGoalState(rawExecuteNextGoalState, details.Session.SessionId, goal)
            : "";
        var prototypeState = string.IsNullOrWhiteSpace(stepState) && string.IsNullOrWhiteSpace(executeNextGoalState)
            ? _stateWriter.ReadLatestPrototypeState(project)
            : "";
        if (string.IsNullOrWhiteSpace(stepState) && string.IsNullOrWhiteSpace(executeNextGoalState) && string.IsNullOrWhiteSpace(prototypeState))
        {
            return new PrototypeNeedsFixRouteResult("", "prototype_required", "当前项目缺少可恢复的游戏场景创建产物。请先运行游戏场景创建，再使用需要修复路由。", goal.GoalIndex, details.Session.Status, goal.Status, []);
        }

        var repairLedger = string.IsNullOrWhiteSpace(stepState) && !string.IsNullOrWhiteSpace(rawStepState)
            ? ""
            : _stateWriter.ReadNeedsFixRepairLedger(project, goal.GoalIndex);
        var repairLedgerBlock = PrototypeNeedsFixRepairLedger.BuildPromptBlock(repairLedger);
        var previousPlatformRejection = await BuildPreviousPlatformRejectionBlockAsync(details, goal, cancellationToken);
        var feedback = BuildFeedback(project, request.Feedback, readme, projectExecutionGuide, prototypeContract, stepState, executeNextGoalState, prototypeState, goal, previousPlatformRejection, repairLedgerBlock);
        var quickFixResult = await _quickFixService.SubmitAsync(
            project.AccountId,
            project.ProjectId,
            new PrototypeFeedbackRequest(
                feedback,
                request.Model,
                request.SkillActionId,
                new PrototypeGoalRepairContext(
                    details.Session.SessionId,
                    goal.GoalId,
                    goal.GoalIndex,
                    goal.Title,
                    goal.Description,
                    goal.AcceptanceHint,
                    BuildCompactSummary(goal.ResultSummary))),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        var routeStatus = NormalizeGoalRouteStatus(quickFixResult.IterationGoalStatus, quickFixResult.Status);
        var latestRun = await _metadataStore.GetRunSnapshotAsync(quickFixResult.RunId, cancellationToken);
        var updatedRepairLedger = PrototypeNeedsFixRepairLedger.UpdateFromRun(
            repairLedger,
            goal.GoalIndex,
            quickFixResult.RunId,
            ExtractAssistantClaimedStatus(quickFixResult.AssistantMessage),
            routeStatus,
            quickFixResult.IterationGoalStatus,
            latestRun?.EvidenceJson);
        _stateWriter.WriteNeedsFixRepairLedger(project, goal.GoalIndex, updatedRepairLedger);
        _stateWriter.WriteNeedsFixState(project, goal.GoalIndex, new
        {
            route = "needs-fix",
            route_skill = PrototypeRouteSkillPolicy.Resolve(project),
            game_type_profile = PrototypeRouteSkillPolicy.ResolveProfile(project),
            project_id = project.ProjectId,
            session_id = details.Session.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            run_id = quickFixResult.RunId,
            status = routeStatus,
            iteration_session_status = quickFixResult.IterationSessionStatus,
            iteration_goal_status = quickFixResult.IterationGoalStatus,
            summary = BuildCompactSummary(quickFixResult.AssistantMessage),
            consumed = new
            {
                project_readme = !string.IsNullOrWhiteSpace(readme),
                project_execution_guide = !string.IsNullOrWhiteSpace(projectExecutionGuide),
                project_execution_guide_path = PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath,
                prototype_contract = !string.IsNullOrWhiteSpace(prototypeContract.Json),
                prototype_contract_path = prototypeContract.RelativePath,
                repair_ledger = true,
                repair_ledger_path = _stateWriter.GetNeedsFixRepairLedgerRelativePath(goal.GoalIndex)
            },
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return new PrototypeNeedsFixRouteResult(
            quickFixResult.RunId,
            routeStatus,
            quickFixResult.AssistantMessage,
            goal.GoalIndex,
            quickFixResult.IterationSessionStatus,
            quickFixResult.IterationGoalStatus,
            quickFixResult.Artifacts);
    }

    private async Task<PrototypeNeedsFixRouteResult> RunProjectLevelNeedsFixAsync(
        ProjectSnapshot project,
        ProjectIterationSessionDetails details,
        PrototypeNeedsFixRouteRequest request,
        CancellationToken cancellationToken)
    {
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeNeedsFixRouteResult("", routeSkill.FailureCode, routeSkill.FailureMessage, 0, details.Session.Status, null, []);
        }

        var prototypeContract = _contractService.Read(project);
        var feedback = BuildProjectLevelFeedback(project, request.Feedback, _stateWriter.ReadProjectReadme(project), _stateWriter.ReadOrCreateProjectExecutionGuide(project, prototypeContract), prototypeContract, _stateWriter.ReadLatestPrototypeState(project));
        var quickFixResult = await _quickFixService.SubmitAsync(
            project.AccountId,
            project.ProjectId,
            new PrototypeFeedbackRequest(
                feedback,
                request.Model,
                request.SkillActionId,
                null),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        _stateWriter.WriteNeedsFixState(project, 0, new
        {
            route = "needs-fix",
            scope = "project",
            route_skill = PrototypeRouteSkillPolicy.Resolve(project),
            game_type_profile = PrototypeRouteSkillPolicy.ResolveProfile(project),
            project_id = project.ProjectId,
            session_id = details.Session.SessionId,
            run_id = quickFixResult.RunId,
            status = quickFixResult.Status,
            summary = BuildCompactSummary(quickFixResult.AssistantMessage),
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return new PrototypeNeedsFixRouteResult(
            quickFixResult.RunId,
            quickFixResult.Status,
            quickFixResult.AssistantMessage,
            0,
            details.Session.Status,
            null,
            quickFixResult.Artifacts);
    }

    private static string NormalizeGoalRouteStatus(string? iterationGoalStatus, string routeStatus)
    {
        return iterationGoalStatus switch
        {
            "succeeded" => routeStatus,
            "needs_fix" => "needs_fix",
            "failed" => "failed",
            "running" => "running",
            "pending" => "pending",
            _ => routeStatus
        };
    }

    private static ProjectIterationGoalSnapshot? ResolveGoal(ProjectIterationSessionDetails details, PrototypeNeedsFixRouteRequest request)
    {
        if (!string.IsNullOrWhiteSpace(request.GoalId))
        {
            return details.Goals.FirstOrDefault(goal => string.Equals(goal.GoalId, request.GoalId, StringComparison.Ordinal));
        }

        if (request.GoalIndex is > 0)
        {
            return details.Goals.FirstOrDefault(goal => goal.GoalIndex == request.GoalIndex.Value);
        }

        return details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal))
               ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "failed", StringComparison.Ordinal))
               ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "running", StringComparison.Ordinal))
               ?? details.Goals.FirstOrDefault(goal =>
                   goal.GoalIndex == details.Session.CurrentGoalIndex &&
                   !string.Equals(goal.Status, "pending", StringComparison.Ordinal) &&
                   !string.Equals(goal.Status, "succeeded", StringComparison.Ordinal));
    }

    private static string SelectCurrentNeedsFixState(
        string needsFixState,
        string executeNextGoalState,
        string sessionId,
        ProjectIterationGoalSnapshot goal)
    {
        if (string.IsNullOrWhiteSpace(needsFixState))
        {
            return "";
        }

        var match = RouteStateMatchesCurrentGoal(needsFixState, sessionId, goal);
        if (match == true)
        {
            return needsFixState;
        }

        if (match == false)
        {
            return "";
        }

        return string.IsNullOrWhiteSpace(executeNextGoalState) ? needsFixState : "";
    }

    private static string SelectCurrentExecuteNextGoalState(
        string executeNextGoalState,
        string sessionId,
        ProjectIterationGoalSnapshot goal)
    {
        if (string.IsNullOrWhiteSpace(executeNextGoalState))
        {
            return "";
        }

        var match = RouteStateMatchesCurrentGoal(executeNextGoalState, sessionId, goal);
        return match == false ? "" : executeNextGoalState;
    }

    private static bool? RouteStateMatchesCurrentGoal(
        string routeState,
        string sessionId,
        ProjectIterationGoalSnapshot goal)
    {
        try
        {
            using var document = JsonDocument.Parse(routeState);
            var root = document.RootElement;
            var stateSessionId = ReadString(root, "session_id");
            var stateGoalId = ReadString(root, "goal_id");
            var stateGoalIndex = ReadInt(root, "goal_index");
            var hasIdentity = !string.IsNullOrWhiteSpace(stateSessionId) ||
                              !string.IsNullOrWhiteSpace(stateGoalId) ||
                              stateGoalIndex.HasValue;
            if (!hasIdentity)
            {
                return null;
            }

            if (!string.IsNullOrWhiteSpace(stateSessionId) &&
                !string.Equals(stateSessionId, sessionId, StringComparison.Ordinal))
            {
                return false;
            }

            if (!string.IsNullOrWhiteSpace(stateGoalId) &&
                !string.Equals(stateGoalId, goal.GoalId, StringComparison.Ordinal))
            {
                return false;
            }

            if (stateGoalIndex.HasValue && stateGoalIndex.Value != goal.GoalIndex)
            {
                return false;
            }

            return true;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private async Task<string> BuildPreviousPlatformRejectionBlockAsync(
        ProjectIterationSessionDetails details,
        ProjectIterationGoalSnapshot goal,
        CancellationToken cancellationToken)
    {
        var latestGoalRun = details.GoalRuns
            .Where(run => string.Equals(run.GoalId, goal.GoalId, StringComparison.Ordinal))
            .OrderByDescending(run => run.CreatedUtc, StringComparer.Ordinal)
            .FirstOrDefault();
        if (latestGoalRun is null)
        {
            return "- Status: none";
        }

        var run = await _metadataStore.GetRunSnapshotAsync(latestGoalRun.RunId, cancellationToken);
        if (run is null || string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return $"""
                - Status: unavailable
                - RunId: {latestGoalRun.RunId}
                - Rule: Do not infer success from prior assistant text when platform evidence is unavailable.
                """;
        }

        return BuildPreviousPlatformRejectionBlock(latestGoalRun.RunId, run.EvidenceJson);
    }

    private static string BuildPreviousPlatformRejectionBlock(string runId, string evidenceJson)
    {
        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            var root = document.RootElement;
            var goalRepairStatus = ReadString(root, "goal_repair_status");
            var acceptanceStatus = ReadString(root, "acceptance_validation_status");
            var acceptanceReason = ReadString(root, "acceptance_validation_reason");
            var acceptanceDetails = ReadString(root, "acceptance_validation_details");
            var mutationGuard = BuildMutationGuardSummary(root);
            var godotSmoke = BuildValidationSummary(root, "godot_smoke_validation");
            var rpgGdUnit = BuildValidationSummary(root, "rpg_gdunit_validation");
            var repairFocus = BuildRepairFocusInstruction(acceptanceReason, acceptanceDetails);

            return $"""
                - RunId: {runId}
                - GoalRepairStatus: {goalRepairStatus ?? "unknown"}
                - PlatformAcceptanceStatus: {acceptanceStatus ?? "unknown"}
                - PlatformAcceptanceReason: {acceptanceReason ?? "unknown"}
                - PlatformAcceptanceDetails: {TrimForPrompt(acceptanceDetails ?? "none", 1800)}
                - MutationGuard: {mutationGuard}
                - GodotSmoke: {godotSmoke}
                - RpgGdUnit: {rpgGdUnit}
                - RepairFocus: {repairFocus}
                - Priority rule: Treat this platform rejection as prior evidence for the next repair. Current platform acceptance diagnosis overrides this prior evidence when they differ. Do not report STATUS: completed until the current platform blocker is actually fixed and platform acceptance can pass.
                - Forbidden detours: Do not work on unrelated gameplay, UI, route state, recovery summaries, or later goals while this platform blocker remains unresolved.
                """;
        }
        catch (JsonException)
        {
            return $"""
                - RunId: {runId}
                - Status: evidence_json_unreadable
                - Rule: Do not infer success from prior assistant text when platform evidence is unreadable.
                """;
        }
    }

    private static string BuildMutationGuardSummary(JsonElement root)
    {
        if (!root.TryGetProperty("mutation_guard", out var guard) || guard.ValueKind != JsonValueKind.Object)
        {
            return "not_recorded";
        }

        var status = ReadString(guard, "status") ?? "unknown";
        var reason = ReadString(guard, "reason") ?? "none";
        var violations = guard.TryGetProperty("violations", out var violationsElement) && violationsElement.ValueKind == JsonValueKind.Array
            ? violationsElement.GetArrayLength()
            : 0;
        return $"{status}; reason={reason}; violations={violations}";
    }

    private static string BuildValidationSummary(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out var validation) || validation.ValueKind != JsonValueKind.Object)
        {
            return "not_recorded";
        }

        var required = ReadBool(validation, "required");
        var ran = ReadBool(validation, "ran");
        var passed = ReadBool(validation, "passed");
        var reason = ReadValidationReason(validation);
        var diagnosticExcerpt = ReadValidationDiagnosticExcerpt(validation);
        var summary = $"required={required?.ToString() ?? "unknown"}; ran={ran?.ToString() ?? "unknown"}; passed={passed?.ToString() ?? "unknown"}; reason={reason}";
        return string.IsNullOrWhiteSpace(diagnosticExcerpt)
            ? summary
            : $"{summary}; diagnostic_excerpt={TrimForPrompt(diagnosticExcerpt, 1400)}";
    }

    private static string BuildRepairFocusInstruction(string? acceptanceReason, string? acceptanceDetails)
    {
        var details = acceptanceDetails ?? "";
        if (string.Equals(acceptanceReason, "core_tests_failed", StringComparison.OrdinalIgnoreCase) &&
            details.Contains("CS0246", StringComparison.OrdinalIgnoreCase) &&
            (details.Contains("Xunit", StringComparison.OrdinalIgnoreCase) ||
             details.Contains("FluentAssertions", StringComparison.OrdinalIgnoreCase)))
        {
            return "Only repair the core test project dependency failure first. Inspect and fix Game.Core.Tests/Game.Core.Tests.csproj PackageReference entries for xunit, xunit.runner.visualstudio, FluentAssertions, Microsoft.NET.Test.Sdk, and related test packages. Do not delete tests, do not replace xUnit with hand-written shims, and do not change gameplay/UI until package restore and core test compilation can pass.";
        }

        if (string.Equals(acceptanceReason, "core_tests_failed", StringComparison.OrdinalIgnoreCase))
        {
            if (details.Contains("CS", StringComparison.OrdinalIgnoreCase))
            {
                return "Only repair the C# compile errors named in PlatformAcceptanceDetails first. Keep changes scoped to the listed files, missing symbols, and error codes. For example, if details name Game.Core/Prototypes/DqRpgPrototypeLoop.cs and missing PlayerX/PlayerY on DqRpgPrototypeState, fix that compile contract before any gameplay/UI/content polish.";
            }

            return "Only repair the core_tests_failed blocker first. Use PlatformAcceptanceDetails as the source of truth. Do not change unrelated gameplay/UI unless the listed core test failure directly requires it.";
        }

        if (string.Equals(acceptanceReason, "godot_project_build_failed", StringComparison.OrdinalIgnoreCase))
        {
            return "Only repair the Godot project build blocker first. Use PlatformAcceptanceDetails as the source of truth and keep changes scoped to the files named by the build errors.";
        }

        if (acceptanceReason?.StartsWith("missing_rpg_map_entry_contract", StringComparison.OrdinalIgnoreCase) == true)
        {
            return "Repair the full RPG/JRPG map-entry contract group, not only the first missing_file. Ensure MapScene.tscn and Scripts/MapScene.cs exist together, and satisfy the platform-required map nodes, grid-position mapping, player visibility restore, and stable movement handling before reporting STATUS: completed. Add RpgEnemyAsset or encounter trigger wiring only when the selected route or latest failure explicitly requires encounter, conflict, or battle.";
        }

        if (acceptanceReason?.StartsWith("missing_rpg_battle_scene_contract", StringComparison.OrdinalIgnoreCase) == true)
        {
            return "Repair the full RPG/JRPG battle-scene contract group, not only the first missing token. Ensure BattleScene.tscn and Scripts/BattleScene.cs exist together, BattleScene.tscn exposes BattleScene, AttackButton, RpgPlayerAsset, and RpgEnemyAsset, and BattleScene.cs exposes BattleFinished plus ResolveBattle or ResolveAttackTurn settlement wiring.";
        }

        if (acceptanceReason?.StartsWith("missing_rpg_reward_flow_contract", StringComparison.OrdinalIgnoreCase) == true)
        {
            return "Repair the full RPG/JRPG reward-flow contract group. Victory or consequence must expose exactly three understandable reward choices, selecting one must call ApplyReward or equivalent, apply visible state/consequence feedback, close reward UI, return or refresh the map, restore player visibility/input, and leave a validation-facing feedback marker such as ShowRewardReturnFeedback, ShowRewardReturnStatus, Returned to map, movement is restored, or rpg_reward_flow_contract.";
        }

        if (acceptanceReason?.StartsWith("missing_required_core_markers", StringComparison.OrdinalIgnoreCase) == true)
        {
            if (details.Contains("MoveOnMap", StringComparison.OrdinalIgnoreCase))
            {
                return "Repair the full JRPG navigation or return-loop contract around MoveOnMap. Ensure the active playable field/map/town remains visible, player visibility and input are restored, and movement proof exists in runtime code, scene wiring, or validation-facing tests before reporting completion.";
            }

            if (details.Contains("RewardOptions.Count", StringComparison.OrdinalIgnoreCase) ||
                details.Contains("ApplyReward", StringComparison.OrdinalIgnoreCase) ||
                details.Contains("Battle reward selected", StringComparison.OrdinalIgnoreCase))
            {
                return "Repair the full JRPG reward/growth contract. Ensure three reward/consequence choices exist when selected by the route, selection applies visible state change, and return/feedback remains coherent before reporting completion.";
            }

            if (details.Contains("Objective", StringComparison.OrdinalIgnoreCase) ||
                details.Contains("Quest", StringComparison.OrdinalIgnoreCase) ||
                details.Contains("Interact", StringComparison.OrdinalIgnoreCase))
            {
                return "Repair the full JRPG objective, interaction, or quest progress contract. Player action must visibly update objective/interaction/story feedback in runtime UI or scene text; do not satisfy this with isolated code-only markers.";
            }

            if (details.Contains("HP", StringComparison.OrdinalIgnoreCase) ||
                details.Contains("Stats", StringComparison.OrdinalIgnoreCase) ||
                details.Contains("Status", StringComparison.OrdinalIgnoreCase))
            {
                return "Repair the full JRPG character-state readability contract. HP, stats, status, or equivalent character state must be visible to the player and remain consistent after the relevant loop event.";
            }

            return "Repair the complete current JRPG capability contract named by the missing markers. Represent each marker in runtime behavior, scene UI, or validation-facing tests as a coherent group; do not add isolated strings just to satisfy static scanning.";
        }

        return "Repair the listed platform blocker first. Do not infer success from prior assistant summaries.";
    }

    private static string BuildFeedback(
        ProjectSnapshot project,
        string? userFeedback,
        string projectReadme,
        string projectExecutionGuide,
        PrototypeContractSnapshot prototypeContract,
        string stepState,
        string executeNextGoalState,
        string prototypeState,
        ProjectIterationGoalSnapshot goal,
        string previousPlatformRejection,
        string repairLedger)
    {
        var sourceLabel = !string.IsNullOrWhiteSpace(stepState)
            ? "current needs fix step state"
            : !string.IsNullOrWhiteSpace(executeNextGoalState)
                ? "current execute next goal step state"
                : "prototype route state";
        var sourceState = CompactRouteState(!string.IsNullOrWhiteSpace(stepState)
            ? stepState
            : !string.IsNullOrWhiteSpace(executeNextGoalState)
                ? executeNextGoalState
                : prototypeState);
        return $"""
            运行当前游戏模块任务的 needs-fix 顶层修复路由。

            方向锁定：
            - 本轮修复目标只能是下面的当前任务。
            - 使用 Prototype Chapter 6 Lite 语义：一次只修复一个任务，并更新路由状态/台账；不要创建 Taskmaster 三联任务、正式验收文件、overlays、contracts 或 review pipeline 产物。
            - Project README、Project Execution Guide 和恢复来源只作为只读恢复上下文，不是修复目标。
            - Project Execution Guide 是项目级 /new 恢复协议。
            - 除非当前任务明确要求，不要修 Phase A 路由、恢复逻辑、文档、脚本、部署或测试。
            - 玩法/Godot/RPG 任务只修游戏文件，并按 AcceptanceHint 验证。
            - 例外：如果最新平台验收阻塞是 core_tests_failed、缺少 Xunit/FluentAssertions/package references 或托管测试项目编译失败，先修托管测试项目/包/引用文件。
            - 平台路由或恢复测试通过，不代表玩法任务已经完成。

            Project README:
            {TrimForPrompt(projectReadme, 220)}

            Project Execution Guide:
            - Path: {PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath}
            - Route Recovery Protocol: follow the project-level /new recovery order from this guide before changing files.
            {TrimForPrompt(projectExecutionGuide, 60)}

            Project prototype contract:
            - Status: {(string.IsNullOrWhiteSpace(prototypeContract.Json) ? "missing" : "present")}
            - ContractPath: {prototypeContract.RelativePath}
            - Rule: preserve contract traceability; do not override user form values with template defaults.

            当前任务：
            - GoalIndex: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}
            - PreviousResultSummary: {BuildCompactSummary(goal.ResultSummary, 120)}

            上一轮平台拒绝：
            {previousPlatformRejection}

            任务修复台账：
            {repairLedger}

            已读取恢复来源：{sourceLabel}
            {TrimForPrompt(sourceState, 80)}

            用户反馈：
            {userFeedback?.Trim()}

            范围规则：
            只修复当前任务。不要读取或使用其他任务的 needs-fix 状态。
            当前平台验收结果优先于上一轮拒绝和修复台账。台账只作为连续修复记忆，不是实时验收权威。
            如果验收仍报告 core_tests_failed 或缺少测试框架引用，在修复托管文件前不要输出 STATUS: completed。
            面向浏览器用户的输出必须使用简体中文。只有 STATUS: completed|needs_fix 这类机器协议值保持英文。

            {PrototypeGameplayPromptGuards.BuildCombatPressureGuardPromptBlock()}

            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            """;
    }

    private static string BuildProjectLevelFeedback(
        ProjectSnapshot project,
        string? userFeedback,
        string projectReadme,
        string projectExecutionGuide,
        PrototypeContractSnapshot prototypeContract,
        string prototypeState)
    {
        return $"""
            Run the needs fix top-level route for a project-level runtime issue.

            Direction lock:
            - This request is still needs-fix-route, but it is not bound to a single iteration task.
            - Use Prototype Chapter 6 Lite semantics: focused repair plus route state; no Taskmaster triplets, formal acceptance files, overlays, contracts, or review pipeline artifacts.
            - Repair the user's reported runtime issue in the hosted game project.
            - Do not generate or rewrite the iteration plan.
            - Do not repair Phase A platform routing, route-state readers, recovery logic, deployment, or tests.
            - Prefer gameplay/project files only. If the report is too vague, inspect the Godot project configuration and fix the concrete runtime wiring problem that matches the report.
            - Output must be browser-safe: do not expose paths, command lines, script names, logs, or environment variables.
            - Browser-facing output must be Simplified Chinese. Keep only machine protocol tokens such as STATUS: completed|needs_fix in English.

            Project README:
            {CompactRouteState(projectReadme)}

            Project Execution Guide:
            - Path: {PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath}
            - Route Recovery Protocol: follow the project-level /new recovery order from this guide before changing files.
            {TrimForPrompt(projectExecutionGuide, 200)}

            {PrototypeContractService.BuildPromptBlock(prototypeContract)}

            Prototype route state:
            {CompactRouteState(prototypeState)}

            Project:
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            {PrototypeGameplayPromptGuards.BuildCombatPressureGuardPromptBlock()}

            User reported issue:
            {userFeedback}
            """;
    }

    private static string BuildCompactSummary(string? value, int maxLength = 1200)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var lines = value
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(line => !line.StartsWith("Project README:", StringComparison.OrdinalIgnoreCase))
            .Where(line => !line.StartsWith("Recovery source consumed:", StringComparison.OrdinalIgnoreCase))
            .Where(line => !line.StartsWith("{", StringComparison.Ordinal))
            .Take(8);
        var summary = string.Join(" ", lines);
        return summary.Length <= maxLength ? summary : summary[..maxLength];
    }

    private static string CompactRouteState(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "(empty)";
        }

        try
        {
            using var document = JsonDocument.Parse(value);
            var root = document.RootElement;
            var compact = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["route"] = ReadString(root, "route"),
                ["status"] = ReadString(root, "status"),
                ["run_id"] = ReadString(root, "run_id"),
                ["goal_index"] = ReadInt(root, "goal_index"),
                ["iteration_session_status"] = ReadString(root, "iteration_session_status"),
                ["iteration_goal_status"] = ReadString(root, "iteration_goal_status"),
                ["summary"] = BuildCompactSummary(ReadString(root, "summary"), 450)
            };

            return JsonSerializer.Serialize(compact.Where(pair => pair.Value is not null).ToDictionary(pair => pair.Key, pair => pair.Value));
        }
        catch (JsonException)
        {
            return TrimForPrompt(BuildCompactSummary(value));
        }
    }

    private static string? ReadString(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static int? ReadInt(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.Number &&
               value.TryGetInt32(out var result)
            ? result
            : null;
    }

    private static bool? ReadBool(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               (value.ValueKind == JsonValueKind.True || value.ValueKind == JsonValueKind.False)
            ? value.GetBoolean()
            : null;
    }

    private static string ReadValidationReason(JsonElement validation)
    {
        var topLevelReason = ReadString(validation, "reason");
        if (!string.IsNullOrWhiteSpace(topLevelReason))
        {
            return topLevelReason;
        }

        if (validation.ValueKind == JsonValueKind.Object &&
            validation.TryGetProperty("smoke", out var smoke) &&
            smoke.ValueKind == JsonValueKind.Object)
        {
            var smokeReason = ReadString(smoke, "reason");
            if (!string.IsNullOrWhiteSpace(smokeReason))
            {
                return smokeReason;
            }
        }

        return "none";
    }

    private static string? ReadValidationDiagnosticExcerpt(JsonElement validation)
    {
        var topLevelExcerpt = ReadString(validation, "diagnostic_excerpt");
        if (!string.IsNullOrWhiteSpace(topLevelExcerpt))
        {
            return topLevelExcerpt;
        }

        if (validation.ValueKind == JsonValueKind.Object &&
            validation.TryGetProperty("smoke", out var smoke) &&
            smoke.ValueKind == JsonValueKind.Object)
        {
            return ReadString(smoke, "diagnostic_excerpt");
        }

        return null;
    }

    private static string TrimForPrompt(string value, int maxLength = 4000)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "(empty)";
        }

        var trimmed = value.Trim();
        return trimmed.Length <= maxLength ? trimmed : trimmed[..maxLength];
    }

    private static string ExtractAssistantClaimedStatus(string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return "unknown";
        }

        foreach (var line in assistantMessage.Replace("\r\n", "\n", StringComparison.Ordinal).Split('\n'))
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("STATUS:", StringComparison.OrdinalIgnoreCase))
            {
                return trimmed["STATUS:".Length..].Trim();
            }
        }

        return "unknown";
    }
}
