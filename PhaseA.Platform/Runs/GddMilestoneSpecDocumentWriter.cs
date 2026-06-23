using System.Text;
using System.Text.RegularExpressions;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public static class GddMilestoneSpecDocumentWriter
{
    private const string PrototypePlanRelativePath = "docs/prototype-v1-plan.md";

    public static async Task<IReadOnlyList<string>> WriteFromGddAsync(
        ProjectSnapshot project,
        string gddText,
        CancellationToken cancellationToken = default)
    {
        var steps = ExtractSteps(gddText);
        if (steps.Count == 0)
        {
            steps = BuildDefaultSteps(gddText);
        }

        if (steps.Count == 0)
        {
            steps.Add(new SpecStep("M1", 1, "M1：首个可玩闭环", "根据当前 GDD 创建第一个可打包、可验证的最小可玩闭环。"));
        }

        return await WriteStepsAsync(project, steps, gddText, cancellationToken);
    }

    public static Task<IReadOnlyList<string>> WriteFromMilestoneStateAsync(
        ProjectSnapshot project,
        IReadOnlyList<GddMilestoneStepResult> steps,
        string gddText,
        CancellationToken cancellationToken = default)
    {
        var specSteps = steps
            .OrderBy(step => step.StepIndex <= 0 ? int.MaxValue : step.StepIndex)
            .Select(step => new SpecStep(
                NormalizeStepId(step.StepId),
                step.StepIndex,
                string.IsNullOrWhiteSpace(step.Title) ? step.StepId : step.Title,
                FirstNonEmpty(step.Description, step.Title, step.StepId),
                string.IsNullOrWhiteSpace(step.ScopeIn) ? null : step.ScopeIn,
                string.IsNullOrWhiteSpace(step.ScopeOut) ? null : step.ScopeOut,
                string.IsNullOrWhiteSpace(step.GodotSlice) ? null : step.GodotSlice,
                string.IsNullOrWhiteSpace(step.Acceptance) ? null : step.Acceptance,
                string.IsNullOrWhiteSpace(step.PackagingValidation) ? null : step.PackagingValidation))
            .ToList();

        return WriteStepsAsync(project, specSteps, gddText, cancellationToken);
    }

    private static async Task<IReadOnlyList<string>> WriteStepsAsync(
        ProjectSnapshot project,
        IReadOnlyList<SpecStep> steps,
        string gddText,
        CancellationToken cancellationToken)
    {
        var written = new List<string>();
        var physicsPolicy = PrototypePhysicsRequirementPolicy.Evaluate(project, gddText);
        var planPath = Path.Combine(project.RepoPath, PrototypePlanRelativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(planPath)!);
        await File.WriteAllTextAsync(planPath, BuildPlan(project, steps, physicsPolicy), Encoding.UTF8, cancellationToken);
        written.Add(PrototypePlanRelativePath);

        foreach (var step in steps)
        {
            var spec = BuildSpec(step, physicsPolicy);
            var relativePath = StepSpecRelativePath(step);
            var path = Path.Combine(project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            await File.WriteAllTextAsync(path, BuildStepMarkdown(project, step, spec, physicsPolicy), Encoding.UTF8, cancellationToken);
            written.Add(relativePath);
        }

        return written;
    }

    private static List<SpecStep> ExtractSteps(string gddText)
    {
        var result = new List<SpecStep>();
        var matches = Regex.Matches(
            gddText,
            @"(?im)^\s*(?:[-*]\s*)?(M\d+(?:[-.]\d+)?)\s*[:：\-]\s*(.+)$");
        foreach (Match match in matches)
        {
            var id = NormalizeStepId(match.Groups[1].Value);
            var titleBody = Compact(match.Groups[2].Value);
            if (string.IsNullOrWhiteSpace(titleBody))
            {
                continue;
            }

            result.Add(new SpecStep(id, result.Count + 1, $"{id}：{Trim(titleBody, 80)}", Trim(titleBody, 420)));
        }

        return result
            .GroupBy(step => step.StepId, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .Take(20)
            .ToList();
    }

    private static List<SpecStep> BuildDefaultSteps(string gddText)
    {
        var text = Compact(gddText);
        var hasControls = ContainsAny(text, "键盘", "鼠标", "WASD", "Controls", "Input");
        var hasScene = ContainsAny(text, "场景", "关卡", "地图", "地城", "Scene", "Room", "Level");
        var hasProgression = ContainsAny(text, "升级", "成长", "奖励", "Progression", "Upgrade", "Reward");
        var hasPolish = ContainsAny(text, "素材", "动画", "音效", "VFX", "Asset", "Animation", "Polish");

        var steps = new List<SpecStep>
        {
            DefaultStep("M1", 1, "首个可玩场景与基础操作", hasScene || hasControls
                ? "创建首个可玩场景，接入 GDD 要求的键盘鼠标基础操作和可见反馈。"
                : "创建首个可玩场景，并提供基础操作入口和可见反馈。"),
            DefaultStep("M2", 2, "核心玩法闭环", "实现 GDD 中最小核心玩法循环，让玩家能完成一次明确的开始、操作、反馈、结果闭环。"),
            DefaultStep("M3", 3, "主要交互与能力扩展", "补齐 GDD 中玩家最常使用的第二层交互、技能、道具、卡牌或操作变体，并提供冷却、消耗或状态反馈。"),
            DefaultStep("M4", 4, "关卡流程与目标推进", "实现关卡、房间、波次、遭遇、回合或流程推进，让玩家能从入口推进到明确目标。"),
            DefaultStep("M5", 5, "敌人、障碍或挑战变化", "加入至少一种新的挑战变化，并验证它与核心操作、失败条件和反馈表现协同工作。")
        };

        steps.Add(hasProgression
            ? DefaultStep("M6", 6, "奖励与成长反馈", "实现奖励、升级、永久成长或其他 GDD 指定的进度反馈。")
            : DefaultStep("M6", 6, "结果结算与重开循环", "实现胜负、结算、重开或继续游玩的结果反馈，让一次试玩有清晰收束。"));
        steps.Add(DefaultStep("M7", 7, "HUD 与关键 UI 状态", "补齐核心屏幕、HUD 信息优先级、输入提示、关键状态、本地化入口和基础 accessibility 表现。"));
        steps.Add(DefaultStep("M8", 8, "反馈表现与手感调整", "补齐命中、受击、交互、奖励、失败、转场等关键反馈，可先使用 placeholder 但保持命名和状态稳定。"));
        steps.Add(DefaultStep("M9", 9, hasPolish ? "素材替换与碰撞验证" : "占位素材整理与碰撞验证", "替换或整理关键占位素材，并验证碰撞、阻挡、移动边界、命中、场景加载和基础交互 smoke。"));
        steps.Add(DefaultStep("M10", 10, "原型可玩性验证与打包", "补齐首轮可玩验证、打包下载提示、截图或 smoke 证据，以及下一轮游戏模块创建准备。"));
        return steps;
    }

    private static SpecStep DefaultStep(string id, int index, string title, string description)
        => new(id, index, $"{id}：{title}", description);

    private static StepSpec BuildSpec(SpecStep step, PrototypePhysicsRequirementResult physicsPolicy)
    {
        var body = Trim(step.Description, 420);
        var combined = $"{step.Title} {step.Description}";
        var isAssetStep = ContainsAny(combined, "素材", "资产", "Asset", "KayKit", "碰撞", "collision", "Animation", "动画");
        var isUiStep = ContainsAny(combined, "UI", "HUD", "界面", "反馈", "screen", "本地化", "accessibility");
        var isFinalStep = ContainsAny(combined, "验收", "打包", "readiness", "polish", "final", "summary");
        var isFirstStep = string.Equals(step.StepId, "M1", StringComparison.OrdinalIgnoreCase);

        var scopeIn = $"只实现 {step.StepId} 当前模块所需的可玩功能：{body} 保持 scene path、screen id、input action、state name 稳定。";
        var scopeOut = "不提前实现后续锁定模块；不做最终视觉精装修；不引入 GDD 之外的新核心系统。";
        var godotSlice = "在 Godot 4.5.1 + C# 项目中完成可运行切片，覆盖场景、组件、输入、HUD/状态反馈和最小 smoke 验证。";
        var acceptance = $"完成并验证：{body} 玩家能通过打包版本直接试玩当前模块，看到明确开始、操作、反馈和结果。";
        var packaging = "当前模块完成后提示玩家打包下载并试玩验证；确认按钮只在当前模块执行完成或反馈修复完成后可用。";

        scopeIn = FirstNonEmpty(step.ScopeInOverride, scopeIn);
        scopeOut = FirstNonEmpty(step.ScopeOutOverride, scopeOut);
        godotSlice = FirstNonEmpty(step.GodotSliceOverride, godotSlice);
        acceptance = FirstNonEmpty(step.AcceptanceOverride, acceptance);
        packaging = FirstNonEmpty(step.PackagingValidationOverride, packaging);

        if (isFirstStep)
        {
            scopeIn += " M1 同时承担原型骨架创建，必须落地首个可进入场景、基础操作映射和首轮手感验证。";
            acceptance += " 原型骨架不能是空壳，必须能让玩家实际操作并判断基本手感。";
        }

        if (physicsPolicy.RequiresPhysics)
        {
            scopeIn += " 词库判定本项目需要物理表达，玩家移动、碰撞、命中、受击、追踪、阻挡或房间穿行不能只用 UI 文本或状态机模拟。";
            godotSlice += $" 物理要求：{physicsPolicy.NodeContract}";
            acceptance += $" 必须使用匹配维度的 Godot 物理节点和碰撞形状；推荐：{physicsPolicy.RecommendedEngine}。";
        }

        if (isAssetStep)
        {
            scopeIn += " 素材替换必须同时验证阻挡、碰撞、导航/移动边界、动画或朝向状态，以及场景加载 smoke。";
            godotSlice += " 对替换后的角色、敌人、道具或阻挡物补充碰撞层、碰撞形状和最小运行检查。";
            acceptance += " 替换素材不能让玩家穿模、卡死、无法命中或无法完成当前房间目标。";
        }

        if (isUiStep)
        {
            scopeIn += " UI 可用 placeholder，但 HUD 信息优先级、输入提示、冷却/生命/目标状态和文本来源必须稳定。";
            godotSlice += " UI screen contract 至少记录 screen id、scene path、关键状态和输入动作。";
            acceptance += " HUD 不遮挡核心读图，关键状态不能只依赖颜色表达。";
        }

        if (isFinalStep)
        {
            acceptance += " 最后一轮还要覆盖核心循环回归、项目包生成、下载验证和下一轮游戏模块创建准备。";
        }

        return new StepSpec(scopeIn, scopeOut, godotSlice, acceptance, packaging);
    }

    private static string BuildPlan(ProjectSnapshot project, IReadOnlyList<SpecStep> steps, PrototypePhysicsRequirementResult physicsPolicy)
    {
        var rows = string.Join("\n", steps.Select(step => $"- {step.StepId}: {step.Title} ({StepSpecRelativePath(step)})"));
        var physicsBlock = physicsPolicy.RequiresPhysics
            ? $"""
                - Physics is required by project/reference/GDD vocabulary. Dimension: {physicsPolicy.Dimension}; recommended engine: {physicsPolicy.RecommendedEngine}.
                - Runtime milestones must use scene objects and matching Godot physics nodes for movement, collision, hit detection, traversal, and enemy pressure when present.
                """
            : "- Physics is not forced by the current vocabulary, but any milestone adding movement/collision/hit detection must re-evaluate and use matching Godot physics nodes.";
        return $"""
            # Prototype V1 Plan

            Source: docs/gdd/GDD.md

            This plan is generated from the current GDD. The listed modules are the first playable prototype route, not a final production roadmap.

            ## Project

            - Game: {project.GameName}
            - Type Source: {project.GameTypeSource}

            ## Development Rules

            - Each module must produce a playable Godot/C# slice before the next module is unlocked.
            - M1 is the first playable skeleton: it should materialize the basic scene, controls, and first feel test instead of creating an empty shell.
            - Keep implementation scoped to the current module spec.
            - Placeholder visuals are allowed when they preserve playability and do not replace player-operated scene behavior.
            - Player package validation is recommended after each module; it is not a hard gate for confirmation.
            {physicsBlock}

            ## Modules

            {rows}
            """;
    }

    private static string BuildStepMarkdown(ProjectSnapshot project, SpecStep step, StepSpec spec, PrototypePhysicsRequirementResult physicsPolicy)
    {
        var physicsNotes = physicsPolicy.RequiresPhysics
            ? $"""
                - Physics required: yes
                - Dimension: {physicsPolicy.Dimension}
                - Recommended engine: {physicsPolicy.RecommendedEngine}
                - Matched terms: {string.Join(", ", physicsPolicy.MatchedTerms)}
                - Node contract: {physicsPolicy.NodeContract}
                """
            : "- Physics required: no forced requirement yet; re-evaluate if this module adds movement, collision, hit detection, traversal, or enemy pressure.";
        return $"""
            # {step.Title}

            Source:
            - GDD: docs/gdd/GDD.md
            - Prototype plan: docs/prototype-v1-plan.md

            ## Goal

            {step.Description}

            ## Scope In

            {spec.ScopeIn}

            ## Scope Out

            {spec.ScopeOut}

            ## Godot Slice

            {spec.GodotSlice}

            ## Acceptance

            {spec.Acceptance}

            ## Player Validation

            {spec.PackagingValidation}

            ## Implementation Notes

            - Project: {project.GameName}
            - Game type source: {project.GameTypeSource}
            - Execute this module as one playable milestone.
            - Do not implement later locked modules while completing this spec.
            {physicsNotes}
            """;
    }

    public static string StepSpecRelativePath(string stepId, string title)
        => StepSpecRelativePath(new SpecStep(stepId, 0, title, ""));

    private static string StepSpecRelativePath(SpecStep step)
    {
        var slug = Regex.Replace(step.Title, @"^[Mm]\d+(?:[-.]\d+)?\s*[:：\-]?\s*", "");
        slug = Regex.Replace(slug.ToLowerInvariant(), @"[^a-z0-9\u4e00-\u9fff]+", "-").Trim('-');
        if (string.IsNullOrWhiteSpace(slug))
        {
            slug = "module";
        }

        return $"docs/{step.StepId.ToLowerInvariant()}-{slug}-spec.md";
    }

    private static bool ContainsAny(string value, params string[] needles)
        => needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));

    private static string NormalizeStepId(string value)
        => value.Trim().ToUpperInvariant().Replace('.', '-');

    private static string Compact(string? value)
        => string.IsNullOrWhiteSpace(value) ? "" : Regex.Replace(value.Trim(), @"\s+", " ");

    private static string FirstNonEmpty(params string?[] values)
        => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value))?.Trim() ?? "";

    private static string Trim(string value, int maxLength)
    {
        var compact = Compact(value);
        return compact.Length <= maxLength ? compact : compact[..maxLength].TrimEnd() + "...";
    }

    private sealed record SpecStep(
        string StepId,
        int StepIndex,
        string Title,
        string Description,
        string? ScopeInOverride = null,
        string? ScopeOutOverride = null,
        string? GodotSliceOverride = null,
        string? AcceptanceOverride = null,
        string? PackagingValidationOverride = null);

    private sealed record StepSpec(
        string ScopeIn,
        string ScopeOut,
        string GodotSlice,
        string Acceptance,
        string PackagingValidation);
}
