using System.Collections.Immutable;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;

namespace PhaseA.Platform.Workspaces;

public sealed record WorkspaceQuota(long LimitBytes, long UsedBytes)
{
    public long RemainingBytes => Math.Max(0, LimitBytes - UsedBytes);
}

public sealed record WorkspaceSnapshotRecord(SnapshotManifest Manifest, string ManifestPath, bool Deleted = false);

public sealed class WorkspaceStorageService
{
    private readonly object _gate = new();
    private readonly Dictionary<string, WorkspaceQuota> _quotas = new(StringComparer.Ordinal);
    private readonly Dictionary<string, WorkspaceSnapshotRecord> _snapshots = new(StringComparer.Ordinal);
    private readonly string? _connectionString;

    public WorkspaceStorageService(string? connectionString = null)
    {
        _connectionString = connectionString;
        if (!string.IsNullOrWhiteSpace(connectionString)) EnsureSchema();
    }

    public WorkspaceQuota SetQuota(string accountId, long limitBytes)
    {
        if (limitBytes < 0) throw new ArgumentOutOfRangeException(nameof(limitBytes));
        lock (_gate)
        {
            var used = GetPersistedQuota(accountId)?.UsedBytes ?? (_quotas.TryGetValue(accountId, out var q) ? q.UsedBytes : 0);
            var result = _quotas[accountId] = new WorkspaceQuota(limitBytes, used);
            PersistQuota(accountId, result);
            return result;
        }
    }

    public WorkspaceSnapshotRecord CreateSnapshot(RequestContext context, string root, string snapshotId, string workspaceId, string projectId, string policyVersion, ISet<string> blacklist)
    {
        context.DemandAccount(context.AccountId);
        DemandProjectOwnership(context, projectId);
        RunnerIsolationPolicy.RequireNoReparsePoint(root, root);
        var files = Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories)
            .Select(path => (Path.GetRelativePath(root, path), File.ReadAllBytes(path)))
            .Where(item => !blacklist.Contains(Path.GetExtension(item.Item1)))
            .ToArray();
        var total = files.Sum(item => (long)item.Item2.LongLength);
        lock (_gate)
        {
            if (_snapshots.ContainsKey(snapshotId)) throw new InvalidOperationException("snapshot is immutable");
            var quota = GetPersistedQuota(context.AccountId) ?? (_quotas.TryGetValue(context.AccountId, out var q) ? q : new WorkspaceQuota(long.MaxValue, 0));
            if (total > quota.RemainingBytes) throw new IOException("account workspace quota exceeded");
            var manifest = SnapshotManifest.Create(snapshotId, workspaceId, context.AccountId, projectId, policyVersion, files, blacklist);
            var manifestPath = Path.Combine(root, $".snapshots-{snapshotId}.json");
            File.WriteAllText(manifestPath, JsonSerializer.Serialize(manifest));
            _quotas[context.AccountId] = quota with { UsedBytes = quota.UsedBytes + total };
            PersistQuota(context.AccountId, _quotas[context.AccountId]);
            PersistSnapshot(context.AccountId, projectId, snapshotId, manifestPath, total);
            return _snapshots[snapshotId] = new WorkspaceSnapshotRecord(manifest, manifestPath);
        }
    }

    public void SoftDeleteSnapshot(RequestContext context, string snapshotId)
    {
        lock (_gate)
        {
            if (!_snapshots.TryGetValue(snapshotId, out var record))
                throw new KeyNotFoundException(snapshotId);
            context.DemandAccount(record.Manifest.AccountId);
            if (record.Deleted) return;
            var bytes = record.Manifest.Files.Sum(file => file.Length);
            var quota = GetPersistedQuota(record.Manifest.AccountId) ?? _quotas.GetValueOrDefault(record.Manifest.AccountId, new WorkspaceQuota(long.MaxValue, 0));
            _quotas[record.Manifest.AccountId] = quota with { UsedBytes = Math.Max(0, quota.UsedBytes - bytes) };
            PersistQuota(record.Manifest.AccountId, _quotas[record.Manifest.AccountId]);
            MarkSnapshotDeleted(snapshotId);
            _snapshots[snapshotId] = record with { Deleted = true };
        }
    }

    public WorkspaceQuota GetQuota(string accountId) => GetPersistedQuota(accountId) ?? (_quotas.TryGetValue(accountId, out var q) ? q : new WorkspaceQuota(long.MaxValue, 0));

    private void EnsureSchema()
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE IF NOT EXISTS workspace_quotas (account_id TEXT PRIMARY KEY, limit_bytes INTEGER NOT NULL, used_bytes INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS workspace_snapshots (snapshot_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, manifest_path TEXT NOT NULL, size_bytes INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
            """;
        command.ExecuteNonQuery();
    }

    private WorkspaceQuota? GetPersistedQuota(string accountId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return null;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand(); command.CommandText = "SELECT limit_bytes, used_bytes FROM workspace_quotas WHERE account_id=$id"; command.Parameters.AddWithValue("$id", accountId);
        using var reader = command.ExecuteReader(); return reader.Read() ? new WorkspaceQuota(reader.GetInt64(0), reader.GetInt64(1)) : null;
    }

    private void PersistQuota(string accountId, WorkspaceQuota quota)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand(); command.CommandText = "INSERT INTO workspace_quotas(account_id,limit_bytes,used_bytes) VALUES($id,$limit,$used) ON CONFLICT(account_id) DO UPDATE SET limit_bytes=$limit, used_bytes=$used";
        command.Parameters.AddWithValue("$id", accountId); command.Parameters.AddWithValue("$limit", quota.LimitBytes); command.Parameters.AddWithValue("$used", quota.UsedBytes); command.ExecuteNonQuery();
    }

    private void PersistSnapshot(string accountId, string projectId, string snapshotId, string path, long size)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO workspace_snapshots(snapshot_id,account_id,project_id,manifest_path,size_bytes) VALUES($snapshot,$account,$project,$path,$size)";
        command.Parameters.AddWithValue("$snapshot", snapshotId); command.Parameters.AddWithValue("$account", accountId); command.Parameters.AddWithValue("$project", projectId); command.Parameters.AddWithValue("$path", path); command.Parameters.AddWithValue("$size", size); command.ExecuteNonQuery();
    }

    private void MarkSnapshotDeleted(string snapshotId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "UPDATE workspace_snapshots SET deleted=1 WHERE snapshot_id=$id"; command.Parameters.AddWithValue("$id", snapshotId); command.ExecuteNonQuery();
    }

    private void DemandProjectOwnership(RequestContext context, string projectId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "SELECT account_id FROM projects WHERE id=$id"; command.Parameters.AddWithValue("$id", projectId);
        var owner = command.ExecuteScalar()?.ToString() ?? throw new UnauthorizedAccessException("project ownership is unknown");
        context.DemandAccount(owner);
    }
}
