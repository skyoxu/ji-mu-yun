using System.Collections.Immutable;
using System.Security.Cryptography;
using System.Text.Json;
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

    public WorkspaceQuota SetQuota(string accountId, long limitBytes)
    {
        if (limitBytes < 0) throw new ArgumentOutOfRangeException(nameof(limitBytes));
        lock (_gate) { var used = _quotas.TryGetValue(accountId, out var q) ? q.UsedBytes : 0; return _quotas[accountId] = new WorkspaceQuota(limitBytes, used); }
    }

    public WorkspaceSnapshotRecord CreateSnapshot(RequestContext context, string root, string snapshotId, string workspaceId, string projectId, string policyVersion, ISet<string> blacklist)
    {
        context.DemandAccount(context.AccountId);
        var files = Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories)
            .Select(path => (Path.GetRelativePath(root, path), File.ReadAllBytes(path)))
            .Where(item => !blacklist.Contains(Path.GetExtension(item.Item1)))
            .ToArray();
        var total = files.Sum(item => (long)item.Item2.LongLength);
        lock (_gate)
        {
            if (_snapshots.ContainsKey(snapshotId)) throw new InvalidOperationException("snapshot is immutable");
            var quota = _quotas.TryGetValue(context.AccountId, out var q) ? q : new WorkspaceQuota(long.MaxValue, 0);
            if (total > quota.RemainingBytes) throw new IOException("account workspace quota exceeded");
            var manifest = SnapshotManifest.Create(snapshotId, workspaceId, context.AccountId, projectId, policyVersion, files, blacklist);
            var manifestPath = Path.Combine(root, $".snapshots-{snapshotId}.json");
            File.WriteAllText(manifestPath, JsonSerializer.Serialize(manifest));
            _quotas[context.AccountId] = quota with { UsedBytes = quota.UsedBytes + total };
            return _snapshots[snapshotId] = new WorkspaceSnapshotRecord(manifest, manifestPath);
        }
    }

    public void SoftDeleteSnapshot(RequestContext context, string snapshotId)
    {
        lock (_gate)
        {
            if (!_snapshots.TryGetValue(snapshotId, out var record)) throw new KeyNotFoundException(snapshotId);
            context.DemandAccount(record.Manifest.AccountId);
            if (record.Deleted) return;
            var bytes = record.Manifest.Files.Sum(file => file.Length);
            var quota = _quotas[record.Manifest.AccountId];
            _quotas[record.Manifest.AccountId] = quota with { UsedBytes = Math.Max(0, quota.UsedBytes - bytes) };
            _snapshots[snapshotId] = record with { Deleted = true };
        }
    }

    public WorkspaceQuota GetQuota(string accountId) => _quotas.TryGetValue(accountId, out var q) ? q : new WorkspaceQuota(long.MaxValue, 0);
}
