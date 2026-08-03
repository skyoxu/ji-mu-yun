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

        var deferredLastActivityStatements = new List<string>();
        foreach (var statement in SchemaStatements)
        {
            if (ShouldDeferLastActivityStatement(statement))
            {
                deferredLastActivityStatements.Add(statement);
                continue;
            }

            await ExecuteAsync(connection, statement, transaction, cancellationToken);
        }

        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "accounts",
            "is_disabled",
            "ALTER TABLE accounts ADD COLUMN is_disabled INTEGER NOT NULL DEFAULT 0;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "accounts",
            "valid_until_utc",
            "ALTER TABLE accounts ADD COLUMN valid_until_utc TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "hosted_context_manifests",
            "key_id",
            "ALTER TABLE hosted_context_manifests ADD COLUMN key_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "accounts",
            "spend_limit_cny",
            "ALTER TABLE accounts ADD COLUMN spend_limit_cny TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "aicodemirror_key_pool",
            "valid_days",
            "ALTER TABLE aicodemirror_key_pool ADD COLUMN valid_days INTEGER NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "aicodemirror_key_pool",
            "expires_utc",
            "ALTER TABLE aicodemirror_key_pool ADD COLUMN expires_utc TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "aicodemirror_key_pool",
            "credential_imported",
            "ALTER TABLE aicodemirror_key_pool ADD COLUMN credential_imported INTEGER NOT NULL DEFAULT 0;",
            cancellationToken);
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
            "projects",
            "last_activity_utc",
            "ALTER TABLE projects ADD COLUMN last_activity_utc TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "projects",
            "game_type_match_json",
            "ALTER TABLE projects ADD COLUMN game_type_match_json TEXT NOT NULL DEFAULT '{}';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_game_type_match_failures",
            "matched_game_type_id",
            "ALTER TABLE project_game_type_match_failures ADD COLUMN matched_game_type_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_game_type_match_failures",
            "matched_guide_path",
            "ALTER TABLE project_game_type_match_failures ADD COLUMN matched_guide_path TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_game_type_match_failures",
            "steam_app_id",
            "ALTER TABLE project_game_type_match_failures ADD COLUMN steam_app_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_game_type_match_failures",
            "steam_name",
            "ALTER TABLE project_game_type_match_failures ADD COLUMN steam_name TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_game_type_match_failures",
            "steam_resolved_query",
            "ALTER TABLE project_game_type_match_failures ADD COLUMN steam_resolved_query TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_game_type_match_failures",
            "steam_attempted_queries_json",
            "ALTER TABLE project_game_type_match_failures ADD COLUMN steam_attempted_queries_json TEXT NOT NULL DEFAULT '[]';",
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
            "runs",
            "queue_position_at_start",
            "ALTER TABLE runs ADD COLUMN queue_position_at_start INTEGER NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_iteration_sessions",
            "latest_evaluation_json",
            "ALTER TABLE project_iteration_sessions ADD COLUMN latest_evaluation_json TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_iteration_sessions",
            "traceability_anchor_json",
            "ALTER TABLE project_iteration_sessions ADD COLUMN traceability_anchor_json TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_iteration_sessions",
            "request_identity_hash",
            "ALTER TABLE project_iteration_sessions ADD COLUMN request_identity_hash TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_iteration_sessions",
            "route_state_json",
            "ALTER TABLE project_iteration_sessions ADD COLUMN route_state_json TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_admin_review_queue",
            "supersedes_entry_id",
            "ALTER TABLE project_admin_review_queue ADD COLUMN supersedes_entry_id TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_admin_review_queue",
            "superseded_by_entry_id",
            "ALTER TABLE project_admin_review_queue ADD COLUMN superseded_by_entry_id TEXT NULL;",
            cancellationToken);
        await ExecuteAsync(
            connection,
            "DROP INDEX IF EXISTS ix_project_admin_review_queue_project_route_requirement_reason;",
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            WITH ranked AS (
                SELECT id, project_id, route_id, requirement_id, status, severity, blocking_reason,
                       FIRST_VALUE(id) OVER (
                           PARTITION BY project_id, route_id, requirement_id
                           ORDER BY
                                CASE
                                    WHEN status IN ('open', 'rejected', 'backlog') THEN 0
                                    WHEN status = 'deferred' AND (
                                        json_valid(decision_metadata_json) = 0 OR
                                        trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_owner'), '')) = '' OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) = '' AND
                                         trim(COALESCE(json_extract(decision_metadata_json, '$.recheck_trigger'), '')) = '') OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) <> '' AND
                                         (julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) IS NULL OR
                                          julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) <= julianday('now'))) OR
                                        json_type(decision_metadata_json, '$.affected_routes') <> 'array' OR
                                        NOT EXISTS (
                                            SELECT 1 FROM json_each(decision_metadata_json, '$.affected_routes') route
                                            WHERE trim(route.value) = route_id)
                                    ) THEN 0
                                    ELSE 1
                                END,
                               CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                               updated_utc DESC, id DESC
                       ) AS winner_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY project_id, route_id, requirement_id
                           ORDER BY
                                CASE
                                    WHEN status IN ('open', 'rejected', 'backlog') THEN 0
                                    WHEN status = 'deferred' AND (
                                        json_valid(decision_metadata_json) = 0 OR
                                        trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_owner'), '')) = '' OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) = '' AND
                                         trim(COALESCE(json_extract(decision_metadata_json, '$.recheck_trigger'), '')) = '') OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) <> '' AND
                                         (julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) IS NULL OR
                                          julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) <= julianday('now'))) OR
                                        json_type(decision_metadata_json, '$.affected_routes') <> 'array' OR
                                        NOT EXISTS (
                                            SELECT 1 FROM json_each(decision_metadata_json, '$.affected_routes') route
                                            WHERE trim(route.value) = route_id)
                                    ) THEN 0
                                    ELSE 1
                                END,
                               CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                               updated_utc DESC, id DESC
                       ) AS row_number
                FROM project_admin_review_queue
                WHERE status <> 'superseded'
            )
            INSERT OR IGNORE INTO project_admin_review_migration_lineage (
                predecessor_entry_id, successor_entry_id, prior_status, prior_severity,
                prior_blocking_reason, migration_reason, migrated_utc)
            SELECT id, winner_id, status, severity, blocking_reason,
                   'stable_requirement_identity_migration', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            FROM ranked
            WHERE row_number > 1;
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            WITH ranked AS (
                SELECT id,
                       FIRST_VALUE(id) OVER (
                           PARTITION BY project_id, route_id, requirement_id
                           ORDER BY
                                CASE
                                    WHEN status IN ('open', 'rejected', 'backlog') THEN 0
                                    WHEN status = 'deferred' AND (
                                        json_valid(decision_metadata_json) = 0 OR
                                        trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_owner'), '')) = '' OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) = '' AND
                                         trim(COALESCE(json_extract(decision_metadata_json, '$.recheck_trigger'), '')) = '') OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) <> '' AND
                                         (julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) IS NULL OR
                                          julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) <= julianday('now'))) OR
                                        json_type(decision_metadata_json, '$.affected_routes') <> 'array' OR
                                        NOT EXISTS (
                                            SELECT 1 FROM json_each(decision_metadata_json, '$.affected_routes') route
                                            WHERE trim(route.value) = route_id)
                                    ) THEN 0
                                    ELSE 1
                                END,
                               CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                               updated_utc DESC, id DESC
                       ) AS winner_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY project_id, route_id, requirement_id
                           ORDER BY
                                CASE
                                    WHEN status IN ('open', 'rejected', 'backlog') THEN 0
                                    WHEN status = 'deferred' AND (
                                        json_valid(decision_metadata_json) = 0 OR
                                        trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_owner'), '')) = '' OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) = '' AND
                                         trim(COALESCE(json_extract(decision_metadata_json, '$.recheck_trigger'), '')) = '') OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) <> '' AND
                                         (julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) IS NULL OR
                                          julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) <= julianday('now'))) OR
                                        json_type(decision_metadata_json, '$.affected_routes') <> 'array' OR
                                        NOT EXISTS (
                                            SELECT 1 FROM json_each(decision_metadata_json, '$.affected_routes') route
                                            WHERE trim(route.value) = route_id)
                                    ) THEN 0
                                    ELSE 1
                                END,
                               CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                               updated_utc DESC, id DESC
                       ) AS row_number
                FROM project_admin_review_queue
                WHERE status <> 'superseded'
            )
            UPDATE project_admin_review_queue
            SET supersedes_entry_id = COALESCE(
                supersedes_entry_id,
                (SELECT loser.id FROM ranked loser WHERE loser.winner_id = project_admin_review_queue.id AND loser.row_number > 1 ORDER BY loser.row_number LIMIT 1))
            WHERE id IN (SELECT winner_id FROM ranked WHERE row_number = 1);
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            WITH ranked AS (
                SELECT id,
                       FIRST_VALUE(id) OVER (
                           PARTITION BY project_id, route_id, requirement_id
                           ORDER BY
                                CASE
                                    WHEN status IN ('open', 'rejected', 'backlog') THEN 0
                                    WHEN status = 'deferred' AND (
                                        json_valid(decision_metadata_json) = 0 OR
                                        trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_owner'), '')) = '' OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) = '' AND
                                         trim(COALESCE(json_extract(decision_metadata_json, '$.recheck_trigger'), '')) = '') OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) <> '' AND
                                         (julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) IS NULL OR
                                          julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) <= julianday('now'))) OR
                                        json_type(decision_metadata_json, '$.affected_routes') <> 'array' OR
                                        NOT EXISTS (
                                            SELECT 1 FROM json_each(decision_metadata_json, '$.affected_routes') route
                                            WHERE trim(route.value) = route_id)
                                    ) THEN 0
                                    ELSE 1
                                END,
                               CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                               updated_utc DESC, id DESC
                       ) AS winner_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY project_id, route_id, requirement_id
                           ORDER BY
                                CASE
                                    WHEN status IN ('open', 'rejected', 'backlog') THEN 0
                                    WHEN status = 'deferred' AND (
                                        json_valid(decision_metadata_json) = 0 OR
                                        trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_owner'), '')) = '' OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) = '' AND
                                         trim(COALESCE(json_extract(decision_metadata_json, '$.recheck_trigger'), '')) = '') OR
                                        (trim(COALESCE(json_extract(decision_metadata_json, '$.deferred_until_utc'), '')) <> '' AND
                                         (julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) IS NULL OR
                                          julianday(json_extract(decision_metadata_json, '$.deferred_until_utc')) <= julianday('now'))) OR
                                        json_type(decision_metadata_json, '$.affected_routes') <> 'array' OR
                                        NOT EXISTS (
                                            SELECT 1 FROM json_each(decision_metadata_json, '$.affected_routes') route
                                            WHERE trim(route.value) = route_id)
                                    ) THEN 0
                                    ELSE 1
                                END,
                               CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,
                               updated_utc DESC, id DESC
                       ) AS row_number
                FROM project_admin_review_queue
                WHERE status <> 'superseded'
            )
            UPDATE project_admin_review_queue
            SET status = 'superseded',
                superseded_by_entry_id = (
                    SELECT winner_id FROM ranked WHERE ranked.id = project_admin_review_queue.id
                )
            WHERE id IN (SELECT id FROM ranked WHERE row_number > 1);
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            CREATE UNIQUE INDEX ix_project_admin_review_queue_project_route_requirement_reason
            ON project_admin_review_queue(project_id, route_id, requirement_id)
            WHERE status <> 'superseded';
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY account_id, project_id, request_identity_hash
                           ORDER BY created_utc DESC, id DESC
                       ) AS row_number
                FROM project_iteration_sessions
                WHERE request_identity_hash IS NOT NULL
                  AND request_identity_hash <> ''
            )
            UPDATE project_iteration_sessions
            SET request_identity_hash = NULL
            WHERE id IN (SELECT id FROM ranked WHERE row_number > 1);
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_project_iteration_sessions_request_identity
            ON project_iteration_sessions(account_id, project_id, request_identity_hash)
            WHERE request_identity_hash IS NOT NULL AND request_identity_hash <> '';
            """,
            transaction,
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "dedupe_scope_key",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN dedupe_scope_key TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_project_diagnostic_spool_unresolved_scope
            ON project_diagnostic_spool(account_id, project_id, route_id, failure_family, severity, dedupe_scope_key)
            WHERE triage_status = 'unresolved' AND dedupe_scope_key <> '';
            """,
            transaction,
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_prototype_drafts",
            "draft_text",
            "ALTER TABLE project_prototype_drafts ADD COLUMN draft_text TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_prototype_drafts",
            "coverage_percent",
            "ALTER TABLE project_prototype_drafts ADD COLUMN coverage_percent INTEGER NOT NULL DEFAULT 0;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_prototype_drafts",
            "coverage_summary",
            "ALTER TABLE project_prototype_drafts ADD COLUMN coverage_summary TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_prototype_drafts",
            "coverage_missing_topics_json",
            "ALTER TABLE project_prototype_drafts ADD COLUMN coverage_missing_topics_json TEXT NOT NULL DEFAULT '[]';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "diagnostic_id",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN diagnostic_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "project_name_snapshot",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN project_name_snapshot TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "run_id",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN run_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "retention_class",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN retention_class TEXT NOT NULL DEFAULT 'unresolved_blocker';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "redaction_status",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN redaction_status TEXT NOT NULL DEFAULT 'redacted';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "spool_ref",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN spool_ref TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "user_safe_summary",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN user_safe_summary TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "source_refs_json",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN source_refs_json TEXT NOT NULL DEFAULT '[]';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "cleanup_status",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN cleanup_status TEXT NOT NULL DEFAULT 'preserved';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "replacement_evidence_refs_json",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN replacement_evidence_refs_json TEXT NOT NULL DEFAULT '[]';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "admin_summary",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN admin_summary TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "remediation_hint_id",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN remediation_hint_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "triage_decision_by",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN triage_decision_by TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "triage_decision_reason",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN triage_decision_reason TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "deletion_event_id",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN deletion_event_id TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_diagnostic_spool",
            "project_tombstone_id",
            "ALTER TABLE project_diagnostic_spool ADD COLUMN project_tombstone_id TEXT NULL;",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_delete_tombstones",
            "project_tombstone_id",
            "ALTER TABLE project_delete_tombstones ADD COLUMN project_tombstone_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);
        await AddColumnIfMissingAsync(
            connection,
            transaction,
            "project_delete_tombstones",
            "deletion_event_id",
            "ALTER TABLE project_delete_tombstones ADD COLUMN deletion_event_id TEXT NOT NULL DEFAULT '';",
            cancellationToken);

        await ExecuteAsync(
            connection,
            """
            UPDATE project_diagnostic_spool
            SET diagnostic_id = id
            WHERE diagnostic_id = '';
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            UPDATE project_diagnostic_spool
            SET user_safe_summary = safe_summary
            WHERE user_safe_summary = '';
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            UPDATE project_diagnostic_spool
            SET retention_class = CASE
                    WHEN triage_status = 'unresolved' AND severity IN ('P0', 'P1', 'P2') THEN 'unresolved_blocker'
                    WHEN triage_status = 'resolved' THEN 'resolved_audit'
                    WHEN triage_status = 'ignored' THEN 'ignored_audit'
                    WHEN triage_status = 'backlog' THEN 'backlog_audit'
                    ELSE retention_class
                END
            WHERE retention_class = '';
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            UPDATE project_delete_tombstones
            SET project_tombstone_id = project_id
            WHERE project_tombstone_id = '';
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            UPDATE project_delete_tombstones
            SET deletion_event_id = 'delete-' || project_id
            WHERE deletion_event_id = '';
            """,
            transaction,
            cancellationToken);

        await ExecuteAsync(
            connection,
            """
            UPDATE projects
            SET last_activity_utc = COALESCE((
                SELECT MAX(activity_utc)
                FROM (
                    SELECT projects.created_utc AS activity_utc
                    UNION ALL
                    SELECT MAX(created_utc) FROM runs WHERE runs.project_id = projects.id
                    UNION ALL
                    SELECT MAX(started_utc) FROM runs WHERE runs.project_id = projects.id
                    UNION ALL
                    SELECT MAX(progress_updated_utc) FROM runs WHERE runs.project_id = projects.id
                    UNION ALL
                    SELECT MAX(finished_utc) FROM runs WHERE runs.project_id = projects.id
                    UNION ALL
                    SELECT MAX(created_utc) FROM artifacts WHERE artifacts.project_id = projects.id
                    UNION ALL
                    SELECT MAX(created_utc) FROM project_chat_messages WHERE project_chat_messages.project_id = projects.id
                    UNION ALL
                    SELECT MAX(updated_utc) FROM project_chat_memories WHERE project_chat_memories.project_id = projects.id
                    UNION ALL
                    SELECT MAX(updated_utc) FROM project_prototype_drafts WHERE project_prototype_drafts.project_id = projects.id
                    UNION ALL
                    SELECT MAX(created_utc) FROM project_iteration_sessions WHERE project_iteration_sessions.project_id = projects.id
                    UNION ALL
                    SELECT MAX(updated_utc) FROM project_iteration_sessions WHERE project_iteration_sessions.project_id = projects.id
                    UNION ALL
                    SELECT MAX(completed_utc) FROM project_iteration_sessions WHERE project_iteration_sessions.project_id = projects.id
                    UNION ALL
                    SELECT MAX(g.created_utc)
                    FROM project_iteration_goals g
                    INNER JOIN project_iteration_sessions s ON s.id = g.session_id
                    WHERE s.project_id = projects.id
                    UNION ALL
                    SELECT MAX(g.updated_utc)
                    FROM project_iteration_goals g
                    INNER JOIN project_iteration_sessions s ON s.id = g.session_id
                    WHERE s.project_id = projects.id
                    UNION ALL
                    SELECT MAX(g.completed_utc)
                    FROM project_iteration_goals g
                    INNER JOIN project_iteration_sessions s ON s.id = g.session_id
                    WHERE s.project_id = projects.id
                    UNION ALL
                    SELECT MAX(updated_utc) FROM project_run_memories WHERE project_run_memories.project_id = projects.id
                )
            ), projects.created_utc)
            WHERE last_activity_utc IS NULL OR last_activity_utc < created_utc;
            """,
            transaction,
            cancellationToken);

        foreach (var statement in deferredLastActivityStatements)
        {
            await ExecuteAsync(connection, statement, transaction, cancellationToken);
        }

        await BackfillRunDurationMetricsAsync(connection, transaction, cancellationToken);
        await PruneRunDurationMetricsAsync(connection, transaction, cancellationToken);

        await ExecuteAsync(connection, "PRAGMA user_version = 1;", transaction, cancellationToken);

        await transaction.CommitAsync(cancellationToken);
    }

    private static async Task BackfillRunDurationMetricsAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        CancellationToken cancellationToken)
    {
        await ExecuteAsync(
            connection,
            """
            INSERT OR IGNORE INTO run_duration_metrics (
                id,
                bucket,
                account_id,
                username,
                project_id,
                project_name,
                game_name,
                run_id,
                run_type,
                status,
                created_utc,
                started_utc,
                finished_utc,
                queue_position_at_start,
                queue_seconds,
                runtime_seconds,
                exit_code)
            SELECT
                lower(hex(randomblob(16))),
                CASE
                    WHEN r.run_type = 'prototype-chat' THEN 'chat'
                    WHEN r.run_type = 'project-asset-generation' OR r.run_type = 'asset-generation' THEN 'asset'
                    ELSE 'workflow'
                END,
                a.id,
                a.username,
                p.id,
                p.name,
                p.game_name,
                r.id,
                r.run_type,
                r.status,
                r.created_utc,
                r.started_utc,
                r.finished_utc,
                r.queue_position_at_start,
                ROUND(CASE
                    WHEN r.started_utc IS NULL THEN NULL
                    ELSE MAX(0.0, (julianday(r.started_utc) - julianday(r.created_utc)) * 86400.0)
                END, 3),
                ROUND(CASE
                    WHEN r.started_utc IS NULL OR r.finished_utc IS NULL THEN NULL
                    ELSE MAX(0.0, (julianday(r.finished_utc) - julianday(r.started_utc)) * 86400.0)
                END, 3),
                r.exit_code
            FROM runs r
            INNER JOIN projects p ON p.id = r.project_id
            INNER JOIN accounts a ON a.id = p.account_id
            WHERE a.is_admin = 0
              AND r.finished_utc IS NOT NULL;
            """,
            transaction,
            cancellationToken);
    }

    private static async Task PruneRunDurationMetricsAsync(
        SqliteConnection connection,
        SqliteTransaction transaction,
        CancellationToken cancellationToken)
    {
        await ExecuteAsync(
            connection,
            """
            DELETE FROM run_duration_metrics
            WHERE bucket = 'workflow'
              AND id NOT IN (
                  SELECT id
                  FROM (
                      SELECT
                          id,
                          ROW_NUMBER() OVER (
                              PARTITION BY account_id
                              ORDER BY created_utc DESC, run_id DESC
                          ) AS rn
                      FROM run_duration_metrics
                      WHERE bucket = 'workflow'
                  )
                  WHERE rn <= 500
              );
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            DELETE FROM run_duration_metrics
            WHERE bucket = 'chat'
              AND id NOT IN (
                  SELECT id
                  FROM run_duration_metrics
                  WHERE bucket = 'chat'
                  ORDER BY created_utc DESC, run_id DESC
                  LIMIT 500
              );
            """,
            transaction,
            cancellationToken);
        await ExecuteAsync(
            connection,
            """
            DELETE FROM run_duration_metrics
            WHERE bucket = 'asset'
              AND id NOT IN (
                  SELECT id
                  FROM run_duration_metrics
                  WHERE bucket = 'asset'
                  ORDER BY created_utc DESC, run_id DESC
                  LIMIT 500
              );
            """,
            transaction,
            cancellationToken);
    }

    private static bool ShouldDeferLastActivityStatement(string statement)
    {
        return statement.Contains("last_activity_utc", StringComparison.Ordinal)
            && !statement.Contains("CREATE TABLE IF NOT EXISTS projects", StringComparison.Ordinal)
            || statement.Contains("ix_project_diagnostic_spool_diagnostic_id", StringComparison.Ordinal)
            || statement.Contains("ix_project_diagnostic_spool_deleted_lookup", StringComparison.Ordinal)
            || statement.Contains("ix_project_diagnostic_spool_retention_cleanup", StringComparison.Ordinal)
            || statement.Contains("ix_project_delete_tombstones_tombstone_event", StringComparison.Ordinal);
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
            last_activity_utc TEXT NULL,
            game_type_match_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_game_type_match_failures (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            game_name TEXT NOT NULL,
            game_type_source TEXT NOT NULL,
            match_status TEXT NOT NULL,
            status_reason TEXT NOT NULL,
            reference_query TEXT NOT NULL,
            normalized_genre_tags_json TEXT NOT NULL DEFAULT '[]',
            candidate_scores_json TEXT NOT NULL DEFAULT '[]',
            missing_guide_path TEXT NOT NULL DEFAULT '',
            matched_game_type_id TEXT NOT NULL DEFAULT '',
            matched_guide_path TEXT NOT NULL DEFAULT '',
            steam_app_id TEXT NOT NULL DEFAULT '',
            steam_name TEXT NOT NULL DEFAULT '',
            steam_resolved_query TEXT NOT NULL DEFAULT '',
            steam_attempted_queries_json TEXT NOT NULL DEFAULT '[]',
            created_utc TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
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
            queue_position_at_start INTEGER NULL,
            llm_gateway TEXT NULL,
            llm_request_id TEXT NULL,
            llm_model TEXT NULL,
            llm_cost_json TEXT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_route_prompt_evidence_bindings (
            project_id TEXT NOT NULL,
            route_id TEXT NOT NULL,
            execution_prompt_hash TEXT NOT NULL,
            persisted_prompt_hash TEXT NOT NULL,
            prompt_artifact_ref TEXT NOT NULL,
            prompt_evidence_ref TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            PRIMARY KEY (project_id, route_id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS run_duration_metrics (
            id TEXT PRIMARY KEY,
            bucket TEXT NOT NULL,
            account_id TEXT NOT NULL,
            username TEXT NOT NULL,
            project_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            game_name TEXT NOT NULL,
            run_id TEXT NOT NULL,
            run_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            started_utc TEXT NULL,
            finished_utc TEXT NULL,
            queue_position_at_start INTEGER NULL,
            queue_seconds REAL NULL,
            runtime_seconds REAL NULL,
            exit_code INTEGER NULL
        );
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_run_duration_metrics_run_id
        ON run_duration_metrics(run_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_run_duration_metrics_bucket_account_created
        ON run_duration_metrics(bucket, account_id, created_utc DESC, run_id DESC);
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
        CREATE TABLE IF NOT EXISTS aicodemirror_key_pool (
            id TEXT PRIMARY KEY,
            key_name TEXT NOT NULL UNIQUE,
            account_id TEXT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'available',
            notes TEXT NULL,
            valid_days INTEGER NULL,
            expires_utc TEXT NULL,
            credential_imported INTEGER NOT NULL DEFAULT 0,
            imported_utc TEXT NOT NULL,
            assigned_utc TEXT NULL,
            updated_utc TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
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
        CREATE TABLE IF NOT EXISTS project_chat_memories (
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            memory_summary TEXT NOT NULL DEFAULT '',
            provider_session_ref TEXT NULL,
            updated_utc TEXT NOT NULL,
            PRIMARY KEY (account_id, project_id),
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS admin_account_audit_events (
            id TEXT PRIMARY KEY,
            actor_account_id TEXT NOT NULL,
            action TEXT NOT NULL,
            target_account_id TEXT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_utc TEXT NOT NULL,
            FOREIGN KEY (actor_account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (target_account_id) REFERENCES accounts(id) ON DELETE SET NULL
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
            draft_text TEXT NULL,
            coverage_percent INTEGER NOT NULL DEFAULT 0,
            coverage_summary TEXT NULL,
            coverage_missing_topics_json TEXT NOT NULL DEFAULT '[]',
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
            traceability_anchor_json TEXT NULL,
            request_identity_hash TEXT NULL,
            route_state_json TEXT NULL,
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
        """
        CREATE TABLE IF NOT EXISTS project_ui_states (
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            state_json TEXT NOT NULL DEFAULT '{}',
            updated_utc TEXT NOT NULL,
            PRIMARY KEY (account_id, project_id),
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_admin_review_queue (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            route_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL,
            blocking_reason TEXT NOT NULL,
            source_artifact_path TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            decision_status TEXT NOT NULL DEFAULT 'pending',
            decision_actor_account_id TEXT NULL,
            decision_reason TEXT NOT NULL DEFAULT '',
            decision_metadata_json TEXT NOT NULL DEFAULT '{}',
            decision_version INTEGER NOT NULL DEFAULT 0,
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            decided_utc TEXT NULL,
            project_deleted_utc TEXT NULL,
            supersedes_entry_id TEXT NULL,
            superseded_by_entry_id TEXT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_admin_review_decisions (
            id TEXT PRIMARY KEY,
            entry_id TEXT NOT NULL,
            decision_version INTEGER NOT NULL,
            decision_status TEXT NOT NULL,
            decision_actor_account_id TEXT NOT NULL,
            decision_reason TEXT NOT NULL,
            decision_metadata_json TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            FOREIGN KEY (entry_id) REFERENCES project_admin_review_queue(id) ON DELETE CASCADE,
            UNIQUE (entry_id, decision_version)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_admin_review_migration_lineage (
            predecessor_entry_id TEXT PRIMARY KEY,
            successor_entry_id TEXT NOT NULL,
            prior_status TEXT NOT NULL,
            prior_severity TEXT NOT NULL,
            prior_blocking_reason TEXT NOT NULL,
            migration_reason TEXT NOT NULL,
            migrated_utc TEXT NOT NULL,
            FOREIGN KEY (predecessor_entry_id) REFERENCES project_admin_review_queue(id) ON DELETE CASCADE,
            FOREIGN KEY (successor_entry_id) REFERENCES project_admin_review_queue(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_diagnostic_spool (
            id TEXT PRIMARY KEY,
            diagnostic_id TEXT NOT NULL DEFAULT '',
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            project_name_snapshot TEXT NOT NULL DEFAULT '',
            run_id TEXT NOT NULL DEFAULT '',
            route_id TEXT NOT NULL,
            failure_family TEXT NOT NULL,
            severity TEXT NOT NULL,
            triage_status TEXT NOT NULL,
            retention_class TEXT NOT NULL DEFAULT 'unresolved_blocker',
            redaction_status TEXT NOT NULL DEFAULT 'redacted',
            spool_ref TEXT NOT NULL DEFAULT '',
            safe_summary TEXT NOT NULL,
            user_safe_summary TEXT NOT NULL DEFAULT '',
            source_refs_json TEXT NOT NULL DEFAULT '[]',
            evidence_refs_json TEXT NOT NULL DEFAULT '[]',
            source_artifact_path TEXT NOT NULL DEFAULT '',
            cleanup_status TEXT NOT NULL DEFAULT 'preserved',
            replacement_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
            admin_summary TEXT NOT NULL DEFAULT '',
            remediation_hint_id TEXT NOT NULL DEFAULT '',
            dedupe_scope_key TEXT NOT NULL DEFAULT '',
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            resolved_utc TEXT NULL,
            triage_decision_by TEXT NULL,
            triage_decision_reason TEXT NOT NULL DEFAULT '',
            deletion_event_id TEXT NULL,
            project_tombstone_id TEXT NULL,
            project_deleted_utc TEXT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_delete_tombstones (
            project_tombstone_id TEXT NOT NULL DEFAULT '',
            deletion_event_id TEXT NOT NULL DEFAULT '',
            project_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            deleted_utc TEXT NOT NULL,
            unresolved_admin_review_count INTEGER NOT NULL DEFAULT 0,
            unresolved_diagnostic_count INTEGER NOT NULL DEFAULT 0,
            evidence_refs_json TEXT NOT NULL DEFAULT '[]'
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS game_type_maintenance_records (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            match_status TEXT NOT NULL,
            selected_game_type_id TEXT NOT NULL DEFAULT '',
            selected_guide_id TEXT NOT NULL DEFAULT '',
            normalized_genre_tags_json TEXT NOT NULL DEFAULT '[]',
            missing_guide INTEGER NOT NULL DEFAULT 0,
            confidence TEXT NOT NULL DEFAULT '',
            evidence_refs_json TEXT NOT NULL DEFAULT '[]',
            created_utc TEXT NOT NULL,
            project_deleted_utc TEXT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS hosted_context_manifests (
            manifest_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            operation_key TEXT NOT NULL,
            snapshot_id TEXT NOT NULL,
            policy_revision TEXT NOT NULL,
            key_id TEXT NOT NULL,
            signature TEXT NOT NULL,
            nonce TEXT NOT NULL,
            expires_utc TEXT NOT NULL,
            created_utc TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS hosted_context_nonce_consumptions (
            manifest_id TEXT NOT NULL,
            nonce TEXT NOT NULL,
            consumed_utc TEXT NOT NULL,
            PRIMARY KEY (manifest_id, nonce),
            FOREIGN KEY (manifest_id) REFERENCES hosted_context_manifests(manifest_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_projects_account_id ON projects(account_id);",
        "CREATE INDEX IF NOT EXISTS ix_projects_account_last_activity ON projects(account_id, last_activity_utc DESC, created_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_game_type_match_failures_created ON project_game_type_match_failures(created_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_game_type_match_failures_project ON project_game_type_match_failures(project_id, created_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_creation_failures_account_id ON project_creation_failures(account_id, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_runs_project_id_status ON runs(project_id, status);",
        "CREATE INDEX IF NOT EXISTS ix_runs_created_utc ON runs(created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_runs_run_type_created ON runs(run_type, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_artifacts_project_id ON artifacts(project_id);",
        "CREATE INDEX IF NOT EXISTS ix_aicodemirror_key_pool_account ON aicodemirror_key_pool(account_id);",
        "CREATE INDEX IF NOT EXISTS ix_project_chat_messages_project_created ON project_chat_messages(project_id, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_project_chat_memories_project ON project_chat_memories(project_id);",
        "CREATE INDEX IF NOT EXISTS ix_admin_account_audit_events_created ON admin_account_audit_events(created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_project_iteration_sessions_project_created ON project_iteration_sessions(project_id, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_project_iteration_goals_session_goal_index ON project_iteration_goals(session_id, goal_index);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_run_memories_project_scope ON project_run_memories(project_id, scope);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_ui_states_account_project ON project_ui_states(account_id, project_id);",
        "CREATE INDEX IF NOT EXISTS ix_project_admin_review_queue_status_created ON project_admin_review_queue(status, created_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_admin_review_queue_project_status ON project_admin_review_queue(project_id, status);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_admin_review_queue_project_route_requirement_reason ON project_admin_review_queue(project_id, route_id, requirement_id) WHERE status <> 'superseded';",
        "CREATE INDEX IF NOT EXISTS ix_project_admin_review_decisions_entry_version ON project_admin_review_decisions(entry_id, decision_version DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_admin_review_migration_lineage_successor ON project_admin_review_migration_lineage(successor_entry_id);",
        "CREATE INDEX IF NOT EXISTS ix_project_diagnostic_spool_triage_created ON project_diagnostic_spool(triage_status, created_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_diagnostic_spool_project_triage ON project_diagnostic_spool(project_id, triage_status);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_diagnostic_spool_diagnostic_id ON project_diagnostic_spool(diagnostic_id);",
        "CREATE INDEX IF NOT EXISTS ix_project_diagnostic_spool_triage_severity_updated ON project_diagnostic_spool(triage_status, severity, updated_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_diagnostic_spool_account_project_triage ON project_diagnostic_spool(account_id, project_id, triage_status);",
        "CREATE INDEX IF NOT EXISTS ix_hosted_context_manifests_account_project ON hosted_context_manifests(account_id, project_id, created_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_diagnostic_spool_deleted_lookup ON project_diagnostic_spool(project_tombstone_id, deletion_event_id);",
        "CREATE INDEX IF NOT EXISTS ix_project_diagnostic_spool_route_family_created ON project_diagnostic_spool(route_id, failure_family, created_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_diagnostic_spool_retention_cleanup ON project_diagnostic_spool(retention_class, triage_status, updated_utc DESC);",
        "CREATE INDEX IF NOT EXISTS ix_project_delete_tombstones_deleted ON project_delete_tombstones(deleted_utc DESC);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_delete_tombstones_tombstone_event ON project_delete_tombstones(project_tombstone_id, deletion_event_id);",
        "CREATE INDEX IF NOT EXISTS ix_game_type_maintenance_records_status_created ON game_type_maintenance_records(match_status, created_utc DESC);",
        """
        CREATE TRIGGER IF NOT EXISTS tr_projects_last_activity_bootstrap_update
        AFTER UPDATE OF bootstrap_status, bootstrap_error ON projects
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < strftime('%Y-%m-%dT%H:%M:%f0000+00:00', 'now') THEN strftime('%Y-%m-%dT%H:%M:%f0000+00:00', 'now')
                ELSE last_activity_utc
            END
            WHERE id = NEW.id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_runs_last_activity_insert
        AFTER INSERT ON runs
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.created_utc THEN NEW.created_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_runs_last_activity_update
        AFTER UPDATE OF started_utc, progress_updated_utc, finished_utc ON runs
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < COALESCE(NEW.finished_utc, NEW.progress_updated_utc, NEW.started_utc, NEW.created_utc) THEN COALESCE(NEW.finished_utc, NEW.progress_updated_utc, NEW.started_utc, NEW.created_utc)
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_artifacts_last_activity_insert
        AFTER INSERT ON artifacts
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.created_utc THEN NEW.created_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_chat_messages_last_activity_insert
        AFTER INSERT ON project_chat_messages
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.created_utc THEN NEW.created_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_chat_memories_last_activity_upsert
        AFTER INSERT ON project_chat_memories
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.updated_utc THEN NEW.updated_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_chat_memories_last_activity_update
        AFTER UPDATE ON project_chat_memories
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.updated_utc THEN NEW.updated_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_prototype_drafts_last_activity_upsert
        AFTER INSERT ON project_prototype_drafts
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.updated_utc THEN NEW.updated_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_prototype_drafts_last_activity_update
        AFTER UPDATE ON project_prototype_drafts
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.updated_utc THEN NEW.updated_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_iteration_sessions_last_activity_insert
        AFTER INSERT ON project_iteration_sessions
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.created_utc THEN NEW.created_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_iteration_sessions_last_activity_update
        AFTER UPDATE OF updated_utc, completed_utc ON project_iteration_sessions
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < COALESCE(NEW.completed_utc, NEW.updated_utc, NEW.created_utc) THEN COALESCE(NEW.completed_utc, NEW.updated_utc, NEW.created_utc)
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_iteration_goals_last_activity_insert
        AFTER INSERT ON project_iteration_goals
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.created_utc THEN NEW.created_utc
                ELSE last_activity_utc
            END
            WHERE id = (SELECT project_id FROM project_iteration_sessions WHERE id = NEW.session_id);
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_iteration_goals_last_activity_update
        AFTER UPDATE OF updated_utc, completed_utc ON project_iteration_goals
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < COALESCE(NEW.completed_utc, NEW.updated_utc, NEW.created_utc) THEN COALESCE(NEW.completed_utc, NEW.updated_utc, NEW.created_utc)
                ELSE last_activity_utc
            END
            WHERE id = (SELECT project_id FROM project_iteration_sessions WHERE id = NEW.session_id);
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_iteration_goal_runs_last_activity_insert
        AFTER INSERT ON project_iteration_goal_runs
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.created_utc THEN NEW.created_utc
                ELSE last_activity_utc
            END
            WHERE id = (SELECT project_id FROM project_iteration_sessions WHERE id = NEW.session_id);
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_run_memories_last_activity_upsert
        AFTER INSERT ON project_run_memories
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.updated_utc THEN NEW.updated_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS tr_project_run_memories_last_activity_update
        AFTER UPDATE ON project_run_memories
        BEGIN
            UPDATE projects
            SET last_activity_utc = CASE
                WHEN last_activity_utc IS NULL OR last_activity_utc < NEW.updated_utc THEN NEW.updated_utc
                ELSE last_activity_utc
            END
            WHERE id = NEW.project_id;
        END;
        """
    ];
}
