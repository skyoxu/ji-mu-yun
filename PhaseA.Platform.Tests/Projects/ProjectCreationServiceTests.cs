using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
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
        var readme = Path.Combine(snapshot.RepoPath, "README.md");
        File.Exists(readme).Should().BeTrue();
        File.ReadAllText(readme).Should().Contain("ProjectId: " + result.ProjectId);
        File.ReadAllText(readme).Should().Contain("GameTypeSource: manual");
        File.ReadAllBytes(readme).Take(3).Should().NotEqual([0xEF, 0xBB, 0xBF]);
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
    public async Task CreateProjectAsync_WhenWorkspaceSeedingFails_RecordsFailureAndDeletesProject()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(
            store,
            options,
            new ProjectRuleCatalog(),
            new ThrowingWorkspaceSeeder());

        var result = await service.CreateProjectAsync(accountId, Request("Game One"));

        result.Succeeded.Should().BeFalse();
        result.FailureCode.Should().Be("project_creation_failed");
        (await store.ListProjectsAsync(accountId)).Should().BeEmpty();
        (await store.ListOrphanedProjectInitializationsAsync()).Should().BeEmpty();
        var failure = await store.GetLatestProjectCreationFailureAsync(accountId);
        failure.Should().NotBeNull();
        failure!.ProjectName.Should().Be("Game One");
        failure.GameName.Should().Be("Game One");
        failure.FailureError.Should().Contain("Project workspace initialization failed before Chapter 2 bootstrap could start.");
        failure.FailureError.Should().Contain("seed failed");
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
    public async Task CreateProjectAsync_QuotaIsScopedPerAccount()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("phaseb-other", 1);
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());

        var ownerFirst = await service.CreateProjectAsync(owner, Request("Owner One"));
        await store.SetProjectBootstrapStatusAsync(ownerFirst.ProjectId!, "succeeded", null);
        var ownerSecond = await service.CreateProjectAsync(owner, Request("Owner Two"));
        await store.SetProjectBootstrapStatusAsync(ownerSecond.ProjectId!, "succeeded", null);
        var ownerThird = await service.CreateProjectAsync(owner, Request("Owner Three"));
        var otherFirst = await service.CreateProjectAsync(other.AccountId, Request("Other One"));

        ownerThird.Succeeded.Should().BeFalse();
        ownerThird.FailureCode.Should().Be("project_quota_exceeded");
        otherFirst.Succeeded.Should().BeTrue();
        Directory.Exists(Path.Combine(workspaceRoot.Path, other.AccountId, otherFirst.ProjectId!)).Should().BeTrue();
    }

    [Fact]
    public async Task CreateProjectAsync_AllowsIndependentCreations_WhenLimiterAllows()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(
            store,
            options,
            new ProjectRuleCatalog(),
            new ProjectWorkspaceSeeder(options),
            creationConcurrencyLimiter: new ProjectCreationConcurrencyLimiter(2, 2));

        var first = await service.CreateProjectAsync(accountId, Request("Game One"));
        var second = await service.CreateProjectAsync(accountId, Request("Game Two"));

        first.Succeeded.Should().BeTrue();
        second.Succeeded.Should().BeTrue();
    }

    [Fact]
    public async Task CreateProjectAsync_Blocks_WhenProjectCreationAccountLimiterIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var limiter = new ProjectCreationConcurrencyLimiter(2, 1);
        var held = await limiter.TryAcquireAsync(accountId);
        var service = new ProjectCreationService(
            store,
            options,
            new ProjectRuleCatalog(),
            new ProjectWorkspaceSeeder(options),
            creationConcurrencyLimiter: limiter);

        try
        {
            var result = await service.CreateProjectAsync(accountId, Request("Game One"));

            result.Succeeded.Should().BeFalse();
            result.FailureCode.Should().Be("user_project_creation_concurrency_limit_exceeded");
        }
        finally
        {
            if (held.Lease is not null)
            {
                await held.Lease.DisposeAsync();
            }
        }
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
    public async Task DeleteProjectAsync_BlocksOtherAccount()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("phaseb-delete-other", 1);
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(owner, Request("Owner Game"));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);

        var deleted = await service.DeleteProjectAsync(other.AccountId, created.ProjectId!, new ProjectDeletionRequest("delete", "delete"));

        deleted.Succeeded.Should().BeFalse();
        deleted.FailureCode.Should().Be("project_not_found");
        (await store.GetProjectSnapshotAsync(created.ProjectId!)).Should().NotBeNull();
    }

    [Fact]
    public async Task DeleteProjectAsync_CascadesProjectRecords_DeletesWorkspace_AndReleasesQuota()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var first = await service.CreateProjectAsync(accountId, Request("Game One"));
        await store.SetProjectBootstrapStatusAsync(first.ProjectId!, "succeeded", null);
        var second = await service.CreateProjectAsync(accountId, Request("Game Two"));
        await store.SetProjectBootstrapStatusAsync(second.ProjectId!, "succeeded", null);
        var firstSnapshot = await store.GetProjectSnapshotAsync(first.ProjectId!);
        var runId = await store.CreateRunAsync(first.ProjectId!, first.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(runId, "succeeded", 0, "ok", "", "{}", CancellationToken.None);
        await store.AddArtifactAsync(new ArtifactCreationCommand(runId, first.ProjectId!, "sample", "logs/ci/sample.txt", "sample"));
        await store.AddProjectChatMessageAsync(accountId, first.ProjectId!, "user", "hello", retainLatest: 10);
        await store.UpsertProjectChatMemoryAsync(accountId, first.ProjectId!, "project chat memory", "session-ref");
        await store.UpsertProjectPrototypeDraftAsync(
            first.ProjectId!,
            "succeeded",
            runId,
            "draft.txt",
            "demo",
            "hypothesis",
            "fantasy",
            "loop",
            "[]",
            "feature",
            "game loop",
            "win",
            "[]",
            "[]",
            null,
            0,
            null,
            "[]",
            null,
            1,
            10);
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            first.ProjectId!,
            "manual",
            "make it playable",
            "overall",
            [new ProjectIterationGoalCreateCommand(1, "goal", "description", "acceptance")]);
        var details = await store.GetLatestProjectIterationSessionAsync(first.ProjectId!);
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, details!.Goals[0].GoalId, runId, "prototype-iteration-goal");
        await store.UpsertProjectRunMemoryAsync(
            first.ProjectId!,
            "prototype",
            "needs_fix",
            "objective",
            "[]",
            "[]",
            "next",
            "[]",
            null,
            null);
        File.WriteAllText(Path.Combine(firstSnapshot!.RuntimePath, "package.zip"), "package");
        var quotaBlocked = await service.CreateProjectAsync(accountId, Request("Game Three"));

        var deleted = await service.DeleteProjectAsync(accountId, first.ProjectId!, new ProjectDeletionRequest("delete", "delete"));
        var replacement = await service.CreateProjectAsync(accountId, Request("Game Three"));

        quotaBlocked.Succeeded.Should().BeFalse();
        quotaBlocked.FailureCode.Should().Be("project_quota_exceeded");
        deleted.Succeeded.Should().BeTrue();
        replacement.Succeeded.Should().BeTrue();
        (await store.GetProjectSnapshotAsync(first.ProjectId!)).Should().BeNull();
        (await store.GetRunSnapshotAsync(runId)).Should().BeNull();
        (await store.ListArtifactsForRunAsync(runId)).Should().BeEmpty();
        (await store.ListProjectChatMessagesAsync(accountId, first.ProjectId!, limit: 10)).Should().BeEmpty();
        (await store.GetProjectChatMemoryAsync(accountId, first.ProjectId!)).Should().BeNull();
        (await store.GetProjectPrototypeDraftAsync(first.ProjectId!)).Should().BeNull();
        (await store.GetLatestProjectIterationSessionAsync(first.ProjectId!)).Should().BeNull();
        (await store.GetProjectRunMemoryAsync(first.ProjectId!, "prototype")).Should().BeNull();
        Directory.Exists(firstSnapshot.WorkspaceRootPath).Should().BeFalse();
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

    [Fact]
    public async Task ListOrphanedProjectInitializationsAsync_FindsRunningProjectWithoutBootstrapRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, Request("Game One"));

        var orphaned = await store.ListOrphanedProjectInitializationsAsync();

        orphaned.Should().ContainSingle(item =>
            item.ProjectId == created.ProjectId &&
            item.RunId == "" &&
            item.RunStatus == "missing");
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

    private sealed class ThrowingWorkspaceSeeder : IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string projectRepoPath)
        {
            throw new IOException("seed failed");
        }
    }
}
