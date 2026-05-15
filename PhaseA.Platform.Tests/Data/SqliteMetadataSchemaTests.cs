using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class SqliteMetadataSchemaTests
{
    [Fact]
    public async Task InitializeAsync_CreatesExpectedTables_AndIsRepeatable()
    {
        using var database = TempSqliteDatabase.Create();

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);

        var tables = await database.ReadTableNamesAsync();

        tables.Should().Contain([
            "accounts",
            "projects",
            "workspaces",
            "runs",
            "artifacts",
            "approvals",
            "project_limits",
            "runner_locks",
            "account_llm_bindings",
            "project_chat_messages",
            "project_prototype_drafts"
        ]);
    }

    [Fact]
    public async Task EnsureSingleAdminAsync_BootstrapsAdminWithDefaultProjectLimit()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);

        var accountId = await store.EnsureSingleAdminAsync();
        var repeatedAccountId = await store.EnsureSingleAdminAsync();
        var projectLimit = await store.GetProjectLimitAsync(accountId);

        repeatedAccountId.Should().Be(accountId);
        projectLimit.Should().Be(2);
    }

    [Fact]
    public async Task CreateProjectAsync_EnforcesDefaultAccountQuota()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();

        var first = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        first.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(first.ProjectId!, "succeeded", null);
        var second = await store.CreateProjectAsync(CreateCommand(accountId, "project-two", "Game Two"));
        second.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(second.ProjectId!, "succeeded", null);
        var third = await store.CreateProjectAsync(CreateCommand(accountId, "project-three", "Game Three"));

        third.Succeeded.Should().BeFalse();
        third.FailureCode.Should().Be("project_quota_exceeded");
        third.ProjectLimit.Should().Be(2);
    }

    [Fact]
    public async Task ProjectChatMessages_AreAccountAndProjectScoped_AndRetained()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));

        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "user", "hello", retainLatest: 2);
        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "assistant", "world", retainLatest: 2);
        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "user", "latest", retainLatest: 2);

        var messages = await store.ListProjectChatMessagesAsync(accountId, project.ProjectId!, limit: 10);
        var otherAccountMessages = await store.ListProjectChatMessagesAsync("other-account", project.ProjectId!, limit: 10);

        messages.Select(message => message.Content).Should().Equal("world", "latest");
        messages.Select(message => message.Role).Should().Equal("assistant", "user");
        otherAccountMessages.Should().BeEmpty();
    }

    [Fact]
    public async Task ReconcileAbandonedRunsAsync_FailsOnlyRunsThatExceededHeartbeatTimeout()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var staleCreated = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Stale Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(staleCreated.ProjectId!, "succeeded", null);
        var freshCreated = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Fresh Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(freshCreated.ProjectId!, "succeeded", null);
        var staleProject = await store.GetProjectSnapshotAsync(staleCreated.ProjectId!);
        var freshProject = await store.GetProjectSnapshotAsync(freshCreated.ProjectId!);
        var staleRunId = await store.CreateRunAsync(staleProject!.ProjectId, staleProject.WorkspaceId, "prototype-feedback-iteration");
        var freshRunId = await store.CreateRunAsync(freshProject!.ProjectId, freshProject.WorkspaceId, "prototype-feedback-iteration");
        await store.MarkRunStartedAsync(staleRunId);
        await store.MarkRunStartedAsync(freshRunId);
        await store.TryAcquireRunnerLockAsync(staleProject.ProjectId, staleRunId);
        await store.TryAcquireRunnerLockAsync(freshProject.ProjectId, freshRunId);

        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                UPDATE runs
                SET started_utc = $old_utc,
                    progress_updated_utc = $old_utc
                WHERE id = $run_id;
                """;
            command.Parameters.AddWithValue("$old_utc", DateTimeOffset.UtcNow.AddHours(-2).ToString("O"));
            command.Parameters.AddWithValue("$run_id", staleRunId);
            await command.ExecuteNonQueryAsync();
        }

        var recovered = await store.ReconcileAbandonedRunsAsync(
            run => run.RunType == "prototype-feedback-iteration" ? TimeSpan.FromHours(1) : null,
            run => $"timeout:{run.RunType}");
        var staleRun = await store.GetRunSnapshotAsync(staleRunId);
        var freshRun = await store.GetRunSnapshotAsync(freshRunId);

        recovered.Should().Be(1);
        staleRun!.Status.Should().Be("failed");
        staleRun.StderrText.Should().Contain("timeout:prototype-feedback-iteration");
        freshRun!.Status.Should().Be("running");
        (await store.HasRunnerLockAsync(staleProject.ProjectId)).Should().BeFalse();
        (await store.HasRunnerLockAsync(freshProject.ProjectId)).Should().BeTrue();
    }

    private static ProjectCreationCommand CreateCommand(string accountId, string projectName, string gameName)
    {
        var projectId = Guid.NewGuid().ToString("N");
        var root = Path.Combine(Path.GetTempPath(), projectId);
        return new ProjectCreationCommand(
            projectId,
            accountId,
            projectName,
            gameName,
            "admin-rule",
            "godot-prototype-default",
            true,
            ["chapter2-bootstrap", "prototype-7day-playable", "prototype-tdd", "prototype-scene"],
            root,
            Path.Combine(root, "repo"),
            Path.Combine(root, "runtime"),
            Path.Combine(root, "meta"));
    }
}
