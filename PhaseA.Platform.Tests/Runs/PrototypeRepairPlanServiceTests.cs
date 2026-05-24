using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
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
