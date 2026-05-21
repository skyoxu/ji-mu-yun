using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeWorkflowTests
{
    [Fact]
    public void MissingRequiredFields_TracksPrototypeLaneIntakeFields()
    {
        var request = new PrototypeWorkflowRequest(null, null, null, null, null, null, null, null, null, null, null);

        var missing = PrototypeWorkflowValidation.MissingRequiredFields(request);

        missing.Should().Equal(
            "slug",
            "hypothesis",
            "core_player_fantasy",
            "minimum_playable_loop",
            "success_criteria",
            "game_feature",
            "core_gameplay_loop",
            "win_fail_conditions");
    }

    [Fact]
    public void CommandBuilder_DelegatesToRunPrototypeWorkflow()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeWorkflowCommandBuilder(options);

        var command = builder.Build(ValidRequest(confirm: true), "docs/prototypes/2026-05-11-demo.md", @"C:\project-repo");

        command.WorkingDirectory.Should().Be(@"C:\project-repo");
        command.Arguments.Should().ContainInOrder(
            "-3",
            "scripts/python/dev_cli.py",
            "run-prototype-workflow",
            "--prototype-file",
            "docs/prototypes/2026-05-11-demo.md",
            "--confirm",
            "--stop-after-day",
            "7",
            "--godot-bin",
            @"C:\Godot\Godot.exe");
        command.Environment["GODOT_BIN"].Should().Be(@"C:\Godot\Godot.exe");
        command.Environment["PHASEA_CODEX_DEFAULT_MODEL"].Should().Be("gpt-5.5");
        command.Environment["PHASEA_CODEX_REASONING_EFFORT"].Should().Be("high");
    }

    [Fact]
    public async Task RunAsync_WritesPrototypeRecord_RunsRouter_AndIndexesPrototypeArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: false));

        result.Status.Should().Be("succeeded");
        result.PrototypeRecordPath.Should().StartWith("docs/prototypes/");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var recordPath = Path.Combine(project!.RepoPath, result.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar));
        File.Exists(recordPath).Should().BeTrue();
        var record = File.ReadAllText(recordPath);
        record.Should().Contain("- Game Name: Demo Game");
        record.Should().Contain("- Game Type: rpg");
        record.Should().Contain("- Game Type Source: 勇者斗恶龙");
        runner.Commands.Should().HaveCount(3);
        runner.Commands[0].WorkingDirectory.Should().Be(project.RepoPath);
        runner.Commands[0].Arguments.Should().Contain("run-prototype-workflow");
        runner.Commands[1].WorkingDirectory.Should().Be(project.RepoPath);
        runner.Commands[1].Arguments.Should().Contain("scripts/python/smoke_headless.py");
        runner.Commands[1].Arguments.Should().Contain(["--strict"]);
        runner.Commands[1].Arguments.Should().Contain("res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn");
        runner.Commands[2].WorkingDirectory.Should().Be(project.RepoPath);
        runner.Commands[2].Arguments.Should().Contain("scripts/python/prototype_main_menu_navigation_smoke.py");
        runner.Commands[2].Arguments.Should().Contain("res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn");
        result.Artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-record",
            "prototype-sidecar-json",
            "active-prototype-json",
            "prototype-packaging-summary",
            "prototype-completion-report"
        ]);

        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.RunType.Should().Be("prototype-7day-playable");
        run.Status.Should().Be("succeeded");
        run.ProgressStep.Should().Be("succeeded");
        run.EvidenceJson.Should().Contain("prototype_artifacts");
        run.EvidenceJson.Should().Contain("prototype_contract");
        run.EvidenceJson.Should().Contain("godot_smoke");
        run.StdoutText.Should().Contain("SMOKE PASS");
        var contract = new PrototypeContractService().Read(project);
        contract.Json.Should().Contain("project-specific source of truth");
        contract.Json.Should().Contain("One-room tactical combat.");
        contract.Json.Should().Contain("Move, choose action, resolve enemy response.");
        contract.Json.Should().Contain("Win by defeating enemy; fail when health reaches zero.");
        new PrototypeRouteStateWriter().ReadLatestPrototypeState(project).Should().Contain("prototype_contract");
    }

    [Fact]
    public async Task RunAsync_SeedsFrozenRpgTemplateBaseline_OnFirstRpgPrototypeRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        SeedRepoRpgTemplate(repoRoot.Path);
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var project = await store.GetProjectSnapshotAsync(projectId);

        result.Status.Should().Be("succeeded");
        File.Exists(Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "DefaultRpgPrototype.tscn")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "Game.Core", "Prototypes", "DefaultRpgPrototypeLoop.cs")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DefaultRpgPrototypeLoopTests.cs")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DefaultRpgPrototype", "test_default_rpg_prototype_scene.gd")).Should().BeTrue();
    }

    [Fact]
    public async Task RunAsync_DoesNotOverwriteExistingFrozenRpgTemplateBaseline()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        SeedRepoRpgTemplate(repoRoot.Path);
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var existingScene = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "DefaultRpgPrototype.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(existingScene)!);
        File.WriteAllText(existingScene, "user-owned-scene\n");
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("succeeded");
        File.ReadAllText(existingScene).Should().Be("user-owned-scene\n");
    }

    [Fact]
    public async Task RunAsync_FailsWhenCompletionStateIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(writeActiveState: false);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("prototype_completion_state_missing");
    }

    [Fact]
    public async Task RunAsync_DoesNotMaskWorkflowFailure_WithMissingCompletionStateNoise()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            workflowExitCode: 1,
            writeActiveState: false,
            workflowStderrOverride: "PROTOTYPE_TDD status=unexpected_red stage=green expected=pass");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("unexpected_red");
        run.StderrText.Should().NotContain("prototype_completion_state_missing");
    }

    [Fact]
    public async Task RunAsync_MapsUnexpectedGreenRedStageToStrictTddFailureMessage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            workflowExitCode: 1,
            writeActiveState: false,
            workflowStdoutOverride: "PROTOTYPE_TDD status=unexpected_green stage=red expected=fail out=logs/ci/demo");
        var service = Service(store, options, runner);

        _ = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var progress = await service.GetProgressAsync(projectId);

        progress.Status.Should().Be("failed");
        progress.Failure.Should().Be("TDD 红灯阶段未出现预期失败，当前原型不符合严格 TDD 预期。");
    }

    [Fact]
    public async Task RunAsync_FailsWhenStep03SkippedBecausePrototypeRedIsAlreadyGreen()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(skippedDays: [3]);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        var progress = await service.GetProgressAsync(projectId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("prototype_completion_step_not_ok:3:skipped");
        progress.Failure.Should().Be("TDD 红灯阶段未出现预期失败，当前原型不符合严格 TDD 预期。");
        runner.Commands.Should().HaveCount(1);
    }

    [Fact]
    public async Task RunAsync_FailsWhenMainMenuCannotNavigateToPrototypeScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(mainMenuNavigationExitCode: 9, mainMenuNavigationStderrOverride: "MAIN_MENU_PROTOTYPE_NAV FAIL prototype_scene_not_loaded");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var progress = await service.GetProgressAsync(projectId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StdoutText.Should().Contain("SMOKE PASS");
        run.StderrText.Should().Contain("MAIN_MENU_PROTOTYPE_NAV FAIL");
        progress.Status.Should().Be("failed");
        progress.Failure.Should().Be("Main.tscn 未能通过主菜单“原型”入口跳转到本次创建的原型场景。");
    }

    [Fact]
    public async Task RunAsync_AllowsStep02SkippedWhenPrototypeScaffoldAlreadyExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(skippedDays: [2]);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.Status.Should().Be("succeeded");
        run.StderrText.Should().NotContain("prototype_completion_step_not_ok:2:skipped");
    }

    [Fact]
    public async Task RunAsync_AllowsPrototypeSmokeNonZeroExit_WhenOutputContainsSmokePass()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(smokeExitCode: 1, smokeStdoutOverride: "SMOKE PASS (any output)\n");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.Status.Should().Be("succeeded");
        run.StdoutText.Should().Contain("SMOKE PASS");
    }

    [Fact]
    public async Task RunAsync_FailsWhenResolvedPrototypeSceneIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(writePrototypeScene: false);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var progress = await service.GetProgressAsync(projectId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("prototype_valid_godot_scene_missing");
        progress.Status.Should().Be("failed");
        progress.Failure.Should().Be("没有创建有效的godot场景文件");
        runner.Commands.Should().HaveCount(1);
    }

    [Fact]
    public async Task RunAsync_FailsWhenStep06Or07ArtifactsAreMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(writePackagingArtifacts: false);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("prototype_packaging_summary_missing");
    }

    [Fact]
    public async Task GetProgressAsync_ReturnsLatestPrototypeWorkflowProgress()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var idle = await service.GetProgressAsync(projectId);
        var result = await service.RunAsync(projectId, ValidRequest(confirm: false));
        var finished = await service.GetProgressAsync(projectId);

        idle.Status.Should().Be("idle");
        finished.Status.Should().Be("succeeded");
        finished.Step.Should().Be("succeeded");
        finished.RunId.Should().Be(result.RunId);
        finished.CompletionSummary.Should().Contain("下一步建议");
        finished.DefaultScene.Should().Be("res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn");
        finished.DefaultSceneLabel.Should().Be("DemoPrototypePrototype 场景");
        finished.TddSummaryCount.Should().Be(1);
        finished.TddRedCount.Should().Be(0);
        finished.TddGreenCount.Should().Be(1);
        finished.TddRefactorCount.Should().Be(0);
        finished.PlaytestFocusPoints.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public async Task QueueAsync_BlocksWhenProjectRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var lockRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        (await store.TryAcquireRunnerLockAsync(projectId, lockRunId)).Should().BeTrue();
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("project_busy");
        result.ExitCode.Should().Be(423);
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task QueueAsync_UsesLatestDraftToRepairMissingOrCorruptedFields()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var draftRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        await store.UpsertProjectPrototypeDraftAsync(
            projectId,
            "succeeded",
            draftRunId,
            "rpg.txt",
            "dq-rpg",
            "复古rpg加肉鸽成长",
            "成长的不确定性和可选择性，是否能过boss",
            "地图移动，概率撞怪，打赢怪物，选择成长",
            "[\"奖励3选1可以正确理解\"]",
            "地图场景用wsad自由连续移动",
            "地图场景玩家可以自由移动",
            "打赢15场战斗赢得游戏胜利",
            "[]",
            "[]",
            null,
            10,
            100);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(projectId, new PrototypeWorkflowRequest(
            Slug: "",
            GameName: null,
            GameType: null,
            GameTypeSource: null,
            Hypothesis: "??rpg?????",
            CorePlayerFantasy: "",
            MinimumPlayableLoop: "",
            SuccessCriteria: ["30?????"],
            GameFeature: "????????????",
            CoreGameplayLoop: "",
            WinFailConditions: "",
            Confirm: true));

        await WaitForCommandsAsync(runner, 3);
        var queuedRun = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");
        result.Status.Should().Be("queued");
        var record = File.ReadAllText(Path.Combine(project!.RepoPath, result.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar)), System.Text.Encoding.UTF8);
        record.Should().Contain("复古rpg加肉鸽成长");
        record.Should().Contain("奖励3选1可以正确理解");
        record.Should().NotContain("??");
        queuedRun.Status.Should().Be("succeeded");
    }

    [Fact]
    public async Task RepairAsync_QueuesRepairFromLatestFailedPrototypeRecord()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var failedRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            1,
            "",
            "first failure",
            "{\"prototype_record\":\"docs/prototypes/2026-05-12-demo-prototype.md\",\"slug\":\"demo-prototype\"}");
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 3);
        var repairRun = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        result.PrototypeRecordPath.Should().Be("docs/prototypes/2026-05-12-demo-prototype.md");
        runner.Commands[0].Arguments.Should().Contain("run-prototype-workflow");
        runner.Commands[0].Arguments.Should().Contain("docs/prototypes/2026-05-12-demo-prototype.md");
        runner.Commands[0].Environment["PHASEA_CODEX_DEFAULT_MODEL"].Should().Be("gpt-5.4");
        repairRun!.Status.Should().Be("succeeded");
        repairRun.EvidenceJson.Should().Contain("\"repair\":true");
    }

    [Fact]
    public async Task RepairAsync_UsesSlugFromPrototypeRecordContent_WhenPathSlugDiffers()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var prototypeRecordPath = "docs/prototypes/2026-05-14-rpgdemo1.md";
        WritePrototypeRecord(project!.RepoPath, prototypeRecordPath, "# Prototype: dq-rpg\n");
        var failedRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            1,
            "",
            "first failure",
            $"{{\"prototype_record\":\"{prototypeRecordPath}\",\"slug\":\"rpgdemo1\"}}");
        var runner = new FakeHostedProcessRunner(completedThroughDay: 7);
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 3);
        var repairRun = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        runner.Commands[0].Arguments.Should().Contain(["--prototype-file", prototypeRecordPath]);
        repairRun!.Status.Should().Be("succeeded");
        repairRun.EvidenceJson.Should().Contain("\"slug\":\"dq-rpg\"");
    }

    [Fact]
    public async Task RepairAsync_RequiresLatestPrototypeRunToBeFailed()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var failedRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            1,
            "",
            "first failure",
            "{\"prototype_record\":\"docs/prototypes/2026-05-12-demo-prototype.md\",\"slug\":\"demo-prototype\"}");
        var succeededRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(succeededRunId);
        await store.CompleteRunAsync(
            succeededRunId,
            "succeeded",
            0,
            "ok",
            "",
            "{\"prototype_record\":\"docs/prototypes/2026-05-12-demo-prototype.md\",\"slug\":\"demo-prototype\"}");
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(projectId, new PrototypeRepairRequest("gpt-5.4"));

        result.Status.Should().Be("prototype_repair_not_available");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_RequiresLlmBinding_ForCodexScoring()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var result = await service.RunAsync(projectId, ValidRequest() with { ScoreEngine = "codex" });

        result.Status.Should().Be("llm_binding_required");
        result.ExitCode.Should().Be(402);
    }

    [Fact]
    public async Task RunAsync_RecordsLlmAudit_WhenCodexScoringIsBoundAndAllowed()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var accountId = (await store.GetProjectSnapshotAsync(projectId))!.AccountId;
        await new LlmBindingService(store, options).BindAsync(accountId, new LlmBindingRequest(
            "new-api",
            "https://new-api.example.com/v1",
            "new-api-user-1",
            "host-secret:new-api-user-1"));
        var service = Service(store, options, new FakeHostedProcessRunner());

        var result = await service.RunAsync(projectId, ValidRequest() with { ScoreEngine = "codex" });
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.LlmGateway.Should().Be("new-api");
        run.LlmModel.Should().Be("codex");
        run.LlmCostJson.Should().Contain("estimated_cost_cny");
    }

    [Fact]
    public void ProjectRuleCatalog_DoesNotExposeChapter3ThroughChapter7()
    {
        var rule = new ProjectRuleCatalog().Find(ProjectRuleCatalog.DefaultRuleId)!;

        rule.AllowedWorkflows.Should().NotContain(["chapter3", "chapter4", "chapter5", "chapter6", "chapter7"]);
    }

    private static PrototypeWorkflowRequest ValidRequest(bool confirm = false)
    {
        return new PrototypeWorkflowRequest(
            Slug: "demo-prototype",
            GameName: "Demo Game",
            GameType: null,
            GameTypeSource: null,
            Hypothesis: "A tiny loop can prove the combat fantasy.",
            CorePlayerFantasy: "Player feels tactical pressure in one minute.",
            MinimumPlayableLoop: "Enter room, fight one enemy, win or fail.",
            SuccessCriteria: ["Player completes one loop.", "Outcome is clear."],
            GameFeature: "One-room tactical combat.",
            CoreGameplayLoop: "Move, choose action, resolve enemy response.",
            WinFailConditions: "Win by defeating enemy; fail when health reaches zero.",
            Confirm: confirm);
    }

    private static async Task<PhaseAMetadataStore> CreateStoreAsync(string connectionString, PhaseAPlatformOptions options)
    {
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var store = new PhaseAMetadataStore(connectionString, options);
        await store.EnsureSingleAdminAsync();
        return store;
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string gameName = "Demo Game", string gameTypeSource = "勇者斗恶龙")
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, gameName, gameTypeSource, null, null, null, null));
        return result.ProjectId!;
    }

    private static void SeedRepoRpgTemplate(string repoRoot)
    {
        static void Write(string path, string content)
        {
            var parent = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(parent))
            {
                Directory.CreateDirectory(parent);
            }

            File.WriteAllText(path, content);
        }

        Write(
            Path.Combine(repoRoot, "docs", "prototype-type-kits", "game-type-template-catalog.json"),
            """
            {
              "schema_version": 1,
              "entries": [
                {
                  "game_type": "rpg",
                  "template_id": "default-rpg-template",
                  "source_mode": "repo-imported",
                  "repo_template_path": "Game.Godot/Prototypes/DefaultRpgTemplate",
                  "manifest_path": "docs/prototype-type-kits/default-rpg-template.manifest.json",
                  "import_source_path": "C:/gametype/rpgdemo",
                  "enabled": true
                }
              ]
            }
            """);
        Write(
            Path.Combine(repoRoot, "docs", "prototype-type-kits", "default-rpg-template.manifest.json"),
            """
            {
              "schema_version": 1,
              "game_type": "rpg",
              "slug": "default-rpg-template",
              "paths": {
                "default_scene": "Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn"
              }
            }
            """);
        Write(
            Path.Combine(repoRoot, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "DefaultRpgPrototype.tscn"),
            "[gd_scene format=3]\n[node name=\"DefaultRpgPrototype\" type=\"Node2D\"]\n");
        Write(
            Path.Combine(repoRoot, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "Scripts", "DefaultRpgPrototype.cs"),
            "public partial class DefaultRpgPrototype : Godot.Node2D {}\n");
        Write(
            Path.Combine(repoRoot, "Game.Core", "Prototypes", "DefaultRpgPrototypeLoop.cs"),
            "public sealed class DefaultRpgPrototypeLoop {}\n");
        Write(
            Path.Combine(repoRoot, "Game.Core.Tests", "Prototypes", "DefaultRpgPrototypeLoopTests.cs"),
            "public sealed class DefaultRpgPrototypeLoopTests {}\n");
        Write(
            Path.Combine(repoRoot, "Tests.Godot", "tests", "Prototype", "DefaultRpgPrototype", "test_default_rpg_prototype_scene.gd"),
            "extends Node\n");
    }

    private static PrototypeWorkflowService Service(PhaseAMetadataStore store, PhaseAPlatformOptions options, IHostedProcessRunner runner)
    {
        return new PrototypeWorkflowService(
            store,
            options,
            runner,
            new PrototypeRecordWriter(options),
            new PrototypeWorkflowCommandBuilder(options),
            new PrototypeArtifactIndexer(),
            new LlmBindingService(store, options),
            new LlmStopLossService(store, options));
    }

    private static async Task WaitForCommandsAsync(FakeHostedProcessRunner runner, int expectedCount)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        while (runner.Commands.Count < expectedCount && DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(50);
        }

        runner.Commands.Should().HaveCount(expectedCount);
    }

    private static async Task<RunSnapshot> WaitForRunStatusAsync(
        PhaseAMetadataStore store,
        string runId,
        string expectedStatus,
        string? expectedProgressStep = null)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        RunSnapshot? run = null;
        while (DateTimeOffset.UtcNow < deadline)
        {
            run = await store.GetRunSnapshotAsync(runId);
            if (run?.Status == expectedStatus &&
                (expectedProgressStep is null || run.ProgressStep == expectedProgressStep))
            {
                return run;
            }

            await Task.Delay(50);
        }

        run.Should().NotBeNull();
        run!.Status.Should().Be(expectedStatus);
        if (expectedProgressStep is not null)
        {
            run.ProgressStep.Should().Be(expectedProgressStep);
        }

        return run;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly int _completedThroughDay;
        private readonly bool _writeActiveState;
        private readonly HashSet<int> _skippedDays;
        private readonly bool _writePrototypeScene;
        private readonly string? _prototypeSceneOverride;
        private readonly int _smokeExitCode;
        private readonly bool _writePackagingArtifacts;
        private readonly string? _smokeStdoutOverride;
        private readonly int _mainMenuNavigationExitCode;
        private readonly string? _mainMenuNavigationStdoutOverride;
        private readonly string? _mainMenuNavigationStderrOverride;
        private readonly int _workflowExitCode;
        private readonly string? _workflowStdoutOverride;
        private readonly string? _workflowStderrOverride;

        public FakeHostedProcessRunner(
            int completedThroughDay = 7,
            bool writeActiveState = true,
            IEnumerable<int>? skippedDays = null,
            bool writePrototypeScene = true,
            string? prototypeSceneOverride = null,
            int smokeExitCode = 0,
            bool writePackagingArtifacts = true,
            string? smokeStdoutOverride = null,
            int mainMenuNavigationExitCode = 0,
            string? mainMenuNavigationStdoutOverride = null,
            string? mainMenuNavigationStderrOverride = null,
            int workflowExitCode = 0,
            string? workflowStdoutOverride = null,
            string? workflowStderrOverride = null)
        {
            _completedThroughDay = completedThroughDay;
            _writeActiveState = writeActiveState;
            _skippedDays = skippedDays is null ? [] : new HashSet<int>(skippedDays);
            _writePrototypeScene = writePrototypeScene;
            _prototypeSceneOverride = prototypeSceneOverride;
            _smokeExitCode = smokeExitCode;
            _writePackagingArtifacts = writePackagingArtifacts;
            _smokeStdoutOverride = smokeStdoutOverride;
            _mainMenuNavigationExitCode = mainMenuNavigationExitCode;
            _mainMenuNavigationStdoutOverride = mainMenuNavigationStdoutOverride;
            _mainMenuNavigationStderrOverride = mainMenuNavigationStderrOverride;
            _workflowExitCode = workflowExitCode;
            _workflowStdoutOverride = workflowStdoutOverride;
            _workflowStderrOverride = workflowStderrOverride;
        }

        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(
                    _smokeExitCode,
                    _smokeStdoutOverride ?? (_smokeExitCode == 0 ? "SMOKE PASS (marker)\n" : ""),
                    _smokeExitCode == 0 ? "" : "SMOKE FAIL\n"));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(
                    _mainMenuNavigationExitCode,
                    _mainMenuNavigationStdoutOverride ?? (_mainMenuNavigationExitCode == 0 ? "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn\n" : ""),
                    _mainMenuNavigationStderrOverride ?? (_mainMenuNavigationExitCode == 0 ? "" : "MAIN_MENU_PROTOTYPE_NAV FAIL\n")));
            }

            var slug = ExtractSlug(command.Arguments, command.WorkingDirectory) ?? "demo-prototype";
            var scenePath = _prototypeSceneOverride ?? BuildPrototypeScene(slug);
            Write(
                $"docs/prototypes/{slug}.prototype.json",
                $$"""
                {
                  "prototype_type_kit": {
                    "manifest": {
                      "paths": {
                        "default_scene": "{{scenePath}}"
                      }
                    }
                  }
                }
                """);
            if (_writePrototypeScene)
            {
                Write(scenePath["res://".Length..].Replace('/', Path.DirectorySeparatorChar), "[gd_scene format=3]\n");
            }
            if (_writePackagingArtifacts)
            {
                Write(
                    $"logs/ci/active-prototypes/{slug}.packaging.json",
                    $$"""
                    {
                      "kind": "prototype-packaging-summary",
                      "default_scene": "{{scenePath}}",
                      "default_scene_label": "DemoPrototypePrototype 场景",
                      "tdd_summary_paths": [
                        "logs/ci/2026-05-14/prototype-tdd-{{slug}}-green/summary.json"
                      ],
                      "tdd_stage_counts": {
                        "red": 0,
                        "green": 1,
                        "refactor": 0
                      },
                      "playtest_focus_points": [
                        "首分钟是否知道目标。",
                        "操作反馈是否清楚。"
                      ]
                    }
                    """);
                Write($"logs/ci/active-prototypes/{slug}.completion.md", "# Prototype Completion Report\n");
            }
            if (_writeActiveState)
            {
                Write(
                    $"logs/ci/active-prototypes/{slug}.active.json",
                    $$"""
                    {
                      "status": "completed-through-day",
                      "completed_through_day": {{_completedThroughDay}},
                      "missing_required_fields": [],
                      "prototype_spec": "docs/prototypes/{{slug}}.prototype.json",
                      "completion_summary": "原型创建完成。\n\n下一步建议：继续试玩并记录反馈。",
                      "steps_run": [
                        { "day": 1, "status": "ok" },
                        { "day": 2, "status": "{{StepStatus(2)}}", "reason": "{{StepReason(2)}}" },
                        { "day": 3, "status": "{{StepStatus(3)}}", "reason": "{{StepReason(3)}}" },
                        { "day": 4, "status": "{{StepStatus(4)}}" },
                        { "day": 5, "status": "{{StepStatus(5)}}" },
                        { "day": 6, "status": "{{StepStatus(6)}}" },
                        { "day": 7, "status": "{{StepStatus(7)}}" }
                      ]
                    }
                    """);
            }
            Write("logs/ci/project-health/latest.html", "<html></html>");
            Write("logs/ci/project-health/latest.json", "{}");
            return Task.FromResult(new HostedProcessResult(
                _workflowExitCode,
                _workflowStdoutOverride ?? (_workflowExitCode == 0 ? "prototype workflow ok\n" : ""),
                _workflowStderrOverride ?? ""));
        }

        private string StepStatus(int day)
        {
            return _skippedDays.Contains(day) ? "skipped" : "ok";
        }

        private string StepReason(int day)
        {
            if (day == 2 && _skippedDays.Contains(day))
            {
                return "prototype_scaffold_already_exists";
            }

            return day == 3 && _skippedDays.Contains(day)
                ? "prototype_red_already_green"
                : "";
        }

        private static string BuildPrototypeScene(string slug)
        {
            var parts = slug.Split(['-', '_'], StringSplitOptions.RemoveEmptyEntries);
            var pascal = string.Concat(parts.Select(part => char.ToUpperInvariant(part[0]) + part[1..]));
            return $"res://Game.Godot/Prototypes/{slug}/{pascal}Prototype.tscn";
        }

        private static string? ExtractSlug(IReadOnlyList<string> arguments, string workingDirectory)
        {
            for (var i = 0; i < arguments.Count - 1; i++)
            {
                if (string.Equals(arguments[i], "--slug", StringComparison.Ordinal))
                {
                    return arguments[i + 1];
                }

                if (string.Equals(arguments[i], "--prototype-file", StringComparison.Ordinal))
                {
                    var path = Path.Combine(workingDirectory, arguments[i + 1].Replace('/', Path.DirectorySeparatorChar));
                    if (!File.Exists(path))
                    {
                        continue;
                    }

                    var firstLine = File.ReadLines(path).FirstOrDefault()?.Trim().TrimStart('\ufeff');
                    if (!string.IsNullOrWhiteSpace(firstLine) &&
                        firstLine.StartsWith("# Prototype:", StringComparison.OrdinalIgnoreCase))
                    {
                        return firstLine["# Prototype:".Length..].Trim();
                    }
                }
            }

            return null;
        }

        private void Write(string relativePath, string text)
        {
            var path = Path.Combine(Commands[^1].WorkingDirectory, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, text);
        }
    }

    private static void WritePrototypeRecord(string repoPath, string relativePath, string text)
    {
        var path = Path.Combine(repoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
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
