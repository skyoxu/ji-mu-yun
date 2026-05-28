using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeRepairPlanService
{
    private const string SourceKind = "repair_plan";
    private const string ExecuteRunType = "prototype-repair-step";

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeQuickFixService _quickFixService;
    private readonly PrototypeRouteStateWriter _stateWriter;
    private readonly PrototypeContractService _contractService;
    private readonly ICodexChatClient? _codexChatClient;

    public PrototypeRepairPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService,
        ICodexChatClient? codexChatClient = null)
        : this(metadataStore, quickFixService, new PrototypeRouteStateWriter(), new PrototypeContractService(), codexChatClient)
    {
    }

    public PrototypeRepairPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService,
        PrototypeRouteStateWriter stateWriter,
        PrototypeContractService? contractService = null,
        ICodexChatClient? codexChatClient = null)
    {
        _metadataStore = metadataStore;
        _quickFixService = quickFixService;
        _stateWriter = stateWriter;
        _contractService = contractService ?? new PrototypeContractService();
        _codexChatClient = codexChatClient;
    }

    public async Task<PrototypeRepairPlanResult> CreateAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await RequireProjectAsync(accountId, projectId, cancellationToken);
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeRepairPlanResult("", routeSkill.FailureCode, routeSkill.FailureMessage, []);
        }

        var failedRun = await FindLatestFailedRunAsync(project.ProjectId, cancellationToken);
        if (failedRun is null)
        {
            return new PrototypeRepairPlanResult("", "missing_failure", "当前项目没有可用于生成修复计划的失败记录。", []);
        }

        var prototypeContract = _contractService.Read(project);
        var failureText = BuildFailureText(failedRun);
        var planContext = BuildPlanContext(project, prototypeContract, failedRun, failureText, routeSkill.Context);
        var goals = await BuildRepairGoalsAsync(project, planContext, cancellationToken);
        var summary = $"已基于最近一次失败生成 {goals.Count} 个修复步骤。请逐项执行，最后一步必须做全量验收。";
        var session = await _metadataStore.CreateProjectIterationSessionAsync(
            accountId,
            project.ProjectId,
            SourceKind,
            BuildSourceMessage(failedRun, failureText, routeSkill.Context),
            $"Repair the failed prototype route through small isolated repair steps for {routeSkill.Context.RouteSkillId}.",
            goals.Select(goal => new ProjectIterationGoalCreateCommand(
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint)).ToArray(),
            cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(session.SessionId, "ready", 0, summary, null, null, cancellationToken);

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, cancellationToken);
        _stateWriter.WriteRepairPlanState(project, new
        {
            route = "repair-plan",
            source_kind = SourceKind,
            source_run_id = failedRun.RunId,
            session_id = session.SessionId,
            status = "ready",
            summary,
            route_skill = routeSkill.Context,
            prototype_contract = prototypeContract.RelativePath,
            goals = goals.Select(goal => new
            {
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint,
                goal.Status
            }).ToArray(),
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return PrototypeRepairPlanResult.FromDetails(details!, summary);
    }

    public async Task<PrototypeRepairPlanResult?> GetLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, SourceKind, cancellationToken);
        return details is null
            ? null
            : PrototypeRepairPlanResult.FromDetails(details, details.Session.LatestSummary ?? "已有修复计划。");
    }

    public async Task<PrototypeRepairStepExecutionResult> ExecuteNextAsync(
        string accountId,
        string projectId,
        PrototypeRepairStepExecutionRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await RequireProjectAsync(accountId, projectId, cancellationToken);
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeRepairStepExecutionResult("", "", "", routeSkill.FailureCode, routeSkill.FailureMessage, 0, false, routeSkill.FailureCode);
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, cancellationToken);
        if (details is null)
        {
            return new PrototypeRepairStepExecutionResult("", "", "", "missing_repair_plan", "当前项目还没有修复计划，请先生成修复计划。", 0, false, "missing_repair_plan");
        }

        var current = details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "needs_fix", StringComparison.OrdinalIgnoreCase))
                      ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "failed", StringComparison.OrdinalIgnoreCase))
                      ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "pending", StringComparison.OrdinalIgnoreCase));
        if (current is null)
        {
            return new PrototypeRepairStepExecutionResult(details.Session.SessionId, "", "", "no_pending_repair_step", "当前修复计划没有待执行步骤。", details.Session.CurrentGoalIndex, false, details.Session.Status);
        }

        await _metadataStore.UpdateProjectIterationGoalStatusAsync(current.GoalId, "running", current.ResultSummary, null, cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "running", current.GoalIndex, $"正在执行修复步骤 {current.GoalIndex}。", null, null, cancellationToken);

        var feedback = BuildStepFeedback(project, details, current, request.Feedback, routeSkill.Context);
        var result = await _quickFixService.SubmitAsync(
            project.ProjectId,
            new PrototypeFeedbackRequest(feedback, request.Model, null, null),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        var completed = string.Equals(result.Status, "completed", StringComparison.OrdinalIgnoreCase);
        var goalStatus = completed ? "succeeded" : "needs_fix";
        await _metadataStore.UpdateProjectIterationGoalStatusAsync(
            current.GoalId,
            goalStatus,
            result.AssistantMessage,
            completed ? DateTimeOffset.UtcNow.ToString("O") : null,
            CancellationToken.None);
        if (!string.IsNullOrWhiteSpace(result.RunId))
        {
            await _metadataStore.LinkProjectIterationGoalRunAsync(details.Session.SessionId, current.GoalId, result.RunId, ExecuteRunType, CancellationToken.None);
        }

        var refreshed = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, CancellationToken.None)
            ?? details;
        var hasNeedsFix = refreshed.Goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.OrdinalIgnoreCase));
        var hasPending = refreshed.Goals.Any(goal => string.Equals(goal.Status, "pending", StringComparison.OrdinalIgnoreCase));
        var sessionStatus = hasNeedsFix ? "needs_fix" : hasPending ? "paused_for_review" : "completed";
        var summary = completed
            ? $"修复步骤 {current.GoalIndex} 已完成。"
            : $"修复步骤 {current.GoalIndex} 仍需继续修复。";
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(refreshed.Session.SessionId, sessionStatus, current.GoalIndex, summary, null, sessionStatus == "completed" ? DateTimeOffset.UtcNow.ToString("O") : null, CancellationToken.None);

        _stateWriter.WriteRepairPlanState(project, new
        {
            route = "execute-repair-step",
            source_kind = SourceKind,
            session_id = refreshed.Session.SessionId,
            run_id = result.RunId,
            goal_id = current.GoalId,
            goal_index = current.GoalIndex,
            status = result.Status,
            goal_status = goalStatus,
            session_status = sessionStatus,
            summary,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return new PrototypeRepairStepExecutionResult(refreshed.Session.SessionId, current.GoalId, result.RunId, result.Status, summary, current.GoalIndex, true, sessionStatus);
    }

    private async Task<ProjectSnapshot> RequireProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        return project;
    }

    private async Task<RunSnapshot?> FindLatestFailedRunAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.FirstOrDefault(run =>
            string.Equals(run.Status, "failed", StringComparison.OrdinalIgnoreCase) &&
            (run.RunType.Contains("prototype", StringComparison.OrdinalIgnoreCase) ||
             run.RunType.Contains("needs-fix", StringComparison.OrdinalIgnoreCase)));
    }

    private static string BuildFailureText(RunSnapshot run)
    {
        return string.Join("\n", run.ProgressLabel, run.StderrText, run.StdoutText, run.EvidenceJson)
            .Trim();
    }

    private static string BuildSourceMessage(RunSnapshot run, string failureText, PrototypeRouteSkillContext routeSkill)
    {
        return JsonSerializer.Serialize(new
        {
            source_run_id = run.RunId,
            source_run_type = run.RunType,
            source_status = run.Status,
            route_skill = routeSkill.RouteSkillId,
            failure_excerpt = Trim(failureText, 4000)
        });
    }

    private static PrototypeRepairPlanContext BuildPlanContext(
        ProjectSnapshot project,
        PrototypeContractSnapshot contract,
        RunSnapshot failedRun,
        string failureText,
        PrototypeRouteSkillContext routeSkill)
    {
        return new PrototypeRepairPlanContext(routeSkill, contract, failedRun, failureText);
    }

    private async Task<List<PrototypeRepairGoalResult>> BuildRepairGoalsAsync(
        ProjectSnapshot project,
        PrototypeRepairPlanContext context,
        CancellationToken cancellationToken)
    {
        if (context.RouteSkill.RouteSkillId == "prototype-rpg-godot-zh")
        {
            var planned = await TryBuildRpgRepairGoalsFromModelAsync(project, context, cancellationToken);
            if (planned.Count > 0)
            {
                return planned;
            }

            return BuildRpgRepairGoals(context);
        }

        return BuildGenericRepairGoals(context);
    }

    private async Task<List<PrototypeRepairGoalResult>> TryBuildRpgRepairGoalsFromModelAsync(
        ProjectSnapshot project,
        PrototypeRepairPlanContext context,
        CancellationToken cancellationToken)
    {
        if (_codexChatClient is null)
        {
            return [];
        }

        var completion = await _codexChatClient.CompleteAsync(
            project.RepoPath,
            PrototypeModelPolicy.Normalize("gpt-5.4"),
            BuildRpgRepairGoalPrompt(project, context),
            billingApiKeyName: project.AccountId,
            cancellationToken: cancellationToken);
        if (!completion.Succeeded)
        {
            return [];
        }

        return ParseRepairGoalPlan(completion.AssistantMessage);
    }

    private static List<PrototypeRepairGoalResult> BuildRpgRepairGoals(PrototypeRepairPlanContext context)
    {
        var goals = new List<PrototypeRepairGoalResult>();
        void Add(string title, string description, string acceptance)
        {
            if (goals.Any(goal => string.Equals(goal.Title, title, StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "恢复原型运行证据与 TDD 绿灯",
            BuildRpgEvidenceRepairDescription(context),
            """
            This step passes only when the latest run blocker is removed and the prototype route can write its completion/TDD evidence without permission, build, or cache-lock failures.
            Do not report this step as succeeded if the latest failure evidence still blocks route completion artifacts.
            """);

        Add(
            "修复 RPG 场景与节点合同",
            BuildRpgSceneContractRepairDescription(context),
            """
            This step passes only when the current RPG prototype has the required contract-aligned scene structure, including the main prototype shell, MapScene, BattleScene, and required named map/player/enemy asset nodes.
            Scene/script contract drift must be eliminated before continuing.
            """);

        Add(
            "修复 RPG 玩法合同与表单追踪",
            BuildRpgGameplayContractRepairDescription(context),
            """
            This step passes only when concrete user form values from prototype-contract form_fields and input_traceability are represented in gameplay behavior, UI/state feedback, tests, or an explicit needs-fix blocker.
            Do not replace concrete project values with RPG template defaults.
            """);

        Add(
            "执行最终全量验收",
            "运行 RPG 类型要求的最终 smoke/导航/可见性/合同一致性验收，确认修复闭环。",
            "最终验收通过后，原型修复才算完成。");

        return goals;
    }

    private static List<PrototypeRepairGoalResult> BuildGenericRepairGoals(PrototypeRepairPlanContext context)
    {
        var goals = new List<PrototypeRepairGoalResult>();
        void Add(string title, string description, string acceptance)
        {
            if (goals.Any(goal => string.Equals(goal.Title, title, StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "恢复原型运行证据",
            BuildGenericEvidenceRepairDescription(context),
            "The latest failure reason is eliminated and the prototype route can produce completion evidence without build, cache, or write failures.");

        Add(
            "修复通用原型合同缺口",
            BuildGenericContractRepairDescription(context),
            "The default prototype route skill and project prototype contract are reflected in the repaired output, with no new prototype drift.");

        Add(
            "执行最终全量验收",
            "运行当前类型要求的最终 smoke/导航/可见性验收，确认修复闭环。",
            "最终验收通过后，原型修复才算完成。");

        return goals;
    }

    private static string BuildRpgEvidenceRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the latest failed RPG prototype route evidence path using the route skill, project contract, and failure output.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillGuide}
            - {context.RouteSkill.RouteSkillContract}

            Failure evidence:
            {context.FailureText}

            Required repair scope:
            - Read the current project README and prototype contract first.
            - Use the latest failed run output as the source of truth for what broke.
            - Restore writable completion artifacts, TDD green evidence, and build outputs needed by the prototype route.
            - Do not broaden this step into gameplay or scene redesign.
            - Preserve browser-safe output.
            """;
    }

    private static string BuildRpgSceneContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the RPG scene and node contract using the selected route skill and prototype contract.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

            Contract requirements:
            - The project prototype contract is authoritative.
            - MapScene, BattleScene, and the main prototype shell must have clear responsibilities.
            - Map, player, and enemy asset instances must use the RPG contract naming rules.
            - Main.tscn default-hidden VBox, Overlays, and ScreenRoot SOP must remain preserved where applicable.

            Latest failure evidence:
            {Trim(context.FailureText, 2400)}
            """;
    }

    private static string BuildRpgGameplayContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair RPG gameplay behavior against project-specific form_fields and input_traceability.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

            Contract requirements:
            - User form fields override RPG defaults and template examples.
            - Encounter probability, guaranteed encounter, player stats, enemy stats, reward choices, return-to-map flow, and win/fail rules must match concrete project values when present.
            - Any concrete non-empty input field that cannot be implemented must become an explicit needs-fix blocker, not a silent omission.

            Latest failure evidence:
            {Trim(context.FailureText, 2400)}
            """;
    }

    private static string BuildGenericEvidenceRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the latest failed prototype route evidence path using the default prototype route skill and the project contract.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillGuide}

            Failure evidence:
            {context.FailureText}

            Required repair scope:
            - Read the current project README and prototype contract first.
            - Use the latest failed run output as the source of truth for what broke.
            - Restore route completion evidence before broader gameplay repair.
            - Preserve browser-safe output.
            """;
    }

    private static string BuildGenericContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the current prototype against the default prototype route skill and project prototype contract.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

            Contract requirements:
            - User form fields override generic defaults.
            - The playable loop, UI feedback, and validation evidence must match the project prototype contract.
            - Do not invent type-specific steps unless the project contract demands them.

            Latest failure evidence:
            {Trim(context.FailureText, 2400)}
            """;
    }

    private static string BuildRpgRepairGoalPrompt(ProjectSnapshot project, PrototypeRepairPlanContext context)
    {
        var failureJson = JsonSerializer.Serialize(new
        {
            runType = context.FailedRun.RunType,
            status = context.FailedRun.Status,
            progressLabel = context.FailedRun.ProgressLabel,
            stderr = Trim(context.FailedRun.StderrText ?? "", 2000),
            stdout = Trim(context.FailedRun.StdoutText ?? "", 2000),
            evidence = Trim(context.FailedRun.EvidenceJson ?? "", 3000)
        });

        return $"""
            You are generating a repair plan for a failed hosted RPG Godot prototype run.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            goals

            goals must be an array of 4 to 6 objects with:
            title, description, acceptanceHint

            Rules:
            - Base the plan on the latest failed blocker, not on a generic RPG template.
            - First goal must target the concrete failed blocker with the highest repair value.
            - If the failure is main-menu/navigation/map-visibility related, do not start with evidence, TDD, permission, cache, or build-recovery steps.
            - Use small isolated gameplay repair steps: MapScene entry, movement/encounter, battle, reward loop, win/fail visibility, final acceptance.
            - Mention evidence/TDD/build recovery only when the failure explicitly points to permission denied, write failure, cache lock, build failure, or missing completion artifacts.
            - Keep the final goal as full playable prototype acceptance.
            - Keep each goal narrow enough to execute independently.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}

            Route skill:
            - RouteSkillId: {context.RouteSkill.RouteSkillId}
            - RouteSkillGuide: {context.RouteSkill.RouteSkillGuide}
            - RouteSkillContract: {context.RouteSkill.RouteSkillContract}

            Prototype contract:
            {Trim(context.Contract.Json ?? "", 3000)}

            Latest failed run:
            {failureJson}

            Failure excerpt:
            {Trim(context.FailureText, 4000)}
            """;
    }

    private static List<PrototypeRepairGoalResult> ParseRepairGoalPlan(string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return [];
        }

        try
        {
            using var document = JsonDocument.Parse(ExtractFirstJsonObject(assistantMessage) ?? assistantMessage);
            if (!document.RootElement.TryGetProperty("goals", out var goalsElement) || goalsElement.ValueKind != JsonValueKind.Array)
            {
                return [];
            }

            var goals = new List<PrototypeRepairGoalResult>();
            var index = 1;
            foreach (var item in goalsElement.EnumerateArray())
            {
                var title = item.TryGetProperty("title", out var titleElement) && titleElement.ValueKind == JsonValueKind.String
                    ? titleElement.GetString()?.Trim()
                    : null;
                var description = item.TryGetProperty("description", out var descriptionElement) && descriptionElement.ValueKind == JsonValueKind.String
                    ? descriptionElement.GetString()?.Trim()
                    : null;
                var acceptance = item.TryGetProperty("acceptanceHint", out var acceptanceElement) && acceptanceElement.ValueKind == JsonValueKind.String
                    ? acceptanceElement.GetString()?.Trim()
                    : null;
                if (string.IsNullOrWhiteSpace(title) || string.IsNullOrWhiteSpace(description) || string.IsNullOrWhiteSpace(acceptance))
                {
                    continue;
                }

                goals.Add(new PrototypeRepairGoalResult(index++, title, description, acceptance, "pending"));
            }

            return goals.Count >= 4 ? goals : [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static string BuildStepFeedback(ProjectSnapshot project, ProjectIterationSessionDetails details, ProjectIterationGoalSnapshot goal, string? feedback, PrototypeRouteSkillContext routeSkill)
    {
        return $"""
            Run the execute-repair-step top-level route.

            Repair plan:
            - SessionId: {details.Session.SessionId}
            - SourceKind: {SourceKind}
            - CurrentStep: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}

            Mandatory rules:
            - Execute only the current repair step.
            - Do not regenerate the prototype, iteration plan, or repair plan.
            - Do not repair PhaseA platform code, docs, scripts, deployment, or route code.
            - Change only hosted game project files needed for this repair step.
            - Keep output browser-safe: no paths, command lines, script names, logs, or environment values.

            Project:
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            Route skill context:
            - RouteSkillId: {routeSkill.RouteSkillId}
            - RouteSkillName: {routeSkill.RouteSkillName}
            - RouteSkillLabel: {routeSkill.RouteSkillLabel}
            - RouteSkillGuide: {routeSkill.RouteSkillGuide}
            - RouteSkillContract: {routeSkill.RouteSkillContract}
            - MandatorySkillEntry: ${routeSkill.RouteSkillId}
            - MandatorySkillPath: {routeSkill.SkillRelativePath}

            Extra user feedback:
            {feedback}
            """;
    }

    private static string Trim(string value, int maxLength)
    {
        return value.Length <= maxLength ? value : value[..maxLength];
    }

    private static string? ExtractFirstJsonObject(string text)
    {
        var start = text.IndexOf('{');
        if (start < 0)
        {
            return null;
        }

        var depth = 0;
        var inString = false;
        var escaped = false;
        for (var index = start; index < text.Length; index++)
        {
            var current = text[index];
            if (inString)
            {
                if (escaped)
                {
                    escaped = false;
                }
                else if (current == '\\')
                {
                    escaped = true;
                }
                else if (current == '"')
                {
                    inString = false;
                }

                continue;
            }

            if (current == '"')
            {
                inString = true;
                continue;
            }

            if (current == '{')
            {
                depth++;
            }
            else if (current == '}')
            {
                depth--;
                if (depth == 0)
                {
                    return text[start..(index + 1)];
                }
            }
        }

        return null;
    }
}

public sealed record PrototypeRepairPlanResult(
    string SessionId,
    string Status,
    string Summary,
    IReadOnlyList<PrototypeRepairGoalResult> Goals)
{
    public static PrototypeRepairPlanResult FromDetails(ProjectIterationSessionDetails details, string summary)
    {
        return new PrototypeRepairPlanResult(
            details.Session.SessionId,
            details.Session.Status,
            summary,
            details.Goals.Select(goal => new PrototypeRepairGoalResult(
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint ?? "",
                goal.Status,
                goal.ResultSummary)).ToArray());
    }
}

public sealed record PrototypeRepairGoalResult(
    int GoalIndex,
    string Title,
    string Description,
    string AcceptanceHint,
    string Status,
    string? ResultSummary = null);

public sealed record PrototypeRepairStepExecutionRequest(string? Model = null, string? Feedback = null);

public sealed record PrototypeRepairStepExecutionResult(
    string SessionId,
    string GoalId,
    string RunId,
    string Status,
    string Summary,
    int GoalIndex,
    bool HasMoreWork,
    string SessionStatus);

public sealed record PrototypeRepairPlanContext(
    PrototypeRouteSkillContext RouteSkill,
    PrototypeContractSnapshot Contract,
    RunSnapshot FailedRun,
    string FailureText);
