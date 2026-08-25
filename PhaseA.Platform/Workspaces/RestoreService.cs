using System.Security.Cryptography;
using PhaseA.Platform.Security;
using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Workspaces;

public sealed class RestoreService
{
    private readonly string? _connectionString;
    private readonly Dictionary<string, RestoreAttempt> _inMemoryAttempts = new(StringComparer.Ordinal);

    public RestoreService(string? connectionString = null)
    {
        _connectionString = connectionString;
        if (!string.IsNullOrWhiteSpace(connectionString))
        {
            using var connection = new SqliteConnection(connectionString); connection.Open(); using var command = connection.CreateCommand();
            command.CommandText = "CREATE TABLE IF NOT EXISTS runner_leases (lease_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, fence INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS restore_attempts (attempt_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, snapshot_id TEXT NOT NULL, workspace_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, status TEXT NOT NULL, fence INTEGER NOT NULL, updated_utc TEXT NOT NULL)"; command.ExecuteNonQuery();
        }
    }

    public RestoreAttempt Restore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease)
        => Restore(context, manifest, sourceRoot, destinationRoot, lease, $"restore:{manifest.SnapshotId}:{manifest.WorkspaceId}");

    public RestoreAttempt Restore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease, string idempotencyKey)
    {
        context.DemandAccount(manifest.AccountId);
        if (manifest.ProjectId != lease.ProjectId || manifest.AccountId != lease.AccountId)
            throw new UnauthorizedAccessException("restore lease ownership does not match snapshot");
        ArgumentException.ThrowIfNullOrWhiteSpace(idempotencyKey);
        DemandAuthoritativeLease(lease);
        var existing = LoadAttempt(idempotencyKey) ?? (_inMemoryAttempts.TryGetValue(idempotencyKey, out var remembered) ? remembered : null);
        if (existing is not null) return existing;
        var attempt = new RestoreAttempt(Guid.NewGuid().ToString("N"), manifest.SnapshotId, manifest.WorkspaceId, RestoreAttemptStatus.Requested).Advance(RestoreAttemptStatus.Staging);
        PersistAttempt(attempt, idempotencyKey, lease, manifest.AccountId, manifest.ProjectId);
        var staging = Path.Combine(destinationRoot, ".restore-staging", attempt.AttemptId);
        Directory.CreateDirectory(staging);
        try
        {
            if (string.IsNullOrWhiteSpace(lease.LeaseId) || lease.Fence <= 0) throw new InvalidOperationException("invalid runner lease");
            RunnerIsolationPolicy.RequireNoReparsePoint(destinationRoot, destinationRoot);
            foreach (var entry in manifest.Files)
            {
                var target = RunnerIsolationPolicy.RequireContainedPath(staging, entry.RelativePath);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                var source = RunnerIsolationPolicy.RequireContainedPath(sourceRoot, entry.RelativePath);
                if (!File.Exists(source) || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(source))).ToLowerInvariant() != entry.Sha256)
                    throw new InvalidDataException("restore hash mismatch");
                File.Copy(source, target);
            }
            var published = Path.Combine(destinationRoot, ".restore-current");
            var backup = Path.Combine(destinationRoot, ".restore-previous", attempt.AttemptId);
            Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
            if (Directory.Exists(published)) Directory.Move(published, backup);
            try { Directory.Move(staging, published); }
            catch { if (Directory.Exists(backup) && !Directory.Exists(published)) Directory.Move(backup, published); throw; }
            var result = attempt.Advance(RestoreAttemptStatus.Published); _inMemoryAttempts[idempotencyKey] = result; PersistAttempt(result, idempotencyKey, lease, manifest.AccountId, manifest.ProjectId); return result;
        }
        catch
        {
            var quarantine = Path.Combine(destinationRoot, ".restore-quarantine", attempt.AttemptId);
            Directory.CreateDirectory(Path.GetDirectoryName(quarantine)!);
            if (Directory.Exists(quarantine)) Directory.Delete(quarantine, true);
            if (Directory.Exists(staging)) Directory.Move(staging, quarantine);
            var result = attempt.Advance(RestoreAttemptStatus.Quarantined); _inMemoryAttempts[idempotencyKey] = result; PersistAttempt(result, idempotencyKey, lease, manifest.AccountId, manifest.ProjectId); return result;
        }
    }

    private RestoreAttempt? LoadAttempt(string key)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return null;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "SELECT attempt_id,snapshot_id,workspace_id,status FROM restore_attempts WHERE idempotency_key=$key"; command.Parameters.AddWithValue("$key", key); using var reader = command.ExecuteReader();
        if (!reader.Read()) return null; return new RestoreAttempt(reader.GetString(0), reader.GetString(1), reader.GetString(2), Enum.Parse<RestoreAttemptStatus>(reader.GetString(3)));
    }

    private void PersistAttempt(RestoreAttempt attempt, string key, RunnerLease lease, string accountId, string projectId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "INSERT INTO restore_attempts(attempt_id,idempotency_key,snapshot_id,workspace_id,account_id,project_id,status,fence,updated_utc) VALUES($id,$key,$snapshot,$workspace,$account,$project,$status,$fence,$updated) ON CONFLICT(idempotency_key) DO UPDATE SET status=$status,fence=$fence,updated_utc=$updated";
        command.Parameters.AddWithValue("$id", attempt.AttemptId); command.Parameters.AddWithValue("$key", key); command.Parameters.AddWithValue("$snapshot", attempt.SnapshotId); command.Parameters.AddWithValue("$workspace", attempt.WorkspaceId); command.Parameters.AddWithValue("$account", accountId); command.Parameters.AddWithValue("$project", projectId); command.Parameters.AddWithValue("$status", attempt.Status.ToString()); command.Parameters.AddWithValue("$fence", lease.Fence); command.Parameters.AddWithValue("$updated", DateTimeOffset.UtcNow.ToString("O")); command.ExecuteNonQuery();
    }

    private void DemandAuthoritativeLease(RunnerLease lease)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT account_id, project_id, fence FROM runner_leases WHERE lease_id=$id";
        command.Parameters.AddWithValue("$id", lease.LeaseId);
        using var reader = command.ExecuteReader();
        if (!reader.Read() || reader.GetString(0) != lease.AccountId || reader.GetString(1) != lease.ProjectId || reader.GetInt64(2) != lease.Fence)
            throw new InvalidOperationException("runner lease is not authoritative");
    }
}
