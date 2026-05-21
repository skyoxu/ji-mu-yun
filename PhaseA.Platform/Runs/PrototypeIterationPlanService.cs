using System.Text.RegularExpressions;
using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeIterationPlanService
{
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
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeRouteStateWriter _routeStateWriter;
    private readonly PrototypeContractService _contractService;

    public PrototypeIterationPlanService(PhaseAMetadataStore metadataStore)
        : this(metadataStore, new PrototypeRouteStateWriter(), new PrototypeContractService())
    {
    }

    public PrototypeIterationPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeRouteStateWriter routeStateWriter,
        PrototypeContractService? contractService = null)
    {
        _metadataStore = metadataStore;
        _routeStateWriter = routeStateWriter;
        _contractService = contractService ?? new PrototypeContractService();
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

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var rawMessage = request.Message?.Trim();
        var message = NormalizePlanningMessage(rawMessage, request.SourceKind);
        if (string.IsNullOrWhiteSpace(message))
        {
            return new PrototypeIterationPlanResult("", "missing_message", "请输入要拆解的优化目标。", []);
        }

        var sourceKind = string.IsNullOrWhiteSpace(request.SourceKind) ? "manual_feedback" : request.SourceKind.Trim();
        if (string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase) &&
            IsInternalExecutionSuggestion(message))
        {
            return new PrototypeIterationPlanResult(
                "",
                "suggestion_needs_fix",
                "当前这条建议更像内部执行或环境修复信息，不适合直接拆成迭代目标。请先处理需修复项，或重新生成更明确的产品向优化建议。",
                []);
        }
        var routeSkill = PrototypeRouteSkillPolicy.Resolve(project);
        var prototypeContract = _contractService.Read(project);
        var goals = BuildGoals(message, sourceKind);
        if (PrototypeRouteSkillPolicy.IsRpgProject(project))
        {
            goals = BuildRpgContractGoals(message, goals, prototypeContract);
        }
        else
        {
            goals = AppendGenericFinalAcceptanceGoal(goals, message, prototypeContract);
        }
        var overallGoal = BuildOverallGoal(project.GameName, message);
        var created = await _metadataStore.CreateProjectIterationSessionAsync(
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
            cancellationToken);

        var summary = $"已生成 {goals.Count} 个迭代目标，最后一个目标是按游戏类型生成的全量交付验收。请先执行目标 1，再逐步推进后续目标。";
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(created.SessionId, "ready", 0, summary, null, null, cancellationToken);
        _routeStateWriter.WriteIterationPlanState(project, new
        {
            route = "iteration-plan",
            route_skill = routeSkill,
            prototype_contract = prototypeContract.RelativePath,
            prototype_contract_present = !string.IsNullOrWhiteSpace(prototypeContract.Json),
            session_id = created.SessionId,
            status = "ready",
            source_kind = sourceKind,
            summary,
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
        return new PrototypeIterationPlanResult(created.SessionId, "ready", summary, goals);
    }

    public async Task<ProjectIterationSessionDetails?> GetLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        return await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
    }

    public async Task<PrototypeIterationPlanEvaluationResult> EvaluateAsync(
        string accountId,
        string projectId,
        PrototypeWorkflowProgress? prototypeProgress,
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
                "当前项目还没有迭代计划。",
                "还没有可执行的目标列表，无法判断是否适合直接进入下一目标。",
                "请先生成迭代计划。",
                null);
            return result;
        }

        var goals = details.Goals.OrderBy(goal => goal.GoalIndex).ToArray();
        if (goals.Length == 0)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划没有有效目标。",
                "计划会话存在，但没有生成任何可执行目标。",
                "请重新生成迭代计划。",
                BuildRegenerationPrompt(prototypeProgress, details)));
        }

        if (goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)))
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有需要先修复的目标。",
                "至少一个目标已经被标记为 needs_fix，继续执行后续目标只会放大不确定性。",
                "先修复当前目标，再决定是否继续后续目标。",
                null));
        }

        if (goals.Any(goal => string.Equals(goal.Status, "running", StringComparison.Ordinal)))
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有进行中的目标。",
                "已有目标正在执行，暂时不适合重新拆解或继续触发下一目标。",
                "等待当前目标完成后再刷新判断。",
                null));
        }

        var pendingGoals = goals.Where(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)).ToArray();
        if (pendingGoals.Length == 0)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "当前计划已经没有待执行目标。",
                "所有目标都已完成或已停止，不需要继续执行下一目标。",
                "如果还有新需求，请基于新的优化目标重新生成计划。",
                null));
        }

        var isRpgProject = PrototypeRouteSkillPolicy.IsRpgProject(project);
        var rpgPlanIssue = isRpgProject ? FindRpgPlanContractIssue(goals) : null;
        if (rpgPlanIssue is not null)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前 RPG 迭代计划缺少类型 skill 要求的场景或素材验收 step。",
                rpgPlanIssue,
                "请先按 RPG 类型 skill 重新生成迭代计划：基础素材验收、地图场景、战斗场景、主原型/场景切换必须分别成 step。",
                BuildRpgRegenerationPrompt(details)));
        }

        var firstPending = pendingGoals[0];
        var firstGoalLooksTooLarge = !IsRecognizedSmallGoal(firstPending) && (LooksTooBroad(firstPending.Title) || LooksTooBroad(firstPending.Description));
        var overallLooksLarge = goals.Length <= 3 && goals.Any(goal => LooksTooBroad(goal.Description));
        var recommendedButStillBroad = string.Equals(prototypeProgress?.NextStepEvaluation, "recommended", StringComparison.OrdinalIgnoreCase)
                                       && goals.Length <= 3
                                       && firstGoalLooksTooLarge;

        if (!isRpgProject && (firstGoalLooksTooLarge || overallLooksLarge || recommendedButStillBroad))
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划可以用，但第一目标仍然偏大，直接执行风险较高。",
                $"当前第一个待执行目标“{firstPending.Title}”混合了多个连续实现点，更像总任务而不是单次小目标。",
                "建议先重生成一次更细的迭代计划，再执行下一目标。",
                BuildRegenerationPrompt(prototypeProgress, details)));
        }

        return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "当前计划适合直接执行下一目标。",
            $"当前待执行目标“{firstPending.Title}”边界相对清楚，没有发现明显的 needs_fix 或过粗拆分信号。",
            "可以直接点击“执行下一目标”。",
            null));
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
            if (goals.Count >= 7)
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
                0 => "目标 1：补齐当前核心缺口",
                1 => "目标 2：收敛关键交互链路",
                _ => "目标 3：完成一次可验证检查"
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
                $"完成并验证：{title}。",
                "pending"));
        }

        return goals;
    }

    private static bool IsRpgProject(ProjectSnapshot project)
    {
        var text = string.Join(" ", project.GameTypeSource, project.TemplateRuleId, project.Name, project.GameName).ToLowerInvariant();
        if (text.Contains("rpg", StringComparison.Ordinal) ||
            text.Contains("dragon quest", StringComparison.Ordinal))
        {
            return true;
        }

        return File.Exists(Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs"));
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgContractGoals(
        string message,
        List<PrototypeIterationPlanGoalResult> existingGoals,
        PrototypeContractSnapshot prototypeContract)
    {
        var hint = TrimForHint(message, 96);
        var contractInstruction = BuildContractGoalInstruction(prototypeContract);
        return
        [
            new PrototypeIterationPlanGoalResult(
                1,
                "RPG Step 1: basic assets and UI validation",
                $"Inventory and wire the RPG prototype baseline for required map, player, enemy, battle, reward, and UI assets before scene work starts. {contractInstruction} Source request: {hint}",
                $"Pass only when the current RPG prototype scene actually references and renders the three required foundation asset categories: map, player, and enemy, with readable UI markers for map play, battle play, and reward selection. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                2,
                "RPG Step 2: Start Adventure to visible MapScene validation",
                $"Create and validate the dedicated RPG MapScene from the player's real entry path. This step must prove that clicking Start Adventure hides the menu, shows a non-empty visible map, spawns the player, exposes a visible encounter affordance, and can start the first encounter. {contractInstruction}",
                $"Pass only when Start Adventure opens a valid visible RPG MapScene and the map scene proves movement plus encounter entry from the prototype entry path. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                3,
                "RPG Step 3: BattleScene creation and validation",
                $"Create and validate a dedicated RPG battle scene. This step must focus on one readable battle, action resolution, victory/defeat settlement, and battle UI feedback. {contractInstruction}",
                $"Pass only when the project contains a valid RPG BattleScene and one battle can independently reach settlement. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                4,
                "RPG Step 4: main prototype scene and scene switching validation",
                $"Create and validate the main RPG prototype scene that connects the menu/start path, map scene, battle scene, and return path without collapsing all logic into one scene. {contractInstruction}",
                $"Pass only when the main prototype scene can switch into the map, enter battle, and return to the correct RPG flow scene. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                5,
                "RPG Step 5: reward loop and return-to-map validation",
                $"Validate the RPG reward flow as its own step: victory leads to three reward choices, choosing one changes visible state, and the player returns to the map loop. {contractInstruction}",
                $"Pass only when reward 3-choice selection, state change, and return-to-map loop are all verified. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                6,
                "RPG Final Step: full playable prototype acceptance",
                $"Run the RPG type-skill final acceptance across the complete prototype: required RPG scenes, actual map/player/enemy asset usage in the current prototype scenes, main menu to prototype navigation, Start Adventure to visible map, battle entry, reward return-to-map, Godot build, prototype scene smoke, and package readiness. {contractInstruction}",
                $"Pass only when the full RPG playable prototype is accepted end-to-end: MapScene, BattleScene, reward return-to-map flow, actual Map/Player/Enemy asset usage in current scenes, main menu navigation, Start Adventure visible-map validation, Godot build, prototype scene smoke, package readiness, and all project-specific prototype contract fields pass.",
                "pending")
        ];
    }

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
        goals.Add(new PrototypeIterationPlanGoalResult(
            nextIndex,
            "Final Step: full playable prototype acceptance",
            $"Run the generic prototype final acceptance across the complete playable slice, using the available prototype skill contract and the project-specific prototype contract as checklist sources. {BuildContractGoalInstruction(prototypeContract)} Source request: {TrimForHint(message, 96)}",
            $"Pass only when the complete playable prototype passes platform acceptance: project build, default prototype scene smoke, main menu entry, package readiness, no pending or needs-fix iteration goals, and all project-specific prototype contract fields pass. {BuildContractGoalInstruction(prototypeContract)}",
            "pending"));
        return goals;
    }

    private static string BuildContractGoalInstruction(PrototypeContractSnapshot prototypeContract)
    {
        return string.IsNullOrWhiteSpace(prototypeContract.Json)
            ? "If the project prototype contract is missing, do not invent form values; mark the goal needs_fix until the contract is restored."
            : "Use the project prototype contract as hard acceptance input; user form values override type template defaults.";
    }

    private static bool IsFinalAcceptanceGoal(PrototypeIterationPlanGoalResult goal)
    {
        var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
        return text.Contains("final", StringComparison.Ordinal) &&
               (text.Contains("acceptance", StringComparison.Ordinal) ||
                text.Contains("full playable", StringComparison.Ordinal) ||
                text.Contains("全量", StringComparison.Ordinal) ||
                text.Contains("交付验收", StringComparison.Ordinal));
    }

    private static string? FindRpgPlanContractIssue(ProjectIterationGoalSnapshot[] goals)
    {
        var combined = string.Join("\n", goals.Select(goal => string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint))).ToLowerInvariant();
        var missing = new List<string>();

        if (!ContainsAny(combined, "asset", "assets", "material", "materials", "sprite", "sprites", "tileset", "ui", "hud", "素材", "美术", "界面"))
        {
            missing.Add("basic assets/UI validation step");
        }

        if (!ContainsAny(combined, "mapscene", "map scene", "mapscene.tscn", "地图场景") ||
            !ContainsAny(combined, "start adventure", "visible map", "visible-map", "opens a valid visible", "可见地图", "开始冒险"))
        {
            missing.Add("Start Adventure to visible MapScene step");
        }

        if (!ContainsAny(combined, "battlescene", "battle scene", "battlescene.tscn", "战斗场景"))
        {
            missing.Add("dedicated BattleScene step");
        }

        var hasMainScene = ContainsAny(combined, "main prototype", "main scene", "prototype scene", "主原型", "主场景");
        var hasSwitching = ContainsAny(combined, "scene switching", "scene switch", "switch into", "return path", "场景切换", "跳转");
        if (!hasMainScene || !hasSwitching)
        {
            missing.Add("main prototype scene and scene switching step");
        }

        if (!ContainsAny(combined, "reward", "3-choice", "three reward", "three choices", "return-to-map", "return to the map", "奖励", "三选一", "3 选 1", "返回地图"))
        {
            missing.Add("reward loop and return-to-map step");
        }

        if (!ContainsAny(combined, "final acceptance", "full playable prototype acceptance", "full playable", "package readiness", "交付验收", "全量验收", "最终验收") ||
            !ContainsAny(combined, "start adventure", "visible map", "visible-map", "可见地图", "开始冒险"))
        {
            missing.Add("final full playable acceptance step with Start Adventure visible-map validation");
        }

        if (missing.Count == 0)
        {
            return null;
        }

        return $"Missing RPG contract steps: {string.Join(", ", missing)}.";
    }

    private static string BuildRpgRegenerationPrompt(ProjectIterationSessionDetails details)
    {
        var sourceMessage = details.Session.SourceMessage?.Trim();
        if (string.IsNullOrWhiteSpace(sourceMessage))
        {
            sourceMessage = details.Session.OverallGoal?.Trim();
        }

        return string.IsNullOrWhiteSpace(sourceMessage)
            ? "Regenerate the RPG iteration plan as strict contract steps: basic assets/UI, Start Adventure to visible MapScene, BattleScene, main prototype scene switching, reward loop return-to-map, final full playable acceptance with Start Adventure visible-map validation."
            : $"Regenerate the RPG iteration plan as strict contract steps: basic assets/UI, Start Adventure to visible MapScene, BattleScene, main prototype scene switching, reward loop return-to-map, final full playable acceptance with Start Adventure visible-map validation. Source request: {sourceMessage}";
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.OrdinalIgnoreCase));
    }

    private static List<PrototypeIterationPlanGoalResult> TryBuildRefinedGoals(string message, string sourceKind)
    {
        if (!string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase))
        {
            return [];
        }

        var normalized = message.Trim();
        if (string.IsNullOrWhiteSpace(normalized))
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
        if (!looksLikeRpgClosure)
        {
            return [];
        }

        return
        [
            new PrototypeIterationPlanGoalResult(
                1,
                "目标 1：补稳地图移动与可见遇敌触发",
                "先让玩家能稳定移动，并且能清楚看到或明确触发第一次遇敌，不要把战斗、奖励和胜负提示一起塞进这一步。",
                "完成并验证：玩家能稳定移动，并能明确进入第一次遇敌。",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                2,
                "目标 2：补通单场战斗与基础结算",
                "在首次遇敌后完成一场可读、可结束的战斗，至少让玩家能看到战斗开始、行动结果和胜利结算，不要在这一步同时处理奖励理解问题。",
                "完成并验证：玩家能完整打完一场战斗，并看到明确的胜利结算。",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                3,
                "目标 3：补通奖励 3 选 1 并返回地图",
                "战斗胜利后展示奖励 3 选 1，并在选择后正确返回地图继续流程，重点保证奖励含义可理解、选择后状态变化可见。",
                "完成并验证：奖励 3 选 1 可理解、可选择，且选择后能正确返回地图。",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                4,
                "目标 4：补齐胜负目标提示与最小验证",
                "把“打赢 15 场胜利、任一战斗失败即失败”的规则做成玩家一眼能看懂的提示，并补一轮最小验证，确认首轮闭环与目标提示能一起工作。",
                "完成并验证：玩家能清楚理解胜负条件，且首轮闭环在提示存在时仍可正常工作。",
                "pending"),
        ];
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
        return $"目标 {index}：{TrimForHint(segment, 24)}";
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
            return $"请把这条原型优化建议重拆成 4 个更小、能单独执行的目标，不要把多个连续实现点塞进同一个目标里：{sourceMessage}";
        }

        if (!string.IsNullOrWhiteSpace(prototypeProgress?.CompletionSummary))
        {
            return "请根据当前 prototype completion report，把下一步优化拆成 4 个更小的目标：先补地图稳定移动和可见遇敌触发，再补完成一场战斗并正常结算，再补胜利后奖励 3 选 1 并返回地图，最后补胜负条件提示与验证。";
        }

        return "请把当前优化目标重拆成 4 个更小的连续目标，每个目标都要足够小，适合一次单独执行。";
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
             description.Contains("任一战斗失败即失败", StringComparison.Ordinal));
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
            "请根据当前 prototype completion report，把下一步优化拆成 4 个更小的目标：",
            "请把当前优化目标重拆成 4 个更小的连续目标，每个目标都要足够小，适合一次单独执行。"
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
}
