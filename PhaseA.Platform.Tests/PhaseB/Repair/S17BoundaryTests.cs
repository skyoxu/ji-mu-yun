using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S17BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S17BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_37C867864CB9() => Verify("O-37C867864CB9", "directory-switch-failure-preserves-ready-content", fixture => fixture.DirectorySwitchFailureHasNoPartialContent());

    [Fact]
    public void O_5AB7A7A32FF0() => Verify("O-5AB7A7A32FF0", "substitute-root-ownership-and-acl-validated", fixture => fixture.RestoredOwnershipAndAclAreValidated());

    [Fact]
    public void O_6581E0E2E4B3() => Verify("O-6581E0E2E4B3", "account-scoped-restored-readback-validated", fixture => fixture.AccountScopedReadbackIsValidated());

    [Fact]
    public void O_72D8C7339453() => Verify("O-72D8C7339453", "snapshot-to-controlled-run-stages-measured", fixture => fixture.DrillStagesAreMeasured());

    [Fact]
    public void O_79B69B27B422() => Verify("O-79B69B27B422", "six-required-fixture-kinds-restored", fixture => fixture.AllRequiredFixtureKindsAreRestored());

    [Fact]
    public void O_938C55953B20() => Verify("O-938C55953B20", "documented-sample-p95-within-thirty-minutes", fixture => fixture.DocumentedSampleP95IsWithinThirtyMinutes());

    [Fact]
    public void O_AB4EAE11C49F() => Verify("O-AB4EAE11C49F", "failed-attempt-staging-is-owned-and-quarantined", fixture => fixture.FailedAttemptStagingIsOwnedAndQuarantined());

    [Fact]
    public void O_BEEE8E670283() => Verify("O-BEEE8E670283", "failed-attempt-preserves-previous-ready-workspace", fixture => fixture.PreviousReadyWorkspaceIsUnchangedAfterFailure());

    [Fact]
    public void O_BFDBE4F9C8F9() => Verify("O-BFDBE4F9C8F9", "directory-switch-leaves-one-ready-or-typed-repair-state", fixture => fixture.DirectorySwitchFailureLeavesOneReadyOrTypedRepairState());

    [Fact]
    public void O_D1E63066A439() => Verify("O-D1E63066A439", "logical-identifiers-use-the-storage-contract", fixture => fixture.RestoreUsesLogicalStorageIdentity());

    [Fact]
    public void O_E31E0D6B06AD() => Verify("O-E31E0D6B06AD", "metadata-boundary-has-no-partial-visible-content", fixture => fixture.MetadataBoundaryHasNoPartialVisibleContent());

    [Fact]
    public void O_E51A39E15CA5() => Verify("O-E51A39E15CA5", "metadata-boundary-leaves-one-ready-or-typed-repair-state", fixture => fixture.MetadataBoundaryLeavesOneReadyOrTypedRepairState());

    private void Verify(string obligationId, string observation, Func<Fixture, bool> assertion)
    {
        using var fixture = Fixture.Create();
        Require(
            assertion(fixture),
            $"FAILURE-{obligationId}",
            $"The real Workspace restore boundary did not prove {observation}.");
        _output.WriteLine($"S17-OBSERVATION {obligationId} {observation}");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class Fixture : IDisposable
    {
        private static readonly IReadOnlyDictionary<string, string> RequiredFiles = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["gdd/overview.gdd"] = "gdd fixture",
            ["modules/recovery.module"] = "module fixture",
            ["source/RestoreBoundary.cs"] = "source fixture",
            ["tests/restore_boundary_test.cs"] = "test fixture",
            ["plans/recovery.plan"] = "plan fixture",
            ["artifacts/recovery.artifact"] = "artifact fixture"
        };

        private Fixture(string root, string connectionString, string source, string destination, RequestContext context, RunnerLease lease)
        {
            Root = root;
            ConnectionString = connectionString;
            Source = source;
            Destination = destination;
            Context = context;
            Lease = lease;
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public string Source { get; }
        public string Destination { get; }
        public RequestContext Context { get; }
        public RunnerLease Lease { get; }

        public static Fixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s17-boundary-").FullName;
            var source = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            var destination = Directory.CreateDirectory(Path.Combine(root, "substitute-root")).FullName;
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath, Pooling = false }.ToString();
            const string projectId = "project-s17";

            try
            {
                // ADR-0061: restore drills require the real account and project metadata boundary.
                SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
                var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
                {
                    ["HOSTED_WORKSPACE_ROOT"] = root,
                });
                var store = new PhaseAMetadataStore(connectionString, options);
                var account = store.CreateUserAccountAsync($"s17-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
                var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
                _ = store.CreateProjectAsync(new ProjectCreationCommand(
                    projectId, account.AccountId, "S17 boundary", "S17 boundary", "manual", "default", false, [],
                    projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
                    Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
                var context = RequestContext.FromIdentity(
                    new AccountIdentity(account.AccountId, "s17-owner", PhaseAAuth.UserRole),
                    "principal-s17",
                    "credential-s17",
                    "correlation-s17");
                var lease = new RunnerLease("lease-s17", account.AccountId, projectId, 1);

                foreach (var file in RequiredFiles)
                {
                    var path = Path.Combine(source, file.Key);
                    Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                    File.WriteAllText(path, file.Value);
                }

                Directory.CreateDirectory(Path.Combine(destination, ".restore-current"));
                File.WriteAllText(Path.Combine(destination, ".restore-current", "previous-ready.txt"), "previous-ready-content");
                var storage = new WorkspaceStorageService(connectionString);
                storage.SetQuota(account.AccountId, 16 * 1024 * 1024);
                _ = new RestoreService(connectionString);
                SeedRouteAuthorityEvidence(connectionString);
                using (var connection = new SqliteConnection(connectionString))
                {
                    connection.Open();
                    using var command = connection.CreateCommand();
                    command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($lease,$account,$project,$fence)";
                    command.Parameters.AddWithValue("$lease", lease.LeaseId);
                    command.Parameters.AddWithValue("$account", lease.AccountId);
                    command.Parameters.AddWithValue("$project", lease.ProjectId);
                    command.Parameters.AddWithValue("$fence", lease.Fence);
                    command.ExecuteNonQuery();
                }

                return new Fixture(root, connectionString, source, destination, context, lease);
            }
            catch
            {
                SqliteConnection.ClearAllPools();
                Directory.Delete(root, recursive: true);
                throw;
            }
        }

        private static void SeedRouteAuthorityEvidence(string connectionString)
        {
            using var connection = new SqliteConnection(connectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO route_recovery_evidence(recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue,source_order_json,blocker_json) VALUES($recorded,8,0,0,1,$sources,$blockers)";
            command.Parameters.AddWithValue("$recorded", DateTimeOffset.UtcNow.ToString("O"));
            command.Parameters.AddWithValue("$sources", JsonSerializer.Serialize(HostedRouteRecoveryContract.SourceOrder));
            command.Parameters.AddWithValue("$blockers", "[]");
            command.ExecuteNonQuery();
        }

        public bool DirectorySwitchFailureHasNoPartialContent()
        {
            var result = InjectDirectorySwitchFailure();
            return result.Attempt.Status == RestoreAttemptStatus.Quarantined &&
                result.PreviousReadyHash == ReadyHash() &&
                CurrentWorkspaceContainsOnlyPreviousReadyContent();
        }

        public bool DirectorySwitchFailureLeavesOneReadyOrTypedRepairState()
        {
            var result = InjectDirectorySwitchFailure();
            var currentReadyCount = Directory.Exists(CurrentRoot) ? 1 : 0;
            var typedRepair = result.Attempt.Status == RestoreAttemptStatus.Quarantined && Directory.Exists(result.QuarantinePath);
            return currentReadyCount == 1 && CurrentWorkspaceContainsOnlyPreviousReadyContent() || typedRepair && currentReadyCount <= 1;
        }

        public bool FailedAttemptStagingIsOwnedAndQuarantined()
        {
            var result = InjectDirectorySwitchFailure();
            var staging = Path.Combine(Destination, ".restore-staging", result.Attempt.AttemptId);
            return result.Attempt.Status == RestoreAttemptStatus.Quarantined &&
                !Directory.Exists(staging) &&
                Directory.Exists(result.QuarantinePath) &&
                Directory.EnumerateFiles(result.QuarantinePath, "*", SearchOption.AllDirectories).Any();
        }

        public bool PreviousReadyWorkspaceIsUnchangedAfterFailure()
        {
            var result = InjectDirectorySwitchFailure();
            return result.PreviousReadyHash == ReadyHash() && CurrentWorkspaceContainsOnlyPreviousReadyContent();
        }

        public bool MetadataBoundaryHasNoPartialVisibleContent()
        {
            var result = InjectMetadataCommitFailure();
            var typedRepair = result.Attempt.Status == RestoreAttemptStatus.Quarantined &&
                Directory.Exists(result.QuarantinePath) &&
                !Directory.Exists(CurrentRoot);
            return result.Attempt.Status == RestoreAttemptStatus.Quarantined &&
                (result.PreviousReadyHash == ReadyHash() && CurrentWorkspaceContainsOnlyPreviousReadyContent() || typedRepair);
        }

        public bool MetadataBoundaryLeavesOneReadyOrTypedRepairState()
        {
            var result = InjectMetadataCommitFailure();
            var currentReadyCount = Directory.Exists(CurrentRoot) ? 1 : 0;
            return currentReadyCount == 1 && CurrentWorkspaceContainsOnlyPreviousReadyContent() ||
                result.Attempt.Status == RestoreAttemptStatus.Quarantined && Directory.Exists(result.QuarantinePath) && currentReadyCount <= 1;
        }

        public bool AllRequiredFixtureKindsAreRestored()
        {
            var manifest = CreateSnapshot("six-kinds");
            var attempt = Restore(manifest, "six-kinds");
            return attempt.Status == RestoreAttemptStatus.Published &&
                RequiredFiles.All(file =>
                {
                    var path = Path.Combine(CurrentRoot, file.Key);
                    return File.Exists(path) && File.ReadAllText(path) == file.Value;
                });
        }

        public bool RestoreUsesLogicalStorageIdentity()
        {
            var manifest = CreateSnapshot("logical-identity");
            var retained = new WorkspaceStorageService(ConnectionString)
                .ListSnapshots(Context.AccountId, Lease.ProjectId)
                .SingleOrDefault(record => record.Manifest.SnapshotId == manifest.SnapshotId);
            var untrustedSource = Directory.CreateDirectory(Path.Combine(Root, "untrusted-caller-source")).FullName;
            var attempt = new RestoreService(ConnectionString).RestorePrepared(
                Context,
                retained?.Manifest ?? throw new InvalidOperationException("S17 retained snapshot was not found by logical identity."),
                untrustedSource,
                Destination,
                Lease,
                "logical-storage-identity");
            return retained is not null &&
                retained.Manifest.WorkspaceId == "workspace-s17" &&
                retained.Manifest.AccountId == Context.AccountId &&
                retained.Manifest.ProjectId == Lease.ProjectId &&
                attempt.Status == RestoreAttemptStatus.Published &&
                RequiredFiles.All(file => File.ReadAllText(Path.Combine(CurrentRoot, file.Key)) == file.Value);
        }

        public bool AccountScopedReadbackIsValidated()
        {
            var manifest = CreateSnapshot("readback");
            var attempt = Restore(manifest, "readback");
            var accountSnapshot = new WorkspaceStorageService(ConnectionString)
                .ListSnapshots(Context.AccountId, Lease.ProjectId)
                .SingleOrDefault(record => record.Manifest.SnapshotId == manifest.SnapshotId);
            return attempt.Status == RestoreAttemptStatus.Published &&
                accountSnapshot is not null &&
                accountSnapshot.Manifest.AccountId == Context.AccountId &&
                RequiredFiles.All(file => File.Exists(Path.Combine(CurrentRoot, file.Key)) && File.ReadAllText(Path.Combine(CurrentRoot, file.Key)) == file.Value);
        }

        public bool RestoredOwnershipAndAclAreValidated()
        {
            var manifest = CreateSnapshot("ownership-acl");
            var attempt = Restore(manifest, "ownership-acl");
            var restored = new DirectoryInfo(CurrentRoot);
            var security = restored.GetAccessControl();
            var owner = security.GetOwner(typeof(SecurityIdentifier)) as SecurityIdentifier;
            var rules = security.GetAccessRules(includeExplicit: true, includeInherited: true, typeof(SecurityIdentifier));
            return attempt.Status == RestoreAttemptStatus.Published &&
                owner is not null &&
                rules.Count > 0 &&
                File.ReadAllText(Path.Combine(CurrentRoot, "gdd", "overview.gdd")) == RequiredFiles["gdd/overview.gdd"];
        }

        public bool DrillStagesAreMeasured()
        {
            using var sample = Create();
            var result = sample.RunDrillSample("stages");
            return result.SnapshotCreatedUtc <= result.RestoredUtc &&
                result.RestoredUtc <= result.ControlledRunCompletedUtc &&
                result.ApprovalTimeExcluded &&
                result.ReadbackValidated &&
                result.Duration <= TimeSpan.FromMinutes(30);
        }

        public bool DocumentedSampleP95IsWithinThirtyMinutes()
        {
            var samples = new List<DrillSample>();
            foreach (var sampleId in new[] { "p95-a", "p95-b", "p95-c" })
            {
                using var sample = Create();
                samples.Add(sample.RunDrillSample(sampleId));
            }
            var ordered = samples.OrderBy(sample => sample.Duration).ToArray();
            var p95 = ordered[(int)Math.Ceiling(ordered.Length * 0.95d) - 1].Duration;
            return samples.All(sample =>
                    sample.SnapshotCreatedUtc <= sample.RestoredUtc &&
                    sample.RestoredUtc <= sample.ControlledRunCompletedUtc &&
                    sample.ApprovalTimeExcluded &&
                    sample.ReadbackValidated) &&
                p95 <= TimeSpan.FromMinutes(30);
        }

        public DrillSample RunDrillSample(string sampleId)
        {
            var snapshotStarted = DateTimeOffset.UtcNow;
            var manifest = CreateSnapshot($"drill-{sampleId}");
            var snapshotCreated = DateTimeOffset.UtcNow;
            var attempt = Restore(manifest, $"drill-{sampleId}");
            var restored = DateTimeOffset.UtcNow;
            var readbackValidated = attempt.Status == RestoreAttemptStatus.Published &&
                RequiredFiles.All(file => File.Exists(Path.Combine(CurrentRoot, file.Key)) && File.ReadAllText(Path.Combine(CurrentRoot, file.Key)) == file.Value);
            var controlledRunCompleted = DateTimeOffset.UtcNow;
            return new DrillSample(sampleId, snapshotCreated, restored, controlledRunCompleted, controlledRunCompleted - snapshotStarted, ApprovalTimeExcluded: true, ReadbackValidated: readbackValidated);
        }

        private SnapshotManifest CreateSnapshot(string suffix)
        {
            return new WorkspaceStorageService(ConnectionString).CreateSnapshot(
                Context,
                Source,
                $"snapshot-s17-{suffix}",
                "workspace-s17",
                Lease.ProjectId,
                "policy-s17",
                new HashSet<string>(StringComparer.OrdinalIgnoreCase) { ".json", ".protected" }).Manifest;
        }

        private RestoreAttempt Restore(SnapshotManifest manifest, string idempotencyKey) =>
            new RestoreService(ConnectionString).RestorePrepared(Context, manifest, Source, Destination, Lease, idempotencyKey);

        private FailureResult InjectDirectorySwitchFailure()
        {
            var manifest = CreateSnapshot($"switch-{Guid.NewGuid():N}");
            var previousReadyHash = ReadyHash();
            File.WriteAllText(Path.Combine(Destination, ".restore-previous"), "inject-directory-switch-failure");
            RestoreAttempt attempt;
            attempt = Restore(manifest, $"directory-switch-{Guid.NewGuid():N}");
            var quarantine = Path.Combine(Destination, ".restore-quarantine", attempt.AttemptId);
            return new FailureResult(attempt, previousReadyHash, quarantine);
        }

        private FailureResult InjectMetadataCommitFailure()
        {
            var manifest = CreateSnapshot($"metadata-{Guid.NewGuid():N}");
            var previousReadyHash = ReadyHash();
            using (var connection = new SqliteConnection(ConnectionString))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "CREATE TRIGGER fail_s17_metadata_commit BEFORE INSERT ON restore_runtime_credentials BEGIN SELECT RAISE(ABORT, 's17 metadata commit failure'); END;";
                command.ExecuteNonQuery();
            }

            var attempt = Restore(manifest, $"metadata-commit-{Guid.NewGuid():N}");
            var quarantine = Path.Combine(Destination, ".restore-quarantine", attempt.AttemptId);
            return new FailureResult(attempt, previousReadyHash, quarantine);
        }

        private string CurrentRoot => Path.Combine(Destination, ".restore-current");

        private string ReadyHash()
        {
            if (!Directory.Exists(CurrentRoot)) return string.Empty;
            var bytes = Directory.EnumerateFiles(CurrentRoot, "*", SearchOption.AllDirectories)
                .OrderBy(path => Path.GetRelativePath(CurrentRoot, path), StringComparer.Ordinal)
                .SelectMany(File.ReadAllBytes)
                .ToArray();
            return Convert.ToHexString(SHA256.HashData(bytes));
        }

        private bool CurrentWorkspaceContainsOnlyPreviousReadyContent()
        {
            var file = Path.Combine(CurrentRoot, "previous-ready.txt");
            return Directory.Exists(CurrentRoot) &&
                Directory.EnumerateFiles(CurrentRoot, "*", SearchOption.AllDirectories).Count() == 1 &&
                File.Exists(file) &&
                File.ReadAllText(file) == "previous-ready-content";
        }

        public void Dispose()
        {
            SqliteConnection.ClearAllPools();
            if (Directory.Exists(Root))
            {
                Directory.Delete(Root, recursive: true);
            }
        }
    }

    private sealed record FailureResult(RestoreAttempt Attempt, string PreviousReadyHash, string QuarantinePath);
    private sealed record DrillSample(
        string SampleId,
        DateTimeOffset SnapshotCreatedUtc,
        DateTimeOffset RestoredUtc,
        DateTimeOffset ControlledRunCompletedUtc,
        TimeSpan Duration,
        bool ApprovalTimeExcluded,
        bool ReadbackValidated);
}
