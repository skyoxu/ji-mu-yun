using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
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
            "project_chat_messages"
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
