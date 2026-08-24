using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Data;

public sealed class SqliteMigrationService
{
    public async Task<MigrationEvidence> MigrateAsync(string connectionString, string accountId, string projectId, string correlationId, CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = "CREATE TABLE IF NOT EXISTS phase_b_schema (version INTEGER NOT NULL); INSERT INTO phase_b_schema(version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM phase_b_schema);";
        await command.ExecuteNonQueryAsync(cancellationToken);
        return new MigrationEvidence(Guid.NewGuid().ToString("N"), accountId, projectId, "completed", correlationId, new Dictionary<string, string> { ["schema_version"] = "1" }).Redacted();
    }
}
