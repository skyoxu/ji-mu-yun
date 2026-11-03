using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text.Json;
using PhaseA.Platform.Security;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061 S2-06: disposable real-host observations, never live metadata.
internal static class S206TestSupport
{
    internal static readonly string RepositoryRoot = Path.GetFullPath(
        Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));

    // ADR-0061: Python owns per-case disposable outputs and decides final business success.
    // Direct dotnet invocations without that owner continue retaining their diagnostics.
    internal static string CreateOwnedFixtureRoot(string prefix)
    {
        var supplied = Environment.GetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT");
        var parent = string.IsNullOrWhiteSpace(supplied) ? Path.GetTempPath() : Path.GetFullPath(supplied);
        if (!string.IsNullOrWhiteSpace(supplied))
        {
            var logs = Path.GetFullPath(Path.Combine(RepositoryRoot, "logs"));
            var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
            if (!parent.StartsWith(logs + Path.DirectorySeparatorChar, comparison) || !Directory.Exists(parent))
                throw new InvalidOperationException("Fixture owner must be an existing repository log directory.");
            for (var current = new DirectoryInfo(parent); current is not null; current = current.Parent)
            {
                if ((current.Attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidOperationException("Fixture owner cannot traverse a link.");
                if (string.Equals(current.FullName, logs, comparison)) break;
            }
        }
        return Path.Combine(parent, prefix + Guid.NewGuid().ToString("N"));
    }

    // A context transport is not an authority oracle. Older production still executes
    // its real path when this additive transport is absent; Python evaluates effects.
    internal static IDisposable? EnterCurrentContext(RequestContext context) =>
        typeof(RequestContext).GetMethod("UseCurrent", System.Reflection.BindingFlags.Public |
            System.Reflection.BindingFlags.Static, [typeof(RequestContext)])?.Invoke(null,[context]) as IDisposable;

    // Linux-only readback fixture registration. This never proves Windows ACL, credentials, dispatch or Job Objects.
    internal static void RegisterLogicalReadbackProject(ProjectSnapshot project)
    {
        if(OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("Logical readback registration is not Windows Runner evidence.");
        var path=Path.GetFullPath(project.WorkspaceRootPath);
        if(!path.StartsWith(RepositoryRoot+Path.DirectorySeparatorChar,StringComparison.Ordinal))
            throw new InvalidOperationException("Readback fixture must remain repository-owned.");
        foreach(var directory in new[]{project.WorkspaceRootPath,project.RepoPath,project.RuntimePath,project.MetaPath})
            Directory.CreateDirectory(directory);
        using var registration=RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
            project.AccountId,project.ProjectId,"logical-readback-fixture",path,true,false,false));
    }

    // ADR-0035/0061: a real Windows registration is mandatory for owned HTTP fixture restart.
    internal static IDisposable RegisterOwnedProjectBoundary(ProjectSnapshot project, PhaseAPlatformOptions options)
    {
        if (!OperatingSystem.IsWindows())
        {
            RegisterLogicalReadbackProject(project);
            return new OwnedProjectRegistration(project.WorkspaceRootPath, null);
        }
        foreach (var directory in new[] { project.WorkspaceRootPath, project.RepoPath, project.RuntimePath, project.MetaPath })
            Directory.CreateDirectory(directory);
        var layout = new WorkspaceLayout(project.WorkspaceRootPath, project.RepoPath, project.RuntimePath, project.MetaPath);
        new WindowsProjectRunnerProvisioner(options).Provision(project.AccountId, project.ProjectId, layout);
        if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.RepoPath, out var descriptor))
            throw new InvalidOperationException("Owned Windows Runner registration missing.");
        return new OwnedProjectRegistration(project.WorkspaceRootPath, descriptor);
    }

    private sealed class OwnedProjectRegistration(string root, RunnerIsolationDescriptor? descriptor) : IDisposable
    {
        private bool _disposed;
        public void Dispose()
        {
            if (_disposed) return;
            if (descriptor is not null) WindowsProjectRunnerProvisioner.RemoveTestRegistration(descriptor);
            else RunnerIsolationPolicy.ForgetWorkspace(root);
            _disposed = true;
        }
    }

    // ADR-0061: explicit isolated test configuration, never process/global production defaults.
    internal static PhaseAPlatformOptions OwnedNodeOptions(Dictionary<string, string?> values)
    {
        var settings = new Dictionary<string, string?>(values);
        settings.TryAdd("HOSTED_WORKSPACE_ROOT", CreateOwnedFixtureRoot("owned-ci-workspaces-"));
        // Metadata-only fixtures use the committed minimal seed, not the test host DLL directory.
        settings.TryAdd("PHASEA_REPOSITORY_ROOT", Path.Combine(RepositoryRoot, "PhaseA.Platform.Tests", "Fixtures", "ProjectSeedRepository"));
        settings.TryAdd("PHASEA_NODE_ID", "owned-ci-node");
        settings.TryAdd("PHASEA_NODE_SCOPE", "single_node_test");
        settings.TryAdd("PHASEA_NODE_TOPOLOGY", "single_service");
        settings.TryAdd("PHASEA_ENABLED_ROLES", "entry,production");
        settings.TryAdd("PHASEA_ACCEPT_NEW_ACCOUNTS", "true");
        settings.TryAdd("PHASEA_SERVICE_STATE", "test");
        settings.TryAdd("PHASEA_ADMIN_TOKEN_HASH", PhaseAAuth.HashTokenForStorage(Guid.NewGuid().ToString("N")));
        return PhaseAPlatformOptionsLoader.FromDictionary(settings);
    }

    internal static async Task<RequestContext> FixtureContextAsync(PhaseAMetadataStore store, string tokenHash)
    {
        var account = await store.ResolveAccountByTokenHashAsync(tokenHash)
            ?? throw new InvalidOperationException("Owned fixture credential did not authenticate.");
        return RequestContext.FromIdentity(new AccountIdentity(account.AccountId, account.Username,
            account.IsAdmin ? PhaseAAuth.AdminRole : PhaseAAuth.UserRole), account.AccountId, tokenHash, "owned-ci-fixture");
    }

    internal static async Task<object> ObserveRoleAsync(string phase, string? roles,
        bool acceptNewAccounts = true, string? existingRoot = null,
        string? instanceId = null, string? requestedReference = null, bool exerciseExistingProject = false)
    {
        var root = existingRoot ?? CreateOwnedFixtureRoot("s206-role-");
        Directory.CreateDirectory(root);
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        var url = $"http://127.0.0.1:{port}";
        var token = Guid.NewGuid().ToString("N");
        var start = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = Path.Combine(RepositoryRoot, "PhaseA.Platform"),
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        start.ArgumentList.Add(typeof(Program).Assembly.Location);
        // The fixture does not inherit platform credentials or live configuration.
        var inherited = new Dictionary<string, string?>();
        foreach (var key in new[] { "PATH", "DOTNET_ROOT", "DOTNET_CLI_HOME", "HOME", "TMPDIR", "TMP", "TEMP", "SystemRoot", "PHASEA_SNAPSHOT_KEY_ROOT" })
            inherited[key] = Environment.GetEnvironmentVariable(key);
        start.Environment.Clear();
        foreach (var item in inherited)
            if (item.Value is not null) start.Environment[item.Key] = item.Value;
        start.Environment["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1";
        start.Environment["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1";
        start.Environment["APP_BIND_URL"] = url;
        start.Environment["ASPNETCORE_URLS"] = url;
        start.Environment["PUBLIC_BASE_URL"] = "https://localhost";
        start.Environment["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3");
        start.Environment["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces");
        start.Environment["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot;
        start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(token);
        start.Environment["PHASEA_SERVICE_STATE"] = phase;
        start.Environment["PHASEA_NODE_ID"] = "test-physical-node";
        start.Environment["PHASEA_NODE_SCOPE"] = "single_node_test";
        start.Environment["PHASEA_NODE_TOPOLOGY"] = "single_service";
        start.Environment["PHASEA_LOGIN_ENDPOINT"] = "https://login.example.invalid";
        start.Environment["PHASEA_WORKBENCH_ENDPOINT"] = "https://workbench.example.invalid";
        start.Environment["PHASEA_ACTIVE_CONTENT_ORIGIN"] = "https://content.example.invalid";
        start.Environment["PHASEA_ACCEPT_NEW_ACCOUNTS"] = acceptNewAccounts ? "true" : "false";
        if (roles is not null) start.Environment["PHASEA_ENABLED_ROLES"] = roles;
        if(roles == "entry")
        {
            // Entry-only may read existing central home/session facts, but must never install a production binding.
            // Prepare the valid central ownership control before starting that role, using the real protected initializer.
            var setup=start.Environment.ToDictionary(item=>item.Key,item=>item.Value);
            setup["PHASEA_ENABLED_ROLES"]="entry,production";
            var initial=PhaseAPlatformOptionsLoader.FromDictionary(setup);
            await SqliteMetadataSchema.InitializeSingleNodeTestAsync("Data Source="+initial.MetadataDatabasePath,initial);
        }
        if (instanceId is not null) start.Environment["PHASEA_INSTANCE_ID"] = instanceId;
        // No real S2-03A measurement exists: operator/request hints are not measurement evidence.
        if (requestedReference is not null)
        {
            start.Environment["PHASEA_CAPACITY_REF"] = requestedReference;
            start.Environment["PHASEA_READINESS_REF"] = requestedReference;
        }
        using var process = Process.Start(start) ?? throw new InvalidOperationException("Fixture host did not start.");
        var ownedWindowsRunners = new List<RunnerIsolationDescriptor>();
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        try
        {
            using var client = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(2) };
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
            var healthy = false;
            for (var attempt = 0; attempt < 50; attempt++)
            {
                if (process.HasExited) break;
                try { healthy = (await client.GetAsync("/healthz")).IsSuccessStatusCode; }
                catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException) { }
                if (healthy) break;
                await Task.Delay(100);
            }
            if (!healthy)
            {
                if (!process.HasExited) throw new TimeoutException("Fixture host did not reach a terminal startup observation.");
                var diagnostic = await stderr + await stdout;
                return new { phase, roles, started = false, startupRejected = process.ExitCode != 0,
                    roleDiagnostic = diagnostic.Contains("PHASEA_ENABLED_ROLES", StringComparison.Ordinal),
                    sessionStatus = 0, projectsStatus = 0, ownership = (JsonElement?)null,
                    session = (JsonElement?)null, acceptNewAccounts };
            }
            using var session = await client.GetAsync("/api/session");
            var sessionBody = await session.Content.ReadAsStringAsync();
            JsonElement? ownership = null;
            JsonElement sessionValue;
            using (var parsed = JsonDocument.Parse(sessionBody))
            {
                sessionValue = parsed.RootElement.Clone();
                if (parsed.RootElement.TryGetProperty("ownership", out var item)) ownership = item.Clone();
            }
            var existingProjectIds = new List<string>();
            var registeredRunnerIds = new List<string>();
            if (exerciseExistingProject)
            {
                var fixtureOptions = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
                {
                    ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3"),
                    ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
                    ["PHASEA_NODE_ID"] = "test-physical-node",
                    ["PHASEA_NODE_SCOPE"] = "single_node_test",
                    ["PHASEA_NODE_TOPOLOGY"] = "single_service",
                    ["PHASEA_ENABLED_ROLES"] = "entry,production",
                    ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = acceptNewAccounts ? "true" : "false"
                });
                var fixtureStore = new PhaseAMetadataStore("Data Source=" + fixtureOptions.MetadataDatabasePath, fixtureOptions);
                for (var index = 0; index < 2; index++)
                {
                    var projectId = "s206-capacity-project-" + Guid.NewGuid().ToString("N");
                    var accountId = sessionValue.GetProperty("accountId").GetString()!;
                    var layout = WorkspaceLayoutBuilder.Build(fixtureOptions.HostedWorkspaceRoot, accountId, projectId);
                    foreach (var child in new[] { layout.RepoPath, layout.RuntimePath, layout.MetaPath }) Directory.CreateDirectory(child);
                    await File.WriteAllTextAsync(Path.Combine(layout.RepoPath, "capacity-control.txt"), projectId);
                    await fixtureStore.CreateProjectAsync(new ProjectCreationCommand(projectId, accountId,
                        "Capacity control", "Capacity control", "manual", "general", false, [],
                        layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath));
                    if (OperatingSystem.IsWindows())
                        new WindowsProjectRunnerProvisioner(fixtureOptions).Provision(accountId, projectId, layout);
                    else
                    {
                        // Existing logical registration only; never Windows ACL/SID/Job Object evidence.
                        using var registration = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
                            accountId, projectId, "logical-test-runner-" + index, layout.RootPath, true, true, true));
                    }
                    if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(layout.RepoPath, out var registered))
                        throw new InvalidOperationException("Actual fixture Runner registration was not readable.");
                    if (OperatingSystem.IsWindows()) ownedWindowsRunners.Add(registered);
                    registeredRunnerIds.Add(registered.ProjectId);
                    existingProjectIds.Add(projectId);
                }
            }
            using var projects = await client.GetAsync("/api/projects");
            var projectsBody = await projects.Content.ReadAsStringAsync();
            bool? unavailableTransportObserved = null;
            if (requestedReference == "unavailable-reference")
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(10));
                try
                {
                    using var unexpected = await client.GetAsync("/api/session");
                    unavailableTransportObserved = false;
                }
                catch (HttpRequestException) { unavailableTransportObserved = true; }
            }
            return new { phase, roles, started = true, startupRejected = false, roleDiagnostic = false,
                sessionStatus = (int)session.StatusCode, projectsStatus = (int)projects.StatusCode, ownership,
                session = sessionValue, acceptNewAccounts, instanceId, requestedReference, existingProjectIds, registeredRunnerIds, projectsBody, nativeWindowsEvidence = OperatingSystem.IsWindows(), unavailableTransportObserved };
        }
        finally
        {
            if (!process.HasExited) process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(10));
            await Task.WhenAll(stdout, stderr).WaitAsync(TimeSpan.FromSeconds(10));
            foreach (var descriptor in ownedWindowsRunners)
                WindowsProjectRunnerProvisioner.RemoveTestRegistration(descriptor);
            // Retain the small owned fixture and its database for diagnosis under the caller's logs root.
        }
    }
}

// A test-owned real process. Teardown is not a Windows graceful-cleanup receipt.
internal sealed class S206OwnedHost : IAsyncDisposable
{
    private readonly Process _process;
    private readonly Task<string> _stdout;
    private readonly Task<string> _stderr;
    private readonly string _root;
    internal string AdminToken { get; }
    internal string Url { get; }
    internal bool Started { get; private set; }
    internal int ProcessId => _process.Id;

    private S206OwnedHost(Process process, string root, string url, string adminToken)
    {
        _process = process; _root = root; Url = url; AdminToken = adminToken;
        _stdout = process.StandardOutput.ReadToEndAsync();
        _stderr = process.StandardError.ReadToEndAsync();
    }

    internal static async Task<S206OwnedHost> StartAsync(string root, string adminToken,
        bool acceptNewAccounts = true, string nodeId = "test-physical-node", string? ticketSecret = null,
        string enabledRoles = "entry,production", string? repositoryRoot = null)
    {
        Directory.CreateDirectory(root);
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start(); var port = ((IPEndPoint)listener.LocalEndpoint).Port; listener.Stop();
        var url = $"http://127.0.0.1:{port}";
        var start = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = Path.Combine(S206TestSupport.RepositoryRoot, "PhaseA.Platform"),
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true
        };
        start.ArgumentList.Add(typeof(Program).Assembly.Location);
        start.Environment.Clear();
        foreach (var key in new[] { "PATH", "DOTNET_ROOT", "DOTNET_CLI_HOME", "HOME", "TMPDIR", "TMP", "TEMP", "SystemRoot" })
            if (Environment.GetEnvironmentVariable(key) is { } value) start.Environment[key] = value;
        var configuration = new Dictionary<string, string>
        {
            ["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1", ["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1",
            ["APP_BIND_URL"] = url, ["ASPNETCORE_URLS"] = url, ["PUBLIC_BASE_URL"] = "https://localhost",
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3"),
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            ["PHASEA_REPOSITORY_ROOT"] = repositoryRoot ?? S206TestSupport.RepositoryRoot,
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken),
            ["PHASEA_SERVICE_STATE"] = "test", ["PHASEA_NODE_ID"] = nodeId,
            ["PHASEA_NODE_SCOPE"] = "single_node_test", ["PHASEA_NODE_TOPOLOGY"] = "single_service",
            ["PHASEA_ENABLED_ROLES"] = enabledRoles,
            ["PHASEA_LOGIN_ENDPOINT"] = "https://login.example.invalid",
            ["PHASEA_WORKBENCH_ENDPOINT"] = "https://workbench.example.invalid",
            ["PHASEA_ACTIVE_CONTENT_ORIGIN"] = "https://content.example.invalid",
            ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = acceptNewAccounts ? "true" : "false"
        };
        foreach (var value in configuration) start.Environment[value.Key] = value.Value;
        if(ticketSecret is not null) start.Environment["PHASEA_TICKET_SIGNING_SECRET"]=ticketSecret;
        var process = Process.Start(start) ?? throw new InvalidOperationException("Owned host failed to start.");
        var host = new S206OwnedHost(process, root, url, adminToken);
        using var client = host.Client();
        for (var attempt = 0; attempt < 100; attempt++)
        {
            if (process.HasExited) return host;
            try { host.Started = (await client.GetAsync("/healthz")).IsSuccessStatusCode; }
            catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException) { }
            if (host.Started) return host;
            await Task.Delay(100);
        }
        await host.DisposeAsync();
        throw new TimeoutException("Owned host neither started nor rejected its configuration.");
    }

    internal HttpClient Client(string? token = null)
    {
        var client = new HttpClient { BaseAddress = new Uri(Url), Timeout = TimeSpan.FromSeconds(5) };
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token ?? AdminToken);
        return client;
    }

    public async ValueTask DisposeAsync()
    {
        if (!_process.HasExited)
        {
            if (OperatingSystem.IsLinux()) _ = SendSignal(_process.Id, 15);
            else _process.Kill(entireProcessTree: true);
            try { await _process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(10)); }
            catch (TimeoutException)
            {
                _process.Kill(entireProcessTree: true);
                await _process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(10));
            }
        }
        var stamp = _process.Id.ToString(System.Globalization.CultureInfo.InvariantCulture);
        await File.WriteAllTextAsync(Path.Combine(_root, "host-" + stamp + ".stdout.log"), await _stdout);
        await File.WriteAllTextAsync(Path.Combine(_root, "host-" + stamp + ".stderr.log"), await _stderr);
        _process.Dispose();
    }

    [System.Runtime.InteropServices.DllImport("libc", EntryPoint = "kill")]
    private static extern int SendSignal(int pid, int signal);
}

// ADR-0061 AD16/17/19: real disposable authority and resource fixtures. Fault SQL
// touches only this owned database; it cannot be used by a production consumer.
internal sealed class S206AuthorityFixture : IAsyncDisposable
{
    internal sealed record Resource(string AccountId, RequestContext Context, ProjectSnapshot Project,
        string RunId, string ArtifactId, string SnapshotId, string Sentinel);
    internal string Root { get; private init; } = null!;
    internal string ConnectionString { get; private init; } = null!;
    internal PhaseAPlatformOptions Options { get; private init; } = null!;
    internal PhaseAMetadataStore Store { get; private init; } = null!;
    internal WorkspaceStorageService Storage { get; private set; } = null!;
    internal S206OwnedHost? Host { get; private set; }
    internal Resource First { get; private set; } = null!;
    internal Resource Second { get; private set; } = null!;
    internal Resource Admin { get; private set; } = null!;
    private readonly Dictionary<string,string> _tokens = new(StringComparer.Ordinal);
    private readonly List<RunnerIsolationDescriptor> _ownedWindowsRegistrations = [];

    internal static async Task<S206AuthorityFixture> CreateAsync(bool startHost=false)
    {
        var root=S206TestSupport.CreateOwnedFixtureRoot("s206-current-authority-");
        Directory.CreateDirectory(root);
        var adminToken=Guid.NewGuid().ToString("N");
        var secret="synthetic-ticket-"+Guid.NewGuid().ToString("N");
        var database=Path.Combine(root,"metadata.sqlite3");
        var options=PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string,string?>
        {
            ["HOSTED_WORKSPACE_ROOT"]=Path.Combine(root,"workspaces"),["PHASEA_METADATA_DB_PATH"]=database,
            ["PHASEA_REPOSITORY_ROOT"]=S206TestSupport.RepositoryRoot,["PHASEA_SERVICE_STATE"]="test",
            ["PHASEA_NODE_ID"]="test-physical-node",["PHASEA_NODE_SCOPE"]="single_node_test",
            ["PHASEA_NODE_TOPOLOGY"]="single_service",["PHASEA_ENABLED_ROLES"]="entry,production",
            ["PHASEA_ACCEPT_NEW_ACCOUNTS"]="true",["PHASEA_ADMIN_TOKEN_HASH"]=PhaseAAuth.HashTokenForStorage(adminToken),
            ["PHASEA_TICKET_SIGNING_SECRET"]=secret,["PHASEA_LOGIN_ENDPOINT"]="https://login.example.invalid",
            ["PHASEA_WORKBENCH_ENDPOINT"]="https://workbench.example.invalid",
            ["PHASEA_ACTIVE_CONTENT_ORIGIN"]="https://content.example.invalid"
        });
        await SqliteMetadataSchema.InitializeSingleNodeTestAsync("Data Source="+database,options);
        var fixture=new S206AuthorityFixture { Root=root,ConnectionString="Data Source="+database,
            Options=options,Store=new PhaseAMetadataStore("Data Source="+database,options) };
        try
        {
            if(startHost)
            {
                fixture.Host=await S206OwnedHost.StartAsync(root,adminToken,ticketSecret:secret);
                if(!fixture.Host.Started) throw new InvalidOperationException("Authority control host did not start.");
            }
            fixture.Storage=fixture.Store.CreateWorkspaceStorageService();
            var first=await fixture.Store.CreateUserAccountAsync("current-a",10);
            var second=await fixture.Store.CreateUserAccountAsync("current-b",10);
            fixture.First=await fixture.CreateResourceAsync(first.Token,"account-a");
            fixture.Second=await fixture.CreateResourceAsync(second.Token,"account-b");
            fixture.Admin=await fixture.CreateResourceAsync(adminToken,"administrator");
            return fixture;
        }
        catch { await fixture.DisposeAsync();throw; }
    }

    private async Task<Resource> CreateResourceAsync(string token,string sentinel)
    {
        var credential=PhaseAAuth.HashTokenForStorage(token);
        var account=await Store.ResolveAccountByTokenHashAsync(credential)
            ?? throw new InvalidOperationException("Current fixture credential did not authenticate.");
        var context=RequestContext.FromIdentity(new AccountIdentity(account.AccountId,account.Username,
            account.IsAdmin?PhaseAAuth.AdminRole:PhaseAAuth.UserRole),account.AccountId,credential,"s206-current");
        using var current=S206TestSupport.EnterCurrentContext(context);
        var creation=new ProjectCreationService(Store,Options,new ProjectRuleCatalog(),new MinimalSeeder(sentinel),
            runnerProvisioner: OperatingSystem.IsWindows() ? new WindowsProjectRunnerProvisioner(Options) : null);
        var request=new ProjectCreationRequest(sentinel,sentinel,"manual",ProjectRuleCatalog.DefaultRuleId,null,null,null);
        var created=await creation.CreateProjectAsync(account.AccountId,request);
        if(!created.Succeeded || created.ProjectId is null) throw new InvalidOperationException("Project fixture creation failed: "+created.FailureCode);
        var project=await Store.GetProjectSnapshotAsync(created.ProjectId)
            ?? throw new InvalidOperationException("Real project registration unavailable.");
        if (OperatingSystem.IsWindows())
        {
            if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.WorkspaceRootPath, out var descriptor) ||
                descriptor.AccountId != account.AccountId || descriptor.ProjectId != project.ProjectId ||
                !RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(descriptor))
                throw new InvalidOperationException("Actual owned Windows Runner registration unavailable.");
            _ownedWindowsRegistrations.Add(descriptor);
        }
        else S206TestSupport.RegisterLogicalReadbackProject(project);
        var run=await Store.CreateRunAsync(project.ProjectId,project.WorkspaceId,"project-package");
        await Store.AddArtifactAsync(new ArtifactCreationCommand(run,project.ProjectId,"sample","private.txt","S2-06 fixture"));
        var artifact=(await Store.ListArtifactsForRunAsync(run)).Single();
        Directory.CreateDirectory(Path.Combine(project.RepoPath,"exports"));
        using(var zip=System.IO.Compression.ZipFile.Open(Path.Combine(project.RepoPath,"exports","fixture.zip"),
                  System.IO.Compression.ZipArchiveMode.Create))
        {
            using var writer=new StreamWriter(zip.CreateEntry("private.txt").Open());writer.Write(sentinel);
        }
        var snapshot="s206-"+Guid.NewGuid().ToString("N");
        Storage.CreateSnapshot(context,project.RepoPath,snapshot,project.WorkspaceId,project.ProjectId,"s206",new HashSet<string>());
        _tokens.Add(account.AccountId,token);
        return new Resource(account.AccountId,context,project,run,artifact.ArtifactId,snapshot,sentinel);
    }

    internal string SyntheticToken(Resource resource) => _tokens[resource.AccountId];

    internal HttpClient Client(Resource resource)=>Host?.Client(_tokens[resource.AccountId])
        ?? throw new InvalidOperationException("HTTP fixture not selected.");

    internal async Task<string> OwnershipAsync(Resource resource)
    {
        await using var connection=new SqliteConnection(ConnectionString);await connection.OpenAsync();
        await using var command=connection.CreateCommand();
        command.CommandText="""
            SELECT a.home_node_id,p.node_id,n.node_id,pr.home_node_id,pr.authority_revision,a.authority_revision
            FROM accounts a JOIN projects p ON p.account_id=a.id
            JOIN node_binding n ON n.singleton_key=1
            LEFT JOIN account_node_projections pr ON pr.account_id=a.id
            WHERE a.id=$account AND p.id=$project;
            """;
        command.Parameters.AddWithValue("$account",resource.AccountId);command.Parameters.AddWithValue("$project",resource.Project.ProjectId);
        await using var reader=await command.ExecuteReaderAsync();
        if(!await reader.ReadAsync()) throw new InvalidOperationException("Original ownership fixture missing.");
        return JsonSerializer.Serialize(Enumerable.Range(0,6).Select(i=>reader.IsDBNull(i)?null:reader.GetValue(i)).ToArray());
    }

    internal string ContentHash(Resource resource) => Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
        File.ReadAllBytes(Path.Combine(resource.Project.RepoPath,"private.txt"))));

    internal async Task FaultAsync(Resource resource,string attack)
    {
        if(attack=="revoked") { await Store.SetUserDisabledAsync(resource.AccountId,true);return; }
        await using var connection=new SqliteConnection(ConnectionString);await connection.OpenAsync();
        await using var transaction=connection.BeginTransaction();
        var triggers=new List<string>();
        await using(var read=connection.CreateCommand())
        {
            read.Transaction=transaction;
            read.CommandText="SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('account_home_immutable','project_node_immutable','account_node_update');";
            await using var reader=await read.ExecuteReaderAsync();while(await reader.ReadAsync())triggers.Add(reader.GetString(0));
        }
        await using var command=connection.CreateCommand();command.Transaction=transaction;
        // Disposable fault injection preserves the actual production triggers before invoking consumers.
        command.CommandText="DROP TRIGGER IF EXISTS account_home_immutable; DROP TRIGGER IF EXISTS project_node_immutable; DROP TRIGGER IF EXISTS account_node_update;";
        await command.ExecuteNonQueryAsync();
        command.CommandText=attack switch
        {
            "missing-home"=>"UPDATE accounts SET home_node_id=NULL WHERE id=$account;",
            "foreign-home"=>"UPDATE accounts SET home_node_id='foreign-node' WHERE id=$account;",
            "missing-project"=>"UPDATE projects SET node_id=NULL WHERE id=$project;",
            "foreign-project"=>"UPDATE projects SET node_id='foreign-node' WHERE id=$project;",
            "foreign-local"=>"UPDATE node_binding SET node_id='foreign-node' WHERE singleton_key=1;",
            "missing-projection"=>"DELETE FROM account_node_projections WHERE account_id=$account;",
            "stale-projection"=>"UPDATE account_node_projections SET authority_revision=authority_revision+1 WHERE account_id=$account;",
            _=>throw new ArgumentOutOfRangeException(nameof(attack))
        };
        command.Parameters.AddWithValue("$account",resource.AccountId);command.Parameters.AddWithValue("$project",resource.Project.ProjectId);
        await command.ExecuteNonQueryAsync();
        command.Parameters.Clear();
        foreach(var trigger in triggers){command.CommandText=trigger;await command.ExecuteNonQueryAsync();}
        await transaction.CommitAsync();
    }

    internal HeavyRunnerQueueService Queue(int maximum=1)
    {
        NodeProjectMetadata node=Store;
        var constructor=typeof(HeavyRunnerQueueService).GetConstructor([typeof(TimeSpan?),typeof(int),typeof(NodeProjectMetadata)]);
        return constructor is null ? new HeavyRunnerQueueService(TimeSpan.FromSeconds(1),maximum)
            : (HeavyRunnerQueueService)constructor.Invoke([TimeSpan.FromSeconds(1),maximum,node]);
    }

    public async ValueTask DisposeAsync()
    {
        if(Host is not null)await Host.DisposeAsync();
        List<Exception>? errors = null;
        foreach (var descriptor in _ownedWindowsRegistrations)
        {
            try { WindowsProjectRunnerProvisioner.RemoveTestRegistration(descriptor); }
            catch (Exception error) { (errors ??= []).Add(error); }
        }
        _ownedWindowsRegistrations.Clear();
        if (errors is not null) throw new AggregateException("Owned Windows fixture cleanup failed.", errors);
    }

    private sealed class MinimalSeeder(string value):IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string root){Directory.CreateDirectory(root);File.WriteAllText(Path.Combine(root,"private.txt"),value);}
    }
}

// The original legacy fixture boundary, applied to the same central implementation after its internal rename.
// This does not issue node capabilities or bypass the public node facade's authorization.
internal static class S206CentralRestoreFixtureIsolation
{
    internal static RestoreAttempt RestorePrepared(this CentralRestoreBackend service,RequestContext context,
        SnapshotManifest manifest,string source,string destination,RunnerLease lease,string? key=null,
        RunnerIsolationDescriptor? descriptor=null)
    {
        if(!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(destination,out _))
        {
            using var isolation=RunnerIsolationPolicy.PrepareWorkspace(descriptor ?? new RunnerIsolationDescriptor(
                manifest.AccountId,manifest.ProjectId,"phase-r-a-p",destination,true,
                OperatingSystem.IsWindows(),OperatingSystem.IsWindows()));
        }
        return key is null ? service.Restore(context,manifest,source,destination,lease)
            : service.Restore(context,manifest,source,destination,lease,key);
    }
}
