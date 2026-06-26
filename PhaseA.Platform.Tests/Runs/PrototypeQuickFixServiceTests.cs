using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;
using System.Text.Json;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeQuickFixServiceTests : IDisposable
{
    private readonly IDisposable routeProfileOverride = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(false);

    public void Dispose()
    {
        routeProfileOverride.Dispose();
    }

    [Fact]
    public void GoalRepairCompletionEvidence_ShouldAcceptStrongStructuredVerification()
    {
        var output = """
STATUS: completed
SUMMARY: Current step is repaired through structured status.
CHANGED: Step repair completed.
VERIFY: Godot gameplay verification passed for map movement and first encounter trigger.
REMAINING: none
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeTrue();
    }

    [Fact]
    public void GoalRepairCompletionEvidence_ShouldAcceptStaticConfirmedPrototypeEvidence()
    {
        var output = """
STATUS: completed
SUMMARY: Current step is repaired.
CHANGED: Removed stale import metadata and external texture dependency.
VERIFY: Static confirmation found the prototype scene no longer contains the failed image resource references.
REMAINING: none
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeTrue();
    }

    [Fact]
    public void GoalRepairCompletionEvidence_ShouldAcceptStaticCheckedPrototypeEvidence()
    {
        var output = """
STATUS: completed
SUMMARY: Current step is repaired.
CHANGED: The prototype no longer references failed image resources.
VERIFY: 已静态核对项目说明、原型契约、失败资源信号、原型场景和原型脚本引用；按限制未运行构建或 Godot 验证，等待平台隔离复验。
REMAINING: none
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeTrue();
    }

    [Fact]
    public void GoalRepairCompletionEvidence_ShouldAcceptStaticResourceRepairWithDeferredEngineValidation()
    {
        var output = """
STATUS: completed

SUMMARY: 当前目标已完成。最新失败中点名的 3 个图片资源现在都存在且是有效图片，原型场景也不再引用缺失资源，因此主菜单进入原型时不应再触发资源加载失败。

CHANGED:
- 本轮未做额外文件改动；确认上一轮修复已落到当前工作区。
- 确认原型契约可用于当前目标验收。

VERIFY:
- 已静态确认场景文件首字符符合 Godot 文本场景格式。
- 已静态确认 3 个失败资源均为有效图片，且旧的缺失引用已消除。
- 按本轮限制未运行引擎验证，等待平台隔离复验。

REMAINING: none
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeTrue();
    }

    [Fact]
    public void GoalRepairCompletionEvidence_ShouldAcceptPlayableLoopDeferredVerification()
    {
        var output = """
STATUS: completed

SUMMARY: 当前 step 2 已补强为“制作完成后仍可继续当前制作循环”：玩家采购后能制作，画面会显示原料扣减、待命名汉堡增加、制作完成反馈，并提示可继续采购后再次制作。没有加入命名、定价或销售入口。

CHANGED: 制作完成后的目标与阶段反馈改为明确提示“继续采购并再次制作”。
CHANGED: 制作按钮逻辑保持有原料时可用、无原料时禁用，并补充场景测试断言再次采购后可继续制作。

VERIFY: 进入游戏后点击“采购原料”，再点击“开始制作”，应看到基础原料变为 0/3、待命名汉堡变为 1。
VERIFY: 再次点击“采购原料”后，“开始制作”应重新可用，且仍不出现销售相关入口。
VERIFY: 按要求未运行本地 dotnet 或 Godot 验证，等待平台隔离验收。

REMAINING: none
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeTrue();
    }

    [Fact]
    public void GoalRepairOutcome_ShouldAcceptAssistantMessageWhenCodexOutputHasToolNoise()
    {
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            2,
            "目标 2：补通制作反馈",
            "在前一步“采购”已经成立的基础上，只补通“制作”及其必要状态变化和可见反馈。不要同时处理后续“销售”。",
            "完成并验证：玩家能制作，且反馈和状态变化清楚可见。",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
        var output = """
STATUS: completed

SUMMARY: 当前 step 2 已补强为“制作完成后仍可继续当前制作循环”：玩家采购后能制作，画面会显示原料扣减、待命名汉堡增加、制作完成反馈，并提示可继续采购后再次制作。没有加入命名、定价或销售入口。

CHANGED: 制作完成后的目标与阶段反馈改为明确提示“继续采购并再次制作”。
CHANGED: 制作按钮逻辑保持有原料时可用、无原料时禁用，并补充场景测试断言再次采购后可继续制作。

VERIFY: 进入游戏后点击“采购原料”，再点击“开始制作”，应看到基础原料变为 0/3、待命名汉堡变为 1。
VERIFY: 再次点击“采购原料”后，“开始制作”应重新可用，且仍不出现销售相关入口。
VERIFY: 按要求未运行本地 dotnet 或 Godot 验证，等待平台隔离验收。

REMAINING: none
""";

        var status = PrototypeQuickFixService.DetermineGoalRepairOutcomeStatusForTesting(
            goal,
            output,
            "Reading route files and command event stream.",
            "Get-ChildItem : path Game.Godot/Prototypes/dq-rpg not found while probing an unrelated old route.");

        status.Should().Be("succeeded");
    }

    [Fact]
    public void GoalRepairCompletionEvidence_ShouldRejectMissingGameplayVerification()
    {
        var output = """
STATUS: completed
SUMMARY: Platform route tests passed, but gameplay acceptance is not verified.
CHANGED: Route recovery behavior was adjusted.
VERIFY: Platform tests passed.
REMAINING: none

还没有做的是 Godot 侧对地图移动稳定、明确进入第一次遇敌的业务验收。
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeFalse();
    }

    [Fact]
    public void GoalRepairOffTopicEvidence_ShouldIgnoreHostedPrototypeScriptReferences()
    {
        PrototypeQuickFixService.HasGoalRepairOffTopicEvidenceForTesting(
            "VERIFY: 已静态核对原型场景和原型脚本引用，且不再包含失败图片引用。").Should().BeFalse();

        PrototypeQuickFixService.HasGoalRepairOffTopicEvidenceForTesting(
            "CHANGED: updated platform startup script and deployment config.").Should().BeTrue();
    }

    [Fact]
    public void ExtractGdUnitPromptSummaryForTesting_ShouldCaptureDynamicPrototypeSuiteFailureDetails()
    {
        var lines = PrototypeQuickFixService.ExtractGdUnitPromptSummaryForTesting(
            """
            res://tests/Prototype/TowerdemoPrototype/test_towerdemo.gd:42 - FAILED:
            'Current map state'
            but is 'Missing map state'
            Statistics: 1 failed
            """,
            10);

        lines.Should().Contain(line => line.Contains("TowerdemoPrototype", StringComparison.Ordinal));
        lines.Should().Contain("'Current map state'");
        lines.Should().Contain("but is 'Missing map state'");
    }

    [Fact]
    public void GoalRepairOutcome_ShouldIgnoreToolLogOffTopicNoise_WhenStructuredOutputIsCompleted()
    {
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            1,
            "恢复原型运行证据",
            "Restore prototype run evidence.",
            "The latest failure reason is eliminated.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
        var output = """
STATUS: completed
SUMMARY: 当前目标已完成。
CHANGED: 确认原型资源可用。
VERIFY: 已静态确认 3 个失败资源均为有效图片，且旧的缺失引用已消除。
REMAINING: none
""";

        var status = PrototypeQuickFixService.DetermineGoalRepairOutcomeStatusForTesting(
            goal,
            output,
            "Reading .agents/skills/prototype-7day-playable-godot-zh/SKILL.md",
            "Tool log mentions docs/workflows while reading route instructions.");

        status.Should().Be("succeeded");
    }

    [Fact]
    public void GoalRepairOutcome_ShouldAcceptLatestStaticResourceRepairOutput()
    {
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            1,
            "恢复原型运行证据",
            "Restore prototype run evidence.",
            "The latest failure reason is eliminated and the prototype route can produce completion evidence without build, cache, or write failures.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
        var output = """
STATUS: completed

SUMMARY: 当前目标已完成。最新失败点名的资源加载问题已消除：原型场景不再引用缺失图片，3 个所需图片资源也都存在且是有效图片，因此主菜单进入原型时不应再因这些资源失败而中断。

CHANGED:
- 本轮未做额外文件改动；确认上一轮资源修复已经落到当前工作区。
- 确认原型契约可读，且当前目标验收项与现状一致。

VERIFY:
- 已静态确认原型场景首字符符合 Godot 文本场景格式。
- 已静态确认 3 个失败图片资源均存在且为有效 PNG。
- 按本轮限制未运行引擎验证，等待平台隔离复验。

REMAINING: none
""";

        var status = PrototypeQuickFixService.DetermineGoalRepairOutcomeStatusForTesting(
            goal,
            output,
            "Reading route skill docs/workflows/prototype-lane.md",
            "Tool output contains route documentation and command logs.");

        status.Should().Be("succeeded");
    }

    [Fact]
    public void GoalRepairOutcome_ShouldAcceptRpgStaticRepairOutputWithHistoricalFailureText()
    {
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            1,
            "修复 RPG 原型资源加载失败",
            "Repair the RPG prototype resource loading failure.",
            "The dq-rpg prototype scene no longer references missing PNG resources and can continue through the RPG route.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
        var output = """
STATUS: completed

SUMMARY: RPG 修复目标已完成。最新失败点名的 dq-rpg 资源加载问题已消除，地图和战斗场景不再引用缺失 PNG。

CHANGED:
- 本轮未做额外文件改动；确认上一轮 RPG 资源修复已经落到当前工作区。
- 确认 prototype-rpg-godot-zh 路由契约可读，且当前目标验收项与现状一致。

VERIFY:
- 已静态确认 Game.Godot/Prototypes/dq-rpg/MapScene.tscn 和 BattleScene.tscn 可读。
- 已静态确认失败资源均存在且为有效 PNG，旧的缺失引用已消除。
- 按本轮限制未运行 Godot 引擎验证，等待平台隔离复验。

REMAINING: none
""";

        var status = PrototypeQuickFixService.DetermineGoalRepairOutcomeStatusForTesting(
            goal,
            output,
            "Reading .agents/skills/prototype-rpg-godot-zh/SKILL.md",
            "Tool output contains route documentation and command logs.");

        status.Should().Be("succeeded");
    }

    [Fact]
    public void GoalRepairOutcome_ShouldAcceptStaticInspectionOutputWithDeferredGodotValidation()
    {
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            2,
            "修复通用原型合同缺口",
            "Repair the current prototype against the default prototype route skill and project prototype contract.",
            "The default prototype route skill and project prototype contract are reflected in the repaired output, with no new prototype drift.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
        var output = """
STATUS: completed

SUMMARY: 当前 step 已完成。奖励闭环现在明确满足：胜利后有 3 个奖励，选择奖励后状态变化可见，并提示玩家返回地图继续刷怪、变强和挑战 Boss。

CHANGED: 修正奖励领取后的状态反馈文案，使其明确表达“返回地图”。
CHANGED: 保持原型合同已有的战士、三类小怪、Boss、掉落、金币、升级、背包装备、技能解锁和药水冷却表现不漂移。

VERIFY: 已做静态检查：场景开头有效，不再引用缺失图片资源，奖励按钮为 3 个，奖励后返回地图文案存在。
VERIFY: 未运行本地 Godot、构建或测试；按要求等待平台隔离验收。

REMAINING: none
""";

        var status = PrototypeQuickFixService.DetermineGoalRepairOutcomeStatusForTesting(
            goal,
            output,
            "Reading .agents/skills/prototype-7day-playable-godot-zh/SKILL.md",
            "Tool output contains route documentation and command logs.");

        status.Should().Be("succeeded");
    }

    [Fact]
    public async Task SubmitAsync_CreatesQuickFixRun_AndArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        WritePrototypeSmokeState(project);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.AssistantMessage.Should().Contain("快速修复已完成");
        run!.RunType.Should().Be("prototype-quick-fix");
        run.Status.Should().Be("completed");
        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.Arguments.Should().Contain(["exec", "--sandbox", "workspace-write", "-m", "gpt-5.4"]);
        codexCommand.Arguments.Should().Contain(["-c", "model_reasoning_effort=\"low\""]);
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "smoke_headless.py"));
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"));
        artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-quick-fix-submission",
            "prototype-quick-fix-result-log",
            "prototype-quick-fix-codex-output"
        ]);
    }

    [Fact]
    public async Task SubmitAsync_RejectsProjectOwnedByAnotherAccount()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var ownerAccountId = await store.EnsureSingleAdminAsync();
        var otherAccount = await store.CreateUserAccountAsync("quick-fix-other-account", 1);
        var projectId = await CreateProjectAsync(store, options, ownerAccountId, prototypeSucceeded: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var act = () => service.SubmitAsync(
            otherAccount.AccountId,
            projectId,
            new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Project not found.");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task SubmitAsync_NonGoalRpgQuickFix_ShouldFailRun_WhenPostFixPrototypeSmokeFails()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var runner = new QuickFixNavigationFailHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("修复 Start Adventure 后空白。", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.AssistantMessage.Should().Contain("STATUS: needs_fix");
        run!.Status.Should().Be("failed");
        run.ProgressStep.Should().Be("failed");
        run.ProgressSubstep.Should().Be("validation");
        run.EvidenceJson.Should().Contain("project_smoke_validation");
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "smoke_headless.py"));
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"));
    }

    [Fact]
    public async Task SubmitAsync_NonGoalRpgQuickFix_ShouldFailRun_WhenPostFixSmokeSceneIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "勇者斗恶龙");
        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/MissingPrototype.tscn"
            }
        });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.AssistantMessage.Should().Contain("STATUS: needs_fix");
        run!.Status.Should().Be("failed");
        run.EvidenceJson.Should().Contain("\"required\":true");
        run.EvidenceJson.Should().Contain("prototype_smoke_scene_missing");
        runner.Commands.Should().NotContain(command => HasScriptArgument(command, "smoke_headless.py"));
    }

    [Fact]
    public async Task SubmitAsync_NonGoalRpgQuickFix_ShouldSkipHostMainSceneAndUsePrototypeEvidence()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        File.WriteAllText(Path.Combine(project.RepoPath, "project.godot"), """
        [application]
        run/main_scene="res://Game.Godot/Scenes/Main.tscn"
        """);
        const string prototypeScene = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn";
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = prototypeScene
            }
        });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        runner.Commands.Should().Contain(command =>
            HasScriptArgument(command, "smoke_headless.py") &&
            command.Arguments.Contains(prototypeScene));
        run!.EvidenceJson.Should().Contain(prototypeScene);
        run.EvidenceJson.Should().NotContain("res://Game.Godot/Scenes/Main.tscn");
    }

    [Fact]
    public async Task SubmitAsync_NonGoalRpgQuickFix_ShouldUseLatestSucceededPrototypeRunBeforeStaleRouteState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        const string succeededScene = "res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn";
        File.WriteAllText(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgUiOptimized.tscn"), "[gd_scene format=3]\n\n[node name=\"Optimized\" type=\"Node\"]\n");
        var succeededRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(succeededRunId, "succeeded", 0, "", "", $$"""
        {
          "prototype_completion": {
            "smoke_scene": "{{succeededScene}}"
          }
        }
        """);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/MissingPrototype.tscn"
            }
        });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        runner.Commands.Should().Contain(command =>
            HasScriptArgument(command, "smoke_headless.py") &&
            command.Arguments.Contains(succeededScene));
        run!.EvidenceJson.Should().Contain(succeededScene);
        run.EvidenceJson.Should().NotContain("MissingPrototype.tscn");
    }

    [Fact]
    public async Task SubmitAsync_ReturnsTimeoutFailure_WhenRunnerDoesNotFinishInTime()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var runner = new TimeoutHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.AssistantMessage.Should().Contain("快速修复超时");
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPromoteGoal_WhenTimedOutRepairAlreadyPassesValidation()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke failed.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new TimedOutValidatedGoalRepairRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke failure.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("succeeded");
        run!.Status.Should().Be("completed");
        run.ExitCode.Should().Be(0);
        run.EvidenceJson.Should().Contain("prototype_quick_fix_timeout_validated_after_cancel");
        runner.Commands.Should().Contain(command => command.Arguments.Contains("exec"));
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"));
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPersistGodotFailure_WhenTimedOutRepairStillFailsSmoke()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        new PrototypeRouteStateWriter().WriteNeedsFixState(project, targetGoal.GoalIndex, new
        {
            route = "needs-fix",
            session_id = details.Session.SessionId,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            gdunit_path = "tests/Prototype/CustomSuite"
        });
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke failed.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new TimedOutSmokeFailingGoalRepairRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke failure.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("failed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("prototype_main_menu_navigation_failed");
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("needs_fix");
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
        run.EvidenceJson.Should().Contain("prototype_quick_fix_timeout_validation_failed_after_cancel");
        run.EvidenceJson.Should().Contain("\"acceptance_validation_status\":\"passed\"");
        run.EvidenceJson.Should().Contain("\"post_acceptance_validation_status\":\"failed\"");
        run.EvidenceJson.Should().Contain("prototype_main_menu_navigation_failed");
        var runMemory = await store.GetProjectRunMemoryAsync(projectId, "goal-repair-step-1");
        runMemory!.AllowedScopeJson.Should().Contain("Tests.Godot/tests/Prototype/CustomSuite");
        runner.Commands.Should().Contain(command => command.Arguments.Contains("exec"));
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"));
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPromoteStepOne_WhenRpgGdUnitHasOnlyBehaviorAssertionFailures()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var details = await CreateRpgGdUnitRepairSessionAsync(store, accountId, projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "GdUnit asset/import step needs repair.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new GoalRepairStepOneBehaviorGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        run!.EvidenceJson.Should().Contain("\"rpg_gdunit_validation\"");
        run.EvidenceJson.Should().Contain("\"passed\":false");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepOneNeedsFix_WhenRpgGdUnitHasInfrastructureFailures()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var details = await CreateRpgGdUnitRepairSessionAsync(store, accountId, projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "GdUnit asset/import step needs repair.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new GoalRepairStepOneInfrastructureGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("RPG GdUnit validation");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepNeedsFix_WhenPrototypeTestsShadowXunit()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var pollutedTestPath = Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs");
        File.AppendAllText(pollutedTestPath, """

namespace Xunit
{
    public sealed class FactAttribute : System.Attribute { }
    public static class Assert { }
}
""");
        var details = await CreateRpgGdUnitRepairSessionAsync(store, accountId, projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "GdUnit asset/import step needs repair.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new GoalRepairStepOneBehaviorGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("Platform mutation guard");
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("\"mutation_guard\"");
        run.EvidenceJson.Should().Contain("test_framework_shadowing_detected");
        run.EvidenceJson.Should().Contain("namespace_xunit");
        run.EvidenceJson.Should().Contain("xunit_assert_shadow");
    }

    [Fact]
    public async Task SubmitAsync_ShouldCompleteEvenWhenCallerTokenIsCanceledAfterRunStarts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        WritePrototypeSmokeState(project);
        using var callerCancellation = new CancellationTokenSource();
        var runner = new CancelCallerThenReturnHostedProcessRunner(callerCancellation);
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(
            accountId,
            projectId,
            new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"),
            callerCancellation.Token);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        run!.Status.Should().Be("completed");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPromoteNeedsFixGoal_WhenCurrentGoalBecomesReady()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"目标 {targetGoal.GoalIndex} 需要修复。");
        var runner = new GoalRepairSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("succeeded");
        refreshed.Session.Status.Should().Be("paused_for_review");
        var planningAnalysis = ReadPlanningAnalysis(project!.MetaPath);
        var loopFields = planningAnalysis.GetProperty("fieldCoverage").EnumerateArray().ToArray();
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "minimum_playable_loop" &&
            field.GetProperty("status").GetString() == "completed");
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "core_gameplay_loop" &&
            field.GetProperty("status").GetString() == "completed");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldContinueToCodex_WhenPreflightGodotSmokeFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke failed.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new QuickFixNavigationFailHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke failure.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "smoke_headless.py"));
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"));
        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.StandardInput.Should().Contain("Latest Godot smoke validation failed after platform static acceptance");
        codexCommand.StandardInput.Should().Contain("prototype_main_menu_navigation_failed");
        codexCommand.StandardInput.Should().Contain("rpg_map_visible_markers_missing_after_start");
        run!.EvidenceJson.Should().NotContain("\"preflight\":true");
        run.EvidenceJson.Should().Contain("\"godot_smoke_validation\"");
        run.EvidenceJson.Should().Contain("diagnostic_excerpt");
        run.EvidenceJson.Should().Contain("rpg_map_visible_markers_missing_after_start");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldContinueToCodex_WhenPreflightGodotSmokeSceneIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair missing smoke scene validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot smoke scene missing.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new QuickFixMissingSmokeSceneHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current missing Godot smoke scene.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "exec", StringComparison.Ordinal)));
        runner.Commands.Should().NotContain(command => HasScriptArgument(command, "smoke_headless.py"));
        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.StandardInput.Should().Contain("Latest Godot smoke validation failed after platform static acceptance");
        codexCommand.StandardInput.Should().Contain("prototype_smoke_scene_missing");
        run!.EvidenceJson.Should().NotContain("\"preflight\":true");
        run.EvidenceJson.Should().Contain("prototype_smoke_scene_missing");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldDiscoverProjectSlugSmokeScene_WhenPrototypeStateSceneIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo2", "Towerdemo2Prototype.tscn");
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            slug = "Towerdemo2",
            prototype_completion = new
            {
                succeeded = false,
                error = "prototype_completion_state_missing",
                smoke_scene = (string?)null
            },
            godot_smoke = new
            {
                ran = false,
                reason = "prototype_completion_validation_failed",
                scene = (string?)null
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair Towerdemo2 module smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot smoke scene missing.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new QuickFixNavigationFailHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current missing Godot smoke scene.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "smoke_headless.py"));
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"));
        runner.Commands.Should().Contain(command => command.Arguments.Contains("res://Game.Godot/Prototypes/Towerdemo2/Towerdemo2Prototype.tscn"));
        run!.EvidenceJson.Should().Contain("prototype_main_menu_navigation_failed");
        run.EvidenceJson.Should().NotContain("prototype_smoke_scene_missing");
    }

    [Fact]
    public void ResolveSmokeScene_ShouldIgnoreDiscoveredScene_WhenSceneDoesNotStartWithGdSceneHeader()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var prototypeDir = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "Towerdemo3");
        Directory.CreateDirectory(prototypeDir);
        File.WriteAllText(Path.Combine(prototypeDir, "Towerdemo3Prototype.tscn"), "[resource]\n");
        File.WriteAllText(Path.Combine(prototypeDir, "Main.tscn"), "\n[gd_scene format=3]\n");
        File.WriteAllText(Path.Combine(prototypeDir, "CleanFallback.tscn"), """
[gd_scene format=3]
[node name="Prototype" type="Node"]
""");
        const string prototypeState = """
{
  "route": "prototype-7day-playable",
  "slug": "Towerdemo3",
  "prototype_completion": { "smoke_scene": null },
  "godot_smoke": { "scene": null }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo3/Main.tscn");
    }

    [Fact]
    public void ResolveSmokeScene_ShouldNotFallbackToDiscoveredScene_WhenRecordedSceneIsInvalid()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var prototypeDir = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "Towerdemo4");
        Directory.CreateDirectory(prototypeDir);
        File.WriteAllText(Path.Combine(prototypeDir, "Towerdemo4Prototype.tscn"), """
[gd_scene format=3]
[node name="Prototype" type="Node"]
""");
        const string prototypeState = """
{
  "route": "prototype-7day-playable",
  "slug": "Towerdemo4",
  "prototype_completion": {
    "smoke_scene": "res://Game.Godot/Prototypes/Towerdemo4/MissingPrototype.tscn"
  },
  "godot_smoke": {
    "scene": "res://Game.Godot/Prototypes/Towerdemo4/AlsoMissing.tscn"
  }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().BeNull();
    }

    [Fact]
    public void ResolveSmokeScene_ShouldRejectAbsoluteAndEscapingRecordedScenes()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        using var outsideRoot = TempDirectory.Create("phase-a-outside");
        var prototypeDir = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "Towerdemo5");
        Directory.CreateDirectory(prototypeDir);
        File.WriteAllText(Path.Combine(prototypeDir, "Towerdemo5Prototype.tscn"), """
[gd_scene format=3]
[node name="Prototype" type="Node"]
""");
        var externalScenePath = Path.Combine(outsideRoot.Path, "ExternalPrototype.tscn");
        File.WriteAllText(externalScenePath, """
[gd_scene format=3]
[node name="External" type="Node"]
""");
        var escapedScene = Path.GetRelativePath(repoRoot.Path, externalScenePath).Replace('\\', '/');
        var prototypeState = $$"""
{
  "route": "prototype-7day-playable",
  "slug": "Towerdemo5",
  "prototype_completion": {
    "smoke_scene": "{{externalScenePath.Replace("\\", "\\\\")}}"
  },
  "godot_smoke": {
    "scene": "res://{{escapedScene}}"
  }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().BeNull();
    }

    [Fact]
    public void ResolveSmokeScene_ShouldUseLaterRecordedScene_WhenEarlierRecordedSceneIsInvalid()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var prototypeDir = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "Towerdemo5b");
        Directory.CreateDirectory(prototypeDir);
        File.WriteAllText(Path.Combine(prototypeDir, "ValidPrototype.tscn"), """
[gd_scene format=3]
[node name="Prototype" type="Node"]
""");
        const string prototypeState = """
{
  "route": "prototype-7day-playable",
  "prototype_completion": {
    "smoke_scene": "res://Game.Godot/Prototypes/Towerdemo5b/MissingPrototype.tscn"
  },
  "godot_smoke": {
    "scene": "res://Game.Godot/Prototypes/Towerdemo5b/ValidPrototype.tscn"
  }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo5b/ValidPrototype.tscn");
    }

    [Fact]
    public void ResolveSmokeScene_ShouldRejectDriveLikeResReferences()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var prototypeDir = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "Towerdemo6");
        Directory.CreateDirectory(prototypeDir);
        File.WriteAllText(Path.Combine(prototypeDir, "Towerdemo6Prototype.tscn"), """
[gd_scene format=3]
[node name="Prototype" type="Node"]
""");
        var alternateScenePath = Path.Combine(prototypeDir, "Alternate.tscn");
        File.WriteAllText(alternateScenePath, """
[gd_scene format=3]
[node name="Alternate" type="Node"]
""");
        var driveLikeScene = "res://" + Path.GetFullPath(alternateScenePath).Replace('\\', '/');
        var prototypeState = $$"""
{
  "route": "prototype-7day-playable",
  "slug": "Towerdemo6",
  "prototype_completion": {
    "smoke_scene": "{{driveLikeScene}}"
  }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().BeNull();
    }

    [Fact]
    public void ResolveSafeRecordedSmokeScene_ShouldKeepMissingButSafeRecordedScene()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        const string prototypeState = """
{
  "route": "prototype-7day-playable",
  "prototype_completion": {
    "smoke_scene": "res://Game.Godot/Prototypes/Towerdemo7/MissingPrototype.tscn"
  }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSafeRecordedSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo7/MissingPrototype.tscn");
    }

    [Fact]
    public void ResolveSafeRecordedSmokeScene_ShouldUseLaterSafeScene_WhenEarlierRecordedSceneIsUnsafe()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        const string prototypeState = """
{
  "route": "prototype-7day-playable",
  "prototype_completion": {
    "smoke_scene": "C:/outside/ExternalPrototype.tscn"
  },
  "godot_smoke": {
    "scene": "res://Game.Godot/Prototypes/Towerdemo7/SafePrototype.tscn"
  }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSafeRecordedSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo7/SafePrototype.tscn");
    }

    [Fact]
    public void ResolveSmokeScene_ShouldAllowBomAndLeadingWhitespaceBeforeGdScene()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var prototypeDir = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "Towerdemo8");
        Directory.CreateDirectory(prototypeDir);
        var scenePath = Path.Combine(prototypeDir, "Towerdemo8Prototype.tscn");
        File.WriteAllText(scenePath, "\uFEFF\n  [gd_scene format=3]\n[node name=\"Prototype\" type=\"Node\"]\n");
        const string prototypeState = """
{
  "route": "prototype-7day-playable",
  "prototype_completion": {
    "smoke_scene": "res://Game.Godot/Prototypes/Towerdemo8/Towerdemo8Prototype.tscn"
  }
}
""";

        var scene = PrototypeGodotSmokeService.ResolveSmokeScene(repoRoot.Path, prototypeState);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo8/Towerdemo8Prototype.tscn");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldTrimOversizedFeedbackBeforeCodexPrompt()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair oversized needs-fix feedback."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Oversized feedback should not enter Codex in full.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new QuickFixMissingSmokeSceneHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);
        var oversizedFeedback = "KEEP_CURRENT_BLOCKER prototype_smoke_scene_missing\n" +
                                string.Concat(Enumerable.Repeat("NEEDS_FIX_BULK_CONTEXT ", 2000)) +
                                "TAIL_SHOULD_NOT_REACH_PROMPT";

        await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            oversizedFeedback,
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.StandardInput.Should().Contain("KEEP_CURRENT_BLOCKER prototype_smoke_scene_missing");
        codexCommand.StandardInput.Should().Contain("[truncated ");
        codexCommand.StandardInput.Should().Contain("TAIL_SHOULD_NOT_REACH_PROMPT");
        codexCommand.StandardInput!.Length.Should().BeLessThan(35000);
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldContinueToCodex_WhenPreflightGodotSmokeTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke timed out.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new QuickFixGodotSmokeTimeoutHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke timeout.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "smoke_headless.py"));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "exec", StringComparison.Ordinal)));
        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.StandardInput.Should().Contain("godot_smoke_validation_timeout");
        run!.EvidenceJson.Should().Contain("prototype_main_menu_navigation_failed");
        run.EvidenceJson.Should().Contain("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
    }

    [Fact]
    public async Task SubmitAsync_QuickFix_ShouldTrimOversizedFeedbackBeforeCodexPrompt()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        WritePrototypeSmokeState(project);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);
        var oversizedFeedback = "QUICK_FIX_KEEP_ME repair the start button\n" +
                                string.Concat(Enumerable.Repeat("QUICK_FIX_BULK_CONTEXT ", 1800)) +
                                "QUICK_FIX_TAIL_SHOULD_NOT_REACH_PROMPT";

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(oversizedFeedback));

        result.Status.Should().Be("completed");
        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.StandardInput.Should().Contain("QUICK_FIX_KEEP_ME repair the start button");
        codexCommand.StandardInput.Should().Contain("[truncated ");
        codexCommand.StandardInput.Should().Contain("QUICK_FIX_TAIL_SHOULD_NOT_REACH_PROMPT");
        codexCommand.StandardInput!.Length.Should().BeLessThan(25000);
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepOneNeedsFix_WhenMapEntryContractIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG map entry step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_map_entry_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("missing_rpg_");
        runner.LastPrompt.Should().Contain("Platform hard acceptance for JRPG field navigation");
        runner.LastPrompt.Should().Contain("visible playable field");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/dq-rpg/MapScene.tscn");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs");
        runner.LastPrompt.Should().Contain("TrackLayer");
        runner.LastPrompt.Should().Contain("MovePlayer");
        runner.LastPrompt.Should().Contain("player marker or character");
        runner.LastPrompt.Should().Contain("Combat pressure interpretation guard");
        runner.LastPrompt.Should().Contain("guaranteed counter damage after player attacks");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRecoverProtectedPrototypeCompletionState()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: true,
            includeActiveState: false,
            includeSecondGoal: true);
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
        refreshed.Goals[1].Status.Should().Be("pending");
        File.Exists(Path.Combine(scenario.Project.RepoPath, "logs", "ci", "active-prototypes", "Towerdemo.active.json")).Should().BeTrue();
        File.Exists(Path.Combine(scenario.Project.RepoPath, "logs", "ci", "active-prototypes", "Towerdemo.packaging.json")).Should().BeTrue();
        File.Exists(Path.Combine(scenario.Project.RepoPath, "logs", "ci", "active-prototypes", "Towerdemo.completion.md")).Should().BeTrue();
        recoveredPrototypeState.Should().Contain("\"status\": \"succeeded\"");
        recoveredPrototypeState.Should().Contain("recovered_from_prototype_repair_state");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepNeedsFix_WhenProtectedRecoveryAlsoViolatesMutationGuard()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: true,
            includeActiveState: false);
        var testShimDir = Path.Combine(scenario.Project.RepoPath, "Game.Core.Tests", "Prototypes");
        Directory.CreateDirectory(testShimDir);
        File.WriteAllText(Path.Combine(testShimDir, "XunitShim.cs"), """
namespace Xunit
{
    public sealed class FactAttribute : System.Attribute { }
}
""");
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var run = await scenario.Store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("test_framework_shadowing_detected");
        result.AssistantMessage.Should().Contain("Platform mutation guard");
        result.AssistantMessage.Should().Contain("test_framework_shadowing_detected");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotRecoverProtectedPrototypeCompletionState_WhenCompletionDayIsIncomplete()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 6,
            includeRepairSteps: true,
            includeActiveState: false);
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        recoveredPrototypeState.Should().Contain("\"status\": \"failed\"");
        File.Exists(Path.Combine(scenario.Project.RepoPath, "logs", "ci", "active-prototypes", "Towerdemo.active.json")).Should().BeFalse();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotRecoverProtectedPrototypeCompletionState_WhenWorkflowStepsAreMissing()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: false,
            includeActiveState: false);
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        recoveredPrototypeState.Should().Contain("\"status\": \"failed\"");
        File.Exists(Path.Combine(scenario.Project.RepoPath, "logs", "ci", "active-prototypes", "Towerdemo.active.json")).Should().BeFalse();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRecoverProtectedPrototypeCompletionState_FromExistingActiveStateSteps()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: false,
            includeActiveState: true);
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.IterationGoalStatus.Should().Be("succeeded");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
        recoveredPrototypeState.Should().Contain("\"status\": \"succeeded\"");
        recoveredPrototypeState.Should().Contain("recovered_from_prototype_repair_state");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotRecoverProtectedPrototypeCompletionState_WhenActiveStateEvidenceDoesNotMatch()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: false,
            includeActiveState: true,
            activeStatePrototypeRecord: "docs/prototypes/2026-06-22-AnotherTowerdemo.md");
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        recoveredPrototypeState.Should().Contain("\"status\": \"failed\"");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotRecoverProtectedPrototypeCompletionState_WhenActiveStatePrototypeSpecDoesNotMatch()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: false,
            includeActiveState: true,
            activeStatePrototypeSpec: "docs/prototypes/AnotherTowerdemo.prototype.json");
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        recoveredPrototypeState.Should().Contain("\"status\": \"failed\"");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotRecoverProtectedPrototypeCompletionState_WhenActiveStateSmokeSceneDoesNotMatch()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: false,
            includeActiveState: true,
            activeStateSmokeScene: "res://Game.Godot/Prototypes/Towerdemo/AnotherTowerdemoPrototype.tscn");
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        recoveredPrototypeState.Should().Contain("\"status\": \"failed\"");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotRecoverProtectedPrototypeCompletionState_WhenSmokeSceneHasInvalidHeader()
    {
        using var scenario = await CreateProtectedCompletionRecoveryScenarioAsync(
            completedThroughDay: 7,
            includeRepairSteps: false,
            includeActiveState: true);
        var scenePath = Path.Combine(scenario.Project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "TowerdemoPrototype.tscn");
        File.WriteAllText(scenePath, "[resource]\n");
        var runner = new CompletionRecoveryNeedsFixRunner();
        var service = new PrototypeQuickFixService(scenario.Store, scenario.Options, runner);

        var result = await service.SubmitAsync(scenario.AccountId, scenario.ProjectId, new PrototypeFeedbackRequest(
            "Repair protected prototype completion state.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(scenario.Details.Session.SessionId, scenario.TargetGoal.GoalId, 1, scenario.TargetGoal.Title, scenario.TargetGoal.Description, scenario.TargetGoal.AcceptanceHint, scenario.TargetGoal.ResultSummary)));
        var refreshed = await scenario.Store.GetLatestProjectIterationSessionAsync(scenario.ProjectId, "repair_plan");
        var recoveredPrototypeState = scenario.Writer.ReadLatestPrototypeState(scenario.Project);

        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        recoveredPrototypeState.Should().Contain("\"status\": \"failed\"");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldReturnSpecificStepOneContractGaps()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        RemoveStepOneMapSizeAndPlayerVisibilityContract(project.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG map entry step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_map_entry_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("map_scene_missing_600x600_custom_minimum_size");
        result.AssistantMessage.Should().Contain("map_script_missing_player_visibility_restore");
        run!.EvidenceJson.Should().Contain("map_scene_missing_600x600_custom_minimum_size");
        run.EvidenceJson.Should().Contain("map_script_missing_player_visibility_restore");
        runner.LastPrompt.Should().Contain("Current platform acceptance diagnosis before repair");
        runner.LastPrompt.Should().Contain("Repair the full RPG/JRPG map-entry contract group");
        runner.LastPrompt.Should().Contain("map_scene_missing_600x600_custom_minimum_size");
        runner.LastPrompt.Should().Contain("map_script_missing_player_visibility_restore");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldOverrideScopeForCoreTestPackageFailures()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        EnsureCoreTestsNeedPackageReferences(project.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the final RPG acceptance step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "final first-loop acceptance");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "core test packages missing", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");
        var runner = new CoreTestPackageFailurePromptRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        runner.LastPrompt.Should().Contain("Platform acceptance scope override:");
        runner.LastPrompt.Should().Contain("core_tests_failed with CS0246 for Xunit or FluentAssertions");
        runner.LastPrompt.Should().Contain("This overrides the generic RPG gameplay-only edit scope");
        runner.LastPrompt.Should().Contain("Required first target: inspect and repair Game.Core.Tests/Game.Core.Tests.csproj PackageReference entries");
        runner.LastPrompt.Should().Contain("Do not create hand-written Xunit shims");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldSanitizeAcceptanceFailureDetails_InPublicGoalSummary()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        EnsureCoreTestsNeedPackageReferences(project.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the final RPG acceptance step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "final first-loop acceptance");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "core test packages missing", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");
        var runner = new AbsolutePathCoreTestPackageFailurePromptRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = refreshed!.Goals.Single(item => item.GoalId == targetGoal.GoalId);

        goal.Status.Should().Be("needs_fix");
        goal.ResultSummary.Should().Contain("核心测试项目缺少测试框架包引用");
        goal.ResultSummary.Should().NotContain(@"C:\jimuyun");
        goal.ResultSummary.Should().NotContain("phase-a-innernet");
        goal.ResultSummary.Should().NotContain("workspaces");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldOverrideScopeForNamedCoreCompileFailures()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the final RPG acceptance step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "final first-loop acceptance");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "core compile error", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");
        var runner = new CoreCompileFailurePromptRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        runner.LastPrompt.Should().Contain("Platform acceptance scope override:");
        runner.LastPrompt.Should().Contain("core_tests_failed with C# compile errors");
        runner.LastPrompt.Should().Contain("repair only the files, symbols, and C# error codes named");
        runner.LastPrompt.Should().Contain("Game.Core/Prototypes/DqRpgPrototypeLoop.cs");
        runner.LastPrompt.Should().Contain("PlayerX/PlayerY");
        runner.LastPrompt.Should().Contain("Do not continue gameplay/UI/content polish");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldOverrideScopeForMsBuildProjectExtensionsPathFailures()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the final RPG acceptance step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "final first-loop acceptance");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "msbuild project extensions path error", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");
        var runner = new MsBuildProjectExtensionsPathFailurePromptRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        runner.LastPrompt.Should().Contain("core_tests_failed with MSB3540 for MSBuildProjectExtensionsPath");
        runner.LastPrompt.Should().Contain("remove any MSBuildProjectExtensionsPath assignment from .csproj files");
        runner.LastPrompt.Should().Contain("Directory.Build.props");
        runner.LastPrompt.Should().Contain("Do not add late MSBuildProjectExtensionsPath properties");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRequireDedicatedBattleScene_ForStepTwo()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG battle scene step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "battle or challenge resolution");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_battle_scene_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("missing_rpg_battle_scene_contract");
        runner.LastPrompt.Should().Contain("Platform hard acceptance for JRPG battle or challenge resolution");
        runner.LastPrompt.Should().Contain("readable battle, challenge, or obstacle resolution loop");
        runner.LastPrompt.Should().Contain("dedicated battle scene");
        runner.LastPrompt.Should().Contain("BattleFinished");
        runner.LastPrompt.Should().Contain("ResolveBattle or ResolveAttackTurn");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepSurvivorsLikeNeedsFix_WhenHardAcceptanceFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "Vampire Survivors-like");
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the survivors-like first loop."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 4);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing core weapon markers", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 4, "Goal 4 needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current survivors-like goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 4, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("missing_required_core_markers");
        result.AssistantMessage.Should().Contain("missing_marker=AutoAttack");
        runner.LastPrompt.Should().Contain("Platform hard acceptance for Vampire Survivors-like core weapon");
        runner.LastPrompt.Should().Contain("missing_marker=AutoAttack");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepTwoTimeoutFocusedOnBattleScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG battle scene step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "battle or challenge resolution");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_battle_scene_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");
        var service = new PrototypeQuickFixService(store, options, new ImmediateCanceledHostedProcessRunner());

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        var summary = refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).ResultSummary;

        result.Status.Should().Be("failed");
        summary.Should().Contain("首次冲突");
        summary.Should().Contain("不推进战斗结算或奖励选择");
        summary.Should().NotContain("胜利后显示 3 个奖励");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldInjectRewardContract_ForStepThree()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward growth loop with a battle reward, three reward choices, visible state change, and return to the map."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "growth, reward, or consequence feedback");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "reward values are wrong", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.LastPrompt.Should().Contain("Platform hard acceptance for JRPG growth, reward, or consequence feedback");
        runner.LastPrompt.Should().Contain("统一 smoke");
        runner.LastPrompt.Should().Contain("exactly three understandable reward choices");
        runner.LastPrompt.Should().Contain("visible state change");
        runner.LastPrompt.Should().Contain("ShowRewardReturnFeedback");
        runner.LastPrompt.Should().Contain("movement is restored");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldAcceptBattleSceneOwnedRewardFlow_ForStepThree()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward growth loop with a battle reward, three reward choices, visible state change, and return to the map."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "growth, reward, or consequence feedback");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");

        var scriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private BattleScene _battleScene = new();
    private MapScene _mapScene = new();
    private DqRpgPrototypeLoop _loop = new();
    private dynamic _state;

    public void Ready()
    {
        _battleScene.RewardSelected += ApplyRewardSelection;
    }

    private void OnBattleFinished(dynamic result)
    {
        if (result.RewardOptions.Count > 0)
        {
            _battleScene.ApplyState(result.NextState);
            return;
        }

        RefreshView();
    }

    private void ApplyRewardSelection(int rewardIndex)
    {
        _state = _loop.ApplyReward(_state, rewardIndex, fromChest: false);
        _mapScene.ResumeAfterReward();
        _mapScene.ShowRewardReturnStatus("Battle reward selected. Return to the map.");
        RefreshView();
    }

    private void RefreshView() { }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private dynamic _player;
    public void ResumeAfterReward() { _player.Visible = true; }
    public void ShowRewardReturnStatus(string status) { _player.Visible = true; }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "BattleScene.cs"), """
public sealed class BattleScene
{
    public event System.Action<int>? RewardSelected;
    private dynamic RewardOptionOneButton;
    private dynamic RewardOptionTwoButton;
    private dynamic RewardOptionThreeButton;

    public void ApplyState(dynamic state)
    {
        var rewardVisible = state.RewardOptions.Count == 3;
        if (state.RewardOptions.Count != 3)
        {
            return;
        }

        ConfigureRewardButton(RewardOptionOneButton, state.RewardOptions[0]);
        ConfigureRewardButton(RewardOptionTwoButton, state.RewardOptions[1]);
        ConfigureRewardButton(RewardOptionThreeButton, state.RewardOptions[2]);
    }

    private void ConfigureRewardButton(dynamic button, dynamic reward) { }
    private void SelectFirstReward() => RewardSelected?.Invoke(0);
}
""");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldAcceptShellOwnedRewardPanelReturningThroughMapApplyState_ForStepThree()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward loop step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "growth, reward, or consequence feedback");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");

        var scriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private MapScene _mapScene = new();
    private BattleScene _battleScene = new();
    private DqRpgPrototypeLoop _loop = new();
    private dynamic _state;
    private dynamic _rewardPanel;
    private dynamic[] _rewardButtons = [];

    private void OnBattleFinished(bool victory)
    {
        var rewards = _state.RewardOptions.Count > 0
            ? _state.RewardOptions
            : _loop.CreateRewardOptions(_state, fromChest: false);
        if (rewards.Count > 0)
        {
            ShowRewardScene(rewards);
            return;
        }

        RefreshView();
    }

    private void ShowRewardScene(System.Collections.Generic.IReadOnlyList<object> rewards)
    {
        _rewardPanel.Visible = true;
        _rewardButtons[0].Text = "+5 HP fully restores to the new max HP";
        _rewardButtons[1].Text = "+2 ATK increases damage";
        _rewardButtons[2].Text = "+1 DEF reduces damage taken";
    }

    private void SelectReward(int rewardIndex)
    {
        _state = _loop.ApplyReward(_state, rewardIndex, fromChest: false);
        _rewardPanel.Visible = false;
        _mapScene.ApplyState("Battle reward selected. HP 105/105, ATK 10, DEF 2. Return to the map.");
        RefreshView();
    }

    private void RefreshView() { }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private dynamic _playerAsset;
    public void ApplyState(string rewardReturnStatus) { _playerAsset.Visible = true; }
}
""");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldShowValidatedSummary_WhenCodexReportsStaleGodotNeedsFix()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward loop step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "growth, reward, or consequence feedback");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");

        var scriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private MapScene _mapScene = new();
    private BattleScene _battleScene = new();
    private DqRpgPrototypeLoop _loop = new();
    private dynamic _state;
    private dynamic _rewardPanel;
    private dynamic[] _rewardButtons = [];

    private void OnBattleFinished(bool victory)
    {
        var rewards = _state.RewardOptions.Count > 0
            ? _state.RewardOptions
            : _loop.CreateRewardOptions(_state, fromChest: false);
        if (rewards.Count > 0)
        {
            ShowRewardScene(rewards);
            return;
        }

        RefreshView();
    }

    private void ShowRewardScene(System.Collections.Generic.IReadOnlyList<object> rewards)
    {
        _rewardPanel.Visible = true;
        _rewardButtons[0].Text = "+5 HP fully restores to the new max HP";
        _rewardButtons[1].Text = "+2 ATK increases damage";
        _rewardButtons[2].Text = "+1 DEF reduces damage taken";
    }

    private void SelectReward(int rewardIndex)
    {
        _state = _loop.ApplyReward(_state, rewardIndex, fromChest: false);
        _rewardPanel.Visible = false;
        _mapScene.ApplyState("Battle reward selected. HP 105/105, ATK 10, DEF 2. Return to the map.");
        RefreshView();
    }

    private void RefreshView() { }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private dynamic _playerAsset;
    public void ApplyState(string rewardReturnStatus) { _playerAsset.Visible = true; }
}
""");

        var runner = new GoalRepairStaleGodotNeedsFixButSmokePassRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.AssistantMessage.Should().Contain($"任务 {targetGoal.GoalIndex} 修复已完成");
        result.AssistantMessage.Should().Contain("已通过 Godot smoke 验证");
        result.AssistantMessage.Should().NotContain("STATUS: needs_fix");
        result.AssistantMessage.Should().NotContain("Failed to open 'user://logs");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRunGodotSmoke_ForStepFiveRewardLoop()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG reward loop to a clean return-to-map validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "growth, reward, or consequence feedback");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need engine verification for reward loop.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");

        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.AssistantMessage.Should().Contain("Godot");
        var smokeCommand = runner.Commands.Single(command => HasScriptArgument(command, "smoke_headless.py"));
        smokeCommand.Environment["GODOT_BIN"].Should().Be(@"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        smokeCommand.Environment["UseSharedCompilation"].Should().Be("false");
        smokeCommand.Environment["MSBUILDDISABLENODEREUSE"].Should().Be("1");
        smokeCommand.Environment["TEMP"].Should().Contain("phase-a-validation-temp");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldAcceptStepFiveRewardEntryMethodSignature()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG reward loop to a clean return-to-map validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "growth, reward, or consequence feedback");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");

        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        File.WriteAllText(
            Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs"),
            """
public sealed class DqRpgPrototype
{
    void ShowMapScene() { }
    public void ShowRewardScene(System.Collections.Generic.IReadOnlyList<object> rewards)
    {
        if (rewards is null || rewards.Count <= 0) { ShowMapScene(); return; }
        ShowRewardReturnStatus();
    }
    public void ShowRewardReturnStatus() { ShowMapScene(); }
}
""");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.AssistantMessage.Should().Contain("Godot");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepFiveNeedsFix_WhenRewardContractIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG reward loop to a clean return-to-map validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "growth, reward, or consequence feedback");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"Goal {targetGoal.GoalIndex} needs fix");

        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        File.WriteAllText(
            Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs"),
            "public sealed class MapScene { dynamic _player; void ResetMap() { _player.Visible = true; } }\n");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("acceptance_validation_status");
        run.EvidenceJson.Should().Contain("\"failed\"");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepFinalStepNeedsFix_WhenMainSceneHostUiIsVisible()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: false);

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("main_scene_default_ui_not_hidden");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldReportGdignore_WhenFinalRpgAssetsAreBlocked()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        File.WriteAllText(Path.Combine(project.RepoPath, "Game.Godot", ".gdignore"), "");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("game_godot_gdignore_blocks_rpg_assets");
        result.AssistantMessage.Should().Contain("game_godot_gdignore_blocks_rpg_assets");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPassFinalStep_WhenMainSceneHostUiDefaultsHidden()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepFinalStepNeedsFix_WhenRpgGdUnitSuiteIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("rpg_gdunit_tests_missing");
        result.AssistantMessage.Should().Contain("GDUNIT_ATTEMPTED_PATHS");
        result.AssistantMessage.Should().Contain("tests/Prototype/dq-rpg");
        result.AssistantMessage.Should().Contain("Tests.Godot/tests/Prototype/dq-rpg");
        run!.EvidenceJson.Should().Contain("rpg_gdunit_tests_missing");
        run.EvidenceJson.Should().Contain("attempted_gdunit_paths");
        run.EvidenceJson.Should().Contain("\"ran\":false");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepExplicitGdUnitGoalNeedsFix_WhenSuiteIsMissing()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        WritePrototypeSmokeState(project);
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "repair_plan",
            "rpg_gdunit_check",
            "Run RPG GdUnit validation.",
            [
                new ProjectIterationGoalCreateCommand(
                    1,
                    "RPG field navigation and stable control GdUnit suite check",
                    "Start Adventure shows a visible MapScene with stable movement, then run the RPG GdUnit suite.",
                    "Map movement acceptance and GdUnit validation both pass.")
            ]);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        var targetGoal = details!.Goals[0];
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "GdUnit suite is missing.", null);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal needs GdUnit fix.");
        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        PrototypeRouteSkillPolicy.Resolve(project).RouteSkillId.Should().Be("prototype-7day-playable-godot-zh");

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("rpg_gdunit_tests_missing");
        result.AssistantMessage.Should().Contain("任务 1 修复已完成");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepFinalStepNeedsFix_WhenRpgGdUnitFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        SeedLatestRpgGdUnitFailureReport(project.RepoPath);

        var runner = new GoalRepairFinalGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("RPG GdUnit validation");
        result.AssistantMessage.Should().Contain("GDUNIT_FAILURES");
        result.AssistantMessage.Should().Contain("Read the three reward cards");
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        refreshed!.Goals.Last().Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldIncludeLatestRpgGdUnitFailuresInFinalRepairPrompt()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        SeedLatestRpgGdUnitFailureReport(project.RepoPath);

        var runner = new GoalRepairFinalGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        _ = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        runner.LastPrompt.Should().Contain("Latest RPG GdUnit validation context");
        runner.LastPrompt.Should().Contain("\"failures\":27");
        runner.LastPrompt.Should().Contain("Encounter ready");
        runner.LastPrompt.Should().Contain("Read the three reward cards");
        runner.LastPrompt.Should().Contain("BattleScene finished");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldUseLocalDateForRpgGdUnitReportDir()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);
        var localDateBefore = DateTimeOffset.Now.ToString("yyyy-MM-dd");

        _ = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        var localDateAfter = DateTimeOffset.Now.ToString("yyyy-MM-dd");
        var gdUnitCommand = runner.Commands.Single(command => HasScriptArgument(command, "run_gdunit.py"));
        gdUnitCommand.Arguments.Should().Contain("--prewarm");
        var reportDir = gdUnitCommand.Arguments.SkipWhile(arg => arg != "--rd").Skip(1).First();
        reportDir.Should().BeOneOf(
            $"logs/e2e/{localDateBefore}/gdunit-dq-rpg-prototype",
            $"logs/e2e/{localDateAfter}/gdunit-dq-rpg-prototype");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldHonorStructuredCompletedStatus()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Stabilize map movement and first encounter trigger."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "still blocked", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "goal 1 needs fix");
        var runner = new StructuredCompletedHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotSyncMainSceneFromFocusedWorkspaceForMapGoal()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        WritePrototypeSmokeState(project);
        File.WriteAllText(Path.Combine(project.RepoPath, "project.godot"), "[application]\nrun/main_scene=\"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn\"\n");
        File.WriteAllText(Path.Combine(project.RepoPath, "Directory.Build.props"), "<Project></Project>\n");
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs focused workspace repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var workspaceRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            var mainScene = Path.Combine(workspaceRoot, "Game.Godot", "Scenes", "Main.tscn");
            File.Exists(mainScene).Should().BeFalse();
            File.AppendAllText(Path.Combine(workspaceRoot, "project.godot"), "\nrun/main_scene=\"res://Game.Godot/Scenes/Main.tscn\"\n");
            File.AppendAllText(Path.Combine(workspaceRoot, "Directory.Build.props"), "<!-- out-of-scope root edit -->\n");
            var catalog = Path.Combine(workspaceRoot, "Game.Godot", "Scripts", "Prototypes", "PrototypeCatalog.cs");
            File.AppendAllText(catalog, "\npublic static class FocusedWorkspaceCatalogMarker { }\n");
            RestoreCoreAcceptanceMarker(workspaceRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().NotBeEmpty();
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "Main.tscn")).Should().NotContain("FocusedWorkspaceMarker");
        File.ReadAllText(Path.Combine(project.RepoPath, "project.godot")).Should().NotContain("res://Game.Godot/Scenes/Main.tscn");
        File.ReadAllText(Path.Combine(project.RepoPath, "Directory.Build.props")).Should().NotContain("out-of-scope root edit");
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Scripts", "Prototypes", "PrototypeCatalog.cs")).Should().Contain("FocusedWorkspaceCatalogMarker");
        runner.LastPrompt.Should().NotContain("Game.Godot/Scenes/**");
        runner.LastPrompt.Should().NotContain("project.godot");
        runner.LastPrompt.Should().NotContain("Directory.Build.props");
        runner.LastPrompt.Should().Contain("Game.Godot/Scripts/Prototypes");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldSyncActiveSlugPrototypeDirectoryFromFocusedWorkspace()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        var towerScriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts");
        Directory.CreateDirectory(towerScriptPath);
        File.WriteAllText(Path.Combine(towerScriptPath, "Hud.cs"), "public sealed class Hud { }\n");
        await CreateSucceededPrototypeRunAsync(store, project, "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn");
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs active slug focused workspace repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            var activeSlugScene = Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "TowerdemoPrototype.tscn");
            File.Exists(activeSlugScene).Should().BeTrue();
            File.AppendAllText(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs"), "\npublic static class TowerdemoFocusedWorkspaceMarker { }\n");
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/Towerdemo/**");
        runner.LastPrompt.Should().NotContain("Game.Godot/Prototypes/dq-rpg/**");
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs")).Should().Contain("TowerdemoFocusedWorkspaceMarker");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldUseLatestSucceededRunForFocusedWorkspace_WhenRouteStateIsStale()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        var towerScriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts");
        Directory.CreateDirectory(towerScriptPath);
        File.WriteAllText(Path.Combine(towerScriptPath, "Hud.cs"), "public sealed class Hud { }\n");
        await CreateSucceededPrototypeRunAsync(store, project, "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn");
        WritePrototypeSmokeState(project);
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs latest prototype focused workspace repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            File.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "TowerdemoPrototype.tscn")).Should().BeTrue();
            File.AppendAllText(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs"), "\npublic static class LatestRunFocusedWorkspaceMarker { }\n");
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/Towerdemo/**");
        runner.LastPrompt.Should().NotContain("Game.Godot/Prototypes/dq-rpg/**");
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs")).Should().Contain("LatestRunFocusedWorkspaceMarker");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldUseExecuteNextGoalStateForFocusedWorkspace_BeforeLatestSucceededRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        var towerScriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts");
        Directory.CreateDirectory(towerScriptPath);
        File.WriteAllText(Path.Combine(towerScriptPath, "Hud.cs"), "public sealed class Hud { }\n");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        new PrototypeRouteStateWriter().WriteExecuteNextGoalState(project, targetGoal.GoalIndex, new
        {
            session_id = details.Session.SessionId,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs execute-next active slug repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            File.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "TowerdemoPrototype.tscn")).Should().BeTrue();
            File.AppendAllText(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs"), "\npublic static class ExecuteNextFocusedWorkspaceMarker { }\n");
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/Towerdemo/**");
        runner.LastPrompt.Should().NotContain("Game.Godot/Prototypes/dq-rpg/**");
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs")).Should().Contain("ExecuteNextFocusedWorkspaceMarker");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldIgnoreStaleSessionStateForFocusedWorkspace()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "StaleSlug", "StalePrototype.tscn");
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        var towerScriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts");
        Directory.CreateDirectory(towerScriptPath);
        File.WriteAllText(Path.Combine(towerScriptPath, "Hud.cs"), "public sealed class Hud { }\n");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair the current RPG map movement goal."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        var writer = new PrototypeRouteStateWriter();
        writer.WriteNeedsFixState(project, targetGoal.GoalIndex, new
        {
            session_id = "old-session",
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/StaleSlug/StalePrototype.tscn"
            }
        });
        writer.WriteExecuteNextGoalState(project, targetGoal.GoalIndex, new
        {
            session_id = details!.Session.SessionId,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs current session repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            File.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "TowerdemoPrototype.tscn")).Should().BeTrue();
            Directory.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "StaleSlug")).Should().BeFalse();
            File.AppendAllText(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs"), "\npublic static class CurrentSessionFocusedWorkspaceMarker { }\n");
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/Towerdemo/**");
        runner.LastPrompt.Should().NotContain("Game.Godot/Prototypes/StaleSlug/**");
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs")).Should().Contain("CurrentSessionFocusedWorkspaceMarker");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPreferCurrentGoalStateOverProjectGodotMainScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "OldMain", "OldMainPrototype.tscn");
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        File.AppendAllText(Path.Combine(project.RepoPath, "project.godot"), "\nrun/main_scene=\"res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn\"\n");
        var towerScriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts");
        Directory.CreateDirectory(towerScriptPath);
        File.WriteAllText(Path.Combine(towerScriptPath, "Hud.cs"), "public sealed class Hud { }\n");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair the current RPG map movement goal."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        new PrototypeRouteStateWriter().WriteExecuteNextGoalState(project, targetGoal.GoalIndex, new
        {
            session_id = details!.Session.SessionId,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs current goal repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            File.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "TowerdemoPrototype.tscn")).Should().BeTrue();
            Directory.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "OldMain")).Should().BeFalse();
            Directory.Exists(Path.Combine(focusedRoot, "Game.Godot", "Scenes")).Should().BeFalse();
            File.AppendAllText(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs"), "\npublic static class CurrentGoalBeatsProjectGodotMarker { }\n");
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/Towerdemo/**");
        runner.LastPrompt.Should().NotContain("Game.Godot/Prototypes/OldMain/**");
        runner.LastPrompt.Should().NotContain("Game.Godot/Scenes/**");
        runner.Commands.Should().Contain(command =>
            HasScriptArgument(command, "smoke_headless.py") &&
            command.Arguments.Contains("res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"));
        runner.Commands.Should().NotContain(command =>
            HasScriptArgument(command, "smoke_headless.py") &&
            command.Arguments.Contains("res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn"));
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts", "Hud.cs")).Should().Contain("CurrentGoalBeatsProjectGodotMarker");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldScopeFocusedWorkspaceFromCurrentGoalScene_WhenSceneFileIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "OldMain", "OldMainPrototype.tscn");
        File.AppendAllText(Path.Combine(project.RepoPath, "project.godot"), "\nrun/main_scene=\"res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn\"\n");
        var towerScriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "Scripts");
        Directory.CreateDirectory(towerScriptPath);
        File.WriteAllText(Path.Combine(towerScriptPath, "Hud.cs"), "public sealed class Hud { }\n");
        var slugTestPath = Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "Towerdemo");
        Directory.CreateDirectory(slugTestPath);
        File.WriteAllText(Path.Combine(slugTestPath, "test_towerdemo.gd"), "extends Node\n");
        var customGdUnitPath = Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "CustomSuite");
        Directory.CreateDirectory(customGdUnitPath);
        File.WriteAllText(Path.Combine(customGdUnitPath, "test_custom.gd"), "extends Node\n");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair the current RPG map movement goal."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        new PrototypeRouteStateWriter().WriteExecuteNextGoalState(project, targetGoal.GoalIndex, new
        {
            session_id = details!.Session.SessionId,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            gdunit_path = "tests/Prototype/CustomSuite",
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/MissingPrototype.tscn"
            }
        });
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs missing scene repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            Directory.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo")).Should().BeTrue();
            Directory.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "OldMain")).Should().BeFalse();
            File.Exists(Path.Combine(focusedRoot, "Tests.Godot", "tests", "Prototype", "Towerdemo", "test_towerdemo.gd")).Should().BeTrue();
            File.Exists(Path.Combine(focusedRoot, "Tests.Godot", "tests", "Prototype", "CustomSuite", "test_custom.gd")).Should().BeTrue();
            File.WriteAllText(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo", "MissingPrototype.tscn"), "[gd_scene format=3]\n[node name=\"Towerdemo\" type=\"Node\"]\n");
            File.AppendAllText(Path.Combine(focusedRoot, "Tests.Godot", "tests", "Prototype", "Towerdemo", "test_towerdemo.gd"), "\n# focused workspace slug test synced\n");
            File.AppendAllText(Path.Combine(focusedRoot, "Tests.Godot", "tests", "Prototype", "CustomSuite", "test_custom.gd"), "\n# focused workspace custom gdunit test synced\n");
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/Towerdemo/**");
        runner.LastPrompt.Should().Contain("Tests.Godot/tests/Prototype/Towerdemo/**");
        runner.LastPrompt.Should().Contain("Tests.Godot/tests/Prototype/CustomSuite/**");
        runner.LastPrompt.Should().NotContain("Game.Godot/Prototypes/OldMain/**");
        File.Exists(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo", "MissingPrototype.tscn")).Should().BeTrue();
        File.ReadAllText(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "Towerdemo", "test_towerdemo.gd")).Should().Contain("focused workspace slug test synced");
        File.ReadAllText(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "CustomSuite", "test_custom.gd")).Should().Contain("focused workspace custom gdunit test synced");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldIgnoreStaleRouteStateGdUnitPathForFocusedWorkspace()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        var customGdUnitPath = Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "CustomSuite");
        Directory.CreateDirectory(customGdUnitPath);
        File.WriteAllText(Path.Combine(customGdUnitPath, "test_custom.gd"), "extends Node\n");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair the current RPG map movement goal."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        var writer = new PrototypeRouteStateWriter();
        writer.WriteNeedsFixState(project, targetGoal.GoalIndex, new
        {
            session_id = "old-session",
            goal_id = "old-goal",
            goal_index = targetGoal.GoalIndex,
            gdunit_path = "tests/Prototype/CustomSuite"
        });
        writer.WriteExecuteNextGoalState(project, targetGoal.GoalIndex, new
        {
            session_id = details!.Session.SessionId,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs current goal repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            Directory.Exists(Path.Combine(focusedRoot, "Game.Godot", "Prototypes", "Towerdemo")).Should().BeTrue();
            Directory.Exists(Path.Combine(focusedRoot, "Tests.Godot", "tests", "Prototype", "CustomSuite")).Should().BeFalse();
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/Towerdemo/**");
        runner.LastPrompt.Should().NotContain("Tests.Godot/tests/Prototype/CustomSuite/**");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldSyncNewActiveSlugGdUnitDirectoryFromFocusedWorkspace()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsurePrototypeSmokeSceneFile(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        await CreateSucceededPrototypeRunAsync(store, project, "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn");
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "needs active slug gdunit test repair", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            var testDirectory = Path.Combine(focusedRoot, "Tests.Godot", "tests", "Prototype", "TowerdemoPrototype");
            Directory.CreateDirectory(testDirectory);
            File.WriteAllText(Path.Combine(testDirectory, "TowerdemoTest.cs"), "public sealed class TowerdemoTest { }\n");
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().Contain("Tests.Godot/tests/Prototype/TowerdemoPrototype/**");
        File.Exists(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "TowerdemoPrototype", "TowerdemoTest.cs")).Should().BeTrue();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldNotDeleteManagedFocusedWorkspaceDirectory_WhenRootIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        WritePrototypeSmokeState(project);
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        var staleDirectory = Path.Combine(project.RepoPath, "Game.Godot", "Scripts", "Prototypes");
        Directory.CreateDirectory(staleDirectory);
        File.WriteAllText(Path.Combine(staleDirectory, "StaleCatalog.cs"), "public sealed class StaleCatalog { }\n");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "remove stale directory", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var focusedRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            Directory.Delete(Path.Combine(focusedRoot, "Game.Godot", "Scripts", "Prototypes"), recursive: true);
            RestoreCoreAcceptanceMarker(focusedRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        Directory.Exists(staleDirectory).Should().BeTrue();
        File.Exists(Path.Combine(staleDirectory, "StaleCatalog.cs")).Should().BeTrue();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldMirrorDeleteManagedFocusedWorkspaceFiles()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        WritePrototypeSmokeState(project);
        RemoveCoreAcceptanceMarker(project.RepoPath, "MoveOnMap");
        var staleFile = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "StaleRoute.cs");
        File.WriteAllText(staleFile, "public sealed class StaleRoute { }\n");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "remove stale file", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "goal needs fix");
        var runner = new FocusedWorkspaceEditRunner(command =>
        {
            var workspaceRoot = command.Arguments.SkipWhile(arg => arg != "--cd").Skip(1).First();
            File.Delete(Path.Combine(workspaceRoot, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "StaleRoute.cs"));
            RestoreCoreAcceptanceMarker(workspaceRoot, "MoveOnMap");
        });
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        runner.LastPrompt.Should().NotBeEmpty();
        File.Exists(staleFile).Should().BeFalse();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepNeedsFix_WhenCurrentGoalIsStillBlocked()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true, gameTypeSource: "rpg");
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"目标 {targetGoal.GoalIndex} 需要修复。");
        var runner = new GoalRepairNeedsFixHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRejectCompletedStatus_WhenGameplayVerificationIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"目标 {targetGoal.GoalIndex} 需要修复。");
        var runner = new StructuredCompletedButMissingGameplayVerificationHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPersistNeedsFixSummary_WhenRepairTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = FindGoal(details!, "field navigation and stable control");
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, $"目标 {targetGoal.GoalIndex} 需要修复。");
        var runner = new ImmediateCanceledHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("failed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.StderrText.Should().Contain("720 second timeout");
        var refreshedGoal = refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex);
        refreshedGoal.Status.Should().Be("needs_fix");
        refreshedGoal.ResultSummary.Should().Contain("修复超时");
        refreshedGoal.ResultSummary.Should().Contain("Start Adventure");
        refreshedGoal.ResultSummary.Should().Contain("MapScene");
        refreshed.Session.Status.Should().Be("needs_fix");
        refreshed.Session.LatestSummary.Should().Contain("修复超时");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var planningAnalysis = ReadPlanningAnalysis(project!.MetaPath);
        var loopFields = planningAnalysis.GetProperty("fieldCoverage").EnumerateArray().ToArray();
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "minimum_playable_loop" &&
            field.GetProperty("status").GetString() == "partial");
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "core_gameplay_loop" &&
            field.GetProperty("status").GetString() == "partial");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldAllowNonGameplayEvidenceRepair_WhenRpgAcceptanceValidationDoesNotRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "repair_plan",
            "restore_runtime_evidence",
            "Restore route evidence.",
            [new ProjectIterationGoalCreateCommand(1, "Restore route evidence", "Restore route run record only.", "Evidence record is present.")]);
        var createdDetails = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        await store.UpdateProjectIterationGoalStatusAsync(createdDetails!.Goals[0].GoalId, "needs_fix", "evidence missing", null);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var details = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        var runner = new StructuredCompletedHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details!.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("completed");
        result.AssistantMessage.Should().NotContain("platform_acceptance_not_run_for_rpg_goal");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
        run!.EvidenceJson.Should().NotContain("platform_acceptance_not_run_for_rpg_goal");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldExplainNeedsFix_WhenGameplayAcceptanceValidationDoesNotRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        File.AppendAllText(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs"), "\n// ShouldReachRewardPhase_AfterWinningTheFirstEncounter BattlesWon\n");
        var testProject = Path.Combine(project.RepoPath, "Game.Core.Tests", "Game.Core.Tests.csproj");
        if (File.Exists(testProject))
        {
            File.Delete(testProject);
        }
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "repair_plan",
            "restore_runtime_evidence",
            "Restore route evidence.",
            [new ProjectIterationGoalCreateCommand(3, "RPG Step 3: BattleScene visualization and settlement validation", "BattleScene resolves one readable battle and victory.", "BattleScene settlement is validated.")]);
        var createdDetails = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        await store.UpdateProjectIterationGoalStatusAsync(createdDetails!.Goals[0].GoalId, "needs_fix", "gameplay acceptance not yet proven", null);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var details = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        var runner = new StructuredCompletedHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details!.Session.SessionId, details.Goals[0].GoalId, 3, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("platform_acceptance_not_run_for_rpg_goal");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("platform_acceptance_not_run_for_rpg_goal");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRejectOffTopicSuccessOutput()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
        runner.LastPrompt.Should().Contain("这是任务级 needs-fix 修复，不是 90 秒快速修复");
    }


    private static ProjectIterationGoalSnapshot FindGoal(ProjectIterationSessionDetails details, string titlePart)
    {
        return details.Goals.Single(goal => GoalTitleMatches(goal.Title, titlePart));
    }

    private static bool GoalTitleMatches(string title, string titlePart)
    {
        return title.Contains(titlePart, StringComparison.OrdinalIgnoreCase) ||
               title.Contains(TranslateGoalTitle(titlePart), StringComparison.OrdinalIgnoreCase);
    }

    private static string TranslateGoalTitle(string titlePart)
    {
        return titlePart switch
        {
            "field navigation and stable control" => "地图导航与稳定操控",
            "battle or challenge resolution" => "战斗或挑战结算",
            "growth, reward, or consequence feedback" => "成长、奖励或后果反馈",
            "final first-loop acceptance" => "最终首轮闭环验收",
            _ => titlePart
        };
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId, bool prototypeSucceeded, string gameTypeSource = "RPG")
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameTypeSource, null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        if (prototypeSucceeded)
        {
            var runId = await store.CreateRunAsync(result.ProjectId!, null, "prototype-7day-playable");
            await store.MarkRunStartedAsync(runId);
            await store.CompleteRunAsync(
                runId,
                "succeeded",
                0,
                "prototype ok",
                "",
                """{"prototype_completion":{"succeeded":true,"smoke_scene":"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"},"godot_smoke":{"scene":"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn","exit_code":0}}""");
        }

        return result.ProjectId!;
    }

    private static async Task CreateSucceededPrototypeRunAsync(PhaseAMetadataStore store, ProjectSnapshot project, string smokeScene)
    {
        var runId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(runId, "succeeded", 0, "", "", $$"""
        {
          "prototype_completion": {
            "smoke_scene": "{{smokeScene}}"
          }
        }
        """);
    }

    private static async Task<ProjectIterationSessionDetails> CreateRpgGdUnitRepairSessionAsync(
        PhaseAMetadataStore store,
        string accountId,
        string projectId)
    {
        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "prototype-repair-plan",
            "Repair RPG GdUnit validation failure.",
            "Repair RPG project-specific GdUnit validation.",
            [
                new ProjectIterationGoalCreateCommand(
                    1,
                    "Repair RPG runtime assets and Godot imports for GdUnit",
                    "Fix missing runtime assets, scene ext_resource paths, and Godot import visibility before broad gameplay redesign.",
                    "This step passes only when the active dq-rpg scenes for the selected capabilities no longer reference missing PNG or .ctex resources and GdUnit can load MapScene.tscn, plus BattleScene.tscn only when battle/conflict capability is selected or named by the latest failure, without ext_resource parse errors."),
                new ProjectIterationGoalCreateCommand(
                    2,
                    "Repair RPG scene node contract for GdUnit",
                    "Fix node paths required by the project-specific GdUnit suite.",
                    "This step passes only when the node paths required by the project-specific GdUnit suite exist or tests and scripts are updated together."),
                new ProjectIterationGoalCreateCommand(
                    3,
                    "Rerun RPG project-specific GdUnit and final prototype acceptance",
                    "Run final acceptance across the full playable RPG prototype.",
                    "Final RPG GdUnit and prototype acceptance pass.")
            ]);
        return (await store.GetLatestProjectIterationSessionAsync(projectId))!;
    }

    private static void SeedLatestRpgGdUnitFailureReport(string repoPath)
    {
        var reportDir = Path.Combine(repoPath, "logs", "e2e", "2099-01-01", "gdunit-dq-rpg-prototype");
        Directory.CreateDirectory(reportDir);
        WriteRpgGdUnitFailureReport(reportDir);
    }

    private static void SeedRpgGdUnitFailureReportForCommand(HostedProcessCommand command)
    {
        var relativeReportDir = command.Arguments.SkipWhile(arg => arg != "--rd").Skip(1).FirstOrDefault();
        if (string.IsNullOrWhiteSpace(relativeReportDir))
        {
            return;
        }

        var reportDir = Path.Combine(command.WorkingDirectory, relativeReportDir.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(reportDir);
        WriteRpgGdUnitFailureReport(reportDir);
    }

    private static void WriteRpgGdUnitFailureReport(string reportDir)
    {
        File.WriteAllText(Path.Combine(reportDir, "run-summary.json"), """
{"rc":100,"normalized_rc":100,"strict_exit_code":false,"results":{"tests":6,"failures":27,"errors":0},"prewarm_rc":0,"prewarm_attempts":1}
""");
        File.WriteAllText(Path.Combine(reportDir, "gdunit-console.txt"), """
res://tests/Prototype/DqRpgPrototype/test_dq_rpg_prototype_scene.gd > test_map_scene_moves_player_and_reaches_first_encounter_with_traversal FAILED
Report:
  Expecting:
  'Position (9, 1)  Encounter chance 80%'
  do contains
  'Encounter ready'
res://tests/Prototype/DqRpgPrototype/test_dq_rpg_prototype_scene.gd > test_full_first_loop_proves_scene_switching_from_start_to_reward_and_back FAILED
Report:
  Expecting:
  'Use WASD to move. Watch encounter chance and step progress in the map panel until battle triggers.'
  do contains
  'Read the three reward cards'
Report:
  Expecting:
  '- Adventure started.'
  do contains
  'BattleScene finished'
Statistics: 6 test cases | 0 errors | 27 failures | 0 flaky | 0 skipped | 0 orphans |
Exit code: 100
""");
    }

    private static JsonElement ReadPlanningAnalysis(string metaPath)
    {
        var path = Path.Combine(metaPath, "routes", "iteration-plan", "latest.json");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        return document.RootElement.GetProperty("planning_analysis").Clone();
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot, string? godotBin = null)
    {
        var values = new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["GODOT_BIN"] = string.IsNullOrWhiteSpace(godotBin) ? @"C:\Godot\Godot.exe" : godotBin
        };

        return PhaseAPlatformOptionsLoader.FromDictionary(values);
    }

    private static void EnsureRpgAcceptanceMarkers(string repoPath)
    {
        var testProjectRoot = Path.Combine(repoPath, "Game.Core.Tests");
        Directory.CreateDirectory(testProjectRoot);
        File.WriteAllText(Path.Combine(testProjectRoot, "Game.Core.Tests.csproj"), """
<Project Sdk="Microsoft.NET.Sdk">
</Project>
""");
        File.WriteAllText(Path.Combine(repoPath, "GodotGame.csproj"), """
<Project Sdk="Microsoft.NET.Sdk">
</Project>
""");

        var testsPath = Path.Combine(repoPath, "Game.Core.Tests", "Prototypes");
        Directory.CreateDirectory(testsPath);
        File.WriteAllText(Path.Combine(testsPath, "DqRpgPrototypeLoopTests.cs"), """
public sealed class DqRpgPrototypeLoopTests
{
    // Objective: Start Adventure, learn the town context, and enter the first field.
    public void MoveOnMap() { }
    public void ShouldReachRewardPhase_AfterWinningTheFirstEncounter() { }
    public void ResolveAttackTurn() { }
    public void BattlesWon() { }
    public void Victory() { }
    public void ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward() { }
    // RewardOptions.Count
    public void ApplyReward() { }
    // Battle reward selected
    // Return to the map
    // VictoryBattleCount
    // IsVictory
    // IsGameOver
}
""");

        var corePath = Path.Combine(repoPath, "Game.Core", "Prototypes");
        Directory.CreateDirectory(corePath);
        File.WriteAllText(Path.Combine(corePath, "DqRpgPrototypeLoop.cs"), """
public sealed class DqRpgPrototypeLoop
{
    public const string Objective = "Start Adventure, learn the town context, and enter the first field.";
    public const int StartingHp = 30;
    public const int StartingAtk = 10;
    public const int StartingDef = 2;
    public const int RewardHpBonus = 5;
    public const int RewardAtkBonus = 2;
    public const int RewardDefBonus = 1;
    public const int VictoryTargetBattles = 15;
    public const int RewardHealPercent = 10;
    public void MoveOnMap() { }
    public void ShouldReachRewardPhase_AfterWinningTheFirstEncounter() { }
    public void ResolveAttackTurn() { }
    public void BattlesWon() { }
    public void Victory() { }
    public void ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward() { }
    // RewardOptions.Count
    public void ApplyReward() { }
    // Battle reward selected
    // Return to the map
}
""");
    }

    private static void EnsureCoreTestsNeedPackageReferences(string repoPath)
    {
        var testProjectRoot = Path.Combine(repoPath, "Game.Core.Tests", "Domain");
        Directory.CreateDirectory(testProjectRoot);
        File.WriteAllText(Path.Combine(testProjectRoot, "PackageReferenceFailureTests.cs"), """
using FluentAssertions;
using Xunit;

namespace Game.Core.Tests.Domain;

public sealed class PackageReferenceFailureTests
{
    [Fact]
    public void UsesXunitAndFluentAssertions()
    {
        true.Should().BeTrue();
    }
}
""");
    }

    private static void RemoveCoreAcceptanceMarker(string repoPath, string marker)
    {
        foreach (var path in EnumerateCoreAcceptanceMarkerFiles(repoPath))
        {
            var text = File.ReadAllText(path);
            File.WriteAllText(path, text.Replace(marker, RemovedCoreAcceptanceMarker(marker), StringComparison.Ordinal));
        }
    }

    private static void RestoreCoreAcceptanceMarker(string repoPath, string marker)
    {
        foreach (var path in EnumerateCoreAcceptanceMarkerFiles(repoPath))
        {
            var text = File.ReadAllText(path);
            File.WriteAllText(path, text.Replace(RemovedCoreAcceptanceMarker(marker), marker, StringComparison.Ordinal));
        }
    }

    private static string RemovedCoreAcceptanceMarker(string marker)
    {
        return $"__REMOVED_CORE_ACCEPTANCE_MARKER_{marker.Length}__";
    }

    private static IEnumerable<string> EnumerateCoreAcceptanceMarkerFiles(string repoPath)
    {
        yield return Path.Combine(repoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs");
        yield return Path.Combine(repoPath, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs");
    }

    private static void EnsureRpgPrototypeContractValues(string metaPath)
    {
        var contractDir = Path.Combine(metaPath, "routes", "prototype-contract");
        Directory.CreateDirectory(contractDir);
        var payload = new
        {
            form_fields = new
            {
                success_criteria = new[]
                {
                    "Player starts with 30 HP, 10 ATK, 2 DEF.",
                    "Rewards can add 5 HP, 2 ATK, or 1 DEF.",
                    "Win after 15 battles.",
                    "Heal reward restores 10% HP."
                }
            }
        };
        File.WriteAllText(
            Path.Combine(contractDir, "latest.json"),
            JsonSerializer.Serialize(payload),
            System.Text.Encoding.UTF8);
    }

    private static void EnsureRpgSmokeSceneFile(string repoPath)
    {
        var scenePath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg");
        Directory.CreateDirectory(scenePath);
        File.WriteAllText(Path.Combine(scenePath, "DqRpgPrototype.tscn"), """
[gd_scene load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map_floor_tile.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="2"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="3"]

[node name="DqRpgPrototype" type="Node"]
[node name="StartButton" type="Button" parent="."]
text = "Start Adventure"
[node name="ObjectiveLabel" type="Label" parent="."]
text = "Objective: Start Adventure and find the village elder."
[node name="CanvasLayer" type="CanvasLayer" parent="."]
[node name="UI" type="Control" parent="CanvasLayer"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
[node name="MapScene" parent="CanvasLayer/UI"]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
[node name="RpgMapAsset" type="TextureRect" parent="MapScene"]
texture = ExtResource("1")
[node name="RpgPlayerAsset" type="TextureRect" parent="MapScene"]
texture = ExtResource("2")
[node name="RpgEnemyAsset" type="TextureRect" parent="MapScene"]
texture = ExtResource("3")
""");
        File.WriteAllText(Path.Combine(scenePath, "MapScene.tscn"), """
[gd_scene load_steps=5 format=3]

[ext_resource type="Script" path="res://Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs" id="script_map"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map_floor_tile.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="2"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="3"]

[node name="MapScene" type="Control"]
script = ExtResource("script_map")
custom_minimum_size = Vector2(700, 700)
[node name="TrackLayer" type="Control" parent="."]
custom_minimum_size = Vector2(600, 600)
[node name="RpgMapAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
custom_minimum_size = Vector2(600, 600)
texture = ExtResource("1")
[node name="Grid" type="GridContainer" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
[node name="Overlay" type="Control" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
[node name="RpgPlayerAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay"]
texture = ExtResource("2")
[node name="RpgEnemyAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay"]
texture = ExtResource("3")
""");
        File.WriteAllText(Path.Combine(scenePath, "BattleScene.tscn"), """
[gd_scene load_steps=3 format=3]

[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="2"]
[node name="BattleScene" type="Node"]
[node name="AttackButton" type="Button" parent="."]
text = "Attack"
[node name="RpgPlayerAsset" type="TextureRect" parent="."]
texture = ExtResource("1")
[node name="RpgEnemyAsset" type="TextureRect" parent="."]
texture = ExtResource("2")
""");
        var scriptPath = Path.Combine(scenePath, "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), "public sealed class DqRpgPrototype { void Ready() { _mapScene = GetNode<MapScene>(\"CanvasLayer/UI/MapScene\"); StartButton.Pressed += ShowMapScene; _mapScene.Visible = true; } void ShowMapScene() {} void ShowRewardScene(object rewards) {} void OnBattleFinished(bool isVictory, System.Collections.Generic.IReadOnlyList<object> rewards) { if (rewards.Count > 0) { ShowRewardScene(rewards); return; } ShowMapScene(); } }\n");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), "public sealed class MapScene { object TrackLayer; public event System.Action? EncounterEntered; void MovePlayer() { GridToPosition(); } void GridToPosition() {} void ShowRewardReturnStatus() { _player.Visible = true; } dynamic _player; }\n");
        File.WriteAllText(Path.Combine(scriptPath, "BattleScene.cs"), "public sealed class BattleScene { public event System.Action? BattleFinished; void ResolveBattle() { ResolveAttackTurn(); } void ResolveAttackTurn() {} }\n");
        var catalogPath = Path.Combine(repoPath, "Game.Godot", "Scripts", "Prototypes");
        Directory.CreateDirectory(catalogPath);
        File.WriteAllText(Path.Combine(catalogPath, "PrototypeCatalog.cs"), """
public static class PrototypeCatalog
{
    public const string DqRpgPrototypeScenePath = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn";
}
""");
        var mainScenePath = Path.Combine(repoPath, "Game.Godot", "Scenes");
        Directory.CreateDirectory(mainScenePath);
        WriteMainScene(repoPath, hidePrototypeHostUi: true);
        var dqAssetPath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Assets");
        Directory.CreateDirectory(dqAssetPath);
        foreach (var assetFile in new[] { "map_floor_tile.png", "player_hero.png", "enemy_slime.png" })
        {
            File.WriteAllText(Path.Combine(dqAssetPath, assetFile), "asset");
        }

        foreach (var (assetDir, assetFile) in new[] { ("Map", "map_tile.png"), ("Player", "player_hero.png"), ("Enemy", "enemy_slime.png") })
        {
            var path = Path.Combine(repoPath, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "Assets", assetDir);
            Directory.CreateDirectory(path);
            File.WriteAllText(Path.Combine(path, assetFile), "asset");
        }
    }

    private static void WritePrototypeSmokeState(ProjectSnapshot project)
    {
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
    }

    private static void RemoveStepOneMapSizeAndPlayerVisibilityContract(string repoPath)
    {
        var mapScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn");
        var sceneText = File.ReadAllText(mapScene);
        sceneText = sceneText
            .Replace("custom_minimum_size = Vector2(700, 700)\n", "", StringComparison.Ordinal)
            .Replace("custom_minimum_size = Vector2(600, 600)\n", "", StringComparison.Ordinal);
        File.WriteAllText(mapScene, sceneText);

        var mapScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs");
        var scriptText = File.ReadAllText(mapScript);
        scriptText = scriptText
            .Replace("ShowRewardReturnStatus() { _player.Visible = true; } dynamic _player;", "ShowRewardReturnStatus() { }", StringComparison.Ordinal);
        File.WriteAllText(mapScript, scriptText);
    }

    private static void SeedRecoveredPrototypeFiles(string repoPath, string slug)
    {
        var prototypeDir = Path.Combine(repoPath, "Game.Godot", "Prototypes", slug);
        Directory.CreateDirectory(prototypeDir);
        File.WriteAllText(Path.Combine(prototypeDir, $"{slug}Prototype.tscn"), "[gd_scene format=3]\n\n[node name=\"Prototype\" type=\"Node\"]\n");

        var docsDir = Path.Combine(repoPath, "docs", "prototypes");
        Directory.CreateDirectory(docsDir);
        File.WriteAllText(Path.Combine(docsDir, $"2026-06-22-{slug}.md"), $"# Prototype: {slug}\n");
        File.WriteAllText(Path.Combine(docsDir, $"{slug}.prototype.json"), $$"""
{
  "schema_version": 1,
  "kind": "prototype-spec",
  "slug": "{{slug}}",
  "prototype_type_kit": {
    "manifest": {
      "default_scene": "res://Game.Godot/Prototypes/{{slug}}/{{slug}}Prototype.tscn"
    }
  }
}
""");

        var contractDir = Path.Combine(repoPath, "routes", "prototype-contract");
        Directory.CreateDirectory(contractDir);
        File.WriteAllText(Path.Combine(contractDir, "latest.json"), "{}");
    }

    private static void EnsurePrototypeSmokeSceneFile(string repoPath, string slug, string sceneFileName)
    {
        var prototypeDir = Path.Combine(repoPath, "Game.Godot", "Prototypes", slug);
        Directory.CreateDirectory(prototypeDir);
        File.WriteAllText(Path.Combine(prototypeDir, sceneFileName), "[gd_scene format=3]\n\n[node name=\"Prototype\" type=\"Node\"]\n");
    }

    private static object[] BuildRecoveredRepairSteps()
    {
        return
        [
            new { day = 1, title = "Recovered workflow step 01", status = "ok", record = "docs/prototypes/2026-06-22-Towerdemo.md" },
            new { day = 2, title = "Recovered workflow step 02", status = "ok", prototype_spec = "docs/prototypes/Towerdemo.prototype.json" },
            new { day = 3, title = "Recovered workflow step 03", status = "ok" },
            new { day = 4, title = "Recovered workflow step 04", status = "ok" },
            new { day = 5, title = "Recovered workflow step 05", status = "ok" },
            new { day = 6, title = "Recovered workflow step 06", status = "ok" },
            new { day = 7, title = "Recovered workflow step 07", status = "ok" }
        ];
    }

    private static async Task<ProtectedCompletionRecoveryScenario> CreateProtectedCompletionRecoveryScenarioAsync(
        int completedThroughDay,
        bool includeRepairSteps,
        bool includeActiveState,
        string? activeStatePrototypeRecord = null,
        string? activeStatePrototypeSpec = null,
        string? activeStateSmokeScene = null,
        bool includeSecondGoal = false)
    {
        var database = TempSqliteDatabase.Create();
        var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        SeedRecoveredPrototypeFiles(project!.RepoPath, "Towerdemo");
        if (includeActiveState)
        {
            WriteRecoveredActivePrototypeState(
                project.RepoPath,
                "Towerdemo",
                activeStatePrototypeRecord,
                activeStatePrototypeSpec,
                activeStateSmokeScene);
        }

        var writer = new PrototypeRouteStateWriter();
        writer.WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            run_id = "failed-run",
            status = "failed",
            prototype_completion = new
            {
                succeeded = false,
                error = "prototype_completion_state_missing"
            }
        });
        writer.WritePrototypeRepairState(project, new
        {
            route = "prototype-repair",
            status = "completed_with_protected_latest_blocker",
            fixed_intent = new[] { "prototype_completion_state_missing" },
            remaining = new[] { "prototype latest state file is protected from overwrite in the current focused workspace" },
            prototype_record = "docs/prototypes/2026-06-22-Towerdemo.md",
            prototype_contract = "routes/prototype-contract/latest.json",
            smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn",
            prototype_completion = new
            {
                succeeded = true,
                status = "completed",
                completed_through_day = completedThroughDay,
                error = (string?)null,
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn",
                completion_summary = completedThroughDay >= 7 ? "Towerdemo prototype route has recovered completion evidence." : "Only partially recovered.",
                steps_run = includeRepairSteps ? BuildRecoveredRepairSteps() : null
            },
            steps_run = includeRepairSteps ? BuildRecoveredRepairSteps() : null
        });
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "repair_plan",
            "prototype_completion_state_missing",
            "Repair prototype completion evidence.",
            includeSecondGoal
                ? [
                    new ProjectIterationGoalCreateCommand(
                        1,
                        "恢复原型运行证据",
                        "恢复路由完成证据，并消除 prototype_completion_state_missing。",
                        "最新失败原因已经消除，并且原型路由可以生成完成证据。"),
                    new ProjectIterationGoalCreateCommand(
                        2,
                        "修复通用原型合同缺口",
                        "Continue only after completion evidence is recovered.",
                        "Contract gaps are fixed.")
                ]
                : [
                    new ProjectIterationGoalCreateCommand(
                        1,
                        "恢复原型运行证据",
                        "恢复路由完成证据，并消除 prototype_completion_state_missing。",
                        "最新失败原因已经消除，并且原型路由可以生成完成证据。")
                ]);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "needs_fix", 1, "Goal 1 needs repair.");
        var details = await store.GetLatestProjectIterationSessionAsync(projectId, "repair_plan");
        var targetGoal = details!.Goals[0];
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "prototype_completion_state_missing", null);
        return new ProtectedCompletionRecoveryScenario(database, workspaceRoot, repoRoot, options, store, accountId, projectId, project, writer, details, targetGoal);
    }

    private static void WriteRecoveredActivePrototypeState(
        string repoPath,
        string slug,
        string? prototypeRecordOverride = null,
        string? prototypeSpecOverride = null,
        string? smokeSceneOverride = null)
    {
        var activeDir = Path.Combine(repoPath, "logs", "ci", "active-prototypes");
        Directory.CreateDirectory(activeDir);
        var prototypeRecord = prototypeRecordOverride ?? $"docs/prototypes/2026-06-22-{slug}.md";
        var prototypeSpec = prototypeSpecOverride ?? $"docs/prototypes/{slug}.prototype.json";
        var smokeScene = smokeSceneOverride ?? $"res://Game.Godot/Prototypes/{slug}/{slug}Prototype.tscn";
        File.WriteAllText(Path.Combine(activeDir, $"{slug}.active.json"), $$"""
{
  "status": "completed-through-day",
  "prototype_file": "{{prototypeRecord}}",
  "prototype_spec": "{{prototypeSpec}}",
  "smoke_scene": "{{smokeScene}}",
  "completed_through_day": 7,
  "missing_required_fields": [],
  "completion_summary": "Recovered from existing active state.",
  "steps_run": [
    { "day": 1, "title": "Recovered workflow step 01", "status": "ok", "record": "{{prototypeRecord}}" },
    { "day": 2, "title": "Recovered workflow step 02", "status": "ok", "prototype_spec": "{{prototypeSpec}}" },
    { "day": 3, "title": "Recovered workflow step 03", "status": "ok" },
    { "day": 4, "title": "Recovered workflow step 04", "status": "ok" },
    { "day": 5, "title": "Recovered workflow step 05", "status": "ok" },
    { "day": 6, "title": "Recovered workflow step 06", "status": "ok" },
    { "day": 7, "title": "Recovered workflow step 07", "status": "ok" }
  ]
}
""");
    }

    private static void WriteMainScene(string repoPath, bool hidePrototypeHostUi)
    {
        var mainScenePath = Path.Combine(repoPath, "Game.Godot", "Scenes");
        Directory.CreateDirectory(mainScenePath);
        var visibility = hidePrototypeHostUi ? "visible = false\n" : "";
        File.WriteAllText(Path.Combine(mainScenePath, "Main.tscn"), $$"""
[gd_scene format=3]

[node name="Main" type="Control"]

[node name="ScreenRoot" type="Control" parent="."]
{{visibility}}layout_mode = 3

[node name="Overlays" type="Control" parent="."]
{{visibility}}layout_mode = 3

[node name="VBox" type="VBoxContainer" parent="."]
{{visibility}}layout_mode = 2
""");
    }

    private static bool HasScriptArgument(HostedProcessCommand command, string scriptFileName)
    {
        return command.Arguments.Any(argument =>
            string.Equals(Path.GetFileName(argument), scriptFileName, StringComparison.OrdinalIgnoreCase) ||
            argument.Replace('\\', '/').EndsWith("/" + scriptFileName, StringComparison.OrdinalIgnoreCase));
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "Quick fix applied.");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class QuickFixNavigationFailHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: rpg_map_visible_markers_missing_after_start"));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Quick fix attempted.
CHANGED: Updated prototype start routing.
VERIFY: Re-run platform validation.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class QuickFixMissingSmokeSceneHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Missing smoke scene still needs repair.
CHANGED: Recorded missing smoke scene context.
VERIFY: Re-run Godot smoke after creating a playable scene path.
REMAINING: Create or register the prototype smoke scene.
""");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class QuickFixGodotSmokeTimeoutHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                if (!_codexStarted)
                {
                    throw new OperationCanceledException(cancellationToken);
                }

                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: rpg_map_visible_markers_missing_after_start"));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Godot smoke still needs repair.
CHANGED: Recorded the timeout condition.
VERIFY: Godot smoke timed out before runtime proof.
REMAINING: Continue fixing the current Godot smoke timeout.
""");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class GoalRepairSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "command ok", ""));
            }

            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前目标修复已完成。
玩家现在可以稳定移动，并且能够明确触发第一次遇敌。
地图中的第一次遇敌入口已经接通，本 step 现在已可继续。
ready to continue
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class FocusedWorkspaceEditRunner(Action<HostedProcessCommand> editWorkspace) : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "command ok", ""));
            }

            LastPrompt = command.StandardInput ?? "";
            editWorkspace(command);
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Focused workspace edit completed.
CHANGED: Updated managed RPG prototype files.
VERIFY: Godot gameplay verification passed for map movement and first encounter trigger.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairStep5HostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            if (HasScriptArgument(command, "run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "GDUNIT_DONE rc=0", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Goal 5 is repaired.
CHANGED: Updated the reward loop.
VERIFY: Platform acceptance validation passed for the current gameplay goal.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairStepOneBehaviorGdUnitFailRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            if (HasScriptArgument(command, "run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(100, """
                    Expecting:
                     'Use WASD to explore the map.' do contains 'Read the three reward cards'
                    Statistics: 6 test cases | 0 errors | 27 failures
                    Exit code: 100
                    """, ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Goal 1 asset/import repair is complete.
CHANGED: Fixed resource import setup for the RPG test project.
VERIFY: Platform acceptance validation passed for the current gameplay goal.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairStepOneInfrastructureGdUnitFailRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            if (HasScriptArgument(command, "run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(1, """
                    ERROR: Failed loading resource: res://Game.Godot/Prototypes/dq-rpg/Assets/Map/showcase_map_overworld.png.
                    ERROR: res://Game.Godot/Prototypes/dq-rpg/MapScene.tscn Parse Error: [ext_resource] referenced non-existent resource.
                    ERROR: Node not found: Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer.
                    GDUNIT_DONE rc=1
                    """, ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Goal 1 asset/import repair attempted.
CHANGED: Updated resource import setup for the RPG test project.
VERIFY: Platform acceptance validation passed for the current gameplay goal.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairFinalGdUnitFailRunner : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            if (HasScriptArgument(command, "run_gdunit.py"))
            {
                SeedRpgGdUnitFailureReportForCommand(command);
                return Task.FromResult(new HostedProcessResult(0, "GDUNIT_DONE rc=1", ""));
            }

            LastPrompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
            STATUS: completed
            SUMMARY: Final RPG repair attempted.
            CHANGED: Updated final RPG validation target.
            VERIFY: Platform acceptance validation passed for the current gameplay goal.
            REMAINING: none
            """);
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairStaleGodotNeedsFixButSmokePassRunner : IHostedProcessRunner
    {
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return _codexStarted
                    ? Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", ""))
                    : Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: stale focus warning before repair"));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Godot smoke still needs repair.
CHANGED: Fixed the focus mode issue.
VERIFY: Godot crashed before runtime proof.
REMAINING: Current step still needs repair because Godot failed to open 'user://logs/godot.log'.
""");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", "ERROR: Failed to open 'user://logs/godot.log'."));
        }
    }

    private sealed class StructuredCompletedHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Current step is repaired through structured status.
CHANGED: Step repair completed.
VERIFY: Godot gameplay verification passed for map movement and first encounter trigger.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class StructuredCompletedButMissingGameplayVerificationHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Platform route tests passed, but gameplay acceptance is not verified.
CHANGED: Route recovery behavior was adjusted.
VERIFY: Platform tests passed.
REMAINING: none

还没有做的是 Godot 侧对地图移动稳定、明确进入第一次遇敌的业务验收。
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairNeedsFixHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前 step 仍需修复。
还有 remaining blocker。
not ready
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class CoreTestPackageFailurePromptRunner : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(
                    1,
                    "",
                    "Game.Core.Tests/Domain/PackageReferenceFailureTests.cs(1,7): error CS0246: The type or namespace name 'FluentAssertions' could not be found. Game.Core.Tests/Domain/PackageReferenceFailureTests.cs(2,7): error CS0246: The type or namespace name 'Xunit' could not be found."));
            }

            if (HasScriptArgument(command, "smoke_headless.py") ||
                HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py") ||
                HasScriptArgument(command, "run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "validation pass", ""));
            }

            LastPrompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Core test package references still need repair.
CHANGED: none
VERIFY: package restore still blocked.
REMAINING: repair Game.Core.Tests.csproj package references
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class AbsolutePathCoreTestPackageFailurePromptRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(
                    1,
                    "",
                    @"C:\jimuyun\logs\phase-a-innernet\workspaces\account\project\repo\Game.Core.Tests\Domain\GameConfigTests.cs(1,7): error CS0246: The type or namespace name 'FluentAssertions' could not be found [C:\jimuyun\logs\phase-a-innernet\workspaces\account\project\repo\Game.Core.Tests\Game.Core.Tests.csproj]
C:\jimuyun\logs\phase-a-innernet\workspaces\account\project\repo\Game.Core.Tests\Domain\PlayerTests.cs(2,7): error CS0246: The type or namespace name 'Xunit' could not be found [C:\jimuyun\logs\phase-a-innernet\workspaces\account\project\repo\Game.Core.Tests\Game.Core.Tests.csproj]"));
            }

            if (HasScriptArgument(command, "smoke_headless.py") ||
                HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py") ||
                HasScriptArgument(command, "run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "validation pass", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: The repair pass updated the current goal.
CHANGED: Updated hosted files.
VERIFY: Await platform validation.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class CoreCompileFailurePromptRunner : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(
                    1,
                    "",
                    "Game.Core/Prototypes/DqRpgPrototypeLoop.cs(202,99): error CS1061: 'DqRpgPrototypeState' does not contain a definition for 'PlayerX'. Game.Core/Prototypes/DqRpgPrototypeLoop.cs(202,116): error CS1061: 'DqRpgPrototypeState' does not contain a definition for 'PlayerY'."));
            }

            if (HasScriptArgument(command, "smoke_headless.py") ||
                HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py") ||
                HasScriptArgument(command, "run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "validation pass", ""));
            }

            LastPrompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Core compile errors still need repair.
CHANGED: none
VERIFY: core compile still blocked.
REMAINING: repair DqRpgPrototypeLoop.cs PlayerX/PlayerY compile errors
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class MsBuildProjectExtensionsPathFailurePromptRunner : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(
                    1,
                    "",
                    "Microsoft.Common.CurrentVersion.targets(873,5): error MSB3540: The value of the property \"MSBuildProjectExtensionsPath\" was modified after it was used by MSBuild which can lead to unexpected build results."));
            }

            if (HasScriptArgument(command, "smoke_headless.py") ||
                HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py") ||
                HasScriptArgument(command, "run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "validation pass", ""));
            }

            LastPrompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: MSBuildProjectExtensionsPath still needs repair.
CHANGED: none
VERIFY: core compile still blocked.
REMAINING: remove late MSBuildProjectExtensionsPath properties
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class TimeoutHostedProcessRunner : IHostedProcessRunner
    {
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
            return new HostedProcessResult(0, "", "");
        }
    }

    private sealed class TimedOutValidatedGoalRepairRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                if (!_codexStarted)
                {
                    return Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: missing map asset before repair"));
                }

                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", ""));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Map navigation is repaired.
CHANGED: Updated RPG map entry wiring.
            VERIFY: Godot gameplay verification passed for map movement and first encounter trigger.
REMAINING: none
""");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class TimedOutSmokeFailingGoalRepairRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(14, "", _codexStarted
                    ? "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: rpg_map_visible_markers_missing_after_timeout"
                    : "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: missing map asset before repair"));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Map navigation repair was attempted.
CHANGED: Updated RPG map entry wiring.
VERIFY: Godot gameplay verification was attempted.
REMAINING: none
""");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class ImmediateCanceledHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class OffTopicSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            LastPrompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前目标修复已完成。
本 step 现在已可继续。
我更新了部署脚本、文档和安全测试。
ready to continue
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class CompletionRecoveryNeedsFixRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: The completion state still needs platform recovery.
CHANGED: Wrote prototype-repair recovery evidence.
VERIFY: Platform should promote the trusted repair evidence.
REMAINING: canonical active prototype state is protected from overwrite.
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed record ProtectedCompletionRecoveryScenario(
        TempSqliteDatabase Database,
        TempDirectory WorkspaceRoot,
        TempDirectory RepoRoot,
        PhaseAPlatformOptions Options,
        PhaseAMetadataStore Store,
        string AccountId,
        string ProjectId,
        ProjectSnapshot Project,
        PrototypeRouteStateWriter Writer,
        ProjectIterationSessionDetails Details,
        ProjectIterationGoalSnapshot TargetGoal) : IDisposable
    {
        public void Dispose()
        {
            RepoRoot.Dispose();
            WorkspaceRoot.Dispose();
            Database.Dispose();
        }
    }

    private sealed class CancelCallerThenReturnHostedProcessRunner : IHostedProcessRunner
    {
        private readonly CancellationTokenSource _callerCancellation;

        public CancelCallerThenReturnHostedProcessRunner(CancellationTokenSource callerCancellation)
        {
            _callerCancellation = callerCancellation;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS", ""));
            }

            _callerCancellation.Cancel();
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "Quick fix applied after caller disconnect.");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
