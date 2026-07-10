using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
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

        var result = await service.RunAsync(accountId, projectId, "game-design-master", new SkillActionRunRequest("Focus on combat loop."));
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        result.SkillName.Should().Be("bmad-agent-game-designer");
        result.AssistantMessage.Should().Contain("skill output");
        artifacts.Select(a => a.ArtifactType).Should().Contain(["skill-action-request", "skill-action-output"]);
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].Arguments.Should().Contain(["exec", "--sandbox", "read-only"]);
        runner.Commands[0].Arguments.Should().Contain(["-c", "model_reasoning_effort=\"high\""]);
        runner.Commands[0].Arguments.Last().Should().Be("-");
        runner.Commands[0].StandardInput.Should().Contain("bmad-agent-game-designer");
        runner.Commands[0].Arguments.Should().NotContain("Focus on combat loop.$other-skill");
        runner.Commands[0].StandardInput.Should().Contain("Focus on combat loop.");
        runner.Commands[0].WorkingDirectory.Should().Be((await store.GetProjectSnapshotAsync(projectId))!.RepoPath);
    }

    [Fact]
    public async Task RunAsync_UsesSeededProjectRepoForReadOnlySkillDiscovery()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var sourceSkillRoot = Path.Combine(repoRoot.Path, ".agents", "skills", "bmad-agent-game-designer");
        Directory.CreateDirectory(sourceSkillRoot);
        Directory.CreateDirectory(Path.Combine(repoRoot.Path, "_bmad", "scripts"));
        Directory.CreateDirectory(Path.Combine(repoRoot.Path, "_bmad", "gds"));
        File.WriteAllText(Path.Combine(sourceSkillRoot, "SKILL.md"), "---\nname: bmad-agent-game-designer\n---\n", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(repoRoot.Path, "_bmad", "scripts", "resolve_customization.py"), "# resolver\n", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(repoRoot.Path, "_bmad", "gds", "config.yaml"), "project_name: test\n", System.Text.Encoding.UTF8);
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var routeEngine = new CapturingLlmRouteEngine("skill output");
        var service = Service(store, options, new FakeHostedProcessRunner("legacy runner should not run"), routeEngine);

        var result = await service.RunAsync(accountId, projectId, "game-design-master", new SkillActionRunRequest("Focus on combat loop."));
        var project = await store.GetProjectSnapshotAsync(projectId);

        result.Status.Should().Be("succeeded");
        routeEngine.LastRequest.Should().NotBeNull();
        routeEngine.LastRequest!.WorkspaceRoot.Should().Be(project!.RepoPath);
        routeEngine.LastRequest.Prompt.Should().Contain("$bmad-agent-game-designer");
        File.Exists(Path.Combine(project.RepoPath, ".agents", "skills", "bmad-agent-game-designer", "SKILL.md")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "_bmad", "scripts", "resolve_customization.py")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "_bmad", "gds", "config.yaml")).Should().BeTrue();
    }

    [Fact]
    public void ListAllowed_ExposesConfiguredMasterActions_AndRemovesPrototypeDefault()
    {
        var actions = new SkillActionCatalog().ListAllowed("user");

        actions.Select(a => a.ActionId).Should().Equal("game-design-master");
        actions.Select(a => a.Label).Should().Equal("\u6e38\u620f\u7b56\u5212\u5927\u5e08");
        actions.Select(a => a.SkillName).Should().Equal("bmad-agent-game-designer");
        actions.Select(a => a.ActionId).Should().NotContain("prototype-playable-advice");
        actions.Select(a => a.ActionId).Should().NotContain("map-making-master");
        actions.Select(a => a.ActionId).Should().NotContain("character-making-master");
        actions.Single(a => a.ActionId == "game-design-master").ExecutionMode.Should().Be("codex-read-only");
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

        var result = await service.RunAsync(accountId, projectId, "not-whitelisted", new SkillActionRunRequest("$prototype-rpg-godot-zh"));

        result.Status.Should().Be("skill_action_not_allowed");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_RejectsProjectOwnedByAnotherAccount()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var ownerAccountId = await store.EnsureSingleAdminAsync();
        var otherAccount = await store.CreateUserAccountAsync("skill-other-account", 1);
        var projectId = await CreateProjectAsync(store, options, ownerAccountId);
        var runner = new FakeHostedProcessRunner("should not run");
        var service = Service(store, options, runner);

        var act = () => service.RunAsync(
            otherAccount.AccountId,
            projectId,
            "game-design-master",
            new SkillActionRunRequest("Focus on combat loop."));

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Project not found.");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_RejectsRemovedImageActions()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner("asset skill output");
        var service = Service(store, options, runner);

        var mapResult = await service.RunAsync(accountId, projectId, "map-making-master", new SkillActionRunRequest("Generate map."));
        var spriteResult = await service.RunAsync(accountId, projectId, "character-making-master", new SkillActionRunRequest("Generate sprite."));

        mapResult.Status.Should().Be("skill_action_not_allowed");
        spriteResult.Status.Should().Be("skill_action_not_allowed");
        runner.Commands.Should().BeEmpty();
    }

    private static SkillActionService Service(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        IHostedProcessRunner runner,
        ILlmRouteEngine? llmRouteEngine = null)
    {
        return new SkillActionService(
            store,
            options,
            new SkillActionCatalog(),
            runner,
            new ProjectWorkspaceSeeder(options),
            llmRouteEngine: llmRouteEngine);
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

    private sealed class CapturingLlmRouteEngine : ILlmRouteEngine
    {
        private readonly string _output;

        public CapturingLlmRouteEngine(string output)
        {
            _output = output;
        }

        public LlmRouteRequest? LastRequest { get; private set; }

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            LastRequest = request;
            return Task.FromResult(new LlmRouteResult(
                true,
                _output,
                null,
                request.Model,
                null,
                null,
                0,
                "",
                "",
                null,
                0,
                request.Prompt.Length,
                System.Text.Encoding.UTF8.GetByteCount(request.Prompt),
                1));
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
