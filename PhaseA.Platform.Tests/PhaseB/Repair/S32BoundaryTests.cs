using System.Diagnostics;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S32BoundaryTests
{
    private const long MaximumFixtureSizeBytes = 100L * 1024 * 1024;
    private readonly ITestOutputHelper _output;

    public S32BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_24C61509CBFA()
    {
        using var fixture = SubstituteRootDrillFixture.Create();
        var sample = await fixture.ExecuteAsync();

        Require(
            sample.HasDocumentedTimingSample &&
            sample.RestoreAttempt.Status == RestoreAttemptStatus.Published &&
            sample.RestoredContentValidated &&
            sample.RestoredRouteValidated &&
            sample.CleanupValidated,
            "FAILURE-O-24C61509CBFA",
            "The substitute-root drill did not record a timing sample tied to a successful restored-content, route, and cleanup validation.");
        Observe(nameof(O_24C61509CBFA), sample);
    }

    [Fact]
    public async Task O_3180CF499B2D()
    {
        using var fixture = SubstituteRootDrillFixture.Create();
        var sample = await fixture.ExecuteAsync();

        Require(
            sample.FixtureSizeBytes > 0 &&
            sample.FixtureSizeBytes <= MaximumFixtureSizeBytes &&
            sample.RestoreAttempt.Status == RestoreAttemptStatus.Published &&
            sample.RestoredContentValidated,
            "FAILURE-O-3180CF499B2D",
            "The representative substitute-root fixture was empty, exceeded 100 MiB, or was not the fixture restored by the drill.");
        Observe(nameof(O_3180CF499B2D), sample);
    }

    [Fact]
    public async Task O_51B1E0927330()
    {
        using var fixture = SubstituteRootDrillFixture.Create();
        var sample = await fixture.ExecuteAsync();

        Require(
            sample.RestoreAttempt.Status == RestoreAttemptStatus.Published &&
            sample.RestoredContentValidated &&
            sample.RestoredRouteValidated,
            "FAILURE-O-51B1E0927330",
            "The substitute-root drill did not successfully validate the controlled route from the restored Workspace.");
        Observe(nameof(O_51B1E0927330), sample);
    }

    [Fact]
    public async Task O_54814D965C36()
    {
        using var fixture = SubstituteRootDrillFixture.Create();
        var sample = await fixture.ExecuteAsync();

        Require(
            sample.RestoreAttempt.Status == RestoreAttemptStatus.Published &&
            sample.RestoredRouteValidated &&
            sample.CleanupValidated,
            "FAILURE-O-54814D965C36",
            "The substitute-root drill did not validate cleanup after the recovered Workspace completed its controlled Run.");
        Observe(nameof(O_54814D965C36), sample);
    }

    [Fact]
    public async Task O_9F7DA3182063()
    {
        using var fixture = SubstituteRootDrillFixture.Create();
        var sample = await fixture.ExecuteAsync();

        Require(
            sample.RestoreAttempt.Status == RestoreAttemptStatus.Published && sample.RestoredContentValidated,
            "FAILURE-O-9F7DA3182063",
            "The substitute-root drill did not validate that the restored Workspace content matches its representative fixture.");
        Observe(nameof(O_9F7DA3182063), sample);
    }

    [Fact]
    public async Task O_A1983E093799()
    {
        using var fixture = SubstituteRootDrillFixture.Create();
        var sample = await fixture.ExecuteAsync();

        Require(
            sample.OperatorApprovalDuration > TimeSpan.Zero &&
            sample.RestoreToControlledRunDuration == sample.ElapsedDuration - sample.OperatorApprovalDuration &&
            sample.RestoreToControlledRunDuration >= TimeSpan.Zero &&
            sample.RestoredRouteValidated,
            "FAILURE-O-A1983E093799",
            "The substitute-root drill included operator approval time in its restore-to-controlled-run timing sample.");
        Observe(nameof(O_A1983E093799), sample);
    }

    private void Observe(string obligation, DrillSample sample)
    {
        _output.WriteLine(
            $"S32-OBSERVATION {obligation};fixture={sample.FixtureId};sample={sample.SampleId};" +
            $"fixtureSizeBytes={sample.FixtureSizeBytes};restoreStatus={sample.RestoreAttempt.Status};" +
            $"contentValidated={sample.RestoredContentValidated.ToString().ToLowerInvariant()};" +
            $"routeValidated={sample.RestoredRouteValidated.ToString().ToLowerInvariant()};" +
            $"cleanupValidated={sample.CleanupValidated.ToString().ToLowerInvariant()};" +
            $"timingSampleRecorded={sample.HasDocumentedTimingSample.ToString().ToLowerInvariant()};" +
            $"approvalTicks={sample.OperatorApprovalDuration.Ticks};wallTicks={sample.ElapsedDuration.Ticks};" +
            $"measuredTicks={sample.RestoreToControlledRunDuration.Ticks}");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class SubstituteRootDrillFixture : IDisposable
    {
        private const string ProjectId = "s32-project";
        private const string WorkspaceId = "s32-workspace";
        private static readonly byte[] RepresentativeContent = "S32_RESTORED_WORKSPACE_ROUTE\n"u8.ToArray();
        private readonly string _root;
        private readonly string _sourceRoot;
        private readonly string _substituteRoot;
        private readonly string _connectionString;
        private readonly SnapshotManifest _manifest;
        private readonly RequestContext _context;
        private readonly RunnerLease _lease;
        private readonly TestRunnerCredentialScope _runnerScope;

        private SubstituteRootDrillFixture(
            string root,
            string sourceRoot,
            string substituteRoot,
            string connectionString,
            SnapshotManifest manifest,
            RequestContext context,
            RunnerLease lease,
            TestRunnerCredentialScope runnerScope)
        {
            _root = root;
            _sourceRoot = sourceRoot;
            _substituteRoot = substituteRoot;
            _connectionString = connectionString;
            _manifest = manifest;
            _context = context;
            _lease = lease;
            _runnerScope = runnerScope;
        }

        public static SubstituteRootDrillFixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s32-substitute-root-").FullName;
            var sourceRoot = Directory.CreateDirectory(Path.Combine(root, "representative-fixture")).FullName;
            var substituteRoot = Directory.CreateDirectory(Path.Combine(root, "substitute-root")).FullName;
            var sourceFile = Path.Combine(sourceRoot, "project.godot");
            File.WriteAllBytes(sourceFile, RepresentativeContent);
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root, "metadata.sqlite3"),
                Pooling = false
            }.ToString();
            // ADR-0061: the substitute-root drill uses production account and project metadata.
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            _ = new RestoreService(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = store.CreateUserAccountAsync($"s32-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            _ = store.CreateProjectAsync(new ProjectCreationCommand(
                ProjectId, account.AccountId, "S32 boundary", "S32 boundary", "manual", "default", false, [],
                projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
            RouteAuthorityFixture.Seed(connectionString, account.AccountId, ProjectId, projectRoot.FullName);
            var manifest = SnapshotManifest.Create(
                "snapshot-s32",
                WorkspaceId,
                account.AccountId,
                ProjectId,
                "policy-s32",
                [("project.godot", RepresentativeContent)]);
            manifest = manifest with
            {
                ProtectedContent = SnapshotManifest.ProtectContent(
                    [("project.godot", RepresentativeContent)],
                    manifest.KeyReference)
            };
            var context = RequestContext.FromIdentity(
                new AccountIdentity(account.AccountId, "owner", PhaseAAuth.UserRole),
                "s32-requester",
                "s32-credential",
                "s32-correlation");
            var lease = new RunnerLease("s32-lease", account.AccountId, ProjectId, 1);
            InsertLease(connectionString, lease);
            var runnerScope = TestRunnerCredentialScope.Create(account.AccountId, ProjectId);
            return new SubstituteRootDrillFixture(root, sourceRoot, substituteRoot, connectionString, manifest, context, lease, runnerScope);
        }

        public async Task<DrillSample> ExecuteAsync()
        {
            var fixtureId = $"s32-fixture-{Guid.NewGuid():N}";
            var sampleId = $"s32-sample-{Guid.NewGuid():N}";
            var fixtureSizeBytes = Directory.EnumerateFiles(_sourceRoot, "*", SearchOption.AllDirectories)
                .Sum(path => new FileInfo(path).Length);
            var stopwatch = Stopwatch.StartNew();
            var startedUtc = DateTimeOffset.UtcNow;
            var restore = new RestoreService(
                _connectionString,
                new RouteRecoveryAuthorityResolver(_connectionString)).RestorePrepared(
                _context,
                _manifest,
                _sourceRoot,
                _substituteRoot,
                _lease,
                sampleId,
                _runnerScope.Describe(_manifest.AccountId, _manifest.ProjectId, _substituteRoot));
            var restoredWorkspaceRoot = Path.Combine(_substituteRoot, ".restore-current");
            var restoredContentPath = Path.Combine(restoredWorkspaceRoot, "project.godot");
            var restoredContentValidated = restore.Status == RestoreAttemptStatus.Published &&
                                           File.Exists(restoredContentPath) &&
                                           File.ReadAllBytes(restoredContentPath).SequenceEqual(RepresentativeContent) &&
                                           File.ReadAllBytes(Path.Combine(_sourceRoot, "project.godot")).SequenceEqual(RepresentativeContent) &&
                                           fixtureSizeBytes == _manifest.ContentSize;

            var approvalStarted = stopwatch.Elapsed;
            await Task.Delay(TimeSpan.FromMilliseconds(25));
            var operatorApprovalDuration = stopwatch.Elapsed - approvalStarted;

            var controlledRun = await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                "powershell.exe",
                [
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    $"$content = Get-Content -Raw -LiteralPath '{EscapePowerShell(restoredContentPath)}'; " +
                    "if ($content -notmatch 'S32_RESTORED_WORKSPACE_ROUTE') { exit 1 }; " +
                    "Write-Output 'S32_CONTROLLED_ROUTE_OK'"
                ],
                restoredWorkspaceRoot,
                new Dictionary<string, string>()));
            var restoredRouteValidated = restore.Status == RestoreAttemptStatus.Published &&
                                         Directory.Exists(restoredWorkspaceRoot) &&
                                         controlledRun.ExitCode == 0 &&
                                         controlledRun.Stdout.Contains("S32_CONTROLLED_ROUTE_OK", StringComparison.Ordinal);
            var elapsedDuration = stopwatch.Elapsed;
            var completedUtc = DateTimeOffset.UtcNow;
            var restoreToControlledRunDuration = elapsedDuration - operatorApprovalDuration;

            Directory.Delete(_substituteRoot, recursive: true);
            var cleanupValidated = !Directory.Exists(_substituteRoot) && !File.Exists(restoredContentPath);
            return new DrillSample(
                fixtureId,
                sampleId,
                fixtureSizeBytes,
                restore,
                restoredContentValidated,
                restoredRouteValidated,
                cleanupValidated,
                startedUtc,
                completedUtc,
                operatorApprovalDuration,
                elapsedDuration,
                restoreToControlledRunDuration);
        }

        public void Dispose()
        {
            _runnerScope.Dispose();
            SqliteConnection.ClearAllPools();
            try
            {
                if (Directory.Exists(_root))
                {
                    Directory.Delete(_root, recursive: true);
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        private static void InsertLease(string connectionString, RunnerLease lease)
        {
            using var connection = new SqliteConnection(connectionString);
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
            command.Parameters.AddWithValue("$id", lease.LeaseId);
            command.Parameters.AddWithValue("$account", lease.AccountId);
            command.Parameters.AddWithValue("$project", lease.ProjectId);
            command.Parameters.AddWithValue("$fence", lease.Fence);
            command.ExecuteNonQuery();
        }

        private static string EscapePowerShell(string path) => path.Replace("'", "''", StringComparison.Ordinal);
    }

    private sealed record DrillSample(
        string FixtureId,
        string SampleId,
        long FixtureSizeBytes,
        RestoreAttempt RestoreAttempt,
        bool RestoredContentValidated,
        bool RestoredRouteValidated,
        bool CleanupValidated,
        DateTimeOffset StartedUtc,
        DateTimeOffset CompletedUtc,
        TimeSpan OperatorApprovalDuration,
        TimeSpan ElapsedDuration,
        TimeSpan RestoreToControlledRunDuration)
    {
        public bool HasDocumentedTimingSample =>
            StartedUtc < CompletedUtc &&
            OperatorApprovalDuration > TimeSpan.Zero &&
            RestoreToControlledRunDuration == ElapsedDuration - OperatorApprovalDuration;
    }
}
