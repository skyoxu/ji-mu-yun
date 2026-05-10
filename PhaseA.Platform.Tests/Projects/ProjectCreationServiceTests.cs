using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Projects;

public sealed class ProjectCreationServiceTests
{
    [Fact]
    public async Task CreateProjectAsync_UsesDefaultRule_AndCreatesOneWorkspace()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());

        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(
            ProjectName: "demo-project",
            GameName: "Demo Game",
            GameTypeSource: "manual",
            TemplateRuleId: null,
            GitUrl: null,
            RepositoryUrl: null,
            RepoUrl: null));

        result.Succeeded.Should().BeTrue();
        result.TemplateRuleId.Should().Be("godot-prototype-default");
        result.LlmBindingRequired.Should().BeTrue();
        result.AllowedWorkflows.Should().Equal("chapter2-bootstrap", "prototype-7day-playable", "prototype-tdd", "prototype-scene");

        var snapshot = await store.GetProjectSnapshotAsync(result.ProjectId!);
        snapshot.Should().NotBeNull();
        snapshot!.WorkspaceId.Should().Be(result.WorkspaceId);
        snapshot.TemplateRuleId.Should().Be("godot-prototype-default");
        snapshot.LlmBindingRequired.Should().BeTrue();
        JsonSerializer.Deserialize<string[]>(snapshot.AllowedWorkflowsJson).Should().Equal(result.AllowedWorkflows);
        Directory.Exists(snapshot.RepoPath).Should().BeTrue();
        Directory.Exists(snapshot.RuntimePath).Should().BeTrue();
        Directory.Exists(snapshot.MetaPath).Should().BeTrue();
    }

    [Fact]
    public async Task CreateProjectAsync_RejectsBrowserProvidedGitUrl()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());

        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(
            ProjectName: "demo-project",
            GameName: "Demo Game",
            GameTypeSource: "manual",
            TemplateRuleId: null,
            GitUrl: "https://example.com/repo.git",
            RepositoryUrl: null,
            RepoUrl: null));

        result.Succeeded.Should().BeFalse();
        result.FailureCode.Should().Be("git_url_not_allowed");
        Directory.GetDirectories(workspaceRoot.Path).Should().BeEmpty();
    }

    [Fact]
    public async Task CreateProjectAsync_StopsAtQuota()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());

        await service.CreateProjectAsync(accountId, Request("Game One"));
        await service.CreateProjectAsync(accountId, Request("Game Two"));
        var third = await service.CreateProjectAsync(accountId, Request("Game Three"));

        third.Succeeded.Should().BeFalse();
        third.FailureCode.Should().Be("project_quota_exceeded");
        Directory.GetDirectories(Path.Combine(workspaceRoot.Path, accountId)).Should().HaveCount(2);
    }

    private static ProjectCreationRequest Request(string gameName)
    {
        return new ProjectCreationRequest(null, gameName, "manual", null, null, null, null);
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3")
        });
    }

    private sealed class TempWorkspaceRoot : IDisposable
    {
        private TempWorkspaceRoot(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempWorkspaceRoot Create()
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"phase-a-workspaces-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempWorkspaceRoot(path);
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
