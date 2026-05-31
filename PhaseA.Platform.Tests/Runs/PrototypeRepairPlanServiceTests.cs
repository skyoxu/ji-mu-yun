using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using System.Text.Json;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeRepairPlanServiceTests
{
    [Fact]
    public async Task CreateAsync_ShouldUseRpgSkillAndWriteRepairPlanState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        await SeedFailedPrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeRepairPlanService(store, quickFix, writer);

        var result = await service.CreateAsync(accountId, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var state = writer.ReadLatestRepairPlanState(project!);
        var stateJson = JsonSerializer.Deserialize<JsonElement>(state);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(4);
        result.Goals[0].Title.Should().Contain("恢复原型运行证据");
        result.Goals[0].Description.Should().Contain("Permission denied");
        result.Goals[1].Title.Should().Contain("修复 RPG 场景与节点合同");
        result.Goals[2].Title.Should().Contain("修复 RPG 玩法合同");
        result.Goals[3].Title.Should().Contain("最终全量验收");
        stateJson.GetProperty("route").GetString().Should().Be("repair-plan");
        stateJson.GetProperty("route_skill").GetProperty("routeSkillId").GetString().Should().Be("prototype-rpg-godot-zh");
        stateJson.GetProperty("summary").GetString().Should().Contain("4 个修复步骤");
        stateJson.GetProperty("goals").GetArrayLength().Should().Be(4);
        stateJson.GetProperty("goals")[0].GetProperty("description").GetString().Should().Contain("Permission denied");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseLlmTailoredRpgRepairPlan_WhenFailureIsNavigationRelated()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        await SeedFailedNavigationPrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var codex = new LlmRepairPlanCodexClient();
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter(), null, codex);

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals[0].Title.Should().Be("RPG Repair Step 1: Start Adventure to visible MapScene");
        result.Goals[1].Title.Should().Contain("movement and first encounter");
        result.Goals[2].Title.Should().Contain("BattleScene");
        result.Goals[3].Title.Should().Contain("reward 3-choice");
        result.Goals[0].Title.Should().NotContain("证据");
        result.Goals[0].Title.Should().NotContain("TDD");
        codex.LastPrompt.Should().Contain("Use only the data provided in this prompt.");
        codex.LastPrompt.Should().Contain("Do not read files, inspect the repository, call tools, or ask for more context.");
        codex.LastOptions.Should().NotBeNull();
        codex.LastOptions!.IgnoreRules.Should().BeTrue();
        codex.LastOptions.ReasoningEffort.Should().Be("minimal");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseNavigationFirstFallbackRepairPlan_WhenNavigationFailureHasNoCodex()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        await SeedFailedNavigationPrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter());

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(4);
        result.Goals[0].Title.Should().Contain("Start Adventure");
        result.Goals[0].Title.Should().Contain("MapScene");
        result.Goals[0].Title.Should().NotContain("证据");
        result.Goals[0].Title.Should().NotContain("TDD");
        result.Goals[1].Title.Should().Contain("奖励");
        result.Goals[2].Description.Should().Contain("15 battles");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseBuildCleanupRepairPlan_WhenFailureIsDuplicateAssemblyAttributes()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        await SeedFailedBuildContaminationPrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var codex = new LlmRepairPlanCodexClient();
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter(), null, codex);

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(4);
        result.Goals[0].Title.Should().Contain("Build cleanup");
        result.Goals[0].Description.Should().Contain("CS0579");
        result.Goals[0].Description.Should().Contain("obj/bin/buildcache");
        result.Goals[0].Title.Should().NotContain("Start Adventure");
        result.Goals[0].Title.Should().NotContain("gameplay");
        codex.LastPrompt.Should().BeNull();
    }

    [Fact]
    public async Task CreateAsync_ShouldNotUseBuildCleanupRepairPlan_WhenGodotStackMentionsTempObjDebug()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        await SeedFailedGodotNodePrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter());

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(4);
        result.Goals[0].Title.Should().NotContain("Build cleanup");
        result.Goals[0].Title.Should().Contain("scene/script node contract");
        result.Goals[0].Description.Should().Contain("BattleStatusLabel");
        result.Goals[0].Description.Should().Contain(".godot/mono/temp/obj/Debug");
        result.Goals[1].Title.Should().Contain("Start Adventure");
        result.Goals[1].Title.Should().Contain("BattleScene");
    }

    [Fact]
    public async Task CreateAsync_ShouldPrioritizeConcreteAssertionFailures_WhenFailureAlreadyNamesMapAnd15Battles()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        await SeedFailedPlayableLoopPrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter());

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(4);
        result.Goals[0].Title.Should().Contain("Start Adventure");
        result.Goals[0].AcceptanceHint.Should().Contain("MapScene");
        result.Goals[1].Description.Should().Contain("reward 3-choice");
        result.Goals[2].Description.Should().Contain("15 battles");
        result.Goals[2].Description.Should().Contain("any-loss defeat");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseConcreteRpgGdUnitRepairPlan_WhenValidationFailed()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var project = await store.GetProjectSnapshotAsync(projectId);
        SeedGdUnitConsole(project!.RepoPath);
        await SeedFailedRpgGdUnitPrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var codex = new LlmRepairPlanCodexClient();
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter(), null, codex);

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(5);
        result.Goals[0].Title.Should().Contain("runtime assets");
        result.Goals[0].Description.Should().Contain("showcase_map_overworld.png");
        result.Goals[1].Title.Should().Contain("scene node contract");
        result.Goals[1].Description.Should().Contain("CanvasLayer/UI/MapScene/RpgEnemyAsset");
        result.Goals[2].Description.Should().Contain("_UnhandledInput");
        result.Goals[3].Description.Should().Contain("15-battle victory");
        result.Goals[3].Description.Should().NotContain("5 battles");
        result.Goals[3].Description.Should().NotContain("5 场");
        result.Goals[4].Description.Should().Contain("tests/Prototype/DqRpgPrototype");
        codex.LastPrompt.Should().BeNull();
    }

    [Fact]
    public async Task CreateAsync_ShouldFallbackToDefaultPrototypeSkill_WhenProjectIsNotRpg()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Action");
        await SeedFailedPrototypeRunAsync(store, projectId);
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter());

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(3);
        result.Goals[0].Title.Should().Contain("恢复原型运行证据");
        result.Goals[0].Description.Should().Contain("default prototype route skill");
        result.Goals[0].Description.Should().Contain("Permission denied");
        result.Goals[1].Title.Should().Contain("修复通用原型合同缺口");
        result.Goals[2].Title.Should().Contain("最终全量验收");
    }

    [Fact]
    public async Task CreateAsync_ShouldRejectWhenNoFailedRunExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
        var service = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter());

        var result = await service.CreateAsync(accountId, projectId);

        result.Status.Should().Be("missing_failure");
        result.Summary.Should().Contain("没有可用于生成修复计划的失败记录");
        result.Goals.Should().BeEmpty();
    }

    private static async Task SeedFailedPrototypeRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var runId = await store.CreateRunAsync(projectId, null, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "Prototype workflow failed.\nDAY4_IMPLEMENTATION_VALIDATION failed",
            "Permission denied\nrpg_scene_node_contract_drift=Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn\nrpg_script_node_contract_drift=Game.Godot/Prototypes/dq-rpg/Scripts/DqRpgPrototype.cs",
            "{\"prototype_completion\":{\"succeeded\":false,\"error\":\"prototype_workflow_failed\"}}");
    }

    private static async Task SeedFailedNavigationPrototypeRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var runId = await store.CreateRunAsync(projectId, null, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "failed",
            12,
            "Prototype workflow failed.\nprototype_main_menu_navigation_failed",
            "Start Adventure clicked but visible MapScene markers were not found after navigation.",
            """
            {"prototype_completion":{"succeeded":true,"completed_through_day":7},"godot_smoke":{"ran":true,"exit_code":12,"reason":"prototype_main_menu_navigation_failed","scene":"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"}}
            """);
    }

    private static async Task SeedFailedBuildContaminationPrototypeRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var runId = await store.CreateRunAsync(projectId, null, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            """
            PROTOTYPE_TDD status=unexpected_red stage=green expected=pass
            Game.Core\obj\Debug\net8.0\.NETCoreApp,Version=v8.0.AssemblyAttributes.cs(4,12): error CS0579: Duplicate 'global::System.Runtime.Versioning.TargetFrameworkAttribute' attribute
            Game.Core\obj\Debug\net8.0\Game.Core.AssemblyInfo.cs(13,12): error CS0579: Duplicate 'System.Reflection.AssemblyCompanyAttribute' attribute
            Game.Core\buildcache\int\Debug\net8.0\Game.Core.AssemblyInfo.cs(13,12): error CS0579: Duplicate 'System.Reflection.AssemblyCompanyAttribute' attribute
            """,
            "",
            "{\"prototype_tdd\":{\"status\":\"unexpected_red\"}}");
    }

    private static async Task SeedFailedGodotNodePrototypeRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var runId = await store.CreateRunAsync(projectId, null, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "MAIN_MENU_PROTOTYPE_NAV FAIL",
            """
            RPG_START_ADVENTURE_MAP_VISIBLE PASS
            MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn
            ERROR: Node not found: "CanvasLayer/UI/BattleScene/BattleStatusLabel" (relative to "/root/Main/ScreenRoot/DqRpgPrototype").
            [8] Game.Godot.Prototypes.DqRpgPrototype.InvokeGodotClassMethod() (C:\repo\.godot\mono\temp\obj\Debug\Godot.SourceGenerators\Generated.cs:220)
            """,
            """
            {"godot_smoke":{"ran":true,"exit_code":1,"reason":"node_not_found","scene":"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"}}
            """);
    }

    private static async Task SeedFailedPlayableLoopPrototypeRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var runId = await store.CreateRunAsync(projectId, null, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            """
            PROTOTYPE_TDD status=unexpected_red stage=green expected=pass
            Start Adventure clicked but visible MapScene markers were not found after navigation.
            Assert.Contains() Failure: Sub-string not found
            Not found: "15 battles"
            """,
            "",
            """
            {"prototype_completion":{"succeeded":false,"error":"prototype_workflow_failed"},"godot_smoke":{"ran":false,"reason":"prototype_workflow_failed","scene":null}}
            """);
    }

    private static async Task SeedFailedRpgGdUnitPrototypeRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var runId = await store.CreateRunAsync(projectId, null, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "Prototype validation-only acceptance executed.",
            "RPG project-specific GdUnit validation failed: rpg_project_specific_gdunit_failed",
            """
            {
              "prototype_completion": {
                "succeeded": true,
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              },
              "godot_smoke": {
                "ran": true,
                "exit_code": 0,
                "reason": "strict_headless_main_menu_navigation"
              },
              "rpg_gdunit_validation": {
                "required": true,
                "ran": true,
                "passed": false,
                "exit_code": 1,
                "reason": "rpg_project_specific_gdunit_failed",
                "gdunit_path": "tests/Prototype/DqRpgPrototype",
                "report_dir": "logs/e2e/2026-05-31/gdunit-dq-rpg-prototype"
              }
            }
            """);
    }

    private static void SeedGdUnitConsole(string repoPath)
    {
        var reportDir = Path.Combine(repoPath, "logs", "e2e", "2026-05-31", "gdunit-dq-rpg-prototype");
        Directory.CreateDirectory(reportDir);
        File.WriteAllText(
            Path.Combine(reportDir, "gdunit-console.txt"),
            """
            ERROR: Failed loading resource: res://Game.Godot/Prototypes/dq-rpg/Assets/Map/showcase_map_overworld.png.
            ERROR: res://Game.Godot/Prototypes/dq-rpg/MapScene.tscn:67 - Parse Error: [ext_resource] referenced non-existent resource at: res://Game.Godot/Prototypes/dq-rpg/Assets/Map/showcase_map_overworld.png.
            ERROR: Node not found: "CanvasLayer/UI/MapScene/RpgEnemyAsset" (relative to "/root/test_dq_rpg_prototype_scene/DqRpgPrototype").
            SCRIPT ERROR: Invalid call. Nonexistent function '_UnhandledInput' in base 'Control'.
            """);
        File.WriteAllText(
            Path.Combine(reportDir, "run-summary.json"),
            """
            {"rc":1,"normalized_rc":0,"added":["tests/Prototype/DqRpgPrototype"]}
            """);
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId, string gameTypeSource)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameTypeSource, null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        return result.ProjectId!;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot
        });
    }

    private sealed class NoopRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            throw new InvalidOperationException("This test should not execute hosted processes.");
        }
    }

    private sealed class LlmRepairPlanCodexClient : ICodexChatClient
    {
        public string? LastPrompt { get; private set; }
        public CodexChatClientOptions? LastOptions { get; private set; }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            LastPrompt = prompt;
            LastOptions = options;
            const string json = """
            {
              "goals": [
                {
                  "title": "RPG Repair Step 1: Start Adventure to visible MapScene",
                  "description": "Repair the main menu route so Start Adventure always opens a visible MapScene instead of leaving the player on a blank or stale shell.",
                  "acceptanceHint": "This step passes only when Start Adventure consistently opens a visible MapScene with the expected map markers."
                },
                {
                  "title": "RPG Repair Step 2: movement and first encounter entry",
                  "description": "Repair player movement and the first encounter trigger on the live map path.",
                  "acceptanceHint": "This step passes only when movement works on the map and the first encounter can be triggered from the visible map route."
                },
                {
                  "title": "RPG Repair Step 3: BattleScene single-loop validation",
                  "description": "Repair the BattleScene so one battle can complete with readable feedback and settlement.",
                  "acceptanceHint": "This step passes only when one battle can be completed end to end with visible battle feedback."
                },
                {
                  "title": "RPG Repair Step 4: reward 3-choice and return-to-map",
                  "description": "Repair the reward loop so victory leads to three reward choices and a return to the map.",
                  "acceptanceHint": "This step passes only when victory leads to a readable 3-choice reward flow and then returns to the map."
                },
                {
                  "title": "RPG Repair Step 5: win/fail visibility",
                  "description": "Repair player-facing win/fail rules so the current prototype outcome rules are obvious.",
                  "acceptanceHint": "This step passes only when the player can clearly understand the current win/fail rules from the UI or flow."
                },
                {
                  "title": "RPG Final Step: full playable acceptance",
                  "description": "Run the final playable acceptance after the route, map, battle, reward, and visibility fixes are complete.",
                  "acceptanceHint": "This step passes only when the full playable RPG prototype acceptance is green."
                }
              ]
            }
            """;

            return Task.FromResult(new CodexChatClientResult(true, json, null, 0, "", ""));
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
