using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S40BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S40BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_063B424D13AA()
    {
        using var fixture = S40Fixture.Create();
        var attempt = fixture.Restore("explicit-authorized");
        var row = fixture.ReadAttempt("explicit-authorized");

        Require(
            attempt.Status == RestoreAttemptStatus.Published &&
            row is not null &&
            row.Status == nameof(RestoreAttemptStatus.Published) &&
            row.RequesterId == fixture.Context.PrincipalId &&
            row.SnapshotId == fixture.Manifest.SnapshotId,
            "FAILURE-O-063B424D13AA",
            "The protected explicit Restore request did not publish and retain its request binding.");
        Observe("O-063B424D13AA explicit-authorized-restore-started-for-snapshot");
    }

    [Fact]
    public async Task O_2532A1C438CC()
    {
        using var fixture = S40Fixture.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        var store = new PhaseAMetadataStore(fixture.ConnectionString, options);
        var account = await store.CreateUserAccountAsync($"s40-run-user-{Guid.NewGuid():N}", 1);
        var projectRoot = Directory.CreateDirectory(Path.Combine(fixture.Root, "run-project"));
        var projectId = $"s40-run-project-{Guid.NewGuid():N}";
        var project = await store.CreateProjectAsync(new ProjectCreationCommand(
            projectId,
            account.AccountId,
            "S40 run boundary",
            "S40 run boundary",
            "manual",
            "default",
            false,
            [],
            projectRoot.FullName,
            Path.Combine(projectRoot.FullName, "repo"),
            Path.Combine(projectRoot.FullName, "runtime"),
            Path.Combine(projectRoot.FullName, "meta")));
        Require(project.ProjectId == projectId, "FAILURE-O-2532A1C438CC", "The disposable Run boundary project could not be created.");
        var runId = await store.CreateRunAsync(projectId, null, "s40-run");
        await store.CompleteRunAsync(runId, "completed", 0, "run-complete", string.Empty, "{}");

        Require(
            fixture.CountRestoreAttempts() == 0,
            "FAILURE-O-2532A1C438CC",
            "Run completion created a Restore operation without an explicit Restore request.");
        Observe("O-2532A1C438CC run-completion-created-no-restore");
    }

    [Fact]
    public void O_2B15F2179A84()
    {
        using var fixture = S40Fixture.Create();
        _ = new WorkspaceStorageService(fixture.ConnectionString).GetQuota(fixture.AccountId);
        var evidence = fixture.ReadRouteRecoveryEvidence();

        Require(
            evidence is not null &&
            evidence.AuthorityCount == 8 &&
            evidence.HasCurrentBlocker &&
            evidence.CanContinue,
            "FAILURE-O-2B15F2179A84",
            "Hosted route recovery did not record all eight authorities and the current blocker before continuing.");
        Observe("O-2B15F2179A84 eight-authorities-and-current-blocker-recorded");
    }

    [Fact]
    public void O_32DDAD281981()
    {
        using var fixture = S40Fixture.Create();
        fixture.SeedInterruptedAttempt("pre-commit-attempt", "verified");
        _ = new RestoreService(fixture.ConnectionString);
        var state = fixture.ReadAttemptById("pre-commit-attempt");

        Require(
            state is not null &&
            state.Status is not nameof(RestoreAttemptStatus.Staging) and not nameof(RestoreAttemptStatus.Requested) &&
            fixture.HasReconciliationOutcome("pre-commit-attempt"),
            "FAILURE-O-32DDAD281981",
            "Restart did not reconcile the interrupted pre-commit Restore from durable Attempt and staging state.");
        Observe("O-32DDAD281981 restart-reconciled-pre-commit-from-durable-state");
    }

    [Fact]
    public void O_3618B7A10715()
    {
        using var fixture = S40Fixture.Create();
        var service = new RestoreService(fixture.ConnectionString);
        var first = service.Restore(fixture.Context, fixture.Manifest, fixture.SourceRoot, fixture.DestinationRoot, fixture.Lease, "equivalent-request");
        var second = service.Restore(fixture.Context, fixture.Manifest, fixture.SourceRoot, fixture.DestinationRoot, fixture.Lease, "equivalent-request");

        Require(
            first.Status == RestoreAttemptStatus.Published &&
            second.AttemptId == first.AttemptId &&
            fixture.CountRestoreAttempts() == 1 &&
            fixture.CountPublicationTargets() == 1,
            "FAILURE-O-3618B7A10715",
            "Equivalent Restore requests did not reuse one operation and one publication target.");
        Observe("O-3618B7A10715 equivalent-request-reused-one-operation");
    }

    [Fact]
    public void O_56D723EB3077()
    {
        using var fixture = S40Fixture.Create();
        var attempt = fixture.Restore("bounded-state");
        var state = fixture.ReadAttempt("bounded-state")?.Status;
        var bounded = Enum.GetNames<RestoreAttemptStatus>();

        Require(
            state is not null &&
            bounded.Contains(state, StringComparer.Ordinal) &&
            bounded.Contains(attempt.Status.ToString(), StringComparer.Ordinal),
            "FAILURE-O-56D723EB3077",
            "The Restore response or durable operation record exposed an unbounded state.");
        Observe("O-56D723EB3077 operation-states-were-bounded");
    }

    [Fact]
    public void O_682DD1974043()
    {
        using var fixture = S40Fixture.Create();
        var attempt = fixture.Restore("missing-authority");
        var authorityEvidence = fixture.ReadRouteRecoveryEvidence();

        Require(
            authorityEvidence is not null &&
            authorityEvidence.IsBlocked &&
            attempt.Status != RestoreAttemptStatus.Published,
            "FAILURE-O-682DD1974043",
            "Restore continued despite missing or stale route authority.");
        Observe("O-682DD1974043 missing-authority-blocked-before-readback-or-run");
    }

    [Fact]
    public void O_AF06B8605D44()
    {
        using var fixture = S40Fixture.Create(withProtectedContent: false);
        var attempt = fixture.Restore("bounded-failure");
        var evidence = fixture.ReadFailureEvidence("bounded-failure");

        Require(
            attempt.Status is RestoreAttemptStatus.Quarantined or RestoreAttemptStatus.Failed &&
            evidence is not null &&
            evidence.HasFailureCategory &&
            evidence.HasRedactedEnvelope &&
            !evidence.ContainsRawException,
            "FAILURE-O-AF06B8605D44",
            "Restore failure was not exposed as a bounded, categorized, redacted result.");
        Observe("O-AF06B8605D44 bounded-failure-category-and-redacted-envelope");
    }

    [Fact]
    public void O_E91BBDCF1838()
    {
        using var fixture = S40Fixture.Create();
        fixture.SeedInterruptedAttempt("post-verification-attempt", "verified");
        _ = new RestoreService(fixture.ConnectionString);
        var state = fixture.ReadAttemptById("post-verification-attempt");

        Require(
            state is not null &&
            state.Status is not nameof(RestoreAttemptStatus.Staging) and not nameof(RestoreAttemptStatus.Requested) &&
            fixture.HasReconciliationOutcome("post-verification-attempt"),
            "FAILURE-O-E91BBDCF1838",
            "Restart did not reconcile the verified interrupted Restore from durable state.");
        Observe("O-E91BBDCF1838 restart-reconciled-post-verification-from-durable-state");
    }

    [Fact]
    public void O_F91AAB48A10C()
    {
        using var fixture = S40Fixture.Create();
        var unauthorized = fixture.Context with { AccountId = "different-account" };
        var denied = false;
        try
        {
            _ = new RestoreService(fixture.ConnectionString).Restore(
                unauthorized,
                fixture.Manifest,
                fixture.SourceRoot,
                fixture.DestinationRoot,
                fixture.Lease,
                "unprotected-request");
        }
        catch (UnauthorizedAccessException)
        {
            denied = true;
        }

        var authorized = fixture.Restore("protected-explicit-request");
        Require(
            denied &&
            fixture.CountRestoreAttempts() == 1 &&
            authorized.Status == RestoreAttemptStatus.Published,
            "FAILURE-O-F91AAB48A10C",
            "An unprotected Restore submission was accepted or created an operation.");
        Observe("O-F91AAB48A10C only-protected-explicit-entry-created-restore");
    }

    private void Observe(string observation) => _output.WriteLine($"S40-OBSERVATION {observation}");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class S40Fixture : IDisposable
    {
        private S40Fixture(string root, string connectionString, SnapshotManifest manifest, RequestContext context, RunnerLease lease)
        {
            Root = root;
            ConnectionString = connectionString;
            Manifest = manifest;
            Context = context;
            Lease = lease;
            SourceRoot = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            DestinationRoot = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
            File.WriteAllText(Path.Combine(SourceRoot, "project.godot"), "s40-content");
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public string AccountId => Context.AccountId;
        public string ProjectId => "s40-project";
        public string WorkspaceId => "s40-workspace";
        public SnapshotManifest Manifest { get; }
        public RequestContext Context { get; }
        public RunnerLease Lease { get; }
        public string SourceRoot { get; }
        public string DestinationRoot { get; }

        public static S40Fixture Create(bool withProtectedContent = true)
        {
            var root = Directory.CreateTempSubdirectory("s40-boundary-").FullName;
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root, "metadata.sqlite3"),
                Pooling = false
            }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            _ = new RestoreService(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = store.CreateUserAccountAsync($"s40-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            _ = store.CreateProjectAsync(new ProjectCreationCommand(
                "s40-project",
                account.AccountId,
                "S40 boundary",
                "S40 boundary",
                "manual",
                "default",
                false,
                [],
                projectRoot.FullName,
                Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"),
                Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
            var manifest = SnapshotManifest.Create(
                "s40-snapshot",
                "s40-workspace",
                account.AccountId,
                "s40-project",
                "s40-policy",
                [("project.godot", "s40-content"u8.ToArray())]);
            if (withProtectedContent)
            {
                manifest = manifest with
                {
                    ProtectedContent = SnapshotManifest.ProtectContent(
                        [("project.godot", "s40-content"u8.ToArray())],
                        manifest.KeyReference)
                };
            }

            var context = RequestContext.FromIdentity(
                new AccountIdentity(account.AccountId, "owner", PhaseAAuth.UserRole),
                "s40-requester",
                "s40-credential",
                "s40-correlation");
            var lease = new RunnerLease("s40-lease", account.AccountId, "s40-project", 1);
            using (var connection = new SqliteConnection(connectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
                command.Parameters.AddWithValue("$id", lease.LeaseId);
                command.Parameters.AddWithValue("$account", lease.AccountId);
                command.Parameters.AddWithValue("$project", lease.ProjectId);
                command.Parameters.AddWithValue("$fence", lease.Fence);
                command.ExecuteNonQuery();
            }

            return new S40Fixture(root, connectionString, manifest, context, lease);
        }

        public RestoreAttempt Restore(string key) => new RestoreService(ConnectionString).Restore(Context, Manifest, SourceRoot, DestinationRoot, Lease, key);

        public AttemptRow? ReadAttempt(string key)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT attempt_id,snapshot_id,status,requester_id FROM restore_attempts WHERE idempotency_key=$key";
            command.Parameters.AddWithValue("$key", key);
            using var reader = command.ExecuteReader();
            return reader.Read()
                ? new AttemptRow(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.IsDBNull(3) ? null : reader.GetString(3))
                : null;
        }

        public AttemptRow? ReadAttemptById(string attemptId)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT attempt_id,snapshot_id,status,requester_id FROM restore_attempts WHERE attempt_id=$id";
            command.Parameters.AddWithValue("$id", attemptId);
            using var reader = command.ExecuteReader();
            return reader.Read()
                ? new AttemptRow(reader.GetString(0), reader.GetString(1), reader.GetString(2), reader.IsDBNull(3) ? null : reader.GetString(3))
                : null;
        }

        public int CountRestoreAttempts()
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(*) FROM restore_attempts";
            return Convert.ToInt32(command.ExecuteScalar());
        }

        public int CountPublicationTargets() => Directory.Exists(Path.Combine(DestinationRoot, ".restore-current")) ? 1 : 0;

        public RouteRecoveryEvidence? ReadRouteRecoveryEvidence()
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var table = connection.CreateCommand();
            table.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='route_recovery_evidence'";
            if (Convert.ToInt32(table.ExecuteScalar()) == 0)
            {
                return null;
            }

            using var command = connection.CreateCommand();
            command.CommandText = "SELECT authority_count,has_current_blocker,is_blocked,can_continue FROM route_recovery_evidence ORDER BY recorded_utc DESC LIMIT 1";
            using var reader = command.ExecuteReader();
            return reader.Read()
                ? new RouteRecoveryEvidence(reader.GetInt32(0), reader.GetInt32(1) != 0, reader.GetInt32(2) != 0, reader.GetInt32(3) != 0)
                : null;
        }

        public FailureEvidence? ReadFailureEvidence(string key)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var table = connection.CreateCommand();
            table.CommandText = "PRAGMA table_info(restore_attempts)";
            var columns = new HashSet<string>(StringComparer.Ordinal);
            using (var reader = table.ExecuteReader())
            {
                while (reader.Read()) columns.Add(reader.GetString(1));
            }

            var hasFailureCategory = columns.Contains("failure_category");
            var hasEnvelope = columns.Contains("error_envelope");
            var hasRawException = columns.Contains("raw_exception");
            if (!hasFailureCategory && !hasEnvelope && !hasRawException) return null;
            return new FailureEvidence(hasFailureCategory, hasEnvelope, hasRawException);
        }

        public void SeedInterruptedAttempt(string attemptId, string outcome)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var insert = connection.CreateCommand();
            insert.CommandText = "INSERT INTO restore_attempts(attempt_id,idempotency_key,snapshot_id,workspace_id,account_id,project_id,status,fence,updated_utc,requester_id,tenant_id,target) VALUES($id,$key,$snapshot,$workspace,$account,$project,$status,1,$updated,$requester,$tenant,$target)";
            insert.Parameters.AddWithValue("$id", attemptId);
            insert.Parameters.AddWithValue("$key", attemptId);
            insert.Parameters.AddWithValue("$snapshot", Manifest.SnapshotId);
            insert.Parameters.AddWithValue("$workspace", WorkspaceId);
            insert.Parameters.AddWithValue("$account", AccountId);
            insert.Parameters.AddWithValue("$project", ProjectId);
            insert.Parameters.AddWithValue("$status", nameof(RestoreAttemptStatus.Staging));
            insert.Parameters.AddWithValue("$updated", DateTimeOffset.UtcNow.ToString("O"));
            insert.Parameters.AddWithValue("$requester", Context.PrincipalId);
            insert.Parameters.AddWithValue("$tenant", AccountId);
            insert.Parameters.AddWithValue("$target", DestinationRoot);
            insert.ExecuteNonQuery();
            using var history = connection.CreateCommand();
            history.CommandText = "INSERT INTO restore_attempt_history(attempt_id,sequence,stage,outcome) VALUES($id,1,'verification',$outcome)";
            history.Parameters.AddWithValue("$id", attemptId);
            history.Parameters.AddWithValue("$outcome", outcome);
            history.ExecuteNonQuery();
            Directory.CreateDirectory(Path.Combine(DestinationRoot, ".restore-staging", attemptId));
        }

        public bool HasReconciliationOutcome(string attemptId)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(*) FROM restore_attempt_history WHERE attempt_id=$id AND outcome IN ('published','quarantined','failed','reconciled')";
            command.Parameters.AddWithValue("$id", attemptId);
            return Convert.ToInt32(command.ExecuteScalar()) > 0;
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(Root, true); } catch (IOException) { }
        }
    }

    private sealed record AttemptRow(string AttemptId, string SnapshotId, string Status, string? RequesterId);
    private sealed record RouteRecoveryEvidence(int AuthorityCount, bool HasCurrentBlocker, bool IsBlocked, bool CanContinue);
    private sealed record FailureEvidence(bool HasFailureCategory, bool HasRedactedEnvelope, bool ContainsRawException);
}
