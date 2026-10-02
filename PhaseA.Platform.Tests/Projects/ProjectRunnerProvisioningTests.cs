using System.Diagnostics;
using System.Text;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Projects;

// ADR-0035/0061: no manual PrepareWorkspace or test credential registration.
public sealed class ProjectRunnerProvisioningTests
{
    [Fact]
    public async Task OrdinaryCreationDispatchesIsolatedRunnerAndSurvivesFreshProcess()
    {
        Assert.True(OperatingSystem.IsWindows(), "Native provisioning requires Windows.");
        using var scope = await Scope.CreateAsync();
        var created = await scope.Service.CreateProjectAsync(scope.AccountId, Request());
        Assert.True(created.Succeeded, created.FailureCode);
        var project = (await scope.Store.GetProjectSnapshotAsync(created.ProjectId!))!;
        Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.RepoPath, out var descriptor));
        scope.Registrations.Add(descriptor);
        Assert.Equal(project.ProjectId, descriptor.ProjectId);
        Assert.Equal(project.AccountId, descriptor.AccountId);
        Assert.InRange(descriptor.OsIdentity.Length, 1, 20);
        Assert.True(RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(descriptor));
        Assert.True(RunnerIsolationPolicy.HasExpectedRestoreTreeSecurity(descriptor, project.RepoPath));
        await RunProbeAsync(project.RepoPath, descriptor);

        // A second testhost has empty registration caches in a separate process.
        // The persisted marker and LOCAL_MACHINE vault entry must be sufficient.
        var start = new ProcessStartInfo("dotnet")
        {
            UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true,
            WorkingDirectory = AppContext.BaseDirectory, CreateNoWindow = true
        };
        foreach (var argument in new[] { "vstest", typeof(ProjectRunnerProvisioningTests).Assembly.Location,
            "/TestCaseFilter:FullyQualifiedName=PhaseA.Platform.Tests.Projects.ProjectRunnerProvisioningTests.PersistedRegistrationDispatches",
            "/Logger:trx;LogFileName=runner-restart.trx", "/ResultsDirectory:" + Path.Combine(scope.Root, "restart-results") })
            start.ArgumentList.Add(argument);
        start.Environment["PHASEA_RUNNER_PROBE_REPO"] = project.RepoPath;
        start.Environment["PHASEA_RUNNER_PROBE_PROJECT"] = project.ProjectId;
        start.Environment["PHASEA_RUNNER_PROBE_ACCOUNT"] = project.AccountId;
        using var process = Process.Start(start)!;
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(2));
        try { await process.WaitForExitAsync(timeout.Token); }
        catch { process.Kill(entireProcessTree: true); throw; }
        Assert.True(process.ExitCode == 0, await stdout + "\n" + await stderr);
        Assert.True(File.Exists(Path.Combine(scope.Root, "restart-results", "runner-restart.trx")));
    }

    [Fact]
    public async Task PersistedRegistrationDispatches()
    {
        var repo = Environment.GetEnvironmentVariable("PHASEA_RUNNER_PROBE_REPO");
        if (string.IsNullOrEmpty(repo))
        {
            // Standalone suite execution still exercises a real registration reload.
            using var scope = await Scope.CreateAsync();
            var result = await scope.Service.CreateProjectAsync(scope.AccountId, Request());
            Assert.True(result.Succeeded, result.FailureCode);
            var project = (await scope.Store.GetProjectSnapshotAsync(result.ProjectId!))!;
            Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.RepoPath, out var original));
            scope.Registrations.Add(original);
            RunnerIsolationPolicy.ForgetWorkspace(project.WorkspaceRootPath);
            Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.RepoPath, out var reloaded));
            await RunProbeAsync(project.RepoPath, reloaded);
            return;
        }
        Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(repo, out var descriptor));
        Assert.Equal(Environment.GetEnvironmentVariable("PHASEA_RUNNER_PROBE_PROJECT"), descriptor.ProjectId);
        Assert.Equal(Environment.GetEnvironmentVariable("PHASEA_RUNNER_PROBE_ACCOUNT"), descriptor.AccountId);
        await RunProbeAsync(repo, descriptor);
    }

    [Fact]
    public async Task ProvisioningFailureRollsBackProjectAndNewWorkspace()
    {
        using var scope = await Scope.CreateAsync(new RejectingProvisioner());
        var result = await scope.Service.CreateProjectAsync(scope.AccountId, Request());
        Assert.False(result.Succeeded);
        Assert.Equal("project_creation_failed", result.FailureCode);
        Assert.Empty(await scope.Store.ListProjectsAsync(scope.AccountId));
        var accountRoot = Path.Combine(scope.Root, scope.AccountId);
        Assert.True(!Directory.Exists(accountRoot) || !Directory.EnumerateDirectories(accountRoot).Any());
    }

    private static async Task RunProbeAsync(string repo, RunnerIsolationDescriptor descriptor)
    {
        Assert.True(RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(descriptor));
        var probe = Path.Combine(repo, "runner-probe.cmd");
        var accountRoot = Directory.GetParent(descriptor.WorkspaceRoot)!.FullName;
        var marker = Path.Combine(descriptor.WorkspaceRoot, ".runner-isolation.json");
        var originalMarker = await File.ReadAllBytesAsync(marker);
        await File.WriteAllTextAsync(probe,
            "@echo off\r\nwhoami\r\necho PROJECT_RUNNER_STARTED\r\n" +
            "echo runner-ok>runner-probe-output.txt\r\n" +
            // cmd redirection errors do not reliably set ERRORLEVEL; verify the actual file.
            $"echo tampered>\"{marker}\" 2>nul\r\n" +
            $"dir \"{accountRoot}\" >nul 2>nul\r\nif not errorlevel 1 exit /b 41\r\nexit /b 0\r\n", Encoding.ASCII);
        var factory = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            repo, Path.Combine(repo, "unused-output.txt"), "harmless native probe", "test-model", "low"));
        var result = await new HostedProcessRunner().RunAsync(factory with
        {
            FileName = "cmd.exe", Arguments = ["/d", "/c", probe], StandardInput = null,
            TotalTimeout = TimeSpan.FromSeconds(30)
        });
        Assert.True(result.ExitCode == 0, $"exit={result.ExitCode}, stderr={result.Stderr}, stdout={result.Stdout}");
        Assert.Contains("PROJECT_RUNNER_STARTED", result.Stdout);
        Assert.Contains(descriptor.OsIdentity.ToLowerInvariant(), result.Stdout.ToLowerInvariant());
        Assert.Contains("runner-ok", await File.ReadAllTextAsync(Path.Combine(repo, "runner-probe-output.txt")));
        Assert.Equal(originalMarker, await File.ReadAllBytesAsync(marker));
    }


    // ADR-0035/0061 review counterexample: a writable nested marker must not own identity.
    [Fact]
    public async Task Review_WritableNestedMarkerMustNotSelectAnotherAccountCredential()
    {
        using var source = await Scope.CreateAsync();
        using var target = await Scope.CreateAsync();
        var a = await source.Service.CreateProjectAsync(source.AccountId, Request());
        var b = await target.Service.CreateProjectAsync(target.AccountId, Request());
        Assert.True(a.Succeeded && b.Succeeded);
        var ap = (await source.Store.GetProjectSnapshotAsync(a.ProjectId!))!;
        var bp = (await target.Store.GetProjectSnapshotAsync(b.ProjectId!))!;
        Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(ap.RepoPath, out var ad));
        Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(bp.RepoPath, out var bd));
        source.Registrations.Add(ad); target.Registrations.Add(bd);
        const string canary = "FOREIGN_PROJECT_REVIEW_CANARY";
        var canaryPath = Path.Combine(bp.RepoPath, "foreign-canary.txt");
        await File.WriteAllTextAsync(canaryPath, canary);
        var readSddl = typeof(RunnerIsolationPolicy).GetMethod("ReadSecurityDescriptor",
            System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic)!;
        var sddl = (string)readSddl.Invoke(null, [ap.RepoPath])!;
        var forgedInput = Path.Combine(ap.RepoPath, "review-forged-input.json");
        await File.WriteAllTextAsync(forgedInput, System.Text.Json.JsonSerializer.Serialize(new
        {
            bd.AccountId, bd.ProjectId, bd.OsIdentity,
            LowPrivilegeRequired = true, JobObjectRequired = true, NtfsAclRequired = true,
            SecurityDescriptor = sddl
        }));
        var runner = new HostedProcessRunner();
        var copy = await runner.RunAsync(new HostedProcessCommand("cmd.exe",
            ["/d", "/c", $"copy /y \"{forgedInput}\" .runner-isolation.json >nul"], ap.RepoPath,
            new Dictionary<string, string>(), TotalTimeout: TimeSpan.FromSeconds(30), RequireIsolation: true));
        Assert.Equal(0, copy.ExitCode);
        var nestedMarker = Path.Combine(ap.RepoPath, ".runner-isolation.json");
        var markerOwner = System.IO.FileSystemAclExtensions.GetAccessControl(new FileInfo(nestedMarker))
            .GetOwner(typeof(System.Security.Principal.SecurityIdentifier)).Value;
        var sourceSid = ((System.Security.Principal.SecurityIdentifier)new System.Security.Principal.NTAccount(
            Environment.MachineName, ad.OsIdentity).Translate(typeof(System.Security.Principal.SecurityIdentifier))).Value;
        Assert.Equal(sourceSid, markerOwner);
        RunnerIsolationPolicy.ForgetWorkspace(ad.WorkspaceRoot);
        try
        {
            var resolved = RunnerIsolationPolicy.TryGetWorkspaceDescriptor(ap.RepoPath, out var loaded);
            HostedProcessResult? result = null;
            string? errorType = null;
            try
            {
                result = await runner.RunAsync(new HostedProcessCommand("cmd.exe",
                    ["/d", "/c", $"whoami & type \"{canaryPath}\""], ap.RepoPath,
                    new Dictionary<string, string>(), TotalTimeout: TimeSpan.FromSeconds(30), RequireIsolation: true));
            }
            catch (Exception error) { errorType = error.GetType().Name; }
            var observation = System.Text.Json.JsonSerializer.Serialize(new
            {
                resolved, expectedAccount = ap.AccountId, actualAccount = loaded?.AccountId,
                actualRoot = loaded?.WorkspaceRoot, actualProject = loaded?.ProjectId,
                expectedProject = ap.ProjectId, markerOwnedBySourceRunner = markerOwner == sourceSid,
                exitCode = result?.ExitCode, foreignCanaryRead = result?.Stdout.Contains(canary) == true,
                stdout = result?.Stdout, stderr = result?.Stderr, errorType
            });
            Console.WriteLine("REVIEW_SHADOW_MARKER=" + observation);
            Assert.True(!resolved || (loaded.AccountId == ap.AccountId && loaded.ProjectId == ap.ProjectId), observation);
            Assert.True(result?.ExitCode == 403 || result?.Stdout.Contains(canary) != true, observation);
        }
        finally { RunnerIsolationPolicy.ForgetWorkspace(ap.RepoPath); }
    }

    // ADR-0035/0061 review: cmd registration probes do not establish configured tool access.
    [Fact]
    public async Task Review_ConfiguredPrivateProfileToolMustBeExecutableByNewRunner()
    {
        using var scope = await Scope.CreateAsync();
        var created = await scope.Service.CreateProjectAsync(scope.AccountId, Request());
        Assert.True(created.Succeeded);
        var project = (await scope.Store.GetProjectSnapshotAsync(created.ProjectId!))!;
        Assert.True(RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.RepoPath, out var descriptor));
        scope.Registrations.Add(descriptor);
        var tools = Path.Combine(scope.Root, "private-profile", "AppData", "Roaming", "npm");
        Directory.CreateDirectory(tools);
        var tool = Path.Combine(tools, "codex.cmd");
        await File.WriteAllTextAsync(tool, "@echo off\r\necho REVIEW_CONFIGURED_TOOL_STARTED\r\nexit /b 0\r\n");
        var security = new System.Security.AccessControl.DirectorySecurity();
        var administrator = new System.Security.Principal.SecurityIdentifier("S-1-5-32-544");
        security.SetAccessRuleProtection(true, false); security.SetOwner(administrator);
        security.AddAccessRule(new System.Security.AccessControl.FileSystemAccessRule(administrator,
            System.Security.AccessControl.FileSystemRights.FullControl,
            System.Security.AccessControl.InheritanceFlags.ContainerInherit | System.Security.AccessControl.InheritanceFlags.ObjectInherit,
            System.Security.AccessControl.PropagationFlags.None, System.Security.AccessControl.AccessControlType.Allow));
        System.IO.FileSystemAclExtensions.SetAccessControl(new DirectoryInfo(tools), security);
        var prior = Environment.GetEnvironmentVariable("PHASEA_CODEX_COMMAND");
        try
        {
            Environment.SetEnvironmentVariable("PHASEA_CODEX_COMMAND", tool);
            var command = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
                project.RepoPath, Path.Combine(project.RepoPath, "unused.txt"), "review only", "test-model", "low"));
            var result = await new HostedProcessRunner().RunAsync(command with { TotalTimeout = TimeSpan.FromSeconds(30) });
            var observation = System.Text.Json.JsonSerializer.Serialize(new
            { projectCreated = created.Succeeded, actualTool = command.FileName, exitCode = result.ExitCode, result.Stdout, result.Stderr });
            Console.WriteLine("REVIEW_PRIVATE_TOOL=" + observation);
            Assert.True(result.ExitCode == 0 && result.Stdout.Contains("REVIEW_CONFIGURED_TOOL_STARTED"), observation);
        }
        finally { Environment.SetEnvironmentVariable("PHASEA_CODEX_COMMAND", prior); }
    }

    private static ProjectCreationRequest Request() => new(null, "native-runner", "manual", null, null, null, null);

    private sealed class RejectingProvisioner : IProjectRunnerProvisioner
    {
        public void Provision(string accountId, string projectId, WorkspaceLayout layout) =>
            throw new InvalidOperationException("provisioning rejected");
    }

    private sealed class Seed : IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string repo) => File.WriteAllText(Path.Combine(repo, "project.godot"), "config_version=5\n");
    }

    private sealed class Scope : IDisposable
    {
        private readonly TempSqliteDatabase _database;
        private Scope(TempSqliteDatabase database, string root, string accountId,
            PhaseAMetadataStore store, ProjectCreationService service)
        { _database = database; Root = root; AccountId = accountId; Store = store; Service = service; }
        public string Root { get; }
        public string AccountId { get; }
        public PhaseAMetadataStore Store { get; }
        public ProjectCreationService Service { get; }
        public List<RunnerIsolationDescriptor> Registrations { get; } = [];
        public static async Task<Scope> CreateAsync(IProjectRunnerProvisioner? provisioner = null)
        {
            var database = TempSqliteDatabase.Create();
            var root = Path.Combine(Path.GetTempPath(), "phase-runner-provision-" + Guid.NewGuid().ToString("N"));
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            { ["HOSTED_WORKSPACE_ROOT"] = root, ["PHASEA_REPOSITORY_ROOT"] = AppContext.BaseDirectory });
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var owner = await store.CreateUserAccountAsync("runner-owner-" + Guid.NewGuid().ToString("N"), projectLimit: 2);
            var service = new ProjectCreationService(store, options, new ProjectRuleCatalog(), new Seed(),
                runnerProvisioner: provisioner ?? new WindowsProjectRunnerProvisioner(options));
            return new Scope(database, root, owner.AccountId, store, service);
        }
        public void Dispose()
        {
            foreach (var descriptor in Registrations) WindowsProjectRunnerProvisioner.RemoveTestRegistration(descriptor);
            _database.Dispose();
            if (Directory.Exists(Root)) Directory.Delete(Root, true);
        }
    }
}
