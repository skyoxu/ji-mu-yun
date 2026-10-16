using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S75BoundaryTests
{
    [Fact]
    public async Task O_AB9213E2F95A()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var owner = await fixture.CreateAccountAsync("s75-known-owner");
        var projectId = await fixture.CreateLegacyProjectAsync(owner.AccountId, "known-owner");

        var resolved = await fixture.ResolveProjectAsync(projectId);
        var persisted = await fixture.ReadWorkspaceMappingAsync(projectId);
        var ownerCanUseProject = await fixture.ProjectBelongsToAccountAsync(owner.AccountId, projectId);
        var ownerProjects = await fixture.ListProjectsAsync(owner.AccountId);

        Require(
            resolved is not null &&
            persisted is not null &&
            !string.IsNullOrWhiteSpace(resolved.WorkspaceId) &&
            resolved.ProjectId == projectId &&
            resolved.AccountId == owner.AccountId &&
            persisted.WorkspaceId == resolved.WorkspaceId &&
            persisted.ProjectId == projectId &&
            persisted.AccountId == owner.AccountId &&
            ownerCanUseProject &&
            ownerProjects.Any(project => project.ProjectId == projectId),
            "FAILURE-O-AB9213E2F95A",
            "The known legacy Workspace was not adopted through a persisted server-owned workspace, account, and project mapping.");
    }

    [Fact]
    public async Task O_1C96420A7A74()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateAccountAsync("s75-ambiguous-requester");
        var alternate = await fixture.CreateAccountAsync("s75-ambiguous-alternate");
        var projectId = await fixture.CreateLegacyProjectWithWorkspaceAsync(
            $"{requester.AccountId}|{alternate.AccountId}");

        var resolved = await fixture.ResolveProjectAsync(projectId);
        var persisted = await fixture.ReadWorkspaceMappingAsync(projectId);
        var requesterCanUseProject = await fixture.ProjectBelongsToAccountAsync(requester.AccountId, projectId);
        var requesterProjects = await fixture.ListProjectsAsync(requester.AccountId);

        Require(
            resolved is not null &&
            resolved.BootstrapStatus == "quarantined" &&
            persisted is not null &&
            persisted.ProjectId == projectId &&
            persisted.AccountId == $"{requester.AccountId}|{alternate.AccountId}" &&
            !requesterCanUseProject &&
            requesterProjects.All(project => project.ProjectId != projectId),
            "FAILURE-O-1C96420A7A74",
            "The ambiguously owned legacy Workspace was not persistently quarantined and denied normal-use access.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class BoundaryFixture : IAsyncDisposable
    {
        private readonly string _root;
        private readonly string _databasePath;
        private readonly PhaseAMetadataStore _store;

        private BoundaryFixture(string root, string databasePath, PhaseAMetadataStore store)
        {
            _root = root;
            _databasePath = databasePath;
            _store = store;
        }

        public static async Task<BoundaryFixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s75-boundary-{Guid.NewGuid():N}");
            Directory.CreateDirectory(root);
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath, Pooling = false }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            });
            return new BoundaryFixture(root, databasePath, new PhaseAMetadataStore(connectionString, options));
        }

        public Task<AdminCreateUserResult> CreateAccountAsync(string username) =>
            _store.CreateUserAccountAsync(username, 1);

        public async Task<string> CreateLegacyProjectAsync(string accountId, string name)
        {
            var projectId = $"legacy-{Guid.NewGuid():N}";
            await using var connection = await OpenLegacyConnectionAsync();
            await InsertLegacyProjectAsync(connection, projectId, accountId, name);
            return projectId;
        }

        public async Task<string> CreateLegacyProjectWithWorkspaceAsync(string accountId)
        {
            var projectId = await CreateLegacyProjectAsync(accountId, "ambiguous-owner");
            var workspaceId = $"legacy-workspace-{Guid.NewGuid():N}";
            var workspaceRoot = Path.Combine(_root, workspaceId);
            Directory.CreateDirectory(workspaceRoot);
            await using var connection = await OpenLegacyConnectionAsync();
            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                INSERT INTO workspaces (id, project_id, root_path, repo_path, runtime_path, meta_path, created_utc)
                VALUES ($id, $project_id, $root_path, $repo_path, $runtime_path, $meta_path, $created_utc);
                """;
            command.Parameters.AddWithValue("$id", workspaceId);
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$root_path", workspaceRoot);
            command.Parameters.AddWithValue("$repo_path", Path.Combine(workspaceRoot, "repo"));
            command.Parameters.AddWithValue("$runtime_path", Path.Combine(workspaceRoot, "runtime"));
            command.Parameters.AddWithValue("$meta_path", Path.Combine(workspaceRoot, "meta"));
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync();
            return projectId;
        }

        public Task<ProjectSnapshot?> ResolveProjectAsync(string projectId) => _store.GetProjectSnapshotAsync(projectId);

        public Task<bool> ProjectBelongsToAccountAsync(string accountId, string projectId) =>
            _store.ProjectBelongsToAccountAsync(accountId, projectId);

        public Task<IReadOnlyList<ProjectListItem>> ListProjectsAsync(string accountId) => _store.ListProjectsAsync(accountId);

        public async Task<WorkspaceOwnershipMapping?> ReadWorkspaceMappingAsync(string projectId)
        {
            await using var connection = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = _databasePath, Pooling = false }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                SELECT w.id, p.account_id, w.project_id
                FROM workspaces w
                INNER JOIN projects p ON p.id = w.project_id
                WHERE w.project_id = $project_id
                ORDER BY w.created_utc ASC, w.id ASC
                LIMIT 1;
                """;
            command.Parameters.AddWithValue("$project_id", projectId);
            await using var reader = await command.ExecuteReaderAsync();
            return await reader.ReadAsync()
                ? new WorkspaceOwnershipMapping(reader.GetString(0), reader.GetString(1), reader.GetString(2))
                : null;
        }

        public ValueTask DisposeAsync()
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(_root, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            return ValueTask.CompletedTask;
        }

        private async Task<SqliteConnection> OpenLegacyConnectionAsync()
        {
            var connection = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = _databasePath, Pooling = false }.ToString());
            await connection.OpenAsync();
            await using var foreignKeys = connection.CreateCommand();
            foreignKeys.CommandText = "PRAGMA foreign_keys = OFF;";
            await foreignKeys.ExecuteNonQueryAsync();
            return connection;
        }

        private static async Task InsertLegacyProjectAsync(
            SqliteConnection connection,
            string projectId,
            string accountId,
            string name)
        {
            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                INSERT INTO projects (
                    id, account_id, name, game_name, game_type_source, template_rule_id, created_utc)
                VALUES ($id, $account_id, $name, $game_name, 'legacy', 'legacy', $created_utc);
                """;
            command.Parameters.AddWithValue("$id", projectId);
            command.Parameters.AddWithValue("$account_id", accountId);
            command.Parameters.AddWithValue("$name", name);
            command.Parameters.AddWithValue("$game_name", name);
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync();
        }
    }

    private sealed record WorkspaceOwnershipMapping(string WorkspaceId, string AccountId, string ProjectId);
}
