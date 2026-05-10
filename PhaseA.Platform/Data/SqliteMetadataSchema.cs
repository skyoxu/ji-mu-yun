using Microsoft.Data.Sqlite;
using SQLitePCL;

namespace PhaseA.Platform.Data;

public static class SqliteMetadataSchema
{
    public static async Task InitializeAsync(string connectionString, CancellationToken cancellationToken = default)
    {
        Batteries_V2.Init();

        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync(cancellationToken);

        await ExecuteAsync(connection, "PRAGMA foreign_keys = ON;", cancellationToken);

        await using var transaction = connection.BeginTransaction();

        foreach (var statement in SchemaStatements)
        {
            await ExecuteAsync(connection, statement, transaction, cancellationToken);
        }

        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "projects",
            "llm_binding_required",
            "ALTER TABLE projects ADD COLUMN llm_binding_required INTEGER NOT NULL DEFAULT 0;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "projects",
            "allowed_workflows_json",
            "ALTER TABLE projects ADD COLUMN allowed_workflows_json TEXT NOT NULL DEFAULT '[]';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "exit_code",
            "ALTER TABLE runs ADD COLUMN exit_code INTEGER NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "stdout_text",
            "ALTER TABLE runs ADD COLUMN stdout_text TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "stderr_text",
            "ALTER TABLE runs ADD COLUMN stderr_text TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "evidence_json",
            "ALTER TABLE runs ADD COLUMN evidence_json TEXT NULL;",
            cancellationToken);

        await ExecuteAsync(connection, "PRAGMA user_version = 1;", transaction, cancellationToken);

        await transaction.CommitAsync(cancellationToken);
    }

    private static async Task ExecuteAsync(SqliteConnection connection, string sql, CancellationToken cancellationToken)
    {
        await ExecuteAsync(connection, sql, null, cancellationToken);
    }

    private static async Task ExecuteAsync(SqliteConnection connection, string sql, SqliteTransaction? transaction, CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        command.Transaction = transaction;
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private static async Task AddColumnIfMissingAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        string tableName,
        string columnName,
        string alterSql,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = $"PRAGMA table_info({tableName});";

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            if (string.Equals(reader.GetString(1), columnName, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }
        }

        await reader.DisposeAsync();
        await ExecuteAsync(connection, alterSql, transaction, cancellationToken);
    }

    private static readonly string[] SchemaStatements =
    [
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NULL,
            token_hash TEXT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_utc TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_limits (
            account_id TEXT PRIMARY KEY,
            project_limit INTEGER NOT NULL CHECK (project_limit >= 1),
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            name TEXT NOT NULL,
            game_name TEXT NOT NULL,
            game_type_source TEXT NOT NULL,
            template_rule_id TEXT NOT NULL,
            llm_binding_required INTEGER NOT NULL DEFAULT 0,
            allowed_workflows_json TEXT NOT NULL DEFAULT '[]',
            created_utc TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL UNIQUE,
            root_path TEXT NOT NULL,
            repo_path TEXT NOT NULL,
            runtime_path TEXT NOT NULL,
            meta_path TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            workspace_id TEXT NULL,
            run_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            started_utc TEXT NULL,
            finished_utc TEXT NULL,
            exit_code INTEGER NULL,
            stdout_text TEXT NULL,
            stderr_text TEXT NULL,
            evidence_json TEXT NULL,
            llm_gateway TEXT NULL,
            llm_request_id TEXT NULL,
            llm_model TEXT NULL,
            llm_cost_json TEXT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            run_id TEXT NULL,
            project_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE SET NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_id TEXT NULL,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            decided_utc TEXT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS runner_locks (
            project_id TEXT PRIMARY KEY,
            run_id TEXT NULL,
            acquired_utc TEXT NOT NULL,
            expires_utc TEXT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE SET NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS account_llm_bindings (
            account_id TEXT PRIMARY KEY,
            gateway_provider TEXT NOT NULL,
            gateway_base_url TEXT NOT NULL,
            external_account_ref TEXT NOT NULL,
            token_ref TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_projects_account_id ON projects(account_id);",
        "CREATE INDEX IF NOT EXISTS ix_runs_project_id_status ON runs(project_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_artifacts_project_id ON artifacts(project_id);"
    ];
}
