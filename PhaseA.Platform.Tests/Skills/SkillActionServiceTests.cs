using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Skills;

public sealed class SkillActionServiceTests
{
    [Fact]
    public async Task RunAsync_ExecutesOnlyWhitelistedAction_AndCreatesArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner("skill output");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, "game-design-master", new SkillActionRunRequest("Focus on combat loop."));
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        result.SkillName.Should().Be("bmad-agent-game-designer");
        result.AssistantMessage.Should().Contain("skill output");
        artifacts.Select(a => a.ArtifactType).Should().Contain(["skill-action-request", "skill-action-output"]);
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].Arguments.Should().Contain(["exec", "--sandbox", "read-only"]);
        string.Join("\n", runner.Commands[0].Arguments).Should().Contain("bmad-agent-game-designer");
        runner.Commands[0].Arguments.Should().NotContain("Focus on combat loop.$other-skill");
        runner.Commands[0].WorkingDirectory.Should().Be((await store.GetProjectSnapshotAsync(projectId))!.RepoPath);
    }

    [Fact]
    public void ListAllowed_ExposesConfiguredMasterActions_AndRemovesPrototypeDefault()
    {
        var actions = new SkillActionCatalog().ListAllowed("user");

        actions.Select(a => a.ActionId).Should().Equal(
            "game-design-master",
            "map-making-master",
            "character-making-master");
        actions.Select(a => a.Label).Should().Equal(
            "\u6e38\u620f\u7b56\u5212\u5927\u5e08",
            "\u5730\u56fe\u5236\u4f5c\u5927\u5e08",
            "\u89d2\u8272\u5236\u4f5c\u5927\u5e08");
        actions.Select(a => a.SkillName).Should().Equal(
            "bmad-agent-game-designer",
            "generate2dmap",
            "generate2dsprite");
        actions.Select(a => a.ActionId).Should().NotContain("prototype-playable-advice");
    }

    [Fact]
    public async Task RunAsync_RejectsUnknownActionId()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner("skill output");
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, "not-whitelisted", new SkillActionRunRequest("$prototype-rpg-godot-zh"));

        result.Status.Should().Be("skill_action_not_allowed");
        runner.Commands.Should().BeEmpty();
    }

    private static SkillActionService Service(PhaseAMetadataStore store, PhaseAPlatformOptions options, IHostedProcessRunner runner)
    {
        return new SkillActionService(
            store,
            options,
            new SkillActionCatalog(),
            runner,
            new ProjectWorkspaceSeeder(options));
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
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

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly string _output;

        public FakeHostedProcessRunner(string output)
        {
            _output = output;
        }

        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, _output);
            return Task.FromResult(new HostedProcessResult(0, "codex stdout", ""));
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
