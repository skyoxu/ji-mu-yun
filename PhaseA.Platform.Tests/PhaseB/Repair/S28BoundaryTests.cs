using System.Diagnostics;
using System.Globalization;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S28BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S28BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_5277C4B77BBF()
    {
        await using var fixture = await S28Fixture.CreateAsync();
        using var oldCancellation = new CancellationTokenSource();

        var oldPidPath = Path.Combine(fixture.Root, "pre-restore.pid");
        var oldRun = fixture.RunAsync(fixture.PreRestoreRoot, oldPidPath, oldCancellation.Token);
        await WaitForFileAsync(oldPidPath);
        var oldPid = int.Parse(await File.ReadAllTextAsync(oldPidPath), CultureInfo.InvariantCulture);

        var restored = fixture.Restore(fixture.OldContext, fixture.OldLease, "s28-pid-restore");
        await fixture.ActivateCurrentLeaseAsync();
        var staleLeaseRejected = false;
        try
        {
            _ = fixture.Restore(fixture.OldContext, fixture.OldLease, "s28-pid-stale-lease");
        }
        catch (InvalidOperationException error) when (error.Message.Contains("not authoritative", StringComparison.OrdinalIgnoreCase))
        {
            staleLeaseRejected = true;
        }

        var currentPidPath = Path.Combine(fixture.Root, "current.pid");
        var releasePath = Path.Combine(fixture.Root, "release-current");
        var currentRun = fixture.RunAsync(fixture.RestoredRoot, currentPidPath, CancellationToken.None, releasePath);
        await WaitForFileAsync(currentPidPath);
        var currentPid = int.Parse(await File.ReadAllTextAsync(currentPidPath), CultureInfo.InvariantCulture);
        var currentProcessWasAlive = IsProcessAlive(currentPid);

        oldCancellation.Cancel();
        await AwaitRunnerAsync(oldRun);
        var oldPidNoLongerIdentifiesProcess = !IsProcessAlive(oldPid);
        var oldPidCannotControlCurrent = oldPid != currentPid && currentProcessWasAlive && !currentRun.IsCompleted;

        await File.WriteAllTextAsync(releasePath, "release");
        var currentResult = await currentRun;

        Require(
            restored.Status == RestoreAttemptStatus.Published &&
            staleLeaseRejected &&
            oldPidNoLongerIdentifiesProcess &&
            oldPidCannotControlCurrent &&
            currentResult.ExitCode == 0,
            "FAILURE-O-5277C4B77BBF",
            $"The pre-restore PID was not non-authoritative after restore. oldPid={oldPid}; currentPid={currentPid}; currentExit={currentResult.ExitCode}.");
        _output.WriteLine($"S28-OBSERVATION old-pid-non-authoritative oldPid={oldPid} currentPid={currentPid}");
    }

    [Fact]
    public async Task O_80DBEB1AFBC6()
    {
        await using var fixture = await S28Fixture.CreateAsync();
        await fixture.ActivateCurrentLeaseAsync();
        var restored = fixture.Restore(fixture.CurrentContext, fixture.CurrentLease, "s28-controlled-run");
        var run = await fixture.RunControlledAsync();

        Require(
            restored.Status == RestoreAttemptStatus.Published &&
            run.ExitCode == 0 &&
            run.Stdout.Contains("S28_SCOPE_ACCOUNT=account-s28", StringComparison.Ordinal) &&
            run.Stdout.Contains("S28_SCOPE_WORKSPACE=workspace-s28", StringComparison.Ordinal),
            "FAILURE-O-80DBEB1AFBC6",
            $"The controlled Run did not prove restored Workspace and Account scope. exit={run.ExitCode}; stdout={run.Stdout}; stderr={run.Stderr}.");
        _output.WriteLine("S28-OBSERVATION controlled-run-restored-workspace-account-scope");
    }

    [Fact]
    public async Task O_DB28C97417D0()
    {
        await using var fixture = await S28Fixture.CreateAsync();
        await fixture.ActivateCurrentLeaseAsync();
        var restored = fixture.Restore(fixture.CurrentContext, fixture.CurrentLease, "s28-credential-restore");
        var oldCredentialRejected = false;
        try
        {
            _ = fixture.Restore(fixture.OldContext, fixture.CurrentLease, "s28-old-credential-attempt");
        }
        catch (UnauthorizedAccessException error) when (error.Message.Contains("credential", StringComparison.OrdinalIgnoreCase))
        {
            oldCredentialRejected = true;
        }

        Require(
            restored.Status == RestoreAttemptStatus.Published &&
            oldCredentialRejected,
            "FAILURE-O-DB28C97417D0",
            "A pre-restore Runner credential remained authoritative after the restored runtime credential was issued.");
        _output.WriteLine("S28-OBSERVATION old-runner-credential-denied-after-restore");
        await Task.CompletedTask;
    }

    private static async Task WaitForFileAsync(string path)
    {
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(10);
        while (!File.Exists(path) && DateTime.UtcNow < deadline)
        {
            await Task.Delay(25);
        }

        if (!File.Exists(path))
        {
            throw new InvalidOperationException($"S28 process fixture did not create PID file: {path}");
        }
    }

    private static async Task AwaitRunnerAsync(Task<HostedProcessResult> run)
    {
        try
        {
            _ = await run;
        }
        catch (OperationCanceledException)
        {
        }
    }

    private static bool IsProcessAlive(int pid)
    {
        try
        {
            using var process = Process.GetProcessById(pid);
            return !process.HasExited;
        }
        catch (ArgumentException)
        {
            return false;
        }
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class S28Fixture : IAsyncDisposable
    {
        private S28Fixture(string root, string connectionString, SnapshotManifest manifest)
        {
            Root = root;
            ConnectionString = connectionString;
            Manifest = manifest;
            PreRestoreRoot = Directory.CreateDirectory(Path.Combine(root, "pre-restore")).FullName;
            RestoredRoot = Directory.CreateDirectory(Path.Combine(root, "restored")).FullName;
            File.WriteAllText(Path.Combine(PreRestoreRoot, "pre-restore.txt"), "pre-restore");
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public string PreRestoreRoot { get; }
        public string RestoredRoot { get; }
        public string RestoredWorkspaceRoot => Path.Combine(RestoredRoot, ".restore-current");
        public SnapshotManifest Manifest { get; }
        public RequestContext OldContext { get; } = RequestContext.FromIdentity(new AccountIdentity("account-s28", "old", PhaseAAuth.UserRole), "principal-old", "credential-old", "s28-old");
        public RequestContext CurrentContext { get; } = RequestContext.FromIdentity(new AccountIdentity("account-s28", "current", PhaseAAuth.UserRole), "principal-current", "credential-current", "s28-current");
        public RunnerLease OldLease { get; } = new("lease-old", "account-s28", "project-s28", 1);
        public RunnerLease CurrentLease { get; } = new("lease-current", "account-s28", "project-s28", 2);

        public static async Task<S28Fixture> CreateAsync()
        {
            var root = Directory.CreateTempSubdirectory("s28-boundary-").FullName;
            var connectionString = new SqliteConnectionStringBuilder
            {
                DataSource = Path.Combine(root, "metadata.sqlite3"),
                Pooling = false
            }.ToString();
            _ = new RestoreService(connectionString);
            var scope = "S28_SCOPE_ACCOUNT=account-s28\nS28_SCOPE_WORKSPACE=workspace-s28\n"u8.ToArray();
            var manifest = SnapshotManifest.Create(
                "snapshot-s28",
                "workspace-s28",
                "account-s28",
                "project-s28",
                "policy-s28",
                [("scope.txt", scope)]);
            manifest = manifest with { ProtectedContent = SnapshotManifest.ProtectContent([("scope.txt", scope)], manifest.KeyReference) };
            var fixture = new S28Fixture(root, connectionString, manifest);
            await fixture.InsertLeaseAsync(fixture.OldLease);
            return fixture;
        }

        public RestoreAttempt Restore(RequestContext context, RunnerLease lease, string idempotencyKey) =>
            new RestoreService(ConnectionString).Restore(context, Manifest, PreRestoreRoot, RestoredRoot, lease, idempotencyKey);

        public Task ActivateCurrentLeaseAsync() => InsertLeaseAsync(CurrentLease);

        public Task<HostedProcessResult> RunAsync(string workingDirectory, string pidPath, CancellationToken cancellationToken, string? releasePath = null)
        {
            var escapedPid = EscapePowerShell(pidPath);
            var script = $"[IO.File]::WriteAllText('{escapedPid}', [string]$PID);" +
                         (releasePath is null
                             ? "while ($true) { Start-Sleep -Milliseconds 100 }"
                             : $"while (-not (Test-Path '{EscapePowerShell(releasePath)}')) {{ Start-Sleep -Milliseconds 100 }}");
            return new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-Command", script],
                workingDirectory,
                new Dictionary<string, string>()), cancellationToken);
        }

        public Task<HostedProcessResult> RunControlledAsync()
        {
            var scopePath = Path.Combine(RestoredWorkspaceRoot, "scope.txt");
            var script = $"Get-Content '{EscapePowerShell(scopePath)}'; Write-Output 'S28_CONTROLLED_RUN_OK'";
            return new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-Command", script],
                RestoredWorkspaceRoot,
                new Dictionary<string, string>()));
        }

        private async Task InsertLeaseAsync(RunnerLease lease)
        {
            await using var connection = new SqliteConnection(ConnectionString);
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
            command.Parameters.AddWithValue("$id", lease.LeaseId);
            command.Parameters.AddWithValue("$account", lease.AccountId);
            command.Parameters.AddWithValue("$project", lease.ProjectId);
            command.Parameters.AddWithValue("$fence", lease.Fence);
            await command.ExecuteNonQueryAsync();
        }

        private static string EscapePowerShell(string path) => path.Replace("'", "''", StringComparison.Ordinal);

        public ValueTask DisposeAsync()
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(Root, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            return ValueTask.CompletedTask;
        }
    }
}
