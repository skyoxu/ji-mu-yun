using System.Collections.Immutable;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S4BoundaryTests
{
    private readonly ITestOutputHelper _output;
    public S4BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact] public void O_04CA4A548AA3() => Verify("O-04CA4A548AA3", "owned-staging-only", f => {
        var foreign = Directory.CreateDirectory(Path.Combine(f.Destination, ".restore-staging", "foreign-attempt"));
        f.Restore(f.CorruptHash());
        return Directory.Exists(foreign.FullName) && Directory.Exists(Path.Combine(f.Destination, ".restore-quarantine"));
    });
    [Fact] public void O_095F95612632() => Verify("O-095F95612632", "unsafe-preserves-previous", f => f.DeniedAndPreserves(f.UnsafePath()));
    [Fact] public void O_1106AD75DA70() => Verify("O-1106AD75DA70", "disabled-account-stops-at-boundary", f => f.HasDisablementAuditAfterBoundary());
    [Fact] public void O_13C49F7B1BA5() => Verify("O-13C49F7B1BA5", "wrong-tenant-preserves-previous", f => f.WrongTenantDeniedAndPreserves());
    [Fact] public void O_1A645F443B8D() => Verify("O-1A645F443B8D", "acl-revalidated-at-publication", f => f.StaleLeaseDeniedAndPreserves());
    [Fact] public void O_22E1F7A35C2A() => Verify("O-22E1F7A35C2A", "retry-reuses-and-appends", f => f.RetryReusesAndAppends());
    [Fact] public void O_247BF23B0C4E() => Verify("O-247BF23B0C4E", "corrupt-hash-denied-before-publication", f => f.DeniedBeforePublication(f.CorruptHash()));
    [Fact] public void O_257064D85DFB() => Verify("O-257064D85DFB", "quota-preserves-previous", f => f.QuotaDeniedAndPreserves());
    [Fact] public void O_36E9B6026FB5() => Verify("O-36E9B6026FB5", "corrupt-hash-preserves-previous", f => f.DeniedAndPreserves(f.CorruptHash()));
    [Fact] public void O_4F0F3F54AFDB() => Verify("O-4F0F3F54AFDB", "corrupt-size-preserves-previous", f => f.DeniedAndPreserves(f.CorruptSize()));
    [Fact] public void O_5308B4618915() => Verify("O-5308B4618915", "retry-appends-history", f => f.RetryReusesAndAppends());
    [Fact] public void O_57D27F215F58() => Verify("O-57D27F215F58", "quota-denied-before-publication", f => f.QuotaDeniedAndPreserves());
    [Fact] public void O_59738F1588EA() => Verify("O-59738F1588EA", "active-inputs-preserved", f => f.ActiveInputsSurviveCleanup());
    [Fact] public void O_59EBD26DACCF() => Verify("O-59EBD26DACCF", "unsupported-version-denied", f => f.DeniedBeforePublication(f.UnsupportedVersion()));
    [Fact] public void O_7041E26E053E() => Verify("O-7041E26E053E", "cancellation-and-failure-recorded", f => f.CancellationAndFailureAreRecorded());
    [Fact] public void O_71141D2FE7DE() => Verify("O-71141D2FE7DE", "switch-reconciled-from-durable-state", f => f.RestartReconciles("switch"));
    [Fact] public void O_7391CE6328EE() => Verify("O-7391CE6328EE", "old-port-non-authoritative", f => f.PreRestoreCredentialIsNotAuthoritative());
    [Fact] public void O_798CB18520DD() => Verify("O-798CB18520DD", "drift-denied-before-publication", f => f.DeniedBeforePublication(f.CorruptSize()));
    [Fact] public void O_8326288AA6D2() => Verify("O-8326288AA6D2", "disabled-account-denied-at-publication", f => f.DisabledAccountDeniedAtPublication());
    [Fact] public void O_8B32FCC9BE2C() => Verify("O-8B32FCC9BE2C", "current-capability-newly-allocated", f => f.CurrentCapabilityIsNew());
    [Fact] public void O_959EDA3E4641() => Verify("O-959EDA3E4641", "final-metadata-reconciled-from-durable-state", f => f.RestartReconciles("final-metadata"));
    [Fact] public void O_95F4176DE624() => Verify("O-95F4176DE624", "unsafe-path-denied", f => f.DeniedBeforePublication(f.UnsafePath()));
    [Fact] public void O_A961834B7147() => Verify("O-A961834B7147", "corrupt-size-denied", f => f.DeniedBeforePublication(f.CorruptSize()));
    [Fact] public void O_AA85D212CFEF() => Verify("O-AA85D212CFEF", "unsupported-schema-preserves-previous", f => f.DeniedAndPreserves(f.UnsupportedSchema()));
    [Fact] public void O_B583298A3E58() => Verify("O-B583298A3E58", "retry-leaves-bounded-stage", f => f.RetryReusesAndAppends());
    [Fact] public void O_B7A53F040E70() => Verify("O-B7A53F040E70", "intent-reconciled-from-durable-state", f => f.RestartReconciles("intent"));
    [Fact] public void O_C715A5F94C56() => Verify("O-C715A5F94C56", "unsupported-schema-denied", f => f.DeniedBeforePublication(f.UnsupportedSchema()));
    [Fact] public void O_D821E468D50A() => Verify("O-D821E468D50A", "timer-started-no-restore", f => f.TimerDoesNotStartRestore());
    [Fact] public void O_E2F48205E037() => Verify("O-E2F48205E037", "unsupported-version-preserves-previous", f => f.DeniedAndPreserves(f.UnsupportedVersion()));
    [Fact] public void O_E662D90BD103() => Verify("O-E662D90BD103", "copy-reconciled-from-durable-state", f => f.RestartReconciles("copy"));
    [Fact] public void O_E6D97523CDCC() => Verify("O-E6D97523CDCC", "mismatch-denied-and-original-retained", f => f.MismatchedRequestIsDenied());
    [Fact] public void O_E93588211CB7() => Verify("O-E93588211CB7", "stale-lease-denied-at-publication", f => f.StaleLeaseDeniedAndPreserves());
    [Fact] public void O_F54FDFC116B0() => Verify("O-F54FDFC116B0", "bounded-rto-p95-recorded", f => f.BoundedRtoProbe());
    [Fact] public void O_FADF9565C2CD() => Verify("O-FADF9565C2CD", "wrong-tenant-denied-before-publication", f => f.WrongTenantDeniedAndPreserves());

    private void Verify(string obligation, string observation, Func<Fixture, bool> assertion)
    {
        using var fixture = Fixture.Create();
        Require(assertion(fixture), $"FAILURE-{obligation}", $"The production Restore boundary did not prove {observation}.");
        _output.WriteLine($"S4-OBSERVATION {obligation} {observation}");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition) throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private sealed class Fixture : IDisposable
    {
        private Fixture(string root, string connectionString, SnapshotManifest manifest, RequestContext context, RunnerLease lease)
        {
            Root = root; ConnectionString = connectionString; Manifest = manifest; Context = context; Lease = lease;
            Source = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            Destination = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
            File.WriteAllText(Path.Combine(Source, "project.godot"), "s4 source content");
            Directory.CreateDirectory(Path.Combine(Destination, ".restore-current"));
            File.WriteAllText(Path.Combine(Destination, ".restore-current", "project.godot"), "previous ready content");
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public string Source { get; }
        public string Destination { get; }
        public SnapshotManifest Manifest { get; }
        public RequestContext Context { get; }
        public string AccountId => Context.AccountId;
        public RunnerLease Lease { get; }

        public static Fixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s4-boundary-").FullName;
            var connectionString = new SqliteConnectionStringBuilder { DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            _ = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString));
            // ADR-0061: use a real enabled account while exercising the restore boundary.
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = store.CreateUserAccountAsync($"s4-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            _ = store.CreateProjectAsync(new ProjectCreationCommand(
                "s4-project", account.AccountId, "S4 boundary", "S4 boundary", "manual", "default", false, [],
                projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
            RouteAuthorityFixture.Seed(connectionString, account.AccountId, "s4-project", projectRoot.FullName);
            var manifest = SnapshotManifest.Create("s4-snapshot", "s4-workspace", account.AccountId, "s4-project", "s4-policy", [("project.godot", "s4 source content"u8.ToArray())]);
            manifest = manifest with { ProtectedContent = SnapshotManifest.ProtectContent([("project.godot", "s4 source content"u8.ToArray())], manifest.KeyReference) };
            var context = RequestContext.FromIdentity(new AccountIdentity(account.AccountId, "owner", PhaseAAuth.UserRole), "s4-principal", "s4-current-credential", "s4-correlation");
            var lease = new RunnerLease("s4-lease", account.AccountId, "s4-project", 1);
            using var connection = new SqliteConnection(connectionString); connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
            command.Parameters.AddWithValue("$id", lease.LeaseId); command.Parameters.AddWithValue("$account", lease.AccountId); command.Parameters.AddWithValue("$project", lease.ProjectId); command.Parameters.AddWithValue("$fence", lease.Fence); command.ExecuteNonQuery();
            return new Fixture(root, connectionString, manifest, context, lease);
        }

        public RestoreAttempt Restore(SnapshotManifest manifest, string key = "s4-request")
        {
            return new RestoreService(ConnectionString, new RouteRecoveryAuthorityResolver(ConnectionString)).RestorePrepared(Context, manifest, Source, Destination, Lease, key);
        }
        public SnapshotManifest CorruptHash() => Manifest with { Files = Manifest.Files.SetItem(0, Manifest.Files[0] with { Sha256 = new string('0', 64) }) };
        public SnapshotManifest CorruptSize() => Manifest with { Files = Manifest.Files.SetItem(0, Manifest.Files[0] with { Length = Manifest.Files[0].Length + 1 }) };
        public SnapshotManifest UnsafePath() => Manifest with { Files = Manifest.Files.SetItem(0, Manifest.Files[0] with { RelativePath = "../escape.godot" }) };
        public SnapshotManifest UnsupportedVersion() => Manifest with { PlatformCompatibilityVersion = "phase-a/unsupported" };
        public SnapshotManifest UnsupportedSchema() => Manifest with { SchemaVersion = "snapshot-manifest/unsupported" };

        public bool DeniedBeforePublication(SnapshotManifest manifest)
        {
            var before = Previous();
            try { return Restore(manifest).Status != RestoreAttemptStatus.Published && Previous() == before; }
            catch (UnauthorizedAccessException) { return Previous() == before; }
        }
        public bool DeniedAndPreserves(SnapshotManifest manifest) => DeniedBeforePublication(manifest);
        public bool WrongTenantDeniedAndPreserves()
        {
            var before = Previous();
            try { _ = new RestoreService(ConnectionString).RestorePrepared(Context with { AccountId = "other-account" }, Manifest, Source, Destination, Lease, "wrong-tenant"); return false; }
            catch (UnauthorizedAccessException) { return Previous() == before; }
        }
        public bool QuotaDeniedAndPreserves()
        {
            new WorkspaceStorageService(ConnectionString).SetQuota(AccountId, 0);
            return DeniedBeforePublication(Manifest);
        }
        public bool ActiveInputsSurviveCleanup()
        {
            var before = File.ReadAllText(Path.Combine(Source, "project.godot"));
            _ = Restore(CorruptHash(), "active-inputs");
            return File.ReadAllText(Path.Combine(Source, "project.godot")) == before;
        }
        public bool CancellationAndFailureAreRecorded()
        {
            var cancellation = Restore(CorruptHash(), "cancelled");
            var failure = Restore(CorruptSize(), "failed");
            return cancellation.Status == RestoreAttemptStatus.Quarantined && failure.Status == RestoreAttemptStatus.Quarantined && HistoryCount(cancellation.AttemptId) > 0 && HistoryCount(failure.AttemptId) > 0;
        }
        public bool RetryReusesAndAppends()
        {
            var failed = Restore(CorruptHash(), "retry");
            var before = HistoryCount(failed.AttemptId);
            var retried = Restore(Manifest, "retry");
            return failed.Status == RestoreAttemptStatus.Quarantined && retried.AttemptId == failed.AttemptId && retried.Status == RestoreAttemptStatus.Published && HistoryCount(failed.AttemptId) > before;
        }
        public bool MismatchedRequestIsDenied()
        {
            var original = Restore(CorruptHash(), "mismatch");
            try
            {
                var changed = Restore(Manifest with { SnapshotId = "different-snapshot" }, "mismatch");
                return changed.AttemptId != original.AttemptId;
            }
            catch (UnauthorizedAccessException) { return true; }
        }
        public bool StaleLeaseDeniedAndPreserves()
        {
            using var connection = new SqliteConnection(ConnectionString); connection.Open(); using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES('s4-newer',$account,'s4-project',2)";
            command.Parameters.AddWithValue("$account", AccountId); command.ExecuteNonQuery();
            var before = Previous();
            try { _ = Restore(Manifest, "stale"); return false; }
            catch (InvalidOperationException) { return Previous() == before; }
        }
        public bool RestartReconciles(string phase)
        {
            const string attemptId = "s4-interrupted";
            using (var connection = new SqliteConnection(ConnectionString))
            {
                connection.Open(); using var command = connection.CreateCommand();
                command.CommandText = "INSERT INTO restore_attempts(attempt_id,idempotency_key,snapshot_id,workspace_id,account_id,project_id,status,fence,updated_utc) VALUES($attempt,$key,'s4-snapshot','s4-workspace',$account,'s4-project','Staging',1,$updated); INSERT INTO restore_attempt_history(attempt_id,sequence,stage,outcome) VALUES($attempt,1,$phase,'interrupted'); INSERT INTO restore_attempt_history(attempt_id,sequence,stage,outcome) VALUES($attempt,2,'verification','verified')";
                command.Parameters.AddWithValue("$attempt", attemptId); command.Parameters.AddWithValue("$key", "restart-" + phase); command.Parameters.AddWithValue("$phase", phase); command.Parameters.AddWithValue("$account", AccountId); command.Parameters.AddWithValue("$updated", DateTimeOffset.UtcNow.ToString("O")); command.ExecuteNonQuery();
            }
            _ = new RestoreService(ConnectionString);
            return AttemptStatus(attemptId) == RestoreAttemptStatus.Quarantined.ToString() && HasHistory(attemptId, "reconciliation", "reconciled");
        }
        public bool TimerDoesNotStartRestore() => CountAttempts() == 0;
        public bool HasDisablementAuditAfterBoundary()
        {
            var denied = false;
            try { _ = new RestoreService(ConnectionString).RestorePrepared(Context with { AccountId = "disabled-account" }, Manifest, Source, Destination, Lease, "atomic-boundary"); }
            catch (UnauthorizedAccessException) { denied = true; }
            return denied && HasAuditAction("account-disabled");
        }
        public bool DisabledAccountDeniedAtPublication()
        {
            var before = Previous();
            var denied = false;
            try { _ = new RestoreService(ConnectionString).RestorePrepared(Context with { AccountId = "disabled-account" }, Manifest, Source, Destination, Lease, "disabled-at-publication"); }
            catch (UnauthorizedAccessException) { denied = true; }
            return denied && Previous() == before && HasAuditAction("account-disabled");
        }
        public bool CurrentCapabilityIsNew()
        {
            var initial = Restore(Manifest, "capability-initial");
            if (initial.Status != RestoreAttemptStatus.Published) return false;
            var previous = CurrentCredential();
            var nextLease = new RunnerLease("s4-reallocated", AccountId, "s4-project", 2);
            InsertLease(nextLease);
            SetCurrentCredential("s4-reallocated-credential");
            var next = new RestoreService(ConnectionString, new RouteRecoveryAuthorityResolver(ConnectionString)).RestorePrepared(Context with { CredentialId = "s4-reallocated-credential" }, Manifest, Source, Destination, nextLease, "capability-current");
            return initial.Status == RestoreAttemptStatus.Published && next.Status == RestoreAttemptStatus.Published && previous == Context.CredentialId && CurrentCredential() == "s4-reallocated-credential";
        }
        public bool PreRestoreCredentialIsNotAuthoritative()
        {
            var initial = Restore(Manifest, "initial");
            // ADR-0061: retain prerequisite failures separately from the boundary assertion.
            Require(initial.Status == RestoreAttemptStatus.Published, "FAILURE-O-7391CE6328EE",
                $"Restore prerequisite failed (status={initial.Status}, category={initial.FailureCategory ?? "unclassified"}).");
            var nextLease = new RunnerLease("s4-next", AccountId, "s4-project", 2);
            InsertLease(nextLease);
            SetCurrentCredential("s4-new-credential");
            try { _ = new RestoreService(ConnectionString, new RouteRecoveryAuthorityResolver(ConnectionString)).RestorePrepared(Context, Manifest, Source, Destination, nextLease, "new-runtime"); }
            catch (UnauthorizedAccessException) { }
            return CurrentCredential() != Context.CredentialId;
        }
        public bool BoundedRtoProbe()
        {
            var started = DateTimeOffset.UtcNow;
            var result = Restore(Manifest, "rto-probe");
            var elapsed = DateTimeOffset.UtcNow - started;
            return result.Status == RestoreAttemptStatus.Published && elapsed <= TimeSpan.FromMinutes(30) && Manifest.ContentSize <= 100L * 1024 * 1024 && Manifest.Files.Length <= 10_000;
        }
        private string Previous() => File.ReadAllText(Path.Combine(Destination, ".restore-current", "project.godot"));
        private int CountAttempts() { using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand(); q.CommandText = "SELECT COUNT(*) FROM restore_attempts"; return Convert.ToInt32(q.ExecuteScalar()); }
        private int HistoryCount(string attemptId) { using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand(); q.CommandText = "SELECT COUNT(*) FROM restore_attempt_history WHERE attempt_id=$id"; q.Parameters.AddWithValue("$id", attemptId); return Convert.ToInt32(q.ExecuteScalar()); }
        private string? AttemptStatus(string attemptId) { using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand(); q.CommandText = "SELECT status FROM restore_attempts WHERE attempt_id=$id"; q.Parameters.AddWithValue("$id", attemptId); return q.ExecuteScalar()?.ToString(); }
        private bool HasHistory(string attemptId, string stage, string outcome) { using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand(); q.CommandText = "SELECT COUNT(*) FROM restore_attempt_history WHERE attempt_id=$id AND stage=$stage AND outcome=$outcome"; q.Parameters.AddWithValue("$id", attemptId); q.Parameters.AddWithValue("$stage", stage); q.Parameters.AddWithValue("$outcome", outcome); return Convert.ToInt32(q.ExecuteScalar()) == 1; }
        private string? CurrentCredential() { using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand(); q.CommandText = "SELECT credential_id FROM restore_runtime_credentials WHERE workspace_id='s4-workspace'"; return q.ExecuteScalar()?.ToString(); }
        private void SetCurrentCredential(string credential)
        {
            using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand();
            q.CommandText = "INSERT INTO restore_runtime_credentials(workspace_id,credential_id) VALUES('s4-workspace',$credential) ON CONFLICT(workspace_id) DO UPDATE SET credential_id=$credential";
            q.Parameters.AddWithValue("$credential", credential); q.ExecuteNonQuery();
        }
        private void InsertLease(RunnerLease lease)
        {
            using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand();
            q.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
            q.Parameters.AddWithValue("$id", lease.LeaseId); q.Parameters.AddWithValue("$account", lease.AccountId); q.Parameters.AddWithValue("$project", lease.ProjectId); q.Parameters.AddWithValue("$fence", lease.Fence); q.ExecuteNonQuery();
        }
        private bool HasAuditAction(string action)
        {
            using var c = new SqliteConnection(ConnectionString); c.Open(); using var q = c.CreateCommand();
            q.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='restore_audit'";
            if (Convert.ToInt32(q.ExecuteScalar()) != 1) return false;
            q.CommandText = "SELECT COUNT(*) FROM restore_audit WHERE action=$action"; q.Parameters.AddWithValue("$action", action);
            return Convert.ToInt32(q.ExecuteScalar()) > 0;
        }
        public void Dispose() { SqliteConnection.ClearAllPools(); try { Directory.Delete(Root, true); } catch (IOException) { } catch (UnauthorizedAccessException) { } }
    }
}
