using System.Collections.Immutable;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;

namespace PhaseA.Platform.Workspaces;

public sealed record WorkspaceQuota(long LimitBytes, long UsedBytes)
{
    public long RemainingBytes => Math.Max(0, LimitBytes - UsedBytes);
}

public sealed record WorkspaceSnapshotRecord(SnapshotManifest Manifest, string ManifestPath, bool Deleted = false);

public sealed class WorkspaceStorageService
{
    private static readonly EnumerationOptions SkipReparsePointEnumeration = new()
    {
        RecurseSubdirectories = true,
        AttributesToSkip = FileAttributes.ReparsePoint
    };
    private readonly object _gate = new();
    private readonly Dictionary<string, WorkspaceQuota> _quotas = new(StringComparer.Ordinal);
    private readonly Dictionary<string, WorkspaceSnapshotRecord> _snapshots = new(StringComparer.Ordinal);
    private readonly string? _connectionString;

    public WorkspaceStorageService(string? connectionString = null)
    {
        _connectionString = connectionString;
        if (!string.IsNullOrWhiteSpace(connectionString))
        {
            EnsureSchema();
            LoadPersistedSnapshots();
        }
    }

    public WorkspaceQuota SetQuota(string accountId, long limitBytes)
    {
        if (limitBytes < 0) throw new ArgumentOutOfRangeException(nameof(limitBytes));
        lock (_gate)
        {
            var used = GetCurrentQuota(accountId).UsedBytes;
            var result = new WorkspaceQuota(limitBytes, used);
            StoreQuota(accountId, result);
            return result;
        }
    }

    public WorkspaceSnapshotRecord CreateSnapshot(RequestContext context, string root, string snapshotId, string workspaceId, string projectId, string policyVersion, ISet<string> blacklist)
    {
        context.DemandAccount(context.AccountId);
        DemandProjectOwnership(context, projectId);
        if (!string.IsNullOrWhiteSpace(_connectionString))
        {
            PhaseAMetadataStore.RegisterBoundaryDiagnosticContext(
                _connectionString,
                root,
                context.AccountId,
                projectId,
                context.CorrelationId);
        }
        RunnerIsolationPolicy.RequireNoReparsePoint(root, root);
        var files = ReadSnapshotFiles(root, blacklist);
        var total = files.Sum(item => (long)item.Item2.LongLength);
        lock (_gate)
        {
            if (_snapshots.ContainsKey(snapshotId)) throw new InvalidOperationException("snapshot is immutable");
            var quota = GetCurrentQuota(context.AccountId);
            var aggregateUsage = checked(quota.UsedBytes + MeasureLiveWorkspaceBytes(context.AccountId, root));
            if (total > Math.Max(0, quota.LimitBytes - aggregateUsage))
            {
                if (!string.IsNullOrWhiteSpace(_connectionString))
                {
                    PhaseAMetadataStore.TryRecordBoundaryDiagnostic(
                        _connectionString,
                        context.AccountId,
                        projectId,
                        "quota_exceeded",
                        context.CorrelationId,
                        "Workspace snapshot could not be completed.");
                }
                throw new IOException("account workspace quota exceeded");
            }
            var manifest = SnapshotManifest.Create(snapshotId, workspaceId, context.AccountId, projectId, policyVersion, files, blacklist);
            var manifestPath = Path.Combine(root, $".snapshots-{snapshotId}.json");
            var protectedPayloadPath = Path.Combine(root, $".snapshots-{snapshotId}.protected");
            var contentByPath = files.ToDictionary(
                file => file.RelativePath.Replace('\\', '/'),
                file => file.Content,
                StringComparer.Ordinal);
            var protectedFiles = manifest.Files
                .Select(entry =>
                {
                    if (!contentByPath.TryGetValue(entry.RelativePath, out var content))
                        throw new InvalidDataException("snapshot manifest content is unavailable");
                    return (entry.RelativePath, content);
                })
                .ToArray();
            var protectedPayload = CreateProtectedPayload(protectedFiles, manifest.KeyReference);
            manifest = manifest with { ProtectedContent = protectedPayload };
            File.WriteAllText(manifestPath, JsonSerializer.Serialize(manifest));
            File.WriteAllBytes(protectedPayloadPath, protectedPayload);
            StoreQuota(context.AccountId, quota with { UsedBytes = quota.UsedBytes + total });
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
            if (record.Manifest.SnapshotId.StartsWith("pinned-", StringComparison.Ordinal)) return;
            if (record.Deleted) return;
            var bytes = record.Manifest.Files.Sum(file => file.Length);
            var quota = GetCurrentQuota(record.Manifest.AccountId);
            StoreQuota(record.Manifest.AccountId, quota with { UsedBytes = Math.Max(0, quota.UsedBytes - bytes) });
            RecordRetentionAction(snapshotId, record.Manifest.AccountId, "expiry");
            RecordRetentionAction(snapshotId, record.Manifest.AccountId, "cleanup");
            RecordRetentionAction(snapshotId, record.Manifest.AccountId, "deletion");
            MarkSnapshotDeleted(snapshotId);
            _snapshots[snapshotId] = record with { Deleted = true };
        }
    }

    public WorkspaceQuota GetQuota(string accountId)
    {
        lock (_gate)
        {
            var quota = GetCurrentQuota(accountId);
            return quota with { UsedBytes = checked(quota.UsedBytes + MeasureLiveWorkspaceBytes(accountId, null)) };
        }
    }

    public IReadOnlyList<WorkspaceSnapshotRecord> ListSnapshots(string accountId, string projectId, bool includeDeleted = false)
    {
        lock (_gate)
        {
            return _snapshots.Values
                .Where(record => record.Manifest.AccountId == accountId && record.Manifest.ProjectId == projectId && (includeDeleted || !record.Deleted))
                .OrderBy(record => record.Manifest.SnapshotId, StringComparer.Ordinal)
                .ToArray();
        }
    }

    private void EnsureSchema()
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE IF NOT EXISTS workspace_quotas (account_id TEXT PRIMARY KEY, limit_bytes INTEGER NOT NULL, used_bytes INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS workspace_snapshots (snapshot_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, manifest_path TEXT NOT NULL, size_bytes INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS snapshot_retention_audit (snapshot_id TEXT NOT NULL, account_id TEXT NOT NULL, action TEXT NOT NULL, occurred_utc TEXT NOT NULL, PRIMARY KEY(snapshot_id, action));
            CREATE TABLE IF NOT EXISTS workspace_publication_blocks (project_id TEXT PRIMARY KEY, owner_drift_detected INTEGER NOT NULL DEFAULT 0);
            """;
        command.ExecuteNonQuery();
    }

    private void LoadPersistedSnapshots()
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT snapshot_id, manifest_path, deleted FROM workspace_snapshots";
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            var path = reader.GetString(1);
            if (!File.Exists(path))
            {
                path = FindRelocatedManifest(reader.GetString(0)) ?? string.Empty;
            }
            if (string.IsNullOrEmpty(path)) continue;
            var manifest = JsonSerializer.Deserialize<SnapshotManifest>(File.ReadAllText(path));
            if (manifest is not null && StringComparer.Ordinal.Equals(manifest.SnapshotId, reader.GetString(0)))
                _snapshots[reader.GetString(0)] = new WorkspaceSnapshotRecord(manifest, path, reader.GetInt32(2) != 0);
        }
    }

    private long MeasureLiveWorkspaceBytes(string accountId, string? excludedRoot)
    {
        var roots = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var usedLegacyPlacementFallback = false;
        if (!string.IsNullOrWhiteSpace(_connectionString))
        {
            using var connection = new SqliteConnection(_connectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT w.root_path FROM workspaces w INNER JOIN projects p ON p.id=w.project_id WHERE p.account_id=$account";
            command.Parameters.AddWithValue("$account", accountId);
            try
            {
                using var reader = command.ExecuteReader();
                while (reader.Read())
                {
                    var path = reader.GetString(0);
                    if (Directory.Exists(path)) roots.Add(Path.GetFullPath(path));
                }
            }
            catch (SqliteException error) when (error.SqliteErrorCode == 1 && error.Message.Contains("no such table", StringComparison.OrdinalIgnoreCase))
            {
                // Legacy/unit fixture databases can have quota tables without
                // the Phase workspace relation. The placement fallback below
                // preserves their existing accounting behavior.
            }
        }

        // Test fixtures and legacy stores may not have a workspace relation;
        // retain the placement-root fallback without ever mixing another
        // account's roots into the current account's usage.
        if (roots.Count == 0)
        {
            usedLegacyPlacementFallback = true;
            var storageRoot = GetStorageRoot();
            var placementsRoot = storageRoot is null ? null : Path.Combine(storageRoot, "placements");
            if (placementsRoot is not null && Directory.Exists(placementsRoot)) roots.Add(Path.GetFullPath(placementsRoot));
        }

        var excluded = string.IsNullOrWhiteSpace(excludedRoot) ? null : Path.GetFullPath(excludedRoot);
        var snapshotSourceRoots = usedLegacyPlacementFallback
            ? _snapshots.Values
                .Select(record => Path.GetDirectoryName(record.ManifestPath))
                .Where(path => !string.IsNullOrWhiteSpace(path))
                .Select(path => Path.GetFullPath(path!))
                .ToArray()
            : Array.Empty<string>();
        var counted = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        long total = 0;
        foreach (var root in roots)
        {
            foreach (var path in Directory.EnumerateFiles(root, "*", SkipReparsePointEnumeration))
            {
                var fullPath = Path.GetFullPath(path);
                if (!counted.Add(fullPath) || IsWithin(fullPath, excluded)) continue;
                if (snapshotSourceRoots.Any(snapshotRoot => IsWithin(fullPath, snapshotRoot))) continue;
                var relative = Path.GetRelativePath(root, fullPath);
                if (IsSnapshotExcluded(relative, new HashSet<string>(StringComparer.OrdinalIgnoreCase))) continue;
                total = checked(total + new FileInfo(fullPath).Length);
            }
        }

        return total;
    }

    private static (string RelativePath, byte[] Content)[] ReadSnapshotFiles(string root, ISet<string> blacklist)
    {
        return Directory.EnumerateFiles(root, "*", SkipReparsePointEnumeration)
            .Select(path => (Path: path, RelativePath: Path.GetRelativePath(root, path)))
            .Where(file => !IsSnapshotExcluded(file.RelativePath, blacklist))
            .Select(file => (RelativePath: file.RelativePath, Content: File.ReadAllBytes(file.Path)))
            .ToArray();
    }

    private static bool IsSnapshotExcluded(string relativePath, ISet<string> blacklist)
    {
        var normalized = relativePath.Replace('\\', '/');
        var segments = normalized.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (segments.Any(segment => segment.Equals(".git", StringComparison.OrdinalIgnoreCase) ||
                                    segment.Equals(".snapshots", StringComparison.OrdinalIgnoreCase) ||
                                    segment.Equals("bin", StringComparison.OrdinalIgnoreCase) ||
                                    segment.Equals("obj", StringComparison.OrdinalIgnoreCase) ||
                                    segment.Equals("cache", StringComparison.OrdinalIgnoreCase) ||
                                    segment.Equals("tmp", StringComparison.OrdinalIgnoreCase) ||
                                    segment.Equals("temp", StringComparison.OrdinalIgnoreCase)))
            return true;
        var name = segments[^1];
        if (name.StartsWith(".snapshots-", StringComparison.OrdinalIgnoreCase) ||
            name.EndsWith(".protected", StringComparison.OrdinalIgnoreCase) ||
            name.EndsWith(".ticket", StringComparison.OrdinalIgnoreCase) ||
            name.EndsWith(".secret", StringComparison.OrdinalIgnoreCase))
            return true;
        return blacklist.Contains(Path.GetExtension(normalized));
    }

    private static byte[] CreateProtectedPayload(
        IEnumerable<(string RelativePath, byte[] Content)> files,
        string keyReference)
    {
        var orderedFiles = files
            .OrderBy(file => file.RelativePath, StringComparer.Ordinal)
            .ToArray();
        return SnapshotManifest.ProtectContent(orderedFiles, keyReference);
    }

    private string? FindRelocatedManifest(string snapshotId)
    {
        var storageRoot = GetStorageRoot();
        if (storageRoot is null || !Directory.Exists(storageRoot)) return null;

        var expectedFileName = $".snapshots-{snapshotId}.json";
        return Directory.EnumerateFiles(storageRoot, expectedFileName, SkipReparsePointEnumeration)
            .FirstOrDefault();
    }

    private string? GetStorageRoot()
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return null;
        var dataSource = new SqliteConnectionStringBuilder(_connectionString).DataSource;
        return string.IsNullOrWhiteSpace(dataSource) ? null : Path.GetDirectoryName(Path.GetFullPath(dataSource));
    }

    private static bool IsWithin(string path, string? root)
    {
        if (root is null) return false;
        var relative = Path.GetRelativePath(root, path);
        return relative.Length == 0 || (!Path.IsPathRooted(relative) && !relative.StartsWith("..", StringComparison.Ordinal));
    }

    private WorkspaceQuota? GetPersistedQuota(string accountId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return null;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand(); command.CommandText = "SELECT limit_bytes, used_bytes FROM workspace_quotas WHERE account_id=$id"; command.Parameters.AddWithValue("$id", accountId);
        using var reader = command.ExecuteReader(); return reader.Read() ? new WorkspaceQuota(reader.GetInt64(0), reader.GetInt64(1)) : null;
    }

    private WorkspaceQuota GetCurrentQuota(string accountId) =>
        GetPersistedQuota(accountId) ?? (_quotas.TryGetValue(accountId, out var quota) ? quota : new WorkspaceQuota(long.MaxValue, 0));

    private void StoreQuota(string accountId, WorkspaceQuota quota)
    {
        _quotas[accountId] = quota;
        PersistQuota(accountId, quota);
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

    private void RecordRetentionAction(string snapshotId, string accountId, string action)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO snapshot_retention_audit(snapshot_id,account_id,action,occurred_utc) VALUES($snapshot,$account,$action,$occurred) ON CONFLICT(snapshot_id,action) DO NOTHING";
        command.Parameters.AddWithValue("$snapshot", snapshotId); command.Parameters.AddWithValue("$account", accountId); command.Parameters.AddWithValue("$action", action); command.Parameters.AddWithValue("$occurred", DateTimeOffset.UtcNow.ToString("O"));
        command.ExecuteNonQuery();
    }

    private void DemandProjectOwnership(RequestContext context, string projectId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "SELECT account_id FROM projects WHERE id=$id"; command.Parameters.AddWithValue("$id", projectId);
        var owner = command.ExecuteScalar()?.ToString() ?? throw new UnauthorizedAccessException("project ownership is unknown");
        if (!StringComparer.Ordinal.Equals(owner, context.AccountId))
        {
            RecordOwnerDrift(connection, projectId);
            throw new UnauthorizedAccessException("project ownership mismatch");
        }
        if (OwnerDriftRequiresRepair(connection, projectId))
            throw new UnauthorizedAccessException("project publication requires protected audited repair");
    }

    private static void RecordOwnerDrift(SqliteConnection connection, string projectId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO workspace_publication_blocks(project_id,owner_drift_detected) VALUES($project,1) ON CONFLICT(project_id) DO UPDATE SET owner_drift_detected=1";
        command.Parameters.AddWithValue("$project", projectId);
        command.ExecuteNonQuery();
    }

    private static bool OwnerDriftRequiresRepair(SqliteConnection connection, string projectId)
    {
        using var block = connection.CreateCommand();
        block.CommandText = "SELECT owner_drift_detected FROM workspace_publication_blocks WHERE project_id=$project";
        block.Parameters.AddWithValue("$project", projectId);
        if (Convert.ToInt32(block.ExecuteScalar() ?? 0) == 0) return false;

        using var audit = connection.CreateCommand();
        audit.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='workspace_repair_audit'";
        if (Convert.ToInt32(audit.ExecuteScalar()) != 1) return true;
        using var repair = connection.CreateCommand();
        repair.CommandText = "SELECT COUNT(*) FROM workspace_repair_audit WHERE project_id=$project AND action='protected-owner-repair'";
        repair.Parameters.AddWithValue("$project", projectId);
        return Convert.ToInt32(repair.ExecuteScalar()) == 0;
    }
}
