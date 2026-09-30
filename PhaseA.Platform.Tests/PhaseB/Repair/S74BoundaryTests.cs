using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S74BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S74BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_FA59596D5B97()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var projectId = await fixture.CreateLegacyWorkspaceWithoutSafetyEvidenceAsync();

        var resolved = await fixture.ResolveThroughMetadataBoundaryAsync(projectId);

        Require(
            resolved is null || string.IsNullOrWhiteSpace(resolved.WorkspaceId),
            "FAILURE-O-FA59596D5B97",
            "The legacy Workspace escaped authorized containment and had no manifest or ACL safety evidence, but it remained available for adoption.");
        _output.WriteLine("S74-OBSERVATION O-FA59596D5B97 unsafe-legacy-workspace-blocked-before-adoption");
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
            var root = Path.Combine(Path.GetTempPath(), $"s74-boundary-{Guid.NewGuid():N}");
            Directory.CreateDirectory(root);
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath, Pooling = false }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "authorized-workspaces"),
            });
            return new BoundaryFixture(root, databasePath, new PhaseAMetadataStore(connectionString, options));
        }

        public async Task<string> CreateLegacyWorkspaceWithoutSafetyEvidenceAsync()
        {
            var account = await _store.CreateUserAccountAsync("s74-known-owner", 1);
            var projectId = $"legacy-{Guid.NewGuid():N}";
            var workspaceId = $"legacy-workspace-{Guid.NewGuid():N}";
            var escapedRoot = Path.Combine(_root, "outside-authorized-root");
            Directory.CreateDirectory(escapedRoot);

            await using var connection = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = _databasePath, Pooling = false }.ToString());
            await connection.OpenAsync();
            await using var foreignKeys = connection.CreateCommand();
            foreignKeys.CommandText = "PRAGMA foreign_keys = OFF;";
            await foreignKeys.ExecuteNonQueryAsync();

            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                INSERT INTO projects (
                    id, account_id, name, game_name, game_type_source, template_rule_id, created_utc)
                VALUES ($project_id, $account_id, 'S74 legacy project', 'S74 legacy project', 'legacy', 'legacy', $created_utc);

                INSERT INTO workspaces (id, project_id, root_path, repo_path, runtime_path, meta_path, created_utc)
                VALUES ($workspace_id, $project_id, $root_path, $repo_path, $runtime_path, $meta_path, $created_utc);
                """;
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$account_id", account.AccountId);
            command.Parameters.AddWithValue("$workspace_id", workspaceId);
            command.Parameters.AddWithValue("$root_path", escapedRoot);
            command.Parameters.AddWithValue("$repo_path", Path.Combine(escapedRoot, "repo"));
            command.Parameters.AddWithValue("$runtime_path", Path.Combine(escapedRoot, "runtime"));
            command.Parameters.AddWithValue("$meta_path", Path.Combine(escapedRoot, "meta"));
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync();
            return projectId;
        }

        public Task<ProjectSnapshot?> ResolveThroughMetadataBoundaryAsync(string projectId) =>
            _store.GetProjectSnapshotAsync(projectId);

        public ValueTask DisposeAsync()
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(_root, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            return ValueTask.CompletedTask;
        }
    }
}
