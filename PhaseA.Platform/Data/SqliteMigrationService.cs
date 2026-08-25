using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Data;

public sealed class SqliteMigrationService
{
    public async Task<MigrationEvidence> MigrateAsync(string connectionString, string accountId, string projectId, string correlationId, CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE IF NOT EXISTS phase_b_schema (version INTEGER NOT NULL);
            INSERT INTO phase_b_schema(version) SELECT 2 WHERE NOT EXISTS (SELECT 1 FROM phase_b_schema);
            CREATE TABLE IF NOT EXISTS workspace_quotas (account_id TEXT PRIMARY KEY, limit_bytes INTEGER NOT NULL, used_bytes INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS workspace_snapshots (snapshot_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, manifest_path TEXT NOT NULL, size_bytes INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS runner_leases (lease_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, fence INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS restore_attempts (attempt_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, snapshot_id TEXT NOT NULL, workspace_id TEXT NOT NULL, account_id TEXT NOT NULL DEFAULT '', project_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, fence INTEGER NOT NULL, updated_utc TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_workspace_snapshots_account ON workspace_snapshots(account_id, deleted);
            CREATE INDEX IF NOT EXISTS ix_restore_attempts_workspace ON restore_attempts(workspace_id, updated_utc);
            """;
        await command.ExecuteNonQueryAsync(cancellationToken);
        return new MigrationEvidence(Guid.NewGuid().ToString("N"), accountId, projectId, "completed", correlationId, new Dictionary<string, string> { ["schema_version"] = "2", ["ownership_tables"] = "workspace_quotas,workspace_snapshots,restore_attempts" }).Redacted();
    }
}
