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
            "projects",
            "bootstrap_status",
            "ALTER TABLE projects ADD COLUMN bootstrap_status TEXT NOT NULL DEFAULT 'initial';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "projects",
            "bootstrap_error",
            "ALTER TABLE projects ADD COLUMN bootstrap_error TEXT NULL;",
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
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "progress_step",
            "ALTER TABLE runs ADD COLUMN progress_step TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "progress_substep",
            "ALTER TABLE runs ADD COLUMN progress_substep TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "progress_label",
            "ALTER TABLE runs ADD COLUMN progress_label TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "runs",
            "progress_updated_utc",
            "ALTER TABLE runs ADD COLUMN progress_updated_utc TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_iteration_sessions",
            "latest_evaluation_json",
            "ALTER TABLE project_iteration_sessions ADD COLUMN latest_evaluation_json TEXT NULL;",
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
        if (tableName == "projects" && columnName == "bootstrap_status")
        {
            await ExecuteAsync(
                connection,
                """
                UPDATE projects
                SET bootstrap_status = CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.project_id = projects.id
                          AND runs.run_type = 'chapter2-bootstrap'
                          AND runs.status = 'succeeded'
                    ) THEN 'succeeded'
                    ELSE 'initial'
                END;
                """,
                transaction,
                cancellationToken);
        }
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
            bootstrap_status TEXT NOT NULL DEFAULT 'initial',
            bootstrap_error TEXT NULL,
            created_utc TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_creation_failures (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            game_name TEXT NOT NULL,
            game_type_source TEXT NOT NULL,
            template_rule_id TEXT NOT NULL,
            workspace_root_path TEXT NOT NULL,
            failure_error TEXT NOT NULL,
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
            progress_step TEXT NOT NULL DEFAULT '',
            progress_substep TEXT NOT NULL DEFAULT '',
            progress_label TEXT NOT NULL DEFAULT '',
            progress_updated_utc TEXT NULL,
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
        """
        CREATE TABLE IF NOT EXISTS project_chat_messages (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            kind TEXT NULL,
            created_utc TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_prototype_drafts (
            project_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            run_id TEXT NULL,
            file_name TEXT NULL,
            prototype_slug TEXT NULL,
            hypothesis TEXT NULL,
            core_player_fantasy TEXT NULL,
            minimum_playable_loop TEXT NULL,
            success_criteria_json TEXT NOT NULL DEFAULT '[]',
            game_feature TEXT NULL,
            core_gameplay_loop TEXT NULL,
            win_fail_conditions TEXT NULL,
            matched_fields_json TEXT NOT NULL DEFAULT '[]',
            warnings_json TEXT NOT NULL DEFAULT '[]',
            failure_code TEXT NULL,
            line_count INTEGER NOT NULL DEFAULT 0,
            byte_count INTEGER NOT NULL DEFAULT 0,
            updated_utc TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE SET NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_iteration_sessions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_message TEXT NOT NULL,
            overall_goal TEXT NOT NULL,
            status TEXT NOT NULL,
            current_goal_index INTEGER NOT NULL DEFAULT 0,
            latest_summary TEXT NULL,
            latest_evaluation_json TEXT NULL,
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            completed_utc TEXT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_iteration_goals (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            goal_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            acceptance_hint TEXT NULL,
            status TEXT NOT NULL,
            result_summary TEXT NULL,
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            completed_utc TEXT NULL,
            FOREIGN KEY (session_id) REFERENCES project_iteration_sessions(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_iteration_goal_runs (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            goal_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            run_type TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES project_iteration_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (goal_id) REFERENCES project_iteration_goals(id) ON DELETE CASCADE,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_run_memories (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            status TEXT NOT NULL,
            current_objective TEXT NOT NULL,
            completed_items_json TEXT NOT NULL DEFAULT '[]',
            current_blockers_json TEXT NOT NULL DEFAULT '[]',
            next_recommended_action TEXT NOT NULL,
            allowed_scope_json TEXT NOT NULL DEFAULT '[]',
            last_verified_result TEXT NULL,
            last_run_outcome TEXT NULL,
            updated_utc TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_projects_account_id ON projects(account_id);",
        "CREATE INDEX IF NOT EXISTS ix_project_creation_failures_account_id ON project_creation_failures(account_id, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_runs_project_id_status ON runs(project_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_artifacts_project_id ON artifacts(project_id);",
        "CREATE INDEX IF NOT EXISTS ix_project_chat_messages_project_created ON project_chat_messages(project_id, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_project_iteration_sessions_project_created ON project_iteration_sessions(project_id, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_project_iteration_goals_session_goal_index ON project_iteration_goals(session_id, goal_index);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_run_memories_project_scope ON project_run_memories(project_id, scope);"
    ];
}
