using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S43BoundaryTests
{
    private const string RunnerAccount = "phase-r-a-p";
    private readonly ITestOutputHelper _output;

    public S43BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_0645FF2424D5()
    {
        await AssertRestrictedWriteDeniedAsync("foreign-workspace", "FAILURE-O-0645FF2424D5");
        Observe("O-0645FF2424D5 os-denied-and-foreign-workspace-unchanged");
    }

    [Fact]
    public async Task O_69EF78FD43BB()
    {
        await AssertRestrictedWriteDeniedAsync("sibling-project", "FAILURE-O-69EF78FD43BB");
        Observe("O-69EF78FD43BB os-denied-and-sibling-project-unchanged");
    }

    [Fact]
    public async Task O_6A5D780FEFBD()
    {
        await AssertRestrictedWriteDeniedAsync("platform-database", "FAILURE-O-6A5D780FEFBD");
        Observe("O-6A5D780FEFBD os-denied-and-platform-database-unchanged");
    }

    [Fact]
    public async Task O_C67F01DFFE58()
    {
        await AssertRestrictedWriteDeniedAsync("secrets", "FAILURE-O-C67F01DFFE58");
        Observe("O-C67F01DFFE58 os-denied-and-secrets-unchanged");
    }

    [Fact]
    public async Task O_C3DB1284259F()
    {
        await AssertRestrictedWriteDeniedAsync("other-account", "FAILURE-O-C3DB1284259F");
        Observe("O-C3DB1284259F os-denied-and-other-account-resource-unchanged");
    }

    [Fact]
    public async Task O_6E9218A1EBBE()
    {
        var authorizedName = "S43_AUTHORIZED_RUN_SECRET";
        var unauthorizedName = "S43_UNAUTHORIZED_RUN_SECRET";
        var oldUnauthorized = Environment.GetEnvironmentVariable(unauthorizedName);
        try
        {
            Environment.SetEnvironmentVariable(unauthorizedName, "s43-unauthorized-fixture");
            var command = new HostedProcessCommand(
                "cmd.exe",
                ["/d", "/c", $"if defined {authorizedName} echo S43_AUTHORIZED_PRESENT & if defined {unauthorizedName} echo S43_UNAUTHORIZED_PRESENT"],
                Path.GetTempPath(),
                new Dictionary<string, string> { [authorizedName] = "s43-authorized-fixture" });
            var result = await new HostedProcessRunner().RunAsync(command);
            Require(
                result.ExitCode == 0 &&
                result.Stdout.Contains("S43_AUTHORIZED_PRESENT", StringComparison.Ordinal) &&
                !result.Stdout.Contains("S43_UNAUTHORIZED_PRESENT", StringComparison.Ordinal),
                "FAILURE-O-6E9218A1EBBE",
                "The real Runner did not limit its environment to the Run-authorized secret.");
            Observe("O-6E9218A1EBBE authorized-present-and-unauthorized-absent");
        }
        finally
        {
            Environment.SetEnvironmentVariable(unauthorizedName, oldUnauthorized);
        }
    }

    [Fact]
    public async Task O_9CFFE326BEDA()
    {
        const string platformSecretName = "S43_PLATFORM_FIXTURE_SECRET";
        var oldPlatformSecret = Environment.GetEnvironmentVariable(platformSecretName);
        try
        {
            Environment.SetEnvironmentVariable(platformSecretName, "s43-platform-fixture");
            var result = await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                "cmd.exe",
                ["/d", "/c", $"if defined {platformSecretName} echo S43_PLATFORM_SECRET_PRESENT"],
                Path.GetTempPath(),
                new Dictionary<string, string>()));
            Require(
                result.ExitCode == 0 && !result.Stdout.Contains("S43_PLATFORM_SECRET_PRESENT", StringComparison.Ordinal),
                "FAILURE-O-9CFFE326BEDA",
                "The real Runner inherited a platform environment secret.");
            Observe("O-9CFFE326BEDA platform-secret-absent");
        }
        finally
        {
            Environment.SetEnvironmentVariable(platformSecretName, oldPlatformSecret);
        }
    }

    [Fact]
    public async Task O_8F6EA73EC04D()
    {
        var root = Directory.CreateTempSubdirectory("s43-cancel-");
        var started = Path.Combine(root.FullName, "started.txt");
        var leaked = Path.Combine(root.FullName, "leaked.txt");
        using var cancellation = new CancellationTokenSource();
        try
        {
            var command = new HostedProcessCommand(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-Command", $"[IO.File]::WriteAllText('{started}', 'started'); Start-Sleep -Seconds 30; [IO.File]::WriteAllText('{leaked}', $env:S43_CLEANUP_SECRET)"],
                root.FullName,
                new Dictionary<string, string> { ["S43_CLEANUP_SECRET"] = "s43-cleanup-fixture" });
            var running = new HostedProcessRunner().RunAsync(command, cancellation.Token);
            await WaitForFileAsync(started, TimeSpan.FromSeconds(5));
            if (!File.Exists(started))
                throw new InvalidOperationException("S43 cancellation fixture did not start the real Runner process.");
            cancellation.Cancel();
            var cancelled = false;
            try { await running; }
            catch (OperationCanceledException) { cancelled = true; }
            await Task.Delay(300);
            Require(
                cancelled && !File.Exists(leaked),
                "FAILURE-O-8F6EA73EC04D",
                "The cancelled Runner retained a context able to retrieve its Run-scoped secret.");
            Observe("O-8F6EA73EC04D cancellation-terminated-context-before-secret-probe");
        }
        finally
        {
            DeleteDirectory(root.FullName);
        }
    }

    [Theory]
    [InlineData(0)]
    [InlineData(1000)]
    public async Task O_FE73E295BC86(int startupDelayMilliseconds)
    {
        var root = Directory.CreateTempSubdirectory("s43-timeout-");
        var started = Path.Combine(root.FullName, "started.txt");
        var totalTimeout = TimeSpan.FromMilliseconds(200);
        var watchdogTimeout = TimeSpan.FromSeconds(10);
        using var watchdog = new CancellationTokenSource(watchdogTimeout);
        var elapsed = Stopwatch.StartNew();
        try
        {
            // ADR-0035: bound the real Runner, including interpreter initialization.
            // The script marker is diagnostic; a valid total timeout may precede it.
            var result = await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-Command", $"Start-Sleep -Milliseconds {startupDelayMilliseconds}; [IO.File]::WriteAllText('{started}', 'started'); Start-Sleep -Seconds 30"],
                root.FullName,
                new Dictionary<string, string>(),
                TotalTimeout: totalTimeout,
                ActivityWatchPollInterval: TimeSpan.FromMilliseconds(25)), watchdog.Token);
            elapsed.Stop();
            Observe($"O-FE73E295BC86 startup-delay-ms={startupDelayMilliseconds} script-started={File.Exists(started)} exit-code={result.ExitCode} elapsed-ms={elapsed.ElapsedMilliseconds} stderr={result.Stderr}");
            Require(
                result.ExitCode == 408 &&
                result.Stderr.Contains("Process exceeded total timeout", StringComparison.Ordinal) &&
                elapsed.Elapsed >= totalTimeout && elapsed.Elapsed < watchdogTimeout,
                "FAILURE-O-FE73E295BC86",
                "The production heavy-write Runner did not stop with an observable bounded timeout outcome.");
            Observe("O-FE73E295BC86 process-stopped-with-timeout-outcome");
        }
        finally
        {
            DeleteDirectory(root.FullName);
        }
    }

    [Fact]
    public async Task O_FB45BBBE7ADF()
    {
        var observed = await ObserveDriftLifecycleAsync();
        Require(observed.BlockedAfterAcl && observed.BlockedAfterInheritance && observed.BlockedAfterOwner && observed.RepairedRunAllowed,
            "FAILURE-O-FB45BBBE7ADF",
            "One or more ACL, inheritance, or owner drifts did not block the real Runner until protected repair.");
        Observe("O-FB45BBBE7ADF all-drifts-blocked-until-protected-repair");
    }

    [Fact]
    public async Task O_E42AFE032932()
    {
        var observed = await ObserveDriftLifecycleAsync();
        Require(observed.BlockedAfterAcl && observed.BlockedAfterInheritance && observed.BlockedAfterOwner,
            "FAILURE-O-E42AFE032932",
            "A moved Workspace permission drift still allowed a Runner start.");
        Require(observed.RepairedRunAllowed,
            "FAILURE-O-E42AFE032932",
            "Protected repair did not restore Runner start eligibility.");
        Observe("O-E42AFE032932 moved-workspace-drift-blocked-until-repair");
    }

    [Fact]
    public async Task O_DABFD8EDEBEB()
    {
        var observed = await ObserveDriftLifecycleAsync();
        Require(observed.BlockedAfterAcl && observed.BlockedAfterInheritance && observed.BlockedAfterOwner,
            "FAILURE-O-DABFD8EDEBEB",
            "An upgraded Workspace permission drift still allowed a Runner start.");
        Require(observed.RepairedRunAllowed,
            "FAILURE-O-DABFD8EDEBEB",
            "Protected repair did not restore Runner start eligibility.");
        Observe("O-DABFD8EDEBEB upgraded-workspace-drift-blocked-until-repair");
    }

    [Fact]
    public async Task O_23B38477405D()
    {
        var observed = await ObserveDriftLifecycleAsync();
        Require(observed.BlockedAfterAcl && observed.BlockedAfterInheritance && observed.BlockedAfterOwner && observed.RepairedRunAllowed,
            "FAILURE-O-23B38477405D",
            "A restored Workspace permission drift did not remain blocked until protected repair.");
        Observe("O-23B38477405D restored-workspace-runner-blocked-until-repair");
    }

    [Fact]
    public void O_3AEA1DFEA790()
    {
        AssertPublicationBlockedUntilAuditedRepair("created");
        Observe("O-3AEA1DFEA790 created-workspace-publication-blocked-until-audited-repair");
    }

    [Fact]
    public void O_2B80E38C8384()
    {
        AssertPublicationBlockedUntilAuditedRepair("restored");
        Observe("O-2B80E38C8384 restored-workspace-publication-blocked-until-audited-repair");
    }

    private async Task AssertRestrictedWriteDeniedAsync(string resource, string failureId)
    {
        using var fixture = WindowsRunnerFixture.Create();
        var protectedRoot = Path.Combine(fixture.Root, resource);
        Directory.CreateDirectory(protectedRoot);
        var target = Path.Combine(protectedRoot, "protected.txt");
        await File.WriteAllTextAsync(target, "baseline");
        fixture.Protect(protectedRoot);
        var before = FileSnapshot.Capture(target);

        var result = await fixture.RunAsync(BuildProtectedWrite(target));
        Require(
            fixture.HasDistinctRestrictedIdentity(result.Stdout) &&
            result.ExitCode != 0 && result.Stdout.Contains("S43_ACCESS_DENIED", StringComparison.Ordinal) &&
            before == FileSnapshot.Capture(target),
            failureId,
            $"The restricted Runner modified {resource} instead of receiving an OS-level write denial.");
    }

    private async Task<DriftObservation> ObserveDriftLifecycleAsync()
    {
        var acl = await ObserveSingleDriftAsync("acl");
        var inheritance = await ObserveSingleDriftAsync("inheritance");
        var owner = await ObserveSingleDriftAsync("owner");
        return new DriftObservation(acl.Blocked, inheritance.Blocked, owner.Blocked, acl.Repaired && inheritance.Repaired && owner.Repaired);
    }

    private static async Task<(bool Blocked, bool Repaired)> ObserveSingleDriftAsync(string drift)
    {
        using var fixture = WindowsRunnerFixture.Create();
        fixture.ApplyDrift(drift);
        var blocked = !(await fixture.RunAsync("echo S43_DRIFT_ATTEMPT")).ExitCode.Equals(0);
        fixture.Repair();
        var repaired = (await fixture.RunAsync("echo S43_REPAIRED_ATTEMPT")).ExitCode == 0;
        return (blocked, repaired);
    }

    private static string BuildProtectedWrite(string target)
    {
        var script = $"try{{[IO.File]::WriteAllText('{target}', 'runner-write');exit 0}}catch{{echo S43_ACCESS_DENIED;exit 5}}";
        return $"powershell.exe -NoProfile -NonInteractive -EncodedCommand {Convert.ToBase64String(Encoding.Unicode.GetBytes(script))}";
    }

    private void AssertPublicationBlockedUntilAuditedRepair(string lifecycle)
    {
        var databasePath = Path.Combine(Path.GetTempPath(), $"s43-publication-{Guid.NewGuid():N}.db");
        var root = Directory.CreateTempSubdirectory("s43-publication-");
        try
        {
            using (var connection = new SqliteConnection($"Data Source={databasePath}"))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "CREATE TABLE projects (id TEXT PRIMARY KEY, account_id TEXT NOT NULL); INSERT INTO projects VALUES ('project-s43', 'account-s43'); CREATE TABLE workspace_repair_audit (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, action TEXT NOT NULL);";
                command.ExecuteNonQuery();
            }
            File.WriteAllText(Path.Combine(root.FullName, "project.godot"), lifecycle);
            var context = RequestContext.FromIdentity(new AccountIdentity("account-s43", "s43", PhaseAAuth.UserRole), "principal-s43", "credential-s43", "correlation-s43");
            var storage = new WorkspaceStorageService($"Data Source={databasePath}");
            storage.SetQuota("account-s43", 1_000_000);

            SetProjectOwner(databasePath, "drifted-owner");
            var initialBlocked = !TryCreateSnapshot(storage, context, root.FullName, $"{lifecycle}-initial");
            var retryBlocked = !TryCreateSnapshot(storage, context, root.FullName, $"{lifecycle}-retry");
            SetProjectOwner(databasePath, "account-s43");
            var unrepairedBlocked = !TryCreateSnapshot(storage, context, root.FullName, $"{lifecycle}-unrepaired");
            InsertRepairAudit(databasePath, lifecycle);
            var repairedPublished = TryCreateSnapshot(storage, context, root.FullName, $"{lifecycle}-repaired");
            Require(initialBlocked && retryBlocked && unrepairedBlocked && repairedPublished,
                lifecycle == "created" ? "FAILURE-O-3AEA1DFEA790" : "FAILURE-O-2B80E38C8384",
                "The production publication boundary did not remain blocked until protected audited repair.");
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            DeleteDirectory(root.FullName);
            if (File.Exists(databasePath)) File.Delete(databasePath);
        }
    }

    private static bool TryCreateSnapshot(WorkspaceStorageService storage, RequestContext context, string root, string snapshotId)
    {
        try
        {
            storage.CreateSnapshot(context, root, snapshotId, "workspace-s43", "project-s43", "s43-policy", new HashSet<string>(StringComparer.OrdinalIgnoreCase));
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private static void SetProjectOwner(string databasePath, string accountId)
    {
        using var connection = new SqliteConnection($"Data Source={databasePath}");
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "UPDATE projects SET account_id = $account WHERE id = 'project-s43';";
        command.Parameters.AddWithValue("$account", accountId);
        command.ExecuteNonQuery();
    }

    private static void InsertRepairAudit(string databasePath, string lifecycle)
    {
        using var connection = new SqliteConnection($"Data Source={databasePath}");
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO workspace_repair_audit VALUES ($id, 'project-s43', 'protected-owner-repair');";
        command.Parameters.AddWithValue("$id", $"s43-{lifecycle}");
        command.ExecuteNonQuery();
    }

    private static async Task WaitForFileAsync(string path, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (!File.Exists(path) && DateTime.UtcNow < deadline) await Task.Delay(25);
    }

    private void Observe(string observation) => _output.WriteLine($"S43-OBSERVATION {observation}");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition) throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private static void DeleteDirectory(string path)
    {
        try { if (Directory.Exists(path)) Directory.Delete(path, recursive: true); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    private sealed record DriftObservation(bool BlockedAfterAcl, bool BlockedAfterInheritance, bool BlockedAfterOwner, bool RepairedRunAllowed);

    private sealed record FileSnapshot(string Content, long Length, DateTime LastWriteTimeUtc)
    {
        public static FileSnapshot Capture(string path)
        {
            var info = new FileInfo(path);
            return new FileSnapshot(File.ReadAllText(path), info.Length, info.LastWriteTimeUtc);
        }
    }

    private sealed class WindowsRunnerFixture : IDisposable
    {
        private readonly RunnerIsolationHandle _isolation;
        private readonly string _runnerSid;

        private WindowsRunnerFixture(string root, string workspace, string runnerSid, RunnerIsolationHandle isolation)
        {
            Root = root;
            Workspace = workspace;
            _runnerSid = runnerSid;
            _isolation = isolation;
        }

        public string Root { get; }
        public string Workspace { get; }

        public static WindowsRunnerFixture Create()
        {
            if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("S43 requires the Windows Runner boundary.");
            var root = Path.Combine(Path.GetTempPath(), "phase-s43-" + Guid.NewGuid().ToString("N"));
            var workspace = Path.Combine(root, "account-a", "project-a");
            Directory.CreateDirectory(root);
            try
            {
                var sid = ((SecurityIdentifier)new NTAccount(Environment.MachineName, RunnerAccount).Translate(typeof(SecurityIdentifier))).Value;
                var isolation = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor("account-a", "project-a", RunnerAccount, workspace, true, true, true));
                return new WindowsRunnerFixture(root, workspace, sid, isolation);
            }
            catch
            {
                DeleteDirectory(root);
                throw;
            }
        }

        public async Task<HostedProcessResult> RunAsync(string operation)
        {
            try
            {
                return await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                    "cmd.exe", ["/d", "/c", $"echo S43_RUNNER_LAUNCHED & whoami /user /fo csv /nh & echo S43_OPERATION_ATTEMPTED & {operation}"], Workspace, new Dictionary<string, string>()));
            }
            catch (Exception error) when (error is Win32Exception or InvalidOperationException)
            {
                throw new InvalidOperationException("S43 real Runner process could not be initialized.", error);
            }
        }

        public bool HasDistinctRestrictedIdentity(string stdout)
        {
            var childSid = Regex.Match(stdout, "S-1-5-[0-9-]+", RegexOptions.CultureInvariant).Value;
            var platformSid = WindowsIdentity.GetCurrent().User?.Value;
            return !string.IsNullOrWhiteSpace(childSid) &&
                   !string.IsNullOrWhiteSpace(platformSid) &&
                   !string.Equals(childSid, platformSid, StringComparison.OrdinalIgnoreCase);
        }

        public void Protect(string path) => ApplyIcacls(path, "/inheritance:r /grant:r \"*S-1-5-32-544:(OI)(CI)F\"");

        public void ApplyDrift(string drift)
        {
            var arguments = drift switch
            {
                "acl" => "/grant \"*S-1-5-32-545:(OI)(CI)M\"",
                "inheritance" => "/inheritance:e",
                "owner" => $"/setowner \"{RunnerAccount}\"",
                _ => throw new ArgumentOutOfRangeException(nameof(drift))
            };
            ApplyIcacls(Workspace, arguments);
        }

        public void Repair()
        {
            using var replacement = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor("account-a", "project-a", RunnerAccount, Workspace, true, true, true));
        }

        private static void ApplyIcacls(string path, string arguments)
        {
            using var process = Process.Start(new ProcessStartInfo("icacls.exe", $"\"{path}\" {arguments}") { UseShellExecute = false, CreateNoWindow = true });
            if (process is null) throw new InvalidOperationException("S43 could not start icacls.");
            process.WaitForExit();
            if (process.ExitCode != 0) throw new InvalidOperationException($"S43 icacls failed with exit {process.ExitCode}.");
        }

        public void Dispose()
        {
            _isolation.Dispose();
            DeleteDirectory(Root);
        }
    }
}
