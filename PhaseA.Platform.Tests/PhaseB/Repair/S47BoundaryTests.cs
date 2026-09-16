using Microsoft.Data.Sqlite;
using PhaseA.Platform.Data;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S47BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S47BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_8FFDBFE8DE13()
    {
        using var database = new DisposableDatabase();
        await CreateLegacyDatabaseAsync(database.ConnectionString);
        var before = await ReadArtifactsAsync(database.ConnectionString);

        await MigrateThroughServiceStartupAsync(database.ConnectionString);
        await MigrateThroughServiceStartupAsync(database.ConnectionString);

        var after = await ReadArtifactsAsync(database.ConnectionString);
        Require(
            before.SequenceEqual(after),
            "FAILURE-O-8FFDBFE8DE13",
            "Existing artifact records or their data changed after migration and reuse.");
        _output.WriteLine("S47-OBSERVATION O-8FFDBFE8DE13 artifacts-preserved-after-reuse");
    }

    [Fact]
    public async Task O_B1796B703851()
    {
        using var database = new DisposableDatabase();
        await CreateLegacyDatabaseAsync(database.ConnectionString);

        await MigrateThroughServiceStartupAsync(database.ConnectionString);

        var artifacts = await ReadArtifactsAsync(database.ConnectionString);
        Require(
            artifacts.Count == 2 && artifacts[0].Id == "artifact-legacy-1" && artifacts[1].Id == "artifact-legacy-2",
            "FAILURE-O-B1796B703851",
            "The populated legacy schema was not upgraded with retained artifact rows.");
        _output.WriteLine("S47-OBSERVATION O-B1796B703851 populated-legacy-schema-upgraded");
    }

    [Fact]
    public async Task O_BAAD0C35FE10()
    {
        using var database = new DisposableDatabase();
        await CreateLegacyDatabaseAsync(database.ConnectionString);
        await MigrateThroughServiceStartupAsync(database.ConnectionString);

        await MigrateThroughServiceStartupAsync(database.ConnectionString);
        var retained = await ReadArtifactsAsync(database.ConnectionString);
        await InsertArtifactAsync(database.ConnectionString, "artifact-after-restart", "restart-check");
        var reopened = await ReadArtifactsAsync(database.ConnectionString);

        Require(
            retained.All(record => reopened.Contains(record)) &&
            reopened.Any(record => record.Id == "artifact-after-restart" && record.Summary == "restart-check"),
            "FAILURE-O-BAAD0C35FE10",
            "The migrated database could not be reopened and used after service restart.");
        _output.WriteLine("S47-OBSERVATION O-BAAD0C35FE10 database-reopened-after-restart");
    }

    [Fact]
    public async Task O_F3ECA0548B57()
    {
        using var database = new DisposableDatabase();
        await CreateLegacyDatabaseAsync(database.ConnectionString);
        var before = await ReadOwnershipAsync(database.ConnectionString);

        await MigrateThroughServiceStartupAsync(database.ConnectionString);
        await MigrateThroughServiceStartupAsync(database.ConnectionString);

        var after = await ReadOwnershipAsync(database.ConnectionString);
        Require(
            before.SequenceEqual(after),
            "FAILURE-O-F3ECA0548B57",
            "Existing artifact ownership relationships changed after migration and reuse.");
        _output.WriteLine("S47-OBSERVATION O-F3ECA0548B57 ownership-preserved-after-reuse");
    }

    private static Task MigrateThroughServiceStartupAsync(string connectionString)
    {
        // Program.cs invokes this production owner during service startup.
        return SqliteMetadataSchema.InitializeAsync(connectionString);
    }

    private static async Task CreateLegacyDatabaseAsync(string connectionString)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NULL,
                token_hash TEXT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                name TEXT NOT NULL,
                game_name TEXT NOT NULL,
                game_type_source TEXT NOT NULL,
                template_rule_id TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT NULL,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                started_utc TEXT NULL,
                finished_utc TEXT NULL
            );
            CREATE TABLE artifacts (
                id TEXT PRIMARY KEY,
                run_id TEXT NULL,
                project_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            INSERT INTO accounts VALUES ('account-legacy', 'legacy-user', NULL, NULL, 0, '2026-08-01T00:00:00Z');
            INSERT INTO projects VALUES ('project-legacy', 'account-legacy', 'Existing Project', 'Existing Game', 'manual', 'rule-legacy', '2026-08-01T00:00:00Z');
            INSERT INTO runs VALUES ('run-legacy', 'project-legacy', 'workspace-legacy', 'repair', 'succeeded', '2026-08-01T01:00:00Z', '2026-08-01T01:01:00Z', '2026-08-01T01:02:00Z');
            INSERT INTO artifacts VALUES ('artifact-legacy-1', 'run-legacy', 'project-legacy', 'report', 'reports/one.json', 'first artifact', '2026-08-01T01:03:00Z');
            INSERT INTO artifacts VALUES ('artifact-legacy-2', 'run-legacy', 'project-legacy', 'snapshot', 'snapshots/two.zip', 'second artifact', '2026-08-01T01:04:00Z');
            """;
        await command.ExecuteNonQueryAsync();
    }

    private static async Task<List<ArtifactRecord>> ReadArtifactsAsync(string connectionString)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT id, run_id, project_id, artifact_type, relative_path, summary, created_utc FROM artifacts ORDER BY id;";
        await using var reader = await command.ExecuteReaderAsync();
        var records = new List<ArtifactRecord>();
        while (await reader.ReadAsync())
        {
            records.Add(new ArtifactRecord(
                reader.GetString(0),
                reader.IsDBNull(1) ? null : reader.GetString(1),
                reader.GetString(2),
                reader.GetString(3),
                reader.GetString(4),
                reader.GetString(5),
                reader.GetString(6)));
        }

        return records;
    }

    private static async Task<List<OwnershipRecord>> ReadOwnershipAsync(string connectionString)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            SELECT a.id, a.project_id, p.account_id
            FROM artifacts a
            JOIN projects p ON p.id = a.project_id
            ORDER BY a.id;
            """;
        await using var reader = await command.ExecuteReaderAsync();
        var records = new List<OwnershipRecord>();
        while (await reader.ReadAsync())
        {
            records.Add(new OwnershipRecord(reader.GetString(0), reader.GetString(1), reader.GetString(2)));
        }

        return records;
    }

    private static async Task InsertArtifactAsync(string connectionString, string id, string summary)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO artifacts (id, run_id, project_id, artifact_type, relative_path, summary, created_utc) VALUES ($id, 'run-legacy', 'project-legacy', 'restart', $path, $summary, '2026-08-01T02:00:00Z');";
        command.Parameters.AddWithValue("$id", id);
        command.Parameters.AddWithValue("$path", $"restart/{id}.json");
        command.Parameters.AddWithValue("$summary", summary);
        await command.ExecuteNonQueryAsync();
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed record ArtifactRecord(
        string Id,
        string? RunId,
        string ProjectId,
        string ArtifactType,
        string RelativePath,
        string Summary,
        string CreatedUtc);

    private sealed record OwnershipRecord(string ArtifactId, string ProjectId, string AccountId);

    private sealed class DisposableDatabase : IDisposable
    {
        private readonly string _path = Path.Combine(Path.GetTempPath(), $"s47-{Guid.NewGuid():N}.db");

        public string ConnectionString => new SqliteConnectionStringBuilder { DataSource = _path }.ToString();

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (File.Exists(_path))
            {
                File.Delete(_path);
            }
        }
    }
}
