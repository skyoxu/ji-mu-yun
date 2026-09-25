using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S6BoundaryTests
{
    private const string ProjectId = "s6-project";
    private readonly ITestOutputHelper _output;

    public S6BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_026DB292EA9A()
    {
        using var fixture = await RestoreFixture.CreateAsync();
        var (source, manifest) = fixture.CreateSnapshot("old-lease", "current-publication");
        var destination = Directory.CreateDirectory(Path.Combine(fixture.Root.FullName, "old-lease-destination"));
        var service = new RestoreService(fixture.ConnectionString);
        var first = service.Restore(
            fixture.Context,
            manifest,
            source.FullName,
            destination.FullName,
            fixture.Lease,
            "s6-pre-restore-lease-initial");

        var oldLeaseRejected = false;
        RestoreAttempt? oldLeaseExercise = null;
        try
        {
            oldLeaseExercise = service.Restore(
                fixture.Context,
                manifest,
                source.FullName,
                destination.FullName,
                fixture.Lease,
                "s6-pre-restore-lease-exercise");
        }
        catch (Exception error) when (
            error is UnauthorizedAccessException or InvalidOperationException &&
            error.Message.Contains("not authoritative", StringComparison.Ordinal))
        {
            oldLeaseRejected = true;
        }

        var currentPublication = Path.Combine(destination.FullName, ".restore-current", "project.godot");
        Require(
            first.Status == RestoreAttemptStatus.Published &&
            File.Exists(currentPublication) &&
            File.ReadAllText(currentPublication) == "current-publication" &&
            oldLeaseRejected &&
            oldLeaseExercise is null,
            "FAILURE-O-026DB292EA9A",
            "A lease retained from before a completed restore remained authoritative at the current publication boundary.");
        _output.WriteLine("S6-OBSERVATION O-026DB292EA9A pre-restore-lease-rejected-at-current-publication-boundary");
    }

    [Fact]
    public async Task O_BA014C1EB184()
    {
        using var fixture = await RestoreFixture.CreateAsync();
        var source = Directory.CreateDirectory(Path.Combine(fixture.Root.FullName, "retry-source"));
        var destination = Directory.CreateDirectory(Path.Combine(fixture.Root.FullName, "retry-destination"));
        var failedManifest = SnapshotManifest.Create(
            "s6-retry-failed-snapshot",
            fixture.WorkspaceId,
            fixture.AccountId,
            ProjectId,
            "s6-policy",
            [("project.godot", "retry-content"u8.ToArray())]);
        var service = new RestoreService(fixture.ConnectionString);
        const string idempotencyKey = "s6-retry-key";

        var failed = service.Restore(
            fixture.Context,
            failedManifest,
            source.FullName,
            destination.FullName,
            fixture.Lease,
            idempotencyKey);
        var beforeRetry = ReadHistory(fixture.ConnectionString, failed.AttemptId);

        RestoreAttempt? retried = null;
        try
        {
            retried = service.Restore(
                fixture.Context,
                failedManifest,
                source.FullName,
                destination.FullName,
                fixture.Lease,
                idempotencyKey);
        }
        catch (Exception)
        {
            // The assertion below records a retry failure as product behavior.
        }

        var afterRetry = ReadHistory(fixture.ConnectionString, failed.AttemptId);
        var priorHistoryRemained = beforeRetry.Count > 0 &&
            afterRetry.Count >= beforeRetry.Count &&
            beforeRetry.SequenceEqual(afterRetry.Take(beforeRetry.Count));
        var appendedHistory = afterRetry.Count > beforeRetry.Count;
        var terminal = retried is not null && retried.Status != RestoreAttemptStatus.Staging;

        Require(
            failed.Status is RestoreAttemptStatus.Quarantined or RestoreAttemptStatus.Failed &&
            priorHistoryRemained &&
            appendedHistory &&
            terminal,
            "FAILURE-O-BA014C1EB184",
            "Retry did not preserve and append durable restore stage/outcome history before reaching a terminal state.");
        _output.WriteLine("S6-OBSERVATION O-BA014C1EB184 retry-appended-history-and-reached-terminal-state");
    }

    [Fact]
    public async Task O_DE0452FC4B15()
    {
        using var fixture = await RestoreFixture.CreateAsync();
        var (source, manifest) = fixture.CreateSnapshot("bindings", "binding-content");
        var destination = Directory.CreateDirectory(Path.Combine(fixture.Root.FullName, "binding-destination"));
        const string idempotencyKey = "s6-binding-key";
        var submitted = new RestoreBindings(
            fixture.Context.PrincipalId,
            fixture.AccountId,
            ProjectId,
            manifest.SnapshotId,
            destination.FullName,
            idempotencyKey);
        var service = new RestoreService(fixture.ConnectionString);
        var created = service.Restore(
            fixture.Context,
            manifest,
            source.FullName,
            destination.FullName,
            fixture.Lease,
            idempotencyKey);
        var initialReadback = ReadBindings(fixture.ConnectionString, idempotencyKey);

        var (mutatedSource, mutatedManifest) = fixture.CreateSnapshot("binding-mutation", "mutated-content");
        var mutatedDestination = Directory.CreateDirectory(Path.Combine(fixture.Root.FullName, "mutated-binding-destination"));
        var conflictingRequestRejected = false;
        try
        {
            service.Restore(
                fixture.Context,
                mutatedManifest,
                mutatedSource.FullName,
                mutatedDestination.FullName,
                fixture.Lease,
                idempotencyKey);
        }
        catch (UnauthorizedAccessException)
        {
            conflictingRequestRejected = true;
        }
        var postMutationReadback = ReadBindings(fixture.ConnectionString, idempotencyKey);

        Require(
            created.Status == RestoreAttemptStatus.Published &&
            initialReadback == submitted &&
            conflictingRequestRejected &&
            !Directory.Exists(Path.Combine(mutatedDestination.FullName, ".restore-current")) &&
            postMutationReadback == submitted,
            "FAILURE-O-DE0452FC4B15",
            "The Restore operation did not read back immutable requester, tenant, project, snapshot, target, and idempotency-key bindings.");
        _output.WriteLine("S6-OBSERVATION O-DE0452FC4B15 six-restore-bindings-read-back-and-remained-immutable");
    }

    private static IReadOnlyList<RestoreHistory> ReadHistory(string connectionString, string attemptId)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT stage, outcome FROM restore_attempt_history WHERE attempt_id=$attempt ORDER BY sequence";
        command.Parameters.AddWithValue("$attempt", attemptId);
        try
        {
            using var reader = command.ExecuteReader();
            var history = new List<RestoreHistory>();
            while (reader.Read())
            {
                history.Add(new RestoreHistory(reader.GetString(0), reader.GetString(1)));
            }

            return history;
        }
        catch (SqliteException error) when (error.Message.Contains("no such table", StringComparison.Ordinal))
        {
            return [];
        }
    }

    private static RestoreBindings? ReadBindings(string connectionString, string idempotencyKey)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        var columns = new HashSet<string>(StringComparer.Ordinal);
        using (var tableInfo = connection.CreateCommand())
        {
            tableInfo.CommandText = "PRAGMA table_info(restore_attempts)";
            using var reader = tableInfo.ExecuteReader();
            while (reader.Read())
            {
                columns.Add(reader.GetString(1));
            }
        }

        var requiredColumns = new[] { "requester_id", "tenant_id", "project_id", "snapshot_id", "target", "idempotency_key" };
        if (!requiredColumns.All(columns.Contains))
        {
            return null;
        }

        using var command = connection.CreateCommand();
        command.CommandText = "SELECT requester_id, tenant_id, project_id, snapshot_id, target, idempotency_key FROM restore_attempts WHERE idempotency_key=$key";
        command.Parameters.AddWithValue("$key", idempotencyKey);
        using var row = command.ExecuteReader();
        return row.Read()
            ? new RestoreBindings(
                row.GetString(0),
                row.GetString(1),
                row.GetString(2),
                row.GetString(3),
                row.GetString(4),
                row.GetString(5))
            : null;
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class RestoreFixture : IDisposable
    {
        private RestoreFixture(
            DirectoryInfo root,
            string connectionString,
            string accountId,
            RequestContext context,
            RunnerLease lease)
        {
            Root = root;
            ConnectionString = connectionString;
            AccountId = accountId;
            Context = context;
            Lease = lease;
        }

        public DirectoryInfo Root { get; }
        public string ConnectionString { get; }
        public string AccountId { get; }
        public string WorkspaceId => "s6-workspace";
        public RequestContext Context { get; }
        public RunnerLease Lease { get; }

        public static async Task<RestoreFixture> CreateAsync()
        {
            var root = Directory.CreateTempSubdirectory("s6-boundary-");
            try
            {
                var connectionString = new SqliteConnectionStringBuilder
                {
                    DataSource = Path.Combine(root.FullName, "metadata.sqlite3"),
                }.ToString();
                await SqliteMetadataSchema.InitializeAsync(connectionString);
                await new SqliteMigrationService().MigrateAsync(connectionString, "s6-account", ProjectId, "s6-migration");
                var store = CreateStore(connectionString, root.FullName);
                var accountId = await CreateProjectAsync(store, root.FullName);
                var runId = await store.CreateRunAsync(ProjectId, null, "s6-run");
                if (!await store.TryAcquireRunnerLockAsync(ProjectId, runId))
                {
                    throw new InvalidOperationException("The disposable S6 runner lease could not be acquired.");
                }

                var lease = await ReadLeaseAsync(connectionString, runId)
                    ?? throw new InvalidOperationException("The disposable S6 runner lease could not be read.");
                var context = RequestContext.FromIdentity(
                    new AccountIdentity(accountId, "owner", PhaseAAuth.UserRole),
                    "s6-requester",
                    "s6-runtime-credential",
                    "s6-correlation");
                return new RestoreFixture(root, connectionString, accountId, context, lease);
            }
            catch
            {
                SqliteConnection.ClearAllPools();
                root.Delete(recursive: true);
                throw;
            }
        }

        public (DirectoryInfo Source, SnapshotManifest Manifest) CreateSnapshot(string snapshotId, string content)
        {
            var source = Directory.CreateDirectory(Path.Combine(Root.FullName, $"source-{snapshotId}"));
            File.WriteAllText(Path.Combine(source.FullName, "project.godot"), content);
            var storage = new WorkspaceStorageService(ConnectionString);
            storage.SetQuota(AccountId, 4 * 1024 * 1024);
            var snapshot = storage.CreateSnapshot(
                Context,
                source.FullName,
                $"s6-{snapshotId}-snapshot",
                WorkspaceId,
                ProjectId,
                "s6-policy",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase));
            return (source, snapshot.Manifest);
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (Root.Exists)
            {
                Root.Delete(recursive: true);
            }
        }

        private static PhaseAMetadataStore CreateStore(string connectionString, string workspaceRoot)
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            });
            return new PhaseAMetadataStore(connectionString, options);
        }

        private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, string root)
        {
            var account = await store.CreateUserAccountAsync($"s6-user-{Guid.NewGuid():N}", 1);
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                ProjectId,
                account.AccountId,
                "S6 boundary",
                "S6 boundary",
                "manual",
                "default",
                false,
                [],
                projectRoot.FullName,
                Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"),
                Path.Combine(projectRoot.FullName, "meta")));
            if (project.ProjectId != ProjectId)
            {
                throw new InvalidOperationException("The disposable S6 project could not be created.");
            }

            return account.AccountId;
        }

        private static async Task<RunnerLease?> ReadLeaseAsync(string connectionString, string leaseId)
        {
            await using var connection = new SqliteConnection(connectionString);
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT lease_id, account_id, project_id, fence FROM runner_leases WHERE lease_id=$lease_id";
            command.Parameters.AddWithValue("$lease_id", leaseId);
            await using var reader = await command.ExecuteReaderAsync();
            return await reader.ReadAsync()
                ? new RunnerLease(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.GetInt64(3))
                : null;
        }
    }

    private sealed record RestoreHistory(string Stage, string Outcome);

    private sealed record RestoreBindings(
        string RequesterId,
        string TenantId,
        string ProjectId,
        string SnapshotId,
        string Target,
        string IdempotencyKey);
}
