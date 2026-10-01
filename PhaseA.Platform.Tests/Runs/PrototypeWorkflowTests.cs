using FluentAssertions;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeWorkflowTests : IDisposable
{
    private readonly IDisposable routeProfileOverride = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(false);

    public void Dispose()
    {
        routeProfileOverride.Dispose();
    }

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
    public void RecordWriter_ResolvesChineseOrGenericSlugToProjectScopedFallback()
    {
        PrototypeRecordWriter.ResolveProjectSlug("Towerdemo2", "abc123", "塔楼测试")
            .Should().Be("Towerdemo2");
        PrototypeRecordWriter.ResolveProjectSlug("prototype", "85d4fccdf6ca4980", "搜打撤的测试")
            .Should().Be("project-85d4fccd");
        PrototypeRecordWriter.ResolveProjectSlug("搜打撤的测试", "85d4fccdf6ca4980", "搜打撤的测试")
            .Should().Be("project-85d4fccd");
        PrototypeRecordWriter.ResolveProjectSlug("", "85d4fccdf6ca4980", "SDC 搜打撤")
            .Should().Be("SDC");
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
    public void GodotSmoke_NormalizesPrototypeScriptsInsideGameGodotNamespace()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var scriptPath = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "mir", "Scripts", "MirPrototype.cs");
        Directory.CreateDirectory(Path.GetDirectoryName(scriptPath)!);
        File.WriteAllText(scriptPath, """
        using Godot;

        namespace Game.Godot.Prototypes;

        public partial class MirPrototype : Node2D
        {
            public Godot.Collections.Array<string> RewardOptions
            {
                get
                {
                    var values = new Godot.Collections.Array<string>();
                    return values;
                }
            }
        }
        """);

        var changed = PrototypeGodotSmokeService.NormalizeGodotCSharpNamespaceAliases(repoRoot.Path);

        changed.Should().Equal("Game.Godot/Prototypes/mir/Scripts/MirPrototype.cs");
        var rewritten = File.ReadAllText(scriptPath);
        rewritten.Should().Contain("public global::Godot.Collections.Array<string> RewardOptions");
        rewritten.Should().Contain("new global::Godot.Collections.Array<string>()");
        rewritten.Should().NotContain("public Godot.Collections.Array<string>");
    }

    [Fact]
    public async Task GodotSmoke_PostPrototypeAcceptance_ShouldAllowNavigationPassAfterDirectSceneWarning()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(repoRoot.Path, repoRoot.Path);
        var runner = new FakeHostedProcessRunner(
            smokeExitCode: 14,
            smokeStdoutOverride: "",
            smokeStderrOverride: "Scene exited with a non-fatal warning.",
            mainMenuNavigationExitCode: 0);

        var result = await PrototypeGodotSmokeService.RunPostPrototypeAcceptanceAsync(
            options,
            runner,
            repoRoot.Path,
            "res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn");

        result.ExitCode.Should().Be(0);
        result.Reason.Should().Be("strict_headless_prototype_scene_warning_main_menu_navigation_passed");
        runner.Commands.Should().HaveCount(2);
        runner.Commands[0].Arguments.Should().Contain("scripts/python/smoke_headless.py");
        runner.Commands[1].Arguments.Should().Contain("scripts/python/prototype_main_menu_navigation_smoke.py");
    }

    [Fact]
    public async Task GodotSmoke_PostPrototypeAcceptance_ShouldFailWhenDirectSceneReportsSmokeFail()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(repoRoot.Path, repoRoot.Path);
        var runner = new FakeHostedProcessRunner(
            smokeExitCode: 1,
            smokeStdoutOverride: "SMOKE FAIL (runtime failure)\n",
            smokeStderrOverride: "",
            mainMenuNavigationExitCode: 0);

        var result = await PrototypeGodotSmokeService.RunPostPrototypeAcceptanceAsync(
            options,
            runner,
            repoRoot.Path,
            "res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn");

        result.ExitCode.Should().Be(1);
        result.Reason.Should().Be("strict_headless_prototype_scene");
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].Arguments.Should().Contain("scripts/python/smoke_headless.py");
    }

    [Fact]
    public void GodotSmokeEvidence_ShouldDiagnoseOnlyRuntimeResources_NotSceneLineMarkers()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var prototypeDir = Path.Combine(repoRoot.Path, "Game.Godot", "Prototypes", "dq-rpg");
        var assetDir = Path.Combine(prototypeDir, "Assets");
        Directory.CreateDirectory(assetDir);
        File.WriteAllText(Path.Combine(prototypeDir, "DqRpgPrototype.tscn"), "[gd_scene]\n");
        File.WriteAllText(Path.Combine(prototypeDir, "MapScene.tscn"), "[gd_scene]\n");
        File.WriteAllBytes(
            Path.Combine(assetDir, "map_player.png"),
            [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00]);
        var stderr = """
        ERROR: res://Game.Godot/Prototypes/dq-rpg/MapScene.tscn:46 - Parse Error: [ext_resource] referenced non-existent resource at: res://Game.Godot/Prototypes/dq-rpg/Assets/map_player.png.
        ERROR: No loader found for resource: res://Game.Godot/Prototypes/dq-rpg/Assets/map_player.png (expected type: Texture2D)
        C# backtrace (most recent call first):
        at: res://Game.Godot/Scripts/Main.gd:107
        ERROR: res://logs/phase-a-validation-temp/main-menu-navigation-smoke.gd:12 - Parse Error: smoke script
        """;
        var result = new PrototypeGodotSmokeResult(
            true,
            1,
            "",
            stderr,
            "prototype_main_menu_navigation_failed",
            "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn",
            repoRoot.Path);

        var json = System.Text.Json.JsonSerializer.Serialize(result.ToEvidence());
        using var document = System.Text.Json.JsonDocument.Parse(json);
        var resources = document.RootElement
            .GetProperty("resource_diagnostics")
            .EnumerateArray()
            .Select(item => item.GetProperty("resource_path").GetString())
            .ToArray();

        resources.Should().Equal("res://Game.Godot/Prototypes/dq-rpg/Assets/map_player.png");
        var diagnostic = document.RootElement.GetProperty("resource_diagnostics").EnumerateArray().Single();
        diagnostic.GetProperty("file_exists").GetBoolean().Should().BeTrue();
        diagnostic.GetProperty("import_exists").GetBoolean().Should().BeFalse();
        diagnostic.GetProperty("png_valid").GetBoolean().Should().BeTrue();
    }

    [Fact]
    public async Task RunAsync_WritesPrototypeRecord_RunsRouter_AndIndexesPrototypeArtifacts()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: false));

        result.Status.Should().Be("succeeded");
        result.PrototypeRecordPath.Should().StartWith("docs/prototypes/");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var recordPath = Path.Combine(project!.RepoPath, result.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar));
        File.Exists(recordPath).Should().BeTrue();
        var record = File.ReadAllText(recordPath);
        record.Should().Contain("- Game Name: Demo Game");
        record.Should().Contain("- Game Type: rpg");
        record.Should().Contain("- Game Type Source: 勇者斗恶龙");
        record.Should().Contain("## Prototype Input Contract");
        record.Should().Contain("Player-visible text inside the generated Godot game screen must default to Chinese");
        record.Should().Contain("Keep code identifiers, class names, method names, node names, resource paths, tests, logs, and platform-required fixed node names in English");
        record.Should().Contain("| Field | Value | Must Reflect In |");
        record.Should().Contain("| core_gameplay_loop | Move, choose action, resolve enemy response. | Map/battle/reward/control flow and loop continuity |");
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
        contract.Json.Should().Contain("\"input_traceability\"");
        contract.Json.Should().Contain("\"form_fields\"");
        contract.Json.Should().Contain("\"field\": \"slug\"");
        contract.Json.Should().Contain("\"field\": \"game_name\"");
        contract.Json.Should().Contain("\"field\": \"game_type\"");
        contract.Json.Should().Contain("\"field\": \"game_type_source\"");
        contract.Json.Should().Contain("\"field\": \"hypothesis\"");
        contract.Json.Should().Contain("\"field\": \"core_player_fantasy\"");
        contract.Json.Should().Contain("\"field\": \"minimum_playable_loop\"");
        contract.Json.Should().Contain("\"field\": \"success_criteria\"");
        contract.Json.Should().Contain("\"field\": \"game_feature\"");
        contract.Json.Should().Contain("\"field\": \"core_gameplay_loop\"");
        contract.Json.Should().Contain("\"field\": \"win_fail_conditions\"");
        contract.Json.Should().Contain("One-room tactical combat.");
        contract.Json.Should().Contain("Move, choose action, resolve enemy response.");
        contract.Json.Should().Contain("Win by defeating enemy; fail when health reaches zero.");
        new PrototypeRouteStateWriter().ReadLatestPrototypeState(project).Should().Contain("prototype_contract");
        var projectGuidePath = Path.Combine(project.RepoPath, PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath.Replace('/', Path.DirectorySeparatorChar));
        File.Exists(projectGuidePath).Should().BeTrue();
        var projectGuide = File.ReadAllText(projectGuidePath);
        projectGuide.Should().Contain("GameTypeId: rpg");
        projectGuide.Should().Contain("Downstream Source Boundary");
        projectGuide.Should().Contain("Only the GDD route may read broad game-type sources");
        projectGuide.Should().Contain("Do not read docs/game-type-guides");
        projectGuide.Should().NotContain("SkillId:");
        projectGuide.Should().NotContain("SkillPath:");
        projectGuide.Should().NotContain("SkillContractPath:");
        projectGuide.Should().Contain("Prototype Chapter 3/6 Lite Protocol");
        projectGuide.Should().Contain("does not create or validate formal acceptance files");
        projectGuide.Should().Contain("Route Recovery Protocol");
        projectGuide.Should().Contain("Do not use AGENTS.md as hosted project recovery memory");
    }

    [Fact]
    public async Task RunAsync_UsesProjectScopedSlug_WhenRequestedSlugWouldFallbackToPrototype()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options, "搜打撤的测试", "逃离鸭科夫");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var expectedSlug = PrototypeRecordWriter.ResolveProjectSlug("搜打撤的测试", projectId, "搜打撤的测试", project!.Name);
        var expectedScene = $"res://Game.Godot/Prototypes/{expectedSlug}/{ToPascalSlugForTest(expectedSlug)}Prototype.tscn";
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: false) with
        {
            Slug = "搜打撤的测试",
            GameName = "搜打撤的测试",
            GameType = "逃离鸭科夫",
            GameTypeSource = "逃离鸭科夫"
        });

        result.Status.Should().Be("succeeded");
        expectedSlug.Should().NotBe("prototype");
        result.PrototypeRecordPath.Should().Contain(expectedSlug);
        var record = File.ReadAllText(Path.Combine(project.RepoPath, result.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar)));
        record.Should().Contain($"# Prototype: {expectedSlug}");
        record.Should().Contain($"| slug | {expectedSlug} |");
        runner.Commands[1].Arguments.Should().Contain(expectedScene);
        runner.Commands[2].Arguments.Should().Contain(expectedScene);
        File.Exists(Path.Combine(project.RepoPath, "logs", "ci", "active-prototypes", $"{expectedSlug}.active.json")).Should().BeTrue();
    }

    [Fact]
    public async Task RunAsync_AllowsNavigationPassAfterDirectSceneWarning()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            smokeExitCode: 14,
            smokeStdoutOverride: "",
            smokeStderrOverride: "Scene exited with a non-fatal warning.",
            mainMenuNavigationExitCode: 0);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: false));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.Status.Should().Be("succeeded");
        run.EvidenceJson.Should().Contain("strict_headless_prototype_scene_warning_main_menu_navigation_passed");
        runner.Commands.Should().HaveCount(3);
        runner.Commands[1].Arguments.Should().Contain("scripts/python/smoke_headless.py");
        runner.Commands[2].Arguments.Should().Contain("scripts/python/prototype_main_menu_navigation_smoke.py");
    }

    [Fact]
    public async Task RunAsync_BlocksWhenProjectRunnerLockIsHeld()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var lockRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        (await store.TryAcquireRunnerLockAsync(projectId, lockRunId)).Should().BeTrue();
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("project_busy");
        result.ExitCode.Should().Be(423);
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_CompletesRunAndReleasesProjectLock_WhenRunnerThrows()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new ThrowingHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(500);
        run!.Status.Should().Be("failed");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        (await store.HasActiveRunAsync(projectId)).Should().BeFalse();
    }

    [Fact]
    public async Task QueueAsync_RejectsProjectOwnedByAnotherAccount()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (ownerAccountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var otherAccount = await store.CreateUserAccountAsync("workflow-other-account", 1);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var act = () => service.QueueAsync(otherAccount.AccountId, projectId, ValidRequest(confirm: true));

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Project not found.");
        runner.Commands.Should().BeEmpty();
        _ = ownerAccountId;
    }

    [Fact]
    public async Task QueueAsync_UsesDedicatedPrototypeCreationQueue()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var otherRunsQueue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
        var prototypeCreationQueue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
        var otherQueueCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var otherQueueStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var service = Service(store, options, runner, otherRunsQueue, prototypeCreationQueue);

        var occupiedOtherQueue = otherRunsQueue.ExecuteAsync(
            "other-run-1",
            accountId,
            projectId,
            "prototype-ui-optimization",
            async _ =>
            {
                otherQueueStarted.SetResult();
                await otherQueueCanFinish.Task;
                return true;
            });
        await otherQueueStarted.Task.WaitAsync(TimeSpan.FromSeconds(5));

        var result = await service.QueueAsync(accountId, projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("queued");
        await WaitForAtLeastCommandsAsync(runner, 1);

        otherQueueCanFinish.SetResult();
        await occupiedOtherQueue.WaitAsync(TimeSpan.FromSeconds(5));
        await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");
    }

    [Fact]
    public async Task QueueFromGddAsync_BlocksUntilGddExists()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var result = await service.QueueFromGddAsync(accountId, projectId, new PrototypeFromGddRequest());

        result.Status.Should().Be("gdd_not_found");
        result.ExitCode.Should().Be(404);
    }

    [Fact]
    public async Task QueueFromGddAsync_UsesCurrentProjectGddAsPrototypeSource()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options, "Phantom Tower Like", "Phantom Tower");
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteFile(Path.Combine(project!.RepoPath, "docs", "gdd", "GDD.md"), """
        # Phantom Tower Like

        ## Reference Game
        Reference game: Phantom Tower. Borrow third-person action roguelike pacing.

        ## Controls
        WASD movement, mouse facing, left click combo, space dodge, right/Q/E skills.

        ## Core Loop
        Enter a random dungeon room, fight waves, choose upgrades, preserve souls after death.

        ## Scenes
        Create a first dungeon room with player, enemy wave spawners, upgrade reward, HUD, and retry flow.

        ## Milestones
        M1 core combat, M2 active skills, M3 waves and upgrades. Adjust later steps after each playable validation.
        """);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueFromGddAsync(accountId, projectId, new PrototypeFromGddRequest(Model: "gpt-5.5"));
        await WaitForAtLeastCommandsAsync(runner, 1);
        var run = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        run.Status.Should().Be("succeeded");
        var record = File.ReadAllText(Path.Combine(project.RepoPath, result.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar)));
        record.Should().Contain("docs/gdd/GDD.md");
        record.Should().Contain("Source Document");
        record.Should().Contain("WASD movement");
        record.Should().Contain("M1 core combat");
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype", "STRUCTURE.md")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype", "MEMORY.md")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype", "ASSETS.md")).Should().BeTrue();
        Directory.EnumerateFiles(Path.Combine(project.RepoPath, "logs", "prototype-evidence", project.ProjectId), "evidence.json", SearchOption.AllDirectories)
            .Should().NotBeEmpty();
    }

    [Fact]
    public async Task QueueFromGddAsync_UsesProjectScopedSlug_WhenProjectNameIsChinese()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options, "搜打撤的测试", "逃离鸭科夫");
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteFile(Path.Combine(project!.RepoPath, "docs", "gdd", "GDD.md"), """
        # 搜打撤的测试

        ## Core Loop
        进入 raid，移动射击，搜箱，拾取核心物，撤离。

        ## Scenes
        首个场景包含玩家、障碍、普通箱、核心箱、敌人和撤离点。
        """);
        var expectedSlug = PrototypeRecordWriter.ResolveProjectSlug(project.GameName, projectId, project.GameName, project.Name);
        var expectedScene = $"res://Game.Godot/Prototypes/{expectedSlug}/{ToPascalSlugForTest(expectedSlug)}Prototype.tscn";
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueFromGddAsync(accountId, projectId, new PrototypeFromGddRequest(Model: "gpt-5.5"));
        await WaitForAtLeastCommandsAsync(runner, 1);
        var run = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        run.Status.Should().Be("succeeded");
        expectedSlug.Should().NotBe("prototype");
        result.PrototypeRecordPath.Should().Contain(expectedSlug);
        var record = File.ReadAllText(Path.Combine(project.RepoPath, result.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar)));
        record.Should().Contain($"# Prototype: {expectedSlug}");
        runner.Commands[1].Arguments.Should().Contain(expectedScene);
        runner.Commands[2].Arguments.Should().Contain(expectedScene);
        using var contractDocument = JsonDocument.Parse(File.ReadAllText(Path.Combine(project.RepoPath, "meta", "routes", "prototype-contract", "latest.json")));
        contractDocument.RootElement.GetProperty("local_entry_contract").GetProperty("expected_entry_scene").GetString()
            .Should().Be(expectedScene);
        using var stateDocument = JsonDocument.Parse(File.ReadAllText(Path.Combine(project.RepoPath, "meta", "routes", "prototype", "latest.json")));
        stateDocument.RootElement.GetProperty("default_scene").GetString().Should().Be(expectedScene);
        stateDocument.RootElement.GetProperty("smoke_scene").GetString().Should().Be(expectedScene);
        stateDocument.RootElement.GetProperty("playable_scene").GetString().Should().Be(expectedScene);
        stateDocument.RootElement.GetProperty("local_entry_contract").GetProperty("status").GetString().Should().Be("ready");
        File.ReadAllText(Path.Combine(project.RepoPath, "meta", "project-execution-guide.md"))
            .Should().Contain($"Local prototype entry scene: {expectedScene}")
            .And.Contain($"Local playable scene: {expectedScene}");
    }

    [Fact]
    public async Task QueueFromGddAsync_WritesPlayableScene_WhenEntrySceneInstancesInnerScene()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options, "Shell Demo", "Action Roguelike");
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteFile(Path.Combine(project!.RepoPath, "docs", "gdd", "GDD.md"), """
        # Shell Demo

        ## Core Loop
        Start from the local menu, enter a shell scene, then play the first raid scene.
        """);
        var expectedSlug = PrototypeRecordWriter.ResolveProjectSlug(project.GameName, projectId, project.GameName, project.Name);
        var entryScene = $"res://Game.Godot/Prototypes/{expectedSlug}/{ToPascalSlugForTest(expectedSlug)}Prototype.tscn";
        var playableScene = $"res://Game.Godot/Prototypes/{expectedSlug}/FirstPlayableRaid.tscn";
        var runner = new FakeHostedProcessRunner(
            prototypeSceneOverride: entryScene,
            instancedPlayableSceneOverride: playableScene);
        var service = Service(store, options, runner);

        var result = await service.QueueFromGddAsync(accountId, projectId, new PrototypeFromGddRequest(Model: "gpt-5.5"));
        await WaitForAtLeastCommandsAsync(runner, 1);
        await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        using var stateDocument = JsonDocument.Parse(File.ReadAllText(Path.Combine(project.RepoPath, "meta", "routes", "prototype", "latest.json")));
        stateDocument.RootElement.GetProperty("default_scene").GetString().Should().Be(entryScene);
        stateDocument.RootElement.GetProperty("smoke_scene").GetString().Should().Be(entryScene);
        stateDocument.RootElement.GetProperty("playable_scene").GetString().Should().Be(playableScene);
        stateDocument.RootElement.GetProperty("local_entry_contract").GetProperty("entry_scene_instances_playable_scene").GetBoolean().Should().BeTrue();
        File.ReadAllText(Path.Combine(project.RepoPath, "meta", "project-execution-guide.md"))
            .Should().Contain($"Local prototype entry scene: {entryScene}")
            .And.Contain($"Local playable scene: {playableScene}");
    }

    [Fact]
    public async Task QueueAsync_FailsCompletion_WhenSmokeSceneIsNotProjectSpecificEntryScene()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var wrongEntryScene = "res://Game.Godot/Prototypes/demo-prototype/GenericPrototype.tscn";
        var expectedEntryScene = "res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn";
        var runner = new FakeHostedProcessRunner(prototypeSceneOverride: wrongEntryScene);
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(accountId, projectId, ValidRequest(confirm: true));
        await WaitForAtLeastCommandsAsync(runner, 1);
        var run = await WaitForRunStatusAsync(store, result.RunId, "failed", "failed");

        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("prototype_project_entry_scene_mismatch");
        run.StderrText.Should().Contain(expectedEntryScene);
        using var stateDocument = JsonDocument.Parse(File.ReadAllText(Path.Combine(
            (await store.GetProjectSnapshotAsync(projectId))!.RepoPath,
            "meta",
            "routes",
            "prototype",
            "latest.json")));
        stateDocument.RootElement.GetProperty("status").GetString().Should().Be("failed");
        stateDocument.RootElement.GetProperty("prototype_completion").GetProperty("error").GetString()
            .Should().Contain("prototype_project_entry_scene_mismatch");
    }

    [Fact]
    public async Task QueueAsync_TimesOutInactivePrototypeCreationCodexAndReleasesProjectLock()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new InactiveTimeoutHostedProcessRunner();
        var service = Service(
            store,
            options,
            runner,
            creationTotalTimeout: TimeSpan.FromSeconds(5),
            creationInactivityTimeout: TimeSpan.FromMilliseconds(50));

        var result = await service.QueueAsync(accountId, projectId, ValidRequest(confirm: true));
        await WaitForInactiveTimeoutRunnerCommandAsync(runner);

        var run = await WaitForRunStatusAsync(store, result.RunId, "failed", "failed");

        run.ExitCode.Should().Be(408);
        run.StderrText.Should().Contain("no stdout, stderr, or watched file activity");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
    }

    [Fact]
    public async Task QueueAsync_ConfiguresPrototypeCreationActivityAndTotalTimeouts()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(accountId, projectId, ValidRequest(confirm: true));
        await WaitForAtLeastCommandsAsync(runner, 1);
        var run = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        var creationCommand = runner.Commands.First();
        creationCommand.TotalTimeout.Should().Be(TimeSpan.FromHours(1));
        creationCommand.InactivityTimeout.Should().Be(TimeSpan.FromMinutes(25));
        creationCommand.ActivityWatchPollInterval.Should().Be(TimeSpan.FromSeconds(10));
        creationCommand.ActivityWatchPaths.Should().NotBeNull();
        creationCommand.ActivityWatchPaths!.Should().Contain(Path.Combine("logs", "ci"));
        creationCommand.ActivityWatchPaths.Should().NotContain(Path.Combine("logs", "e2e"));
        creationCommand.ActivityWatchPaths.Should().Contain(Path.Combine("Game.Godot", "Prototypes"));
        run.Status.Should().Be("succeeded");
    }

    [Fact]
    public async Task GetProgressAsync_RejectsProjectOwnedByAnotherAccount()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (_, projectId) = await CreateProjectWithAccountAsync(store, options);
        var otherAccount = await store.CreateUserAccountAsync("workflow-progress-other", 1);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var act = () => service.GetProgressAsync(otherAccount.AccountId, projectId);

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Project not found.");
    }

    [Fact]
    public async Task QueueAsync_FailsPostCompletionDirectSmoke_WhenGodotReportsError()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            smokeExitCode: 1,
            smokeStderrOverride: "ERROR: Cannot instantiate C# script because the associated class could not be found.");
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(accountId, projectId, ValidRequest(confirm: true));
        await WaitForCommandsAsync(runner, 2);
        var run = await WaitForRunStatusAsync(store, result.RunId, "failed", "failed");

        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(1);
        run.EvidenceJson.Should().Contain("strict_headless_prototype_scene");
        runner.Commands[1].Arguments.Should().Contain("scripts/python/smoke_headless.py");
        runner.Commands.Should().NotContain(command => command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"));
    }

    [Fact]
    public void PrototypeContractPromptBlock_RequiresInputTraceabilityForAllTopLevelRoutes()
    {
        var contract = new PrototypeContractSnapshot(
            "routes/prototype-contract/latest.json",
            """
            {
              "form_fields": {
                "game_feature": "Each movement increases encounter chance by 10%.",
                "win_fail_conditions": "First enemy has 30 HP and 5 attack."
              },
              "input_traceability": [
                {
                  "field": "game_feature",
                  "route_rule": "Implement or explicitly preserve this field as a needs_fix blocker; do not silently drop it."
                }
              ]
            }
            """);

        var block = PrototypeContractService.BuildPromptBlock(contract);

        block.Should().Contain("consume form_fields and input_traceability");
        block.Should().Contain("planning, coding, validating, or repairing");
        block.Should().Contain("report needs_fix instead of succeeded");
        block.Should().Contain("Each movement increases encounter chance by 10%.");
        block.Should().Contain("First enemy has 30 HP and 5 attack.");
    }

    [Fact]
    public async Task RunAsync_SeedsFrozenRpgTemplateBaseline_OnFirstRpgPrototypeRun()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        SeedRepoRpgTemplate(repoRoot.Path);
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
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
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        SeedRepoRpgTemplate(repoRoot.Path);
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var existingScene = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "DefaultRpgPrototype.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(existingScene)!);
        File.WriteAllText(existingScene, "user-owned-scene\n");
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("succeeded");
        File.ReadAllText(existingScene).Should().Be("user-owned-scene\n");
    }

    [Fact]
    public async Task RunAsync_FailsWhenCompletionStateIsMissing()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(writeActiveState: false);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("prototype_completion_state_missing");
    }

    [Fact]
    public async Task RunAsync_DoesNotMaskWorkflowFailure_WithMissingCompletionStateNoise()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            workflowExitCode: 1,
            writeActiveState: false,
            workflowStderrOverride: "PROTOTYPE_TDD status=unexpected_red stage=green expected=pass");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("unexpected_red");
        run.StderrText.Should().NotContain("prototype_completion_state_missing");
    }

    [Fact]
    public async Task RunAsync_MapsUnexpectedGreenRedStageToStrictTddFailureMessage()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            workflowExitCode: 1,
            writeActiveState: false,
            workflowStdoutOverride: "PROTOTYPE_TDD status=unexpected_green stage=red expected=fail out=logs/ci/demo");
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var progress = await service.GetProgressAsync(accountId, projectId);

        progress.Status.Should().Be("failed");
        progress.Failure.Should().Be("TDD 红灯阶段未出现预期失败，当前原型不符合严格 TDD 预期。");
    }

    [Fact]
    public async Task RunAsync_AllowsStep03AndStep04SkippedWhenExistingPrototypeCanGoDirectlyToGreen()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(skippedDays: [3, 4]);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        var progress = await service.GetProgressAsync(accountId, projectId);

        result.Status.Should().Be("succeeded");
        run!.Status.Should().Be("succeeded");
        run.StderrText.Should().NotContain("prototype_completion_step_not_ok:3:skipped");
        run.StderrText.Should().NotContain("prototype_completion_step_not_ok:4:skipped");
        progress.Failure.Should().BeNullOrEmpty();
        runner.Commands.Should().Contain(command => command.Arguments.Contains("run-prototype-workflow"));
    }

    [Fact]
    public async Task RunAsync_FailsWhenMainMenuCannotNavigateToPrototypeScene()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(mainMenuNavigationExitCode: 9, mainMenuNavigationStderrOverride: "MAIN_MENU_PROTOTYPE_NAV FAIL prototype_scene_not_loaded");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var progress = await service.GetProgressAsync(accountId, projectId);

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
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(skippedDays: [2]);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.Status.Should().Be("succeeded");
        run.StderrText.Should().NotContain("prototype_completion_step_not_ok:2:skipped");
    }

    [Fact]
    public async Task RunAsync_AllowsPrototypeSmokeNonZeroExit_WhenOutputContainsSmokePass()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            smokeExitCode: 1,
            smokeStdoutOverride: "SMOKE PASS (any output)\n",
            smokeStderrOverride: "");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.Status.Should().Be("succeeded");
        run.StdoutText.Should().Contain("SMOKE PASS");
    }

    [Fact]
    public async Task RunAsync_FailsPrototypeSmoke_WhenGodotReportsErrorEvenWithSmokePass()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            smokeExitCode: 1,
            smokeStdoutOverride: "SMOKE PASS (any output)\n",
            smokeStderrOverride: "ERROR: No loader found for resource: res://Game.Godot/Prototypes/dq-rpg/Assets/Player/map_player.png\n");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StdoutText.Should().Contain("SMOKE PASS");
        run.StderrText.Should().Contain("No loader found for resource");
    }

    [Fact]
    public async Task RunAsync_FailsPrototypeSmoke_WhenGodotReportsErrorWithZeroExitCode()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            smokeExitCode: 0,
            smokeStdoutOverride: "SMOKE PASS (prototype scene alive)\n",
            smokeStderrOverride: "ERROR: res://Game.Godot/Examples/UI/ScorePanel.tscn:1 - Parse Error: Expected '['.\n");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("Parse Error");
    }

    [Fact]
    public async Task RunAsync_FailsWhenResolvedPrototypeSceneIsMissing()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(writePrototypeScene: false);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var progress = await service.GetProgressAsync(accountId, projectId);

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
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(writePackagingArtifacts: false);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("prototype_packaging_summary_missing");
    }

    [Fact]
    public async Task GetProgressAsync_ReturnsLatestPrototypeWorkflowProgress()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var idle = await service.GetProgressAsync(accountId, projectId);
        var result = await service.RunAsync(accountId, projectId, ValidRequest(confirm: false));
        var finished = await service.GetProgressAsync(accountId, projectId);

        idle.Status.Should().Be("idle");
        finished.Status.Should().Be("succeeded");
        finished.PrototypeCreationStatus.Should().Be("succeeded");
        finished.AcceptanceStatus.Should().BeNull();
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
        finished.Form.Should().NotBeNull();
        finished.Form!.PrototypeSlug.Should().Be("demo-prototype");
        finished.Form.Hypothesis.Should().Be("A tiny loop can prove the combat fantasy.");
        finished.Form.CorePlayerFantasy.Should().Be("Player feels tactical pressure in one minute.");
        finished.Form.MinimumPlayableLoop.Should().Be("Enter room, fight one enemy, win or fail.");
        finished.Form.SuccessCriteria.Should().Equal("Player completes one loop.", "Outcome is clear.");
        finished.Form.GameFeature.Should().Be("One-room tactical combat.");
        finished.Form.CoreGameplayLoop.Should().Be("Move, choose action, resolve enemy response.");
        finished.Form.WinFailConditions.Should().Be("Win by defeating enemy; fail when health reaches zero.");
        finished.Form.SourcePath.Should().StartWith("docs/prototypes/");
    }

    [Fact]
    public async Task GetProgressAsync_IgnoresFinalValidationFailureThatPredatesCompletedIteration()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var creation = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var failedRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            1,
            "",
            "old final validation failed",
            """{"validation_only":true,"prototype_completion":{"succeeded":false}}""");
        await Task.Delay(20);
        await CreateCompletedIterationPlanAsync(store, accountId, projectId);

        var progress = await service.GetProgressAsync(accountId, projectId);

        progress.Status.Should().Be("succeeded");
        progress.RunId.Should().Be(creation.RunId);
        progress.AcceptanceStatus.Should().BeNull();
        progress.AcceptanceRunId.Should().BeNull();
        progress.Failure.Should().BeNull();
    }

    [Fact]
    public async Task GetProgressAsync_RecoversRunningRun_WhenCompletionArtifactsExist()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = Service(store, options, new FakeHostedProcessRunner());
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.UpdateRunProgressAsync(runId, "running_step07_review", "", "任务 07：正在生成最终摘要。");
        var prototypeFile = "docs/prototypes/2026-06-03-demo-prototype.md";
        WriteFile(Path.Combine(project.RepoPath, prototypeFile.Replace('/', Path.DirectorySeparatorChar)), "# Demo prototype\n");
        WriteFile(Path.Combine(project.RepoPath, "docs/prototypes/demo-prototype.prototype.json"), """
        {
          "prototype_type_kit": {
            "manifest": {
              "paths": {
                "default_scene": "res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn"
              }
            }
          }
        }
        """);
        WriteFile(Path.Combine(project.RepoPath, "Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn".Replace('/', Path.DirectorySeparatorChar)), "[gd_scene format=3]\n");
        WriteFile(Path.Combine(project.RepoPath, "logs/ci/active-prototypes/demo-prototype.packaging.json".Replace('/', Path.DirectorySeparatorChar)), """
        {
          "kind": "prototype-packaging-summary",
          "default_scene": "res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn",
          "default_scene_label": "DemoPrototypePrototype 场景",
          "tdd_summary_paths": ["logs/ci/2026-06-03/prototype-tdd-demo-prototype-green/summary.json"],
          "tdd_stage_counts": { "red": 0, "green": 1, "refactor": 0 },
          "playtest_focus_points": ["确认首分钟目标。"]
        }
        """);
        WriteFile(Path.Combine(project.RepoPath, "logs/ci/active-prototypes/demo-prototype.completion.md".Replace('/', Path.DirectorySeparatorChar)), "# Prototype Completion Report\n");
        WriteFile(Path.Combine(project.RepoPath, "logs/ci/active-prototypes/demo-prototype.active.json".Replace('/', Path.DirectorySeparatorChar)), $$"""
        {
          "status": "completed-through-day",
          "completed_through_day": 7,
          "missing_required_fields": [],
          "prototype_file": "{{prototypeFile}}",
          "prototype_spec": "docs/prototypes/demo-prototype.prototype.json",
          "completion_summary": "原型创建完成。\n\n下一步建议：继续试玩。",
          "steps_run": [
            { "day": 1, "status": "ok" },
            { "day": 2, "status": "ok" },
            { "day": 3, "status": "ok" },
            { "day": 4, "status": "ok" },
            { "day": 5, "status": "ok" },
            { "day": 6, "status": "ok" },
            { "day": 7, "status": "ok" }
          ]
        }
        """);

        var progress = await service.GetProgressAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(runId);

        progress.Status.Should().Be("succeeded");
        progress.Step.Should().Be("succeeded");
        progress.Label.Should().Be("游戏场景创建已完成。");
        progress.CompletionSummary.Should().Contain("下一步建议");
        progress.DefaultScene.Should().Be("res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn");
        run!.Status.Should().Be("succeeded");
        run.EvidenceJson.Should().Contain("recovered_from_completion_artifacts");
    }

    [Fact]
    public async Task GetProgressAsync_DoesNotRecoverRepairRun_FromCompletionArtifacts()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = Service(store, options, new FakeHostedProcessRunner());
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.UpdateRunProgressAsync(runId, "repair", "", "Repair queued.");
        WriteFile(Path.Combine(project.RepoPath, "logs/ci/active-prototypes/demo-prototype.packaging.json".Replace('/', Path.DirectorySeparatorChar)), """
        {
          "kind": "prototype-packaging-summary",
          "default_scene": "res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn"
        }
        """);
        WriteFile(Path.Combine(project.RepoPath, "logs/ci/active-prototypes/demo-prototype.completion.md".Replace('/', Path.DirectorySeparatorChar)), "# Prototype Completion Report\n");
        WriteFile(Path.Combine(project.RepoPath, "logs/ci/active-prototypes/demo-prototype.active.json".Replace('/', Path.DirectorySeparatorChar)), """
        {
          "status": "completed-through-day",
          "completed_through_day": 7,
          "missing_required_fields": [],
          "prototype_file": "docs/prototypes/2026-06-03-demo-prototype.md",
          "steps_run": [
            { "day": 1, "status": "ok" },
            { "day": 2, "status": "ok" },
            { "day": 3, "status": "ok" },
            { "day": 4, "status": "ok" },
            { "day": 5, "status": "ok" },
            { "day": 6, "status": "ok" },
            { "day": 7, "status": "ok" }
          ]
        }
        """);

        var progress = await service.GetProgressAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(runId);

        progress.Status.Should().Be("running");
        progress.Step.Should().Be("repair");
        run!.Status.Should().Be("running");
        run.EvidenceJson.Should().BeNullOrEmpty();
    }

    [Fact]
    public async Task ValidateSkeletonAsync_RevalidatesExistingPrototypeWithoutRequiringIterationPlan()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        runner.Commands.Should().HaveCount(3);

        var result = await service.ValidateSkeletonAsync(accountId, projectId);
        var progress = await service.GetProgressAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        result.ExitCode.Should().Be(0);
        result.PrototypeRecordPath.Should().StartWith("docs/prototypes/");
        runner.Commands.Should().HaveCount(6);
        runner.Commands.Skip(3).SelectMany(command => command.Arguments).Should().NotContain("run-prototype-workflow");
        runner.Commands[3].Arguments.Should().Contain("scripts/python/smoke_headless.py");
        runner.Commands[4].Arguments.Should().Contain("scripts/python/prototype_main_menu_navigation_smoke.py");
        runner.Commands[5].Arguments.Should().Contain(["scripts/python/run_gdunit.py", "--add", "tests/Prototype/DemoPrototype"]);
        runner.Commands[5].Arguments.Should().Contain("--prewarm");
        run!.EvidenceJson.Should().Contain("\"validation_only\":true");
        run.EvidenceJson.Should().Contain("\"skeleton_validation_only\":true");
        run.EvidenceJson.Should().Contain("\"dotnet_build\"");
        run.EvidenceJson.Should().Contain("\"rpg_gdunit_validation\"");
        run.EvidenceJson.Should().Contain("\"passed\":true");
        run.Status.Should().Be("succeeded");
        progress.Status.Should().Be("succeeded");
        progress.RunId.Should().Be(result.RunId);
        progress.AcceptanceStatus.Should().BeNull();
        progress.AcceptanceRunId.Should().BeNull();
    }

    [Fact]
    public async Task ValidateSkeletonAsync_FailsWithDotnetBuildDiagnosticsBeforeSmoke()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(
            dotnetBuildExitCode: 1,
            dotnetBuildStdoutOverride: "Game.Core/Prototypes/Towerdemo2PrototypeLoop.cs(385,34): error CS8506: No best type was found for the switch expression.");
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        runner.Commands.Should().HaveCount(3);
        var project = await store.GetProjectSnapshotAsync(projectId);
        File.WriteAllText(Path.Combine(project!.RepoPath, "GodotGame.csproj"), "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>");

        var result = await service.ValidateSkeletonAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(1);
        result.Stderr.Should().Contain("CS8506");
        run!.StderrText.Should().Contain("CS8506");
        run.EvidenceJson.Should().Contain("\"dotnet_build\"");
        run.EvidenceJson.Should().Contain("\"passed\":false");
        runner.Commands.Should().HaveCount(4);
        runner.Commands[3].FileName.Should().Be("dotnet");
        runner.Commands[3].Arguments.Should().Contain("build");
        runner.Commands[3].Arguments.Should().Contain(argument => argument.Contains("UseSharedCompilation=false", StringComparison.Ordinal));
        runner.Commands[3].Arguments.Should().NotContain(argument => argument.Contains("BaseIntermediateOutputPath", StringComparison.Ordinal));
        runner.Commands.Skip(4).SelectMany(command => command.Arguments).Should().NotContain("scripts/python/smoke_headless.py");
    }

    [Fact]
    public async Task ValidateAsync_BlocksWhenIterationPlanIsMissing()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        runner.Commands.Should().HaveCount(3);

        var result = await service.ValidateAsync(accountId, projectId);

        result.Status.Should().Be("iteration_plan_not_complete");
        result.ExitCode.Should().Be(409);
        runner.Commands.Should().HaveCount(3);
    }

    [Fact]
    public async Task ValidateAsync_BlocksWhenProjectRunnerLockIsHeld()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);
        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        runner.Commands.Clear();
        var project = await store.GetProjectSnapshotAsync(projectId);
        var lockRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        (await store.TryAcquireRunnerLockAsync(projectId, lockRunId)).Should().BeTrue();

        var result = await service.ValidateAsync(accountId, projectId);

        result.Status.Should().Be("project_busy");
        result.ExitCode.Should().Be(423);
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task ValidateAsync_CompletesRunAndReleasesProjectLock_WhenRunnerThrows()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var setupRunner = new FakeHostedProcessRunner();
        var setupService = Service(store, options, setupRunner);
        _ = await setupService.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        await CreateCompletedIterationPlanAsync(store, accountId, projectId);
        var service = Service(store, options, new ThrowingHostedProcessRunner());

        var result = await service.ValidateAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(500);
        run!.Status.Should().Be("failed");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        (await store.HasActiveRunAsync(projectId)).Should().BeFalse();
    }

    [Fact]
    public async Task ValidateAsync_ShouldRunRpgAcceptanceAfterCompletedIterationPlanWithoutUiOptimization()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        await CreateCompletedIterationPlanAsync(store, accountId, projectId);

        var result = await service.ValidateAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        result.ExitCode.Should().Be(0);
        runner.Commands.Should().HaveCount(6);
        runner.Commands[5].Arguments.Should().Contain(["scripts/python/run_gdunit.py", "--add", "tests/Prototype/DemoPrototype"]);
        runner.Commands[5].Arguments.Should().Contain("--prewarm");
        run!.EvidenceJson.Should().Contain("\"rpg_gdunit_validation\"");
        run.EvidenceJson.Should().Contain("\"required\":true");
    }

    [Fact]
    public async Task ValidateAsync_ShouldKeepUiOptimizationCurrent_WhenOnlyIterationSessionEvaluationChanged()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        var session = await CreateCompletedIterationPlanAsync(store, accountId, projectId);
        await CreateSucceededUiOptimizationRunAsync(store, projectId);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "ready", 0, "Evaluation refreshed after UI optimization.", "{}");

        var result = await service.ValidateAsync(accountId, projectId);

        result.Status.Should().Be("succeeded");
        result.ExitCode.Should().Be(0);
        runner.Commands.Should().HaveCount(6);
    }

    [Fact]
    public async Task ValidateAsync_FailsRpgValidation_WhenProjectSpecificGdUnitFails()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(gdUnitExitCode: 1, gdUnitStderrOverride: "Node not found: CanvasLayer/UI/MapScene/RpgEnemyAsset");
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        await CreateCompletedIterationPlanAsync(store, accountId, projectId);
        runner.Commands.Should().HaveCount(3);

        var result = await service.ValidateAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var progress = await service.GetProgressAsync(accountId, projectId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(1);
        runner.Commands.Should().HaveCount(6);
        runner.Commands[5].Arguments.Should().Contain(["scripts/python/run_gdunit.py", "--add", "tests/Prototype/DemoPrototype"]);
        runner.Commands[5].Arguments.Should().Contain("--prewarm");
        run!.EvidenceJson.Should().Contain("\"rpg_gdunit_validation\"");
        run.EvidenceJson.Should().Contain("\"reason\":\"rpg_project_specific_gdunit_failed\"");
        run.StderrText.Should().Contain("RPG project-specific GdUnit validation failed");
        run.StderrText.Should().Contain("Node not found");
        progress.Status.Should().Be("failed");
        progress.PrototypeCreationStatus.Should().Be("succeeded");
        progress.PrototypeCreationRunId.Should().NotBeNullOrWhiteSpace();
        progress.AcceptanceStatus.Should().Be("failed");
        progress.AcceptanceRunId.Should().Be(result.RunId);
        progress.Label.Should().Be("RPG behavior validation failed. Generate or continue a repair plan before packaging.");
        progress.Form.Should().NotBeNull();
        progress.Form!.PrototypeSlug.Should().Be("demo-prototype");
    }

    [Fact]
    public async Task ValidateAsync_FailsRpgValidation_WhenGdUnitFindsNoTests()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(gdUnitStdoutOverride: "No test cases found");
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        await CreateCompletedIterationPlanAsync(store, accountId, projectId);

        var result = await service.ValidateAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(1);
        run!.EvidenceJson.Should().Contain("\"reason\":\"rpg_project_specific_gdunit_no_tests_found\"");
    }

    [Fact]
    public async Task ValidateAsync_FailsRpgValidation_WhenGdUnitWrapperReportsFailureInStdout()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner(gdUnitStdoutOverride: "GDUNIT_DONE rc=1 out=logs/e2e/2026-05-31");
        var service = Service(store, options, runner);

        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        await CreateCompletedIterationPlanAsync(store, accountId, projectId);

        var result = await service.ValidateAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(1);
        run!.EvidenceJson.Should().Contain("\"exit_code\":1");
        run.EvidenceJson.Should().Contain("\"reason\":\"rpg_project_specific_gdunit_failed\"");
    }

    [Fact]
    public async Task QueueAsync_BlocksWhenProjectRunnerLockIsHeld()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var lockRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        (await store.TryAcquireRunnerLockAsync(projectId, lockRunId)).Should().BeTrue();
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(accountId, projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("project_busy");
        result.ExitCode.Should().Be(423);
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task QueueAsync_BlocksWhenPrototypeSkeletonAlreadySucceeded()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);
        _ = await service.RunAsync(accountId, projectId, ValidRequest(confirm: true));
        runner.Commands.Clear();

        var result = await service.QueueAsync(accountId, projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("prototype_skeleton_locked");
        result.ExitCode.Should().Be(409);
        result.Progress.Should().NotBeNull();
        result.Progress!.PrototypeCreationStatus.Should().Be("succeeded");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task QueueAsync_UsesLatestDraftToRepairMissingOrCorruptedFields()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
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
            0,
            null,
            "[]",
            null,
            10,
            100);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(accountId, projectId, new PrototypeWorkflowRequest(
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
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
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

        var result = await service.RepairAsync(accountId, projectId, new PrototypeRepairRequest("gpt-5.4"));
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
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
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

        var result = await service.RepairAsync(accountId, projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 3);
        var repairRun = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        runner.Commands[0].Arguments.Should().Contain(["--prototype-file", prototypeRecordPath]);
        repairRun!.Status.Should().Be("succeeded");
        repairRun.EvidenceJson.Should().Contain("\"slug\":\"dq-rpg\"");
    }

    [Fact]
    public async Task RepairAsync_UsesPostValidationRepair_WhenCompletedPrototypeFailedSmoke()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var prototypeRecordPath = "docs/prototypes/2026-05-14-dq-rpg.md";
        WritePrototypeRecord(project!.RepoPath, prototypeRecordPath, "# Prototype: dq-rpg\n");
        var failedRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            10,
            "previous stdout",
            "MAIN_MENU_PROTOTYPE_NAV FAIL rpg_start_button_missing",
            $$"""
            {
              "prototype_record": "{{prototypeRecordPath}}",
              "slug": "dq-rpg",
              "prototype_completion": {
                "succeeded": true,
                "completed_through_day": 7,
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              },
              "godot_smoke": {
                "ran": true,
                "exit_code": 9,
                "reason": "prototype_main_menu_navigation_failed",
                "scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              }
        }
        """);
        var runner = new FakeHostedProcessRunner();
        var issuer = new HostedContextManifestIssuer(
            store,
            new HostedContextManifestSignatureService("test-key", new Dictionary<string, string>
            {
                ["test-key"] = "test-hosted-context-signing-secret"
            }));
        var validator = new CapturingManifestValidator();
        var policy = new HostedContextGatePolicy(new Dictionary<string, HostedContextGateMode>
        {
            ["codex:prototype-post-validation-repair"] = HostedContextGateMode.Enforce
        });
        var service = Service(store, options, runner, contextManifestIssuer: issuer, contextGatePolicy: policy, contextManifestValidator: validator);

        var result = await service.RepairAsync(accountId, projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 3);
        var repairRun = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        runner.Commands[0].Arguments.Should().Contain("exec");
        runner.Commands[0].Arguments.Should().NotContain("run-prototype-workflow");
        runner.Commands[0].StandardInput.Should().Contain("post-validation prototype repair");
        runner.Commands[0].StandardInput.Should().Contain("rpg_start_button_missing");
        repairRun!.Status.Should().Be("succeeded");
        repairRun.EvidenceJson.Should().Contain("\"repair_mode\":\"post_validation\"");
        validator.Envelope.Should().NotBeNull();
        validator.Envelope!.AccountId.Should().Be(accountId);
        validator.Envelope.ProjectId.Should().Be(projectId);
        validator.Envelope.OperationKey.Should().Be("codex:prototype-post-validation-repair");
        validator.Envelope.SignatureKeyId.Should().Be("test-key");
        validator.OperationKey.Should().Be("codex:prototype-post-validation-repair");
    }

    [Fact]
    public async Task RepairAsync_UsesOriginalPostValidationFailure_WhenLatestRepairFailed()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var prototypeRecordPath = "docs/prototypes/2026-05-14-dq-rpg.md";
        WritePrototypeRecord(project!.RepoPath, prototypeRecordPath, "# Prototype: dq-rpg\n");
        var originalFailureRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(originalFailureRunId);
        await store.CompleteRunAsync(
            originalFailureRunId,
            "failed",
            10,
            "previous stdout",
            "MAIN_MENU_PROTOTYPE_NAV FAIL rpg_start_button_missing",
            $$"""
            {
              "prototype_record": "{{prototypeRecordPath}}",
              "slug": "dq-rpg",
              "prototype_completion": {
                "succeeded": true,
                "completed_through_day": 7,
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              },
              "godot_smoke": {
                "ran": true,
                "exit_code": 9,
                "reason": "prototype_main_menu_navigation_failed",
                "scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              }
            }
            """);
        var failedRepairRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRepairRunId);
        await store.CompleteRunAsync(
            failedRepairRunId,
            "failed",
            1,
            "",
            "PROTOTYPE_TDD status=unexpected_green stage=red expected=fail",
            $$"""
            {
              "repair": true,
              "prototype_record": "{{prototypeRecordPath}}",
              "slug": "dq-rpg",
              "prototype_completion": {
                "succeeded": false,
                "status": "failed",
                "error": "prototype_repair_failed"
              }
            }
            """);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(accountId, projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 3);
        var repairRun = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        runner.Commands[0].Arguments.Should().Contain("exec");
        runner.Commands[0].Arguments.Should().NotContain("run-prototype-workflow");
        runner.Commands[0].StandardInput.Should().Contain("post-validation prototype repair");
        runner.Commands[0].StandardInput.Should().Contain("rpg_start_button_missing");
        repairRun!.Status.Should().Be("succeeded");
        repairRun.EvidenceJson.Should().Contain("\"repair_mode\":\"post_validation\"");
    }

    [Fact]
    public async Task RepairAsync_PrefersPrototypeShellSceneOverBattleSceneWhenManifestFallbackIsNeeded()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var prototypeRecordPath = "docs/prototypes/2026-05-14-dq-rpg.md";
        WritePrototypeRecord(project!.RepoPath, prototypeRecordPath, "# Prototype: dq-rpg\n");

        var prototypeRoot = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg");
        Directory.CreateDirectory(prototypeRoot);
        File.WriteAllText(Path.Combine(prototypeRoot, "BattleScene.tscn"), "[gd_scene format=3]\n", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(prototypeRoot, "DqRpgPrototype.tscn"), "[gd_scene format=3]\n", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(prototypeRoot, "MapScene.tscn"), "[gd_scene format=3]\n", System.Text.Encoding.UTF8);

        var failedRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            10,
            "previous stdout",
            "MAIN_MENU_PROTOTYPE_NAV FAIL rpg_start_button_missing",
            $$"""
            {
              "prototype_record": "{{prototypeRecordPath}}",
              "slug": "dq-rpg",
              "prototype_completion": {
                "succeeded": true,
                "completed_through_day": 7,
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              },
              "godot_smoke": {
                "ran": true,
                "exit_code": 9,
                "reason": "prototype_main_menu_navigation_failed",
                "scene": "res://Game.Godot/Prototypes/dq-rpg/BattleScene.tscn"
              }
            }
            """);

        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(accountId, projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 3);

        result.Status.Should().Be("queued");
        runner.Commands[0].StandardInput.Should().Contain("PreferredPrototypeShellScene: res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
        runner.Commands[0].StandardInput.Should().Contain("Do not use BattleScene or MapScene as the main entry scene");
    }

    [Fact]
    public async Task RepairAsync_WritesRepairStateAndChatProgress_ForNextRepair()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var prototypeRecordPath = "docs/prototypes/2026-05-14-dq-rpg.md";
        WritePrototypeRecord(project!.RepoPath, prototypeRecordPath, "# Prototype: dq-rpg\n");
        var failedRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            10,
            "",
            "MAIN_MENU_PROTOTYPE_NAV FAIL rpg_start_button_missing",
            $$"""
            {
              "prototype_record": "{{prototypeRecordPath}}",
              "slug": "dq-rpg",
              "prototype_completion": {
                "succeeded": true,
                "completed_through_day": 7,
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              },
              "godot_smoke": {
                "ran": true,
                "exit_code": 10,
                "reason": "prototype_main_menu_navigation_failed",
                "scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              }
            }
            """);
        var runner = new FakeHostedProcessRunner(mainMenuNavigationExitCode: 14, mainMenuNavigationStderrOverride: "MAIN_MENU_PROTOTYPE_NAV FAIL rpg_map_visible_markers_missing_after_start");
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(accountId, projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 3);
        var repairRun = await WaitForRunStatusAsync(store, result.RunId, "failed", "failed");
        var messages = await store.ListProjectChatMessagesAsync(project.AccountId, projectId, 10);
        var repairState = new PrototypeRouteStateWriter().ReadLatestPrototypeRepairState(project);

        repairRun!.Status.Should().Be("failed");
        messages.Should().NotContain(message => message.Kind == "prototype-repair-result");
        repairState.Should().Contain("rpg_map_visible_markers_missing_after_start");
        repairState.Should().Contain("next_repair_focus");
    }

    [Fact]
    public async Task RepairAsync_RequiresLatestPrototypeRunToBeFailed()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
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

        var result = await service.RepairAsync(accountId, projectId, new PrototypeRepairRequest("gpt-5.4"));

        result.Status.Should().Be("prototype_repair_not_available");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_RequiresLlmBinding_ForCodexScoring()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var result = await service.RunAsync(accountId, projectId, ValidRequest() with { ScoreEngine = "codex" });

        result.Status.Should().Be("llm_binding_required");
        result.ExitCode.Should().Be(402);
    }

    [Fact]
    public async Task RunAsync_RecordsLlmAudit_WhenCodexScoringIsBoundAndAllowed()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        await new LlmBindingService(store, options).BindAsync(accountId, new LlmBindingRequest(
            "new-api",
            "https://new-api.example.com/v1",
            "new-api-user-1",
            "host-secret:new-api-user-1"));
        var service = Service(store, options, new FakeHostedProcessRunner());

        var result = await service.RunAsync(accountId, projectId, ValidRequest() with { ScoreEngine = "codex" });
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.LlmGateway.Should().Be("codex-cli");
        run.LlmModel.Should().Be(PrototypeModelPolicy.Normalize(null));
        run.LlmCostJson.Should().Contain("calls");
        run.LlmCostJson.Should().Contain("estimated_cost_cny");
        run.LlmCostJson.Should().Contain("billing_source");
        run.LlmCostJson.Should().Contain("codex-cli");
        run.LlmCostJson.Should().Contain("usage_status");
        run.LlmCostJson.Should().Contain("unknown");
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

    private static string ToPascalSlugForTest(string slug)
    {
        var parts = slug.Split(['-', '_'], StringSplitOptions.RemoveEmptyEntries);
        return string.Concat(parts.Select(part => char.ToUpperInvariant(part[0]) + part[1..]));
    }

    private static async Task<PhaseAMetadataStore> CreateStoreAsync(string connectionString, PhaseAPlatformOptions options)
    {
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var store = new PhaseAMetadataStore(connectionString, options);
        await store.EnsureSingleAdminAsync();
        return store;
    }

    private static async Task<(string AccountId, string ProjectId)> CreateProjectWithAccountAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string gameName = "Demo Game", string gameTypeSource = "勇者斗恶龙")
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(
            store,
            options,
            new ProjectRuleCatalog(),
            new ProjectWorkspaceSeeder(options),
            gameTypeMatchService: new FakeGameTypeMatchService());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, gameName, gameTypeSource, null, null, null, null));
        return (accountId, result.ProjectId!);
    }

    private static async Task<ProjectIterationSessionSnapshot> CreateCompletedIterationPlanAsync(PhaseAMetadataStore store, string accountId, string projectId)
    {
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "manual_feedback",
            "Improve the prototype.",
            "Improve the prototype.",
            [
                new ProjectIterationGoalCreateCommand(1, "Improve field UI", "Make field state visible.", "Field UI is visible."),
                new ProjectIterationGoalCreateCommand(2, "Improve battle UI", "Make battle state visible.", "Battle UI is visible.")
            ]);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in details!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} completed.", DateTimeOffset.UtcNow.ToString("O"));
        }

        return session;
    }

    private static async Task CreateSucceededUiOptimizationRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var project = await store.GetProjectSnapshotAsync(projectId);
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-ui-optimization");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(runId, "succeeded", 0, "", "", "{\"route\":\"prototype-ui-optimization\",\"godot_smoke\":{\"ran\":true,\"exit_code\":0,\"reason\":\"strict_headless_main_menu_navigation\",\"scene\":\"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn\"}}");
        await store.UpdateRunProgressAsync(runId, "succeeded", "completed", "UI optimization completed.");
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string gameName = "Demo Game", string gameTypeSource = "勇者斗恶龙")
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(
            store,
            options,
            new ProjectRuleCatalog(),
            new ProjectWorkspaceSeeder(options),
            gameTypeMatchService: new FakeGameTypeMatchService());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, gameName, gameTypeSource, null, null, null, null));
        return result.ProjectId!;
    }

    private sealed class FakeGameTypeMatchService : IProjectGameTypeMatchService
    {
        public Task<ProjectGameTypeMatchEvidence> ResolveAsync(string gameTypeSource, CancellationToken cancellationToken)
        {
            var matched = ResolveMatchedGameType(gameTypeSource);
            var tags = TagsFor(matched);
            var now = DateTimeOffset.UtcNow.ToString("O");
            return Task.FromResult(new ProjectGameTypeMatchEvidence(
                1,
                string.IsNullOrWhiteSpace(matched) ? "no_match" : "matched",
                string.IsNullOrWhiteSpace(matched) ? "test_no_match" : "matched_by_test_genre_tags",
                "steam",
                gameTypeSource,
                "1",
                "Test App",
                tags,
                [],
                tags,
                tags,
                matched,
                string.IsNullOrWhiteSpace(matched) ? "" : $"docs/game-type-guides/{matched}.md",
                string.IsNullOrWhiteSpace(matched) ? 0 : 20,
                [],
                "",
                "test",
                now,
                now));
        }

        private static string ResolveMatchedGameType(string gameTypeSource)
        {
            var text = gameTypeSource.ToLowerInvariant();
            if (ContainsAny(text, "survivors", "vampire", "bullet heaven", "arena survival", "horde survival"))
            {
                return "survivorslike";
            }

            if (ContainsAny(text, "card", "deck", "tcg", "ccg", "slay the spire", "balatro"))
            {
                return "card-game";
            }

            if (ContainsAny(text, "roguelike", "roguelite", "procedural", "permadeath"))
            {
                return "roguelike";
            }

            return "rpg";
        }

        private static string[] TagsFor(string matched)
        {
            return matched switch
            {
                "survivorslike" => ["survivorslike", "vampire-survivors", "bullet-heaven", "arena-survival"],
                "card-game" => ["card", "deck-building", "card-game", "roguelike"],
                "roguelike" => ["roguelike", "roguelite", "procedural", "permadeath"],
                "rpg" => ["rpg", "role-playing", "jrpg"],
                _ => []
            };
        }

        private static bool ContainsAny(string text, params string[] needles)
        {
            return needles.Any(needle => text.Contains(needle, StringComparison.Ordinal));
        }
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

    private static PrototypeWorkflowService Service(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        IHostedProcessRunner runner,
        HeavyRunnerQueueService? heavyRunnerQueue = null,
        HeavyRunnerQueueService? prototypeCreationQueue = null,
        TimeSpan? creationTotalTimeout = null,
        TimeSpan? creationInactivityTimeout = null,
        HostedContextManifestIssuer? contextManifestIssuer = null,
        HostedContextGatePolicy? contextGatePolicy = null,
        IHostedContextManifestValidator? contextManifestValidator = null)
    {
        return new PrototypeWorkflowService(
            store,
            options,
            runner,
            new PrototypeRecordWriter(options),
            new PrototypeWorkflowCommandBuilder(options),
            new PrototypeArtifactIndexer(),
            new LlmBindingService(store, options),
            new LlmStopLossService(store, options),
            new ProjectWorkspaceSeeder(options),
            new GameTypeTemplateCatalog(options),
            heavyRunnerQueue: heavyRunnerQueue,
            prototypeCreationQueue: prototypeCreationQueue,
            creationTotalTimeout: creationTotalTimeout,
            creationInactivityTimeout: creationInactivityTimeout,
            contextManifestIssuer: contextManifestIssuer,
            contextGatePolicy: contextGatePolicy,
            contextManifestValidator: contextManifestValidator);
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

    private static async Task WaitForAtLeastCommandsAsync(FakeHostedProcessRunner runner, int expectedCount)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        while (runner.Commands.Count < expectedCount && DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(50);
        }

        runner.Commands.Should().HaveCountGreaterThanOrEqualTo(expectedCount);
    }

    private static async Task WaitForInactiveTimeoutRunnerCommandAsync(InactiveTimeoutHostedProcessRunner runner)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        while (runner.Commands.Count == 0 && DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(50);
        }

        runner.Commands.Should().NotBeEmpty();
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

    private static void WriteFile(string path, string content)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    private sealed class CapturingManifestValidator : IHostedContextManifestValidator
    {
        public HostedContextEnvelope? Envelope { get; private set; }
        public string? OperationKey { get; private set; }

        public Task<bool> ValidateAndConsumeAsync(
            HostedContextEnvelope envelope,
            string operationKey,
            CancellationToken cancellationToken = default)
        {
            Envelope = envelope;
            OperationKey = operationKey;
            return Task.FromResult(true);
        }
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly int _completedThroughDay;
        private readonly bool _writeActiveState;
        private readonly HashSet<int> _skippedDays;
        private readonly bool _writePrototypeScene;
        private readonly string? _prototypeSceneOverride;
        private readonly string? _instancedPlayableSceneOverride;
        private readonly int _smokeExitCode;
        private readonly bool _writePackagingArtifacts;
        private readonly string? _smokeStdoutOverride;
        private readonly string? _smokeStderrOverride;
        private readonly int _mainMenuNavigationExitCode;
        private readonly string? _mainMenuNavigationStdoutOverride;
        private readonly string? _mainMenuNavigationStderrOverride;
        private readonly int _gdUnitExitCode;
        private readonly string? _gdUnitStdoutOverride;
        private readonly string? _gdUnitStderrOverride;
        private readonly int _workflowExitCode;
        private readonly string? _workflowStdoutOverride;
        private readonly string? _workflowStderrOverride;
        private readonly int _dotnetBuildExitCode;
        private readonly string? _dotnetBuildStdoutOverride;
        private readonly string? _dotnetBuildStderrOverride;

        public FakeHostedProcessRunner(
            int completedThroughDay = 7,
            bool writeActiveState = true,
            IEnumerable<int>? skippedDays = null,
            bool writePrototypeScene = true,
            string? prototypeSceneOverride = null,
            string? instancedPlayableSceneOverride = null,
            int smokeExitCode = 0,
            bool writePackagingArtifacts = true,
            string? smokeStdoutOverride = null,
            string? smokeStderrOverride = null,
            int mainMenuNavigationExitCode = 0,
            string? mainMenuNavigationStdoutOverride = null,
            string? mainMenuNavigationStderrOverride = null,
            int gdUnitExitCode = 0,
            string? gdUnitStdoutOverride = null,
            string? gdUnitStderrOverride = null,
            int workflowExitCode = 0,
            string? workflowStdoutOverride = null,
            string? workflowStderrOverride = null,
            int dotnetBuildExitCode = 0,
            string? dotnetBuildStdoutOverride = null,
            string? dotnetBuildStderrOverride = null)
        {
            _completedThroughDay = completedThroughDay;
            _writeActiveState = writeActiveState;
            _skippedDays = skippedDays is null ? [] : new HashSet<int>(skippedDays);
            _writePrototypeScene = writePrototypeScene;
            _prototypeSceneOverride = prototypeSceneOverride;
            _instancedPlayableSceneOverride = instancedPlayableSceneOverride;
            _smokeExitCode = smokeExitCode;
            _writePackagingArtifacts = writePackagingArtifacts;
            _smokeStdoutOverride = smokeStdoutOverride;
            _smokeStderrOverride = smokeStderrOverride;
            _mainMenuNavigationExitCode = mainMenuNavigationExitCode;
            _mainMenuNavigationStdoutOverride = mainMenuNavigationStdoutOverride;
            _mainMenuNavigationStderrOverride = mainMenuNavigationStderrOverride;
            _gdUnitExitCode = gdUnitExitCode;
            _gdUnitStdoutOverride = gdUnitStdoutOverride;
            _gdUnitStderrOverride = gdUnitStderrOverride;
            _workflowExitCode = workflowExitCode;
            _workflowStdoutOverride = workflowStdoutOverride;
            _workflowStderrOverride = workflowStderrOverride;
            _dotnetBuildExitCode = dotnetBuildExitCode;
            _dotnetBuildStdoutOverride = dotnetBuildStdoutOverride;
            _dotnetBuildStderrOverride = dotnetBuildStderrOverride;
        }

        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (string.Equals(command.FileName, "dotnet", StringComparison.OrdinalIgnoreCase) &&
                command.Arguments.Contains("build"))
            {
                return Task.FromResult(new HostedProcessResult(
                    _dotnetBuildExitCode,
                    _dotnetBuildStdoutOverride ?? (_dotnetBuildExitCode == 0 ? "Build succeeded.\n" : ""),
                    _dotnetBuildStderrOverride ?? (_dotnetBuildExitCode == 0 ? "" : "Build failed.\n")));
            }

            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(
                    _smokeExitCode,
                    _smokeStdoutOverride ?? (_smokeExitCode == 0 ? "SMOKE PASS (marker)\n" : ""),
                    _smokeStderrOverride ?? (_smokeExitCode == 0 ? "" : "SMOKE FAIL\n")));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(
                    _mainMenuNavigationExitCode,
                    _mainMenuNavigationStdoutOverride ?? (_mainMenuNavigationExitCode == 0 ? "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/demo-prototype/DemoPrototypePrototype.tscn\n" : ""),
                    _mainMenuNavigationStderrOverride ?? (_mainMenuNavigationExitCode == 0 ? "" : "MAIN_MENU_PROTOTYPE_NAV FAIL\n")));
            }

            if (command.Arguments.Contains("scripts/python/run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(
                    _gdUnitExitCode,
                    _gdUnitStdoutOverride ?? (_gdUnitExitCode == 0 ? "GdUnit tests: 6 passed\n" : ""),
                    _gdUnitStderrOverride ?? (_gdUnitExitCode == 0 ? "" : "GdUnit tests failed\n")));
            }

            if (command.Arguments.Contains("exec"))
            {
                var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).FirstOrDefault();
                if (!string.IsNullOrWhiteSpace(outputPath))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
                    File.WriteAllText(outputPath, "STATUS: completed\nSUMMARY: post-validation repair completed\n");
                }

                var repairSlug = ExtractSlugFromPrompt(command.StandardInput) ?? "dq-rpg";
                var repairScenePath = $"res://Game.Godot/Prototypes/{repairSlug}/DqRpgPrototype.tscn";
                Write($"docs/prototypes/{repairSlug}.prototype.json", $$"""
                {
                  "prototype_type_kit": {
                    "manifest": {
                      "paths": {
                        "default_scene": "{{repairScenePath}}"
                      }
                    }
                  }
                }
                """);
                Write(repairScenePath["res://".Length..].Replace('/', Path.DirectorySeparatorChar), "[gd_scene format=3]\n");
                Write($"logs/ci/active-prototypes/{repairSlug}.packaging.json", $$"""
                {
                  "kind": "prototype-packaging-summary",
                  "default_scene": "{{repairScenePath}}",
                  "tdd_stage_counts": { "red": 1, "green": 1, "refactor": 0 }
                }
                """);
                Write($"logs/ci/active-prototypes/{repairSlug}.completion.md", "# Prototype Completion Report\n");
                Write($"logs/ci/active-prototypes/{repairSlug}.active.json", $$"""
                {
                  "status": "completed-through-day",
                  "completed_through_day": 7,
                  "missing_required_fields": [],
                  "prototype_spec": "docs/prototypes/{{repairSlug}}.prototype.json",
                  "completion_summary": "repaired",
                  "steps_run": [
                    { "day": 1, "status": "ok" },
                    { "day": 2, "status": "ok" },
                    { "day": 3, "status": "ok" },
                    { "day": 4, "status": "ok" },
                    { "day": 5, "status": "ok" },
                    { "day": 6, "status": "ok" },
                    { "day": 7, "status": "ok" }
                  ]
                }
                """);
                Write("logs/ci/project-health/latest.html", "<html></html>");
                Write("logs/ci/project-health/latest.json", "{}");
                return Task.FromResult(new HostedProcessResult(0, "codex repair ok", ""));
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
                if (string.IsNullOrWhiteSpace(_instancedPlayableSceneOverride))
                {
                    Write(scenePath["res://".Length..].Replace('/', Path.DirectorySeparatorChar), "[gd_scene format=3]\n");
                }
                else
                {
                    Write(scenePath["res://".Length..].Replace('/', Path.DirectorySeparatorChar), $$"""
                    [gd_scene load_steps=2 format=3]

                    [ext_resource type="PackedScene" path="{{_instancedPlayableSceneOverride}}" id="1"]

                    [node name="ShellPrototype" type="Node2D"]

                    [node name="PrototypeLoop" type="Node2D" parent="."]

                    [node name="FirstPlayableRaid" parent="PrototypeLoop" instance=ExtResource("1")]
                    """);
                    Write(_instancedPlayableSceneOverride["res://".Length..].Replace('/', Path.DirectorySeparatorChar), "[gd_scene format=3]\n");
                }
            }
            Write($"Tests.Godot/tests/Prototype/{ToPascalCase(slug)}/test_{slug.Replace('-', '_')}_prototype_scene.gd", "extends Node\n");
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
                        { "day": 4, "status": "{{StepStatus(4)}}", "reason": "{{StepReason(4)}}" },
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

            return (day == 3 || day == 4) && _skippedDays.Contains(day)
                ? "existing_project_specific_prototype_ready_for_green"
                : "";
        }

        private static string BuildPrototypeScene(string slug)
        {
            var parts = slug.Split(['-', '_'], StringSplitOptions.RemoveEmptyEntries);
            var pascal = ToPascalCase(slug);
            return $"res://Game.Godot/Prototypes/{slug}/{pascal}Prototype.tscn";
        }

        private static string ToPascalCase(string slug)
        {
            var parts = slug.Split(['-', '_'], StringSplitOptions.RemoveEmptyEntries);
            return string.Concat(parts.Select(part => char.ToUpperInvariant(part[0]) + part[1..]));
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

        private static string? ExtractSlugFromPrompt(string? prompt)
        {
            if (string.IsNullOrWhiteSpace(prompt))
            {
                return null;
            }

            foreach (var line in prompt.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                if (line.StartsWith("- Slug:", StringComparison.OrdinalIgnoreCase))
                {
                    return line["- Slug:".Length..].Trim();
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

    private sealed class ThrowingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            throw new InvalidOperationException("runner failed");
        }
    }

    private sealed class InactiveTimeoutHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (!command.Arguments.Contains("scripts/python/smoke_headless.py") &&
                !command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py") &&
                !command.Arguments.Contains("scripts/python/run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(408, "", "Process had no stdout, stderr, or watched file activity for 25 minute(s)."));
            }

            return Task.FromResult(new HostedProcessResult(0, "", ""));
        }
    }
}
