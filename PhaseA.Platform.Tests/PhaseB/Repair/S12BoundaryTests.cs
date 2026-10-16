using Microsoft.Data.Sqlite;
using PhaseA.Platform.Data;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S12BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S12BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_53F5B5BDADAC()
    {
        using var database = new DisposableDatabase();

        await MigrateThroughServiceStartupAsync(database.ConnectionString);

        var tables = await ReadTableNamesAsync(database.ConnectionString, "accounts", "projects", "runs");
        Require(
            tables.SetEquals(["accounts", "projects", "runs"]),
            "FAILURE-O-53F5B5BDADAC",
            "Fresh startup migration did not create the current application tables.");
        _output.WriteLine("S12-OBSERVATION O-53F5B5BDADAC fresh-current-schema");
    }

    [Fact]
    public async Task O_69160595B925()
    {
        using var database = new DisposableDatabase();
        await CreateLegacyDatabaseAsync(database.ConnectionString, includeRun: false);

        await MigrateThroughServiceStartupAsync(database.ConnectionString);
        await MigrateThroughServiceStartupAsync(database.ConnectionString);

        var project = await ReadProjectAsync(database.ConnectionString);
        Require(
            project == ("project-legacy", "account-legacy", "Existing Project", "Existing Game", "manual", "rule-legacy", "2026-08-01T00:00:00Z"),
            "FAILURE-O-69160595B925",
            "The legacy project identity or data changed after migration and reuse.");
        _output.WriteLine("S12-OBSERVATION O-69160595B925 project-preserved-after-reuse");
    }

    [Fact]
    public async Task O_6D67982456AE()
    {
        using var fresh = new DisposableDatabase();
        await MigrateThroughServiceStartupAsync(fresh.ConnectionString);
        await InsertLegacyShapedRecordsAsync(fresh.ConnectionString, includeRun: true);

        var freshFields = await ReadIntroducedFieldsAsync(fresh.ConnectionString);
        Require(
            freshFields == ExpectedIntroducedFields,
            "FAILURE-O-6D67982456AE",
            "Fresh startup migration did not expose usable defaults for current project and run fields.");

        using var legacy = new DisposableDatabase();
        await CreateLegacyDatabaseAsync(legacy.ConnectionString, includeRun: true);
        await MigrateThroughServiceStartupAsync(legacy.ConnectionString);

        var legacyFields = await ReadIntroducedFieldsAsync(legacy.ConnectionString);
        Require(
            legacyFields == ExpectedIntroducedFields,
            "FAILURE-O-6D67982456AE",
            "Legacy upgrade did not expose usable defaults for current project and run fields.");
        _output.WriteLine("S12-OBSERVATION O-6D67982456AE fresh-and-legacy-introduced-fields");
    }

    [Fact]
    public async Task O_7E6C4AC321CE()
    {
        using var database = new DisposableDatabase();
        await CreateLegacyDatabaseAsync(database.ConnectionString, includeRun: true);

        await MigrateThroughServiceStartupAsync(database.ConnectionString);
        await MigrateThroughServiceStartupAsync(database.ConnectionString);

        var run = await ReadRunAsync(database.ConnectionString);
        Require(
            run == ("run-legacy", "project-legacy", "workspace-legacy", "repair", "succeeded", "2026-08-01T01:00:00Z", "2026-08-01T01:01:00Z", "2026-08-01T01:02:00Z"),
            "FAILURE-O-7E6C4AC321CE",
            "The legacy run identity or data changed after migration and reuse.");
        _output.WriteLine("S12-OBSERVATION O-7E6C4AC321CE run-preserved-after-reuse");
    }

    private static readonly (
        long LlmBindingRequired,
        string AllowedWorkflows,
        string BootstrapStatus,
        string GameTypeMatch,
        string ProgressStep,
        string ProgressSubstep,
        string ProgressLabel)
        ExpectedIntroducedFields = (0, "[]", "initial", "{}", "", "", "");

    private static Task MigrateThroughServiceStartupAsync(string connectionString)
    {
        // Program.cs invokes this production owner during service startup.
        return SqliteMetadataSchema.InitializeAsync(connectionString);
    }

    private static async Task CreateLegacyDatabaseAsync(string connectionString, bool includeRun)
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
            INSERT INTO accounts VALUES ('account-legacy', 'legacy-user', NULL, NULL, 0, '2026-08-01T00:00:00Z');
            INSERT INTO projects VALUES ('project-legacy', 'account-legacy', 'Existing Project', 'Existing Game', 'manual', 'rule-legacy', '2026-08-01T00:00:00Z');
            """ + (includeRun
                ? "INSERT INTO runs VALUES ('run-legacy', 'project-legacy', 'workspace-legacy', 'repair', 'succeeded', '2026-08-01T01:00:00Z', '2026-08-01T01:01:00Z', '2026-08-01T01:02:00Z');"
                : string.Empty);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task InsertLegacyShapedRecordsAsync(string connectionString, bool includeRun)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            INSERT INTO accounts (id, username, created_utc) VALUES ('account-legacy', 'legacy-user', '2026-08-01T00:00:00Z');
            INSERT INTO projects (id, account_id, name, game_name, game_type_source, template_rule_id, created_utc)
            VALUES ('project-legacy', 'account-legacy', 'Existing Project', 'Existing Game', 'manual', 'rule-legacy', '2026-08-01T00:00:00Z');
            INSERT INTO workspaces (id, project_id, root_path, repo_path, runtime_path, meta_path, created_utc)
            VALUES ('workspace-legacy', 'project-legacy', 'C:/legacy', 'C:/legacy/repo', 'C:/legacy/runtime', 'C:/legacy/meta', '2026-08-01T00:00:00Z');
            """ + (includeRun
                ? "INSERT INTO runs (id, project_id, workspace_id, run_type, status, created_utc) VALUES ('run-legacy', 'project-legacy', 'workspace-legacy', 'repair', 'succeeded', '2026-08-01T01:00:00Z');"
                : string.Empty);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task<HashSet<string>> ReadTableNamesAsync(string connectionString, params string[] tableNames)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('accounts', 'projects', 'runs');";
        await using var reader = await command.ExecuteReaderAsync();
        var actual = new HashSet<string>(StringComparer.Ordinal);
        while (await reader.ReadAsync())
        {
            actual.Add(reader.GetString(0));
        }

        return actual;
    }

    private static async Task<(string, string, string, string, string, string, string)> ReadProjectAsync(string connectionString)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT id, account_id, name, game_name, game_type_source, template_rule_id, created_utc FROM projects WHERE id = 'project-legacy';";
        await using var reader = await command.ExecuteReaderAsync();
        Require(await reader.ReadAsync(), "FAILURE-O-69160595B925", "The legacy project was not found after migration.");
        return (reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetString(3), reader.GetString(4), reader.GetString(5), reader.GetString(6));
    }

    private static async Task<(string, string, string, string, string, string, string, string)> ReadRunAsync(string connectionString)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT id, project_id, workspace_id, run_type, status, created_utc, started_utc, finished_utc FROM runs WHERE id = 'run-legacy';";
        await using var reader = await command.ExecuteReaderAsync();
        Require(await reader.ReadAsync(), "FAILURE-O-7E6C4AC321CE", "The legacy run was not found after migration.");
        return (reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetString(3), reader.GetString(4), reader.GetString(5), reader.GetString(6), reader.GetString(7));
    }

    private static async Task<(long, string, string, string, string, string, string)> ReadIntroducedFieldsAsync(string connectionString)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            SELECT p.llm_binding_required, p.allowed_workflows_json, p.bootstrap_status, p.game_type_match_json,
                   r.progress_step, r.progress_substep, r.progress_label
            FROM projects p
            JOIN runs r ON r.project_id = p.id
            WHERE p.id = 'project-legacy' AND r.id = 'run-legacy';
            """;
        await using var reader = await command.ExecuteReaderAsync();
        Require(await reader.ReadAsync(), "FAILURE-O-6D67982456AE", "The migrated records could not be queried with current fields.");
        return (
            reader.GetInt64(0),
            ReadRequiredText(reader, 1),
            ReadRequiredText(reader, 2),
            ReadRequiredText(reader, 3),
            ReadRequiredText(reader, 4),
            ReadRequiredText(reader, 5),
            ReadRequiredText(reader, 6));
    }

    private static string ReadRequiredText(SqliteDataReader reader, int ordinal)
    {
        return reader.IsDBNull(ordinal) ? "<NULL>" : reader.GetString(ordinal);
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class DisposableDatabase : IDisposable
    {
        private readonly string _path = Path.Combine(Path.GetTempPath(), $"s12-{Guid.NewGuid():N}.db");

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
