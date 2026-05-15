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
        snapshot.BootstrapStatus.Should().Be("running");
        snapshot.BootstrapError.Should().BeNull();
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
        var first = (await store.ListProjectsAsync(accountId)).Single();
        await store.SetProjectBootstrapStatusAsync(first.ProjectId, "succeeded", null);
        await service.CreateProjectAsync(accountId, Request("Game Two"));
        var secondProject = (await store.ListProjectsAsync(accountId)).Single(p => p.GameName == "Game Two");
        await store.SetProjectBootstrapStatusAsync(secondProject.ProjectId, "succeeded", null);
        var third = await service.CreateProjectAsync(accountId, Request("Game Three"));

        third.Succeeded.Should().BeFalse();
        third.FailureCode.Should().Be("project_quota_exceeded");
        Directory.GetDirectories(Path.Combine(workspaceRoot.Path, accountId)).Should().HaveCount(2);
    }

    [Fact]
    public async Task CreateProjectAsync_BlocksWhileInitializationIsRunning()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());

        var first = await service.CreateProjectAsync(accountId, Request("Game One"));
        var second = await service.CreateProjectAsync(accountId, Request("Game Two"));

        first.Succeeded.Should().BeTrue();
        second.Succeeded.Should().BeFalse();
        second.FailureCode.Should().Be("project_initialization_in_progress");
    }

    [Fact]
    public async Task DeleteProjectAsync_RequiresTwoDeleteConfirmations_AndDeletesWorkspace()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, Request("Game One"));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var snapshot = await store.GetProjectSnapshotAsync(created.ProjectId!);

        var rejected = await service.DeleteProjectAsync(accountId, created.ProjectId!, new ProjectDeletionRequest("delete", "DELETE"));
        var deleted = await service.DeleteProjectAsync(accountId, created.ProjectId!, new ProjectDeletionRequest("delete", "delete"));

        rejected.Succeeded.Should().BeFalse();
        rejected.FailureCode.Should().Be("delete_confirmation_required");
        deleted.Succeeded.Should().BeTrue();
        (await store.GetProjectSnapshotAsync(created.ProjectId!)).Should().BeNull();
        Directory.Exists(snapshot!.WorkspaceRootPath).Should().BeFalse();
    }

    [Fact]
    public async Task DeleteProjectAsync_BlocksRunningProject()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, Request("Game One"));

        var deleted = await service.DeleteProjectAsync(accountId, created.ProjectId!, new ProjectDeletionRequest("delete", "delete"));

        deleted.Succeeded.Should().BeFalse();
        deleted.FailureCode.Should().Be("project_busy");
    }

    [Fact]
    public async Task DeleteProjectAsync_BlocksActiveRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, Request("Game One"));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var runId = await store.CreateRunAsync(created.ProjectId!, created.WorkspaceId, "prototype-draft-analysis");
        await store.MarkRunStartedAsync(runId);

        var deleted = await service.DeleteProjectAsync(accountId, created.ProjectId!, new ProjectDeletionRequest("delete", "delete"));

        deleted.Succeeded.Should().BeFalse();
        deleted.FailureCode.Should().Be("project_busy");
    }

    [Fact]
    public async Task DeleteProjectAsync_AllowsFailedProject()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, Request("Game One"));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "failed", "hard checks failed");
        var snapshot = await store.GetProjectSnapshotAsync(created.ProjectId!);

        var deleted = await service.DeleteProjectAsync(accountId, created.ProjectId!, new ProjectDeletionRequest("delete", "delete"));

        deleted.Succeeded.Should().BeTrue();
        (await store.GetProjectSnapshotAsync(created.ProjectId!)).Should().BeNull();
        Directory.Exists(snapshot!.WorkspaceRootPath).Should().BeFalse();
    }

    [Fact]
    public async Task ListStaleProjectInitializationsAsync_FindsOldRunningBootstrap()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, Request("Game One"));
        var runId = await store.CreateRunAsync(created.ProjectId!, created.WorkspaceId, "chapter2-bootstrap");
        await store.MarkRunStartedAsync(runId);

        using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                UPDATE runs
                SET created_utc = $old_utc,
                    started_utc = $old_utc
                WHERE id = $run_id;
                """;
            command.Parameters.AddWithValue("$old_utc", DateTimeOffset.UtcNow.AddMinutes(-20).ToString("O"));
            command.Parameters.AddWithValue("$run_id", runId);
            await command.ExecuteNonQueryAsync();
        }

        var stale = await store.ListStaleProjectInitializationsAsync(TimeSpan.FromMinutes(15));

        stale.Should().ContainSingle(item => item.ProjectId == created.ProjectId && item.RunId == runId);
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
