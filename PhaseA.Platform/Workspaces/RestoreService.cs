using PhaseA.Platform.Readback;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Microsoft.Data.Sqlite;
using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workspaces;

public sealed class RestoreService
{
    private readonly string? _connectionString;
    // Single-node publication coordination. The durable SQLite row remains the
    // authority across restarts; this gate prevents two in-process callers from
    // staging and publishing different attempts for the same idempotency key.
    private readonly object _restoreGate = new();
    private readonly Dictionary<string, RestoreAttempt> _inMemoryAttempts = new(StringComparer.Ordinal);
    private readonly HashSet<string> _invalidatedLeaseIds = new(StringComparer.Ordinal);
    private readonly RouteRecoveryAuthorityResolver? _routeAuthorityResolver;

    public RestoreService(string? connectionString = null, RouteRecoveryAuthorityResolver? routeAuthorityResolver = null)
    {
        _connectionString = connectionString;
        _routeAuthorityResolver = routeAuthorityResolver;
        if (!string.IsNullOrWhiteSpace(connectionString))
        {
            using var connection = new SqliteConnection(connectionString); connection.Open(); using var command = connection.CreateCommand();
            command.CommandText = "CREATE TABLE IF NOT EXISTS runner_leases (lease_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, fence INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS invalidated_runner_leases (lease_id TEXT PRIMARY KEY, invalidated_utc TEXT NOT NULL); CREATE TABLE IF NOT EXISTS restore_attempts (attempt_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, snapshot_id TEXT NOT NULL, workspace_id TEXT NOT NULL, account_id TEXT NOT NULL, project_id TEXT NOT NULL, status TEXT NOT NULL, fence INTEGER NOT NULL, updated_utc TEXT NOT NULL, requester_id TEXT, tenant_id TEXT, target TEXT); CREATE TABLE IF NOT EXISTS restore_attempt_history (attempt_id TEXT NOT NULL, sequence INTEGER NOT NULL, stage TEXT NOT NULL, outcome TEXT NOT NULL, PRIMARY KEY(attempt_id, sequence)); CREATE TABLE IF NOT EXISTS restore_runtime_credentials (workspace_id TEXT PRIMARY KEY, credential_id TEXT NOT NULL); CREATE TABLE IF NOT EXISTS restore_audit (recorded_utc TEXT NOT NULL, action TEXT NOT NULL, account_id TEXT NOT NULL, workspace_id TEXT NOT NULL, correlation_id TEXT NOT NULL)"; command.ExecuteNonQuery();
            EnsureRestoreAttemptColumns(connection);
            EnsureRouteRecoveryEvidence(connection);
            ReconcileInterruptedAttempts(connection);
        }
    }

    public RestoreAttempt Restore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease)
        => Restore(context, manifest, sourceRoot, destinationRoot, lease, $"restore:{manifest.SnapshotId}:{manifest.WorkspaceId}");

    public RunnerLease? GetAuthoritativeLease(string accountId, string projectId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return null;
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT lease_id, account_id, project_id, fence FROM runner_leases WHERE account_id=$account AND project_id=$project AND NOT EXISTS (SELECT 1 FROM invalidated_runner_leases i WHERE i.lease_id=runner_leases.lease_id) ORDER BY fence DESC LIMIT 1";
        command.Parameters.AddWithValue("$account", accountId);
        command.Parameters.AddWithValue("$project", projectId);
        using var reader = command.ExecuteReader();
        return reader.Read()
            ? new RunnerLease(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetInt64(3))
            : null;
    }

    public RestoreAttempt Restore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease, string idempotencyKey)
    {
        lock (_restoreGate)
        {
            return RestoreCore(context, manifest, sourceRoot, destinationRoot, lease, idempotencyKey);
        }
    }

    private RestoreAttempt RestoreCore(RequestContext context, SnapshotManifest manifest, string sourceRoot, string destinationRoot, RunnerLease lease, string idempotencyKey)
    {
        using var coordination = AcquireCrossProcessCoordination(destinationRoot, idempotencyKey);
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
        if (!HasCurrentRouteAuthority(manifest.AccountId, manifest.ProjectId))
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
            if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(destinationRoot, out var destinationDescriptor) ||
                destinationDescriptor.AccountId != manifest.AccountId || destinationDescriptor.ProjectId != manifest.ProjectId ||
                !RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(destinationDescriptor))
                throw new RestoreBoundaryFailure("acl_invalid");
            var capturedFiles = manifest.ReadProtectedContent();
            StageProtectedContent(manifest, capturedFiles, staging);
            try { RunnerIsolationPolicy.PrepareRestoreTree(destinationDescriptor, staging); }
            catch (Exception error) when (error is UnauthorizedAccessException or IOException or System.ComponentModel.Win32Exception)
            { throw new RestoreBoundaryFailure("acl_invalid"); }
            WritePublicationCheckpoint(destinationRoot, attempt.AttemptId, "staging-written");
            WaitForTestFaultPoint(destinationRoot, attempt.AttemptId, "staging-written");
            // Re-check authority at the publication boundary. A lease or
            // runtime capability revoked while content was being staged must
            // not be able to publish a new ready directory.
            DemandAuthoritativeLease(lease);
            DemandCurrentRuntimeCredential(context, manifest.WorkspaceId);
            if (!HasCurrentRouteAuthority(manifest.AccountId, manifest.ProjectId))
                throw new RestoreBoundaryFailure("route_authority_missing");
            WritePublicationCheckpoint(destinationRoot, attempt.AttemptId, "post-verification");
            WaitForTestFaultPoint(destinationRoot, attempt.AttemptId, "post-verification");
            if (!RunnerIsolationPolicy.HasExpectedRestoreTreeSecurity(destinationDescriptor, staging))
                throw new RestoreBoundaryFailure("acl_invalid");
            Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
            if (Directory.Exists(published)) Directory.Move(published, backup);
            WritePublicationCheckpoint(destinationRoot, attempt.AttemptId, "previous-moved");
            WaitForTestFaultPoint(destinationRoot, attempt.AttemptId, "previous-moved");
            try { Directory.Move(staging, published); publishedFromStaging = true; }
            catch { if (Directory.Exists(backup) && !Directory.Exists(published)) Directory.Move(backup, published); throw; }
            WritePublicationCheckpoint(destinationRoot, attempt.AttemptId, "current-switched");
            WaitForTestFaultPoint(destinationRoot, attempt.AttemptId, "current-switched");
            if (!RunnerIsolationPolicy.HasExpectedRestoreTreeSecurity(destinationDescriptor, published))
                throw new RestoreBoundaryFailure("acl_invalid");
            var result = attempt.Advance(RestoreAttemptStatus.Published);
            PersistCurrentRuntimeCredential(context, manifest.WorkspaceId);
            ProjectAssetPreviewTicketService.InvalidateTickets(manifest.AccountId, manifest.ProjectId);
            _inMemoryAttempts[idempotencyKey] = result;
            PersistAttempt(result, idempotencyKey, lease, context, manifest, destinationRoot);
            WritePublicationCheckpoint(destinationRoot, attempt.AttemptId, "metadata-committed");
            WaitForTestFaultPoint(destinationRoot, attempt.AttemptId, "metadata-committed");
            AppendHistory(result.AttemptId, "publish", "published");
            WritePublicationCheckpoint(destinationRoot, attempt.AttemptId, "history-appended");
            _invalidatedLeaseIds.Add(lease.LeaseId);
            PersistInvalidatedLease(lease.LeaseId);
            WritePublicationCheckpoint(destinationRoot, attempt.AttemptId, "lease-invalidated");
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

    private static FileStream AcquireCrossProcessCoordination(string destinationRoot, string idempotencyKey)
    {
        Directory.CreateDirectory(destinationRoot);
        var suffix = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(idempotencyKey))).ToLowerInvariant()[..24];
        var path = Path.Combine(destinationRoot, $".restore-lock-{suffix}");
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(15);
        while (true)
        {
            try { return new FileStream(path, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None, 1, FileOptions.DeleteOnClose); }
            catch (IOException) when (DateTime.UtcNow < deadline) { Thread.Sleep(25); }
        }
    }

    private static void WritePublicationCheckpoint(string destinationRoot, string attemptId, string checkpoint)
    {
        var directory = Path.Combine(destinationRoot, ".restore-checkpoints", attemptId);
        Directory.CreateDirectory(directory);
        File.WriteAllText(Path.Combine(directory, checkpoint + ".json"),
            System.Text.Json.JsonSerializer.Serialize(new
            {
                attemptId,
                checkpoint,
                recordedUtc = DateTimeOffset.UtcNow
            }));
    }

    private static void WaitForTestFaultPoint(string destinationRoot, string attemptId, string checkpoint)
    {
        if (!string.Equals(Environment.GetEnvironmentVariable("PHASEA_RESTORE_FAULT_POINT"), checkpoint, StringComparison.Ordinal))
            return;

        var release = Path.Combine(destinationRoot, ".restore-checkpoints", attemptId, checkpoint + ".release");
        var deadline = DateTime.UtcNow + TimeSpan.FromMinutes(2);
        while (!File.Exists(release) && DateTime.UtcNow < deadline)
            Thread.Sleep(25);
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
        var category = ClassifyRestoreFailure(error);
        var detail = error is InvalidDataException or System.Security.Cryptography.CryptographicException
            ? error.Message
            : null;
        var result = attempt.Advance(RestoreAttemptStatus.Quarantined) with { FailureCategory = category, FailureDetail = detail };
        _inMemoryAttempts[idempotencyKey] = result;
        var envelope = System.Text.Json.JsonSerializer.Serialize(new
        {
            code = category,
            message = "Workspace restore could not be completed.",
            detail,
            requestId = context.CorrelationId
        });
        PersistAttempt(result, idempotencyKey, lease, context, manifest, destinationRoot, category, envelope);
        // Preserve every failure as a controlled diagnostic. The route
        // authority resolver decides separately which families are live
        // publication blockers; operation-local failures remain retryable.
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
        using (var invalidated = connection.CreateCommand())
        {
            invalidated.CommandText = "SELECT 1 FROM invalidated_runner_leases WHERE lease_id=$id";
            invalidated.Parameters.AddWithValue("$id", lease.LeaseId);
            if (invalidated.ExecuteScalar() is not null)
                throw new InvalidOperationException("runner lease is not authoritative");
        }
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

    private void PersistInvalidatedLease(string leaseId)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO invalidated_runner_leases(lease_id,invalidated_utc) VALUES($id,$utc) ON CONFLICT(lease_id) DO NOTHING";
        command.Parameters.AddWithValue("$id", leaseId);
        command.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O"));
        command.ExecuteNonQuery();
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
        command.CommandText = "CREATE TABLE IF NOT EXISTS route_recovery_evidence (recorded_utc TEXT NOT NULL, authority_count INTEGER NOT NULL, has_current_blocker INTEGER NOT NULL, is_blocked INTEGER NOT NULL, can_continue INTEGER NOT NULL, source_order_json TEXT NOT NULL DEFAULT '[]', blocker_json TEXT NOT NULL DEFAULT '[]')";
        command.ExecuteNonQuery();
        foreach (var column in new[] { "source_order_json", "blocker_json" })
        {
            command.CommandText = $"ALTER TABLE route_recovery_evidence ADD COLUMN {column} TEXT NOT NULL DEFAULT '[]'";
            try { command.ExecuteNonQuery(); }
            catch (SqliteException error) when (error.Message.Contains("duplicate column name", StringComparison.OrdinalIgnoreCase)) { }
        }
    }

    private void RecordRouteRecoveryEvidence(
        int authorityCount,
        bool hasCurrentBlocker,
        bool isBlocked,
        bool canContinue,
        IReadOnlyList<string>? sourceEvidence = null,
        IReadOnlyList<string>? blockers = null)
    {
        if (string.IsNullOrWhiteSpace(_connectionString)) return;
        using var connection = new SqliteConnection(_connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO route_recovery_evidence(recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue,source_order_json,blocker_json) VALUES($recorded,$authorityCount,$hasCurrentBlocker,$isBlocked,$canContinue,$sources,$blockers)";
        command.Parameters.AddWithValue("$recorded", DateTimeOffset.UtcNow.ToString("O")); command.Parameters.AddWithValue("$authorityCount", authorityCount); command.Parameters.AddWithValue("$hasCurrentBlocker", hasCurrentBlocker ? 1 : 0); command.Parameters.AddWithValue("$isBlocked", isBlocked ? 1 : 0); command.Parameters.AddWithValue("$canContinue", canContinue ? 1 : 0);
        command.Parameters.AddWithValue("$sources", System.Text.Json.JsonSerializer.Serialize(sourceEvidence ?? PhaseA.Platform.Workflow.HostedRouteRecoveryContract.SourceOrder));
        command.Parameters.AddWithValue("$blockers", System.Text.Json.JsonSerializer.Serialize(blockers ?? Array.Empty<string>())); command.ExecuteNonQuery();
    }

    private void ReconcileInterruptedAttempts(SqliteConnection connection)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT attempt_id, account_id, project_id, target FROM restore_attempts WHERE status=$staging";
        command.Parameters.AddWithValue("$staging", RestoreAttemptStatus.Staging.ToString());
        var attemptContexts = new List<(string AttemptId, string AccountId, string ProjectId, string? Target)>();
        using (var contextReader = command.ExecuteReader())
        {
            while (contextReader.Read())
                attemptContexts.Add((contextReader.GetString(0), contextReader.GetString(1), contextReader.GetString(2), contextReader.IsDBNull(3) ? null : contextReader.GetString(3)));
        }

        foreach (var (attemptId, accountId, projectId, target) in attemptContexts)
        {
            ReconcileAttemptDirectories(attemptId, target);
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

    private void ReconcileAttemptDirectories(string attemptId, string? target)
    {
        if (string.IsNullOrWhiteSpace(target) || !Directory.Exists(target)) return;
        var current = Path.Combine(target, ".restore-current");
        var staging = Path.Combine(target, ".restore-staging", attemptId);
        var previous = Path.Combine(target, ".restore-previous", attemptId);
        var quarantine = Path.Combine(target, ".restore-quarantine", attemptId);
        // A crash after moving ready aside but before switching staging must
        // restore the previous ready directory. A crash after switching keeps
        // the new ready directory and only isolates leftover staging.
        if (!Directory.Exists(current) && Directory.Exists(previous))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(current)!);
            Directory.Move(previous, current);
        }
        if (Directory.Exists(staging))
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(quarantine)!);
                if (Directory.Exists(quarantine)) Directory.Delete(quarantine, true);
                Directory.Move(staging, quarantine);
            }
            catch (IOException)
            {
                // A crashed worker may still have a short-lived file handle.
                // Keep the attempt quarantined in metadata and retry physical
                // isolation on the next service reconciliation.
            }
        }
    }

    private bool HasCurrentRouteAuthority(string accountId, string projectId)
    {
        // A connectionless RestoreService is only used by isolated in-memory
        // unit fixtures. Production and persistent callers always provide the
        // metadata-backed resolver, where missing authority fails closed.
        if (string.IsNullOrWhiteSpace(_connectionString)) return true;
        if (_routeAuthorityResolver is not null)
        {
            var resolved = _routeAuthorityResolver.Resolve(accountId, projectId);
            RecordRouteRecoveryEvidence(
                resolved.AuthorityCount,
                resolved.HasCurrentBlocker,
                !resolved.CanContinue,
                resolved.CanContinue,
                resolved.SourceEvidence,
                resolved.Blockers);
            return resolved.CanContinue;
        }
        if (string.IsNullOrWhiteSpace(_connectionString)) return false;
        using var connection = new SqliteConnection(_connectionString); connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue,source_order_json,blocker_json FROM route_recovery_evidence ORDER BY recorded_utc DESC LIMIT 1";
        using var reader = command.ExecuteReader();
        if (!reader.Read()) return false;
        if (!DateTimeOffset.TryParse(reader.GetString(0), out var recorded) || DateTimeOffset.UtcNow - recorded > TimeSpan.FromMinutes(30)) return false;
        if (reader.GetInt32(1) < 8 || reader.GetInt32(2) != 0 || reader.GetInt32(3) != 0 || reader.GetInt32(4) != 1) return false;
        try
        {
            var sources = System.Text.Json.JsonSerializer.Deserialize<string[]>(reader.GetString(5)) ?? [];
            var blockers = System.Text.Json.JsonSerializer.Deserialize<string[]>(reader.GetString(6)) ?? [];
            return sources.SequenceEqual(PhaseA.Platform.Workflow.HostedRouteRecoveryContract.SourceOrder, StringComparer.Ordinal) && blockers.Length == 0;
        }
        catch (System.Text.Json.JsonException) { return false; }
    }

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
