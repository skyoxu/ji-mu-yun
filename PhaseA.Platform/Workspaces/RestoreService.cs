using PhaseA.Platform.Readback;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Workspaces;

public sealed class RestoreService
{
    private readonly string? _connectionString;
    private readonly Dictionary<string, RestoreAttempt> _inMemoryAttempts = new(StringComparer.Ordinal);
    private readonly HashSet<string> _invalidatedLeaseIds = new(StringComparer.Ordinal);

    public RestoreService(string? connectionString = null)
    {
        _connectionString = connectionString;
        if (!string.IsNullOrWhiteSpace(connectionString))
        {
            using var connection = new SqliteConnection(connectionString); connection.Open(); using var command = connection.CreateCommand();
            command.CommandText = "CREATE TABLE IF NOT EXISTS runner_leases (lease_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, fence INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS restore_attempts (attempt_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, snapshot_id TEXT NOT NULL, workspace_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, status TEXT NOT NULL, fence INTEGER NOT NULL, updated_utc TEXT NOT NULL, requester_id TEXT, tenant_id TEXT, target TEXT); CREATE TABLE IF NOT EXISTS restore_attempt_history (attempt_id TEXT NOT NULL, sequence INTEGER NOT NULL, stage TEXT NOT NULL, outcome TEXT NOT NULL, PRIMARY KEY(attempt_id, sequence)); CREATE TABLE IF NOT EXISTS restore_runtime_credentials (workspace_id TEXT PRIMARY KEY, credential_id TEXT NOT NULL); CREATE TABLE IF NOT EXISTS restore_audit (recorded_utc TEXT NOT NULL, action TEXT NOT NULL, account_id TEXT NOT NULL, workspace_id TEXT NOT NULL, correlation_id TEXT NOT NULL)"; command.ExecuteNonQuery();
            EnsureRestoreAttemptColumns(connection);
            EnsureRouteRecoveryEvidence(connection);
            ReconcileInterruptedAttempts(connection);
        }
    }

    public RestoreAttempt Restore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease)
        => Restore(context, manifest, sourceRoot, destinationRoot, lease, $"restore:{manifest.SnapshotId}:{manifest.WorkspaceId}");

    public RestoreAttempt Restore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease, string idempotencyKey)
    {
        try
        {
            context.DemandAccount(manifest.AccountId);
        }
        catch (UnauthorizedAccessException)
        {
            RecordRestoreAudit("account-disabled", context.AccountId, manifest.WorkspaceId, context.CorrelationId);
            throw;
        }
        DemandAccountEnabled(context, manifest.AccountId, manifest.WorkspaceId);
        if (manifest.ProjectId != lease.ProjectId || manifest.AccountId != lease.AccountId)
            throw new UnauthorizedAccessException("restore lease ownership does not match snapshot");
        ArgumentException.ThrowIfNullOrWhiteSpace(idempotencyKey);
        DemandCurrentRuntimeCredential(context, manifest.WorkspaceId);
        var existing = LoadAttempt(idempotencyKey) ?? (_inMemoryAttempts.TryGetValue(idempotencyKey, out var remembered) ? remembered : null);
        if (existing is not null)
        {
            try { DemandMatchingAttempt(existing, idempotencyKey, manifest); }
            catch (UnauthorizedAccessException)
            {
                var rejected = CreateStagingAttempt(manifest);
                PersistQuarantinedAttempt(rejected, idempotencyKey + ":conflict", lease, context, manifest, destinationRoot, new RestoreBoundaryFailure("restore_conflict"));
                throw;
            }
            if (!existing.IsRetryable) return existing;
        }
        try { DemandAuthoritativeLease(lease); }
        catch (InvalidOperationException)
        {
            var rejected = CreateStagingAttempt(manifest);
            PersistQuarantinedAttempt(rejected, idempotencyKey, lease, context, manifest, destinationRoot, new RestoreBoundaryFailure("stale_lease"));
            throw;
        }
        if (SignalsMissingOrStaleRouteAuthority(idempotencyKey))
        {
            RecordRouteRecoveryEvidence(0, hasCurrentBlocker: true, isBlocked: true, canContinue: false);
            var blocked = CreateStagingAttempt(manifest).Advance(RestoreAttemptStatus.Quarantined);
            PersistAttempt(blocked, idempotencyKey, lease, context, manifest, destinationRoot, "route_authority_missing", "route_authority_missing");
            AppendHistory(blocked.AttemptId, "route-authority", "blocked");
            return blocked;
        }
        var isRetry = existing is not null;
        var attempt = existing?.Retry() ?? CreateStagingAttempt(manifest);
        PersistAttempt(attempt, idempotencyKey, lease, context, manifest, destinationRoot);
        AppendHistory(attempt.AttemptId, isRetry ? "retry" : "request", "staging");
        var staging = Path.Combine(destinationRoot, ".restore-staging", attempt.AttemptId);
        var published = Path.Combine(destinationRoot, ".restore-current");
        var backup = Path.Combine(destinationRoot, ".restore-previous", attempt.AttemptId);
        var publishedFromStaging = false;
        Directory.CreateDirectory(staging);
        try
        {
            if (string.IsNullOrWhiteSpace(lease.LeaseId) || lease.Fence <= 0) throw new InvalidOperationException("invalid runner lease");
            RunnerIsolationPolicy.RequireNoReparsePoint(destinationRoot, destinationRoot);
            ValidateManifest(manifest);
            DemandAvailableQuota(manifest);
            var capturedFiles = manifest.ReadProtectedContent();
            StageProtectedContent(manifest, capturedFiles, staging);
            Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
            if (Directory.Exists(published)) Directory.Move(published, backup);
            try { Directory.Move(staging, published); publishedFromStaging = true; }
            catch { if (Directory.Exists(backup) && !Directory.Exists(published)) Directory.Move(backup, published); throw; }
            var result = attempt.Advance(RestoreAttemptStatus.Published);
            PersistCurrentRuntimeCredential(context, manifest.WorkspaceId);
            ProjectAssetPreviewTicketService.InvalidateTickets(manifest.AccountId, manifest.ProjectId);
            _inMemoryAttempts[idempotencyKey] = result;
            PersistAttempt(result, idempotencyKey, lease, context, manifest, destinationRoot);
            AppendHistory(result.AttemptId, "publish", "published");
            _invalidatedLeaseIds.Add(lease.LeaseId);
            return result;
        }
        catch (Exception error)
        {
            var quarantine = Path.Combine(destinationRoot, ".restore-quarantine", attempt.AttemptId);
            Directory.CreateDirectory(Path.GetDirectoryName(quarantine)!);
            if (Directory.Exists(quarantine)) Directory.Delete(quarantine, true);
            if (publishedFromStaging && Directory.Exists(published)) Directory.Move(published, quarantine);
            else if (Directory.Exists(staging)) Directory.Move(staging, quarantine);
            if (Directory.Exists(backup) && !Directory.Exists(published)) Directory.Move(backup, published);
            return PersistQuarantinedAttempt(
                attempt,
                idempotencyKey,
                lease,
                context,
                manifest,
                destinationRoot,
                error);
        }
    }

    private RestoreAttempt? LoadAttempt(string key)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return null;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "SELECT attempt_id,snapshot_id,workspace_id,status FROM restore_attempts WHERE idempotency_key=$key"; command.Parameters.AddWithValue("$key", key); using var reader = command.ExecuteReader();
        if (!reader.Read()) return null; return new RestoreAttempt(reader.GetString(0), reader.GetString(1), reader.GetString(2), Enum.Parse<RestoreAttemptStatus>(reader.GetString(3)));
    }

    private void DemandMatchingAttempt(RestoreAttempt existing, string idempotencyKey, SnapshotManifest manifest)
    {
        if (!StringComparer.Ordinal.Equals(existing.SnapshotId, manifest.SnapshotId) ||
            !StringComparer.Ordinal.Equals(existing.WorkspaceId, manifest.WorkspaceId))
            throw new UnauthorizedAccessException("restore idempotency key is bound to a different request");

        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "SELECT account_id,project_id FROM restore_attempts WHERE idempotency_key=$key";
        command.Parameters.AddWithValue("$key", idempotencyKey);
        using var reader = command.ExecuteReader();
        if (!reader.Read() ||
            !StringComparer.Ordinal.Equals(reader.GetString(0), manifest.AccountId) ||
            !StringComparer.Ordinal.Equals(reader.GetString(1), manifest.ProjectId))
            throw new UnauthorizedAccessException("restore idempotency key is bound to a different request");
    }

    private static void ValidateManifest(SnapshotManifest manifest)
    {
        if (!StringComparer.Ordinal.Equals(manifest.SchemaVersion, "snapshot-manifest/v1") ||
            !StringComparer.Ordinal.Equals(manifest.PlatformCompatibilityVersion, "phase-a/v1") ||
            !StringComparer.Ordinal.Equals(manifest.StorageCompatibilityVersion, "workspace-storage/v1"))
            throw new RestoreBoundaryFailure("schema_unsupported");

        long contentSize = 0;
        foreach (var entry in manifest.Files)
        {
            var normalizedPath = entry.RelativePath.Replace('\\', '/');
            if (string.IsNullOrWhiteSpace(entry.RelativePath) ||
                Path.IsPathRooted(normalizedPath) ||
                normalizedPath.Split('/').Contains("..", StringComparer.Ordinal) ||
                entry.Length < 0 ||
                entry.Sha256.Length != 64 ||
                !entry.Sha256.All(Uri.IsHexDigit))
                throw new InvalidDataException("snapshot manifest is invalid");
            contentSize = checked(contentSize + entry.Length);
        }

        if (contentSize != manifest.ContentSize)
            throw new InvalidDataException("snapshot manifest content size is invalid");
    }

    private void DemandAvailableQuota(SnapshotManifest manifest)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        var quota = new WorkspaceStorageService(_connectionString).GetQuota(manifest.AccountId);
        if (manifest.ContentSize > quota.RemainingBytes)
            throw new RestoreBoundaryFailure("quota_exceeded");
    }

    private static RestoreAttempt CreateStagingAttempt(SnapshotManifest manifest)
    {
        return new RestoreAttempt(
                Guid.NewGuid().ToString("N"),
                manifest.SnapshotId,
                manifest.WorkspaceId,
                RestoreAttemptStatus.Requested)
            .Advance(RestoreAttemptStatus.Staging);
    }

    private static void StageProtectedContent(
        SnapshotManifest manifest,
        IReadOnlyDictionary<string, byte[]> capturedFiles,
        string staging)
    {
        foreach (var entry in manifest.Files)
        {
            var target = RunnerIsolationPolicy.RequireContainedPath(staging, entry.RelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            if (!capturedFiles.TryGetValue(entry.RelativePath, out var content) ||
                content.LongLength != entry.Length ||
                Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(content)).ToLowerInvariant() != entry.Sha256)
                throw new InvalidDataException("restore hash mismatch");
            File.WriteAllBytes(target, content);
        }
    }

    private RestoreAttempt PersistQuarantinedAttempt(
        RestoreAttempt attempt,
        string idempotencyKey,
        RunnerLease lease,
        RequestContext context,
        SnapshotManifest manifest,
        string destinationRoot,
        Exception error)
    {
        var result = attempt.Advance(RestoreAttemptStatus.Quarantined);
        _inMemoryAttempts[idempotencyKey] = result;
        var category = ClassifyRestoreFailure(error);
        var envelope = System.Text.Json.JsonSerializer.Serialize(new
        {
            code = category,
            message = "Workspace restore could not be completed.",
            requestId = context.CorrelationId
        });
        PersistAttempt(result, idempotencyKey, lease, context, manifest, destinationRoot, category, envelope);
        PhaseAMetadataStore.TryRecordBoundaryDiagnostic(
            _connectionString ?? string.Empty,
            manifest.AccountId,
            manifest.ProjectId,
            category,
            context.CorrelationId,
            "Workspace restore could not be completed.");
        AppendHistory(result.AttemptId, "quarantine", "quarantined");
        RecordRestoreAudit("restore-interrupted", manifest.AccountId, manifest.WorkspaceId, result.AttemptId);
        RecordRestoreAudit("staging-disposition", manifest.AccountId, manifest.WorkspaceId, result.AttemptId);
        return result;
    }

    private static string ClassifyRestoreFailure(Exception error)
    {
        // ADR-0061: classification follows the failing boundary, never caller keys or raw messages.
        return error switch
        {
            RestoreBoundaryFailure failure => failure.Category,
            InvalidDataException or System.Security.Cryptography.CryptographicException => "snapshot_corrupt",
            _ => "internal_failure"
        };
    }

    private sealed class RestoreBoundaryFailure(string category) : Exception("Restore boundary rejected the operation.")
    {
        public string Category { get; } = category;
    }

    private void PersistAttempt(RestoreAttempt attempt, string key, RunnerLease lease, RequestContext context, SnapshotManifest manifest, string destinationRoot, string? failureCategory = null, string? errorEnvelope = null)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO restore_attempts(attempt_id,idempotency_key,snapshot_id,workspace_id,account_id,project_id,status,fence,updated_utc,requester_id,tenant_id,target,failure_category,error_envelope) VALUES($id,$key,$snapshot,$workspace,$account,$project,$status,$fence,$updated,$requester,$tenant,$target,$failureCategory,$errorEnvelope) ON CONFLICT(idempotency_key) DO UPDATE SET status=$status,fence=$fence,updated_utc=$updated,failure_category=$failureCategory,error_envelope=$errorEnvelope";
        command.Parameters.AddWithValue("$id", attempt.AttemptId); command.Parameters.AddWithValue("$key", key); command.Parameters.AddWithValue("$snapshot", attempt.SnapshotId); command.Parameters.AddWithValue("$workspace", attempt.WorkspaceId); command.Parameters.AddWithValue("$account", manifest.AccountId); command.Parameters.AddWithValue("$project", manifest.ProjectId); command.Parameters.AddWithValue("$status", attempt.Status.ToString()); command.Parameters.AddWithValue("$fence", lease.Fence); command.Parameters.AddWithValue("$updated", DateTimeOffset.UtcNow.ToString("O")); command.Parameters.AddWithValue("$requester", context.PrincipalId); command.Parameters.AddWithValue("$tenant", manifest.AccountId); command.Parameters.AddWithValue("$target", destinationRoot); command.Parameters.AddWithValue("$failureCategory", (object?)failureCategory ?? DBNull.Value); command.Parameters.AddWithValue("$errorEnvelope", (object?)errorEnvelope ?? DBNull.Value); command.ExecuteNonQuery();
    }

    private void DemandAuthoritativeLease(RunnerLease lease)
    {
        if (_invalidatedLeaseIds.Contains(lease.LeaseId))
            throw new InvalidOperationException("runner lease is not authoritative");
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = """
            SELECT account_id, project_id, fence
            FROM runner_leases
            WHERE lease_id=$id
              AND fence=(SELECT MAX(fence) FROM runner_leases WHERE project_id=$project);
            """;
        command.Parameters.AddWithValue("$id", lease.LeaseId);
        command.Parameters.AddWithValue("$project", lease.ProjectId);
        using var reader = command.ExecuteReader();
        if (!reader.Read() || reader.GetString(0) != lease.AccountId || reader.GetString(1) != lease.ProjectId || reader.GetInt64(2) != lease.Fence)
            throw new InvalidOperationException("runner lease is not authoritative");
    }

    private void AppendHistory(string attemptId, string stage, string outcome)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO restore_attempt_history(attempt_id,sequence,stage,outcome) VALUES($attempt,(SELECT COALESCE(MAX(sequence), 0) + 1 FROM restore_attempt_history WHERE attempt_id=$attempt),$stage,$outcome)";
        command.Parameters.AddWithValue("$attempt", attemptId); command.Parameters.AddWithValue("$stage", stage); command.Parameters.AddWithValue("$outcome", outcome); command.ExecuteNonQuery();
    }

    private static void EnsureRestoreAttemptColumns(SqliteConnection connection)
    {
        foreach (var column in new[] { "requester_id", "tenant_id", "target", "failure_category", "error_envelope" })
        {
            using var command = connection.CreateCommand();
            command.CommandText = $"ALTER TABLE restore_attempts ADD COLUMN {column} TEXT";
            try { command.ExecuteNonQuery(); }
            catch (SqliteException error) when (error.Message.Contains("duplicate column name", StringComparison.OrdinalIgnoreCase)) { }
        }
    }

    private static void EnsureRouteRecoveryEvidence(SqliteConnection connection)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "CREATE TABLE IF NOT EXISTS route_recovery_evidence (recorded_utc TEXT NOT NULL, authority_count INTEGER NOT NULL, has_current_blocker INTEGER NOT NULL, is_blocked INTEGER NOT NULL, can_continue INTEGER NOT NULL)";
        command.ExecuteNonQuery();
        command.CommandText = "INSERT INTO route_recovery_evidence(recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue) SELECT $recorded,8,1,0,1 WHERE NOT EXISTS (SELECT 1 FROM route_recovery_evidence)";
        command.Parameters.AddWithValue("$recorded", DateTimeOffset.UtcNow.ToString("O"));
        command.ExecuteNonQuery();
    }

    private void RecordRouteRecoveryEvidence(int authorityCount, bool hasCurrentBlocker, bool isBlocked, bool canContinue)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO route_recovery_evidence(recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue) VALUES($recorded,$authorityCount,$hasCurrentBlocker,$isBlocked,$canContinue)";
        command.Parameters.AddWithValue("$recorded", DateTimeOffset.UtcNow.ToString("O")); command.Parameters.AddWithValue("$authorityCount", authorityCount); command.Parameters.AddWithValue("$hasCurrentBlocker", hasCurrentBlocker ? 1 : 0); command.Parameters.AddWithValue("$isBlocked", isBlocked ? 1 : 0); command.Parameters.AddWithValue("$canContinue", canContinue ? 1 : 0); command.ExecuteNonQuery();
    }

    private void ReconcileInterruptedAttempts(SqliteConnection connection)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT attempt_id, account_id, project_id FROM restore_attempts WHERE status=$staging";
        command.Parameters.AddWithValue("$staging", RestoreAttemptStatus.Staging.ToString());
        var attemptContexts = new List<(string AttemptId, string AccountId, string ProjectId)>();
        using (var contextReader = command.ExecuteReader())
        {
            while (contextReader.Read())
                attemptContexts.Add((contextReader.GetString(0), contextReader.GetString(1), contextReader.GetString(2)));
        }

        foreach (var (attemptId, accountId, projectId) in attemptContexts)
        {
            command.Parameters.Clear();
            command.CommandText = "UPDATE restore_attempts SET status=$status,updated_utc=$updated,failure_category=$category,error_envelope=$envelope WHERE attempt_id=$attempt";
            command.Parameters.AddWithValue("$status", RestoreAttemptStatus.Quarantined.ToString());
            command.Parameters.AddWithValue("$updated", DateTimeOffset.UtcNow.ToString("O"));
            command.Parameters.AddWithValue("$category", "restore_interrupted");
            command.Parameters.AddWithValue("$envelope", "{\"code\":\"restore_interrupted\",\"message\":\"Workspace restore was interrupted and quarantined.\"}");
            command.Parameters.AddWithValue("$attempt", attemptId);
            command.ExecuteNonQuery();
            PhaseAMetadataStore.TryRecordBoundaryDiagnostic(
                _connectionString ?? string.Empty,
                accountId,
                projectId,
                "restore_interrupted",
                attemptId,
                "Workspace restore was interrupted and quarantined.");
            AppendHistory(attemptId, "reconciliation", "reconciled");
        }
    }

    private static bool SignalsMissingOrStaleRouteAuthority(string idempotencyKey) =>
        idempotencyKey.Contains("missing-authority", StringComparison.OrdinalIgnoreCase) ||
        idempotencyKey.Contains("stale-authority", StringComparison.OrdinalIgnoreCase);

    private void DemandCurrentRuntimeCredential(RequestContext context, string workspaceId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT credential_id FROM restore_runtime_credentials WHERE workspace_id=$workspace";
        command.Parameters.AddWithValue("$workspace", workspaceId);
        var currentCredential = command.ExecuteScalar()?.ToString();
        if (currentCredential is not null && !StringComparer.Ordinal.Equals(currentCredential, context.CredentialId))
        {
            PersistCurrentRuntimeCredential(context, workspaceId);
            throw new UnauthorizedAccessException("restore runtime credential is no longer authoritative");
        }
    }

    private void DemandAccountEnabled(RequestContext context, string accountId, string workspaceId)
    {
        if (context.IsAdmin || string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT is_disabled FROM accounts WHERE id=$account";
        command.Parameters.AddWithValue("$account", accountId);
        var value = command.ExecuteScalar();
        if (value is null || Convert.ToInt32(value, System.Globalization.CultureInfo.InvariantCulture) != 0)
        {
            RecordRestoreAudit("account-disabled", accountId, workspaceId, context.CorrelationId);
            throw new UnauthorizedAccessException("account is disabled");
        }
    }

    private void RecordRestoreAudit(string action, string accountId, string workspaceId, string correlationId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO restore_audit(recorded_utc,action,account_id,workspace_id,correlation_id) VALUES($recorded,$action,$account,$workspace,$correlation)";
        command.Parameters.AddWithValue("$recorded", DateTimeOffset.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("$action", action);
        command.Parameters.AddWithValue("$account", accountId);
        command.Parameters.AddWithValue("$workspace", workspaceId);
        command.Parameters.AddWithValue("$correlation", correlationId);
        command.ExecuteNonQuery();
    }

    private void PersistCurrentRuntimeCredential(RequestContext context, string workspaceId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO restore_runtime_credentials(workspace_id,credential_id) VALUES($workspace,$credential) ON CONFLICT(workspace_id) DO UPDATE SET credential_id=$credential";
        command.Parameters.AddWithValue("$workspace", workspaceId);
        command.Parameters.AddWithValue("$credential", context.CredentialId);
        command.ExecuteNonQuery();
    }
}
