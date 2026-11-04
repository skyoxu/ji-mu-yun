using System.Net.Http.Json;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.NodeIdentity;

[CollectionDefinition("S206 persistence environment", DisableParallelization = true)]
public sealed class S206PersistenceEnvironmentCollection { }

[Collection("S206 persistence environment")]
public sealed class NodePersistenceTests(ITestOutputHelper output)
{
    // ADR-0061: real local persistence survives a new test-host process; no service/global owner startup.
    [Fact]
    public async Task O_E173D2E7279D()
    {
        using var environment = FoundationEnvironment.Create();
        var restartInput = Environment.GetEnvironmentVariable("S206_PERSISTENCE_RESTART_INPUT");
        if (!string.IsNullOrEmpty(restartInput))
        {
            output.WriteLine("S206_FOUNDATION_REOPEN:" + JsonSerializer.Serialize(await ReadFoundationAsync(restartInput)));
            return;
        }
        var root = S206TestSupport.CreateOwnedFixtureRoot("f7-");
        Directory.CreateDirectory(root);
        var database = Path.Combine(root, "metadata.sqlite3");
        var connectionString = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
        var options = FoundationOptions(root);
        await SqliteMetadataSchema.InitializeSingleNodeTestAsync(connectionString, options);
        var store = new PhaseAMetadataStore(connectionString, options);
        var account = await store.CreateUserAccountAsync("foundation-synthetic", 2);
        var credential = PhaseAAuth.HashTokenForStorage(account.Token);
        var context = await S206TestSupport.FixtureContextAsync(store, credential);
        var projectId = "f7" + Guid.NewGuid().ToString("N")[..8];
        var layout = PhaseA.Platform.Workspaces.WorkspaceLayoutBuilder.Build(options.HostedWorkspaceRoot, account.AccountId, projectId);
        foreach (var directory in new[] { layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath }) Directory.CreateDirectory(directory);
        if (layout.RepoPath.Length > 247 || Path.Combine(layout.RepoPath, ".snapshots-f7.protected").Length > 259)
            throw new InvalidOperationException("Owned persistence fixture exceeds native cleanup path limits.");
        var content = System.Text.Encoding.UTF8.GetBytes("foundation-byte-control\r\n\0\u4e2d\n");
        File.WriteAllBytes(Path.Combine(layout.RepoPath, "persisted.txt"), content);
        var creation = await store.CreateProjectAsync(new(projectId, account.AccountId, "Foundation", "Foundation", "manual", "default", false, [],
            layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath));
        if (!creation.Succeeded) throw new InvalidOperationException("Actual temporary project setup failed.");
        var project = await store.GetProjectSnapshotAsync(projectId) ?? throw new InvalidOperationException("Created project missing.");
        using (S206TestSupport.EnterCurrentContext(context))
            store.CreateWorkspaceStorageService().CreateSnapshot(context, project.RepoPath, "f7", project.WorkspaceId,
                project.ProjectId, "foundation-test", new HashSet<string>());
        var input = Path.Combine(root, "restart-input.json");
        File.WriteAllText(input, JsonSerializer.Serialize(new { root, accountId = account.AccountId, projectId, credential }));
        var before = await ReadFoundationAsync(input);
        // A fresh exact test-host process recreates the production store/workspace service.
        var results = Path.Combine(root, "restart-trx"); Directory.CreateDirectory(results);
        var start = new System.Diagnostics.ProcessStartInfo("dotnet")
        {
            WorkingDirectory = S206TestSupport.RepositoryRoot, UseShellExecute = false,
            RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true
        };
        foreach (var arg in new[] { "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--no-build", "--filter",
            "FullyQualifiedName=PhaseA.Platform.Tests.NodeIdentity.NodePersistenceTests.O_E173D2E7279D", "--logger", "trx", "--results-directory", results })
            start.ArgumentList.Add(arg);
        start.Environment["S206_PERSISTENCE_RESTART_INPUT"] = input;
        using var child = System.Diagnostics.Process.Start(start) ?? throw new InvalidOperationException("Readback child did not start.");
        var stdout = child.StandardOutput.ReadToEndAsync(); var stderr = child.StandardError.ReadToEndAsync();
        try { await child.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(90)); }
        catch { if (!child.HasExited) child.Kill(entireProcessTree: true); await child.WaitForExitAsync(); throw; }
        var captured = await stdout; var errors = await stderr;
        if (child.ExitCode != 0) throw new InvalidOperationException("Separate readback harness failed: " + captured + errors);
        var files = Directory.GetFiles(results, "*.trx");
        if (files.Length != 1) throw new InvalidOperationException("Separate readback requires one fresh TRX.");
        var trx = System.Xml.Linq.XDocument.Load(files[0]); System.Xml.Linq.XNamespace ns = "http://microsoft.com/schemas/VisualStudio/TeamTest/2010";
        var units = trx.Descendants(ns + "UnitTestResult").ToArray();
        var methods = trx.Descendants(ns + "TestMethod").ToArray();
        if (units.Length != 1 || units[0].Attribute("outcome")?.Value != "Passed" || methods.Length != 1 ||
            methods[0].Attribute("name")?.Value != nameof(O_E173D2E7279D) ||
            methods[0].Attribute("className")?.Value.Split(',')[0] != GetType().FullName)
            throw new InvalidOperationException("Separate readback ran the wrong native case.");
        var lines = units[0].Descendants(ns + "StdOut").SelectMany(n => n.Value.Split('\n')).Select(s => s.Trim())
            .Where(s => s.StartsWith("S206_FOUNDATION_REOPEN:", StringComparison.Ordinal)).ToArray();
        if (lines.Length != 1) throw new InvalidOperationException("Separate readback observation is ambiguous.");
        var after = JsonSerializer.Deserialize<JsonElement>(lines[0]["S206_FOUNDATION_REOPEN:".Length..]);
        output.WriteLine("S206_FOUNDATION:" + JsonSerializer.Serialize(new
        {
            schema = "s206.local-foundation.v1", before, after, expectedContentSha256 = Convert.ToHexString(SHA256.HashData(content)).ToLowerInvariant(),
            processId = Environment.ProcessId, childLauncherProcessId = child.Id,
            framework = System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription,
            storeAssembly = typeof(PhaseAMetadataStore).Assembly.GetName().Name,
            sqliteAssembly = typeof(SqliteConnection).Assembly.GetName().Name,
            storageAssembly = typeof(PhaseA.Platform.Workspaces.WorkspaceStorageService).Assembly.GetName().Name,
            sourceHead = await FoundationHeadAsync(),
            sourceHashes = new[] { "PhaseA.Platform/Program.cs", "PhaseA.Platform/Data/PhaseAMetadataStore.cs", "PhaseA.Platform/Data/SqliteMetadataSchema.cs",
                "PhaseA.Platform/Workspaces/WorkspaceStorageService.cs", "PhaseA.Platform/PhaseA.Platform.csproj", "PhaseA.Platform/packages.lock.json" }
                .ToDictionary(p => p, p => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(S206TestSupport.RepositoryRoot, p)))).ToLowerInvariant()),
            nativeReadbackTrx = files[0], fixedAnchorOpened = false, windowsAccountOrCredentialCreated = false
        }));
    }

    // The nonparallel collection confines these temporary process environment values.
    // No machine/user environment, key directory or existing ACL is modified.
    private sealed class FoundationEnvironment : IDisposable
    {
        private readonly string? _oldOwner = Environment.GetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT");
        private readonly string? _oldKeys = Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT");
        private bool _changed;
        internal static FoundationEnvironment Create()
        {
            var scope = new FoundationEnvironment();
            if (string.IsNullOrWhiteSpace(scope._oldOwner) && string.IsNullOrWhiteSpace(scope._oldKeys))
            {
                var owner = S206TestSupport.CreateOwnedFixtureRoot("f7s-");
                Directory.CreateDirectory(owner);
                Environment.SetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT", owner);
                Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", Path.Combine(owner, "synthetic-snapshot-keys"));
                scope._changed = true;
            }
            try
            {
                var owner = Environment.GetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT");
                var keys = Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT");
                if (string.IsNullOrWhiteSpace(owner) || string.IsNullOrWhiteSpace(keys) || !Directory.Exists(owner) ||
                    !Path.GetFullPath(keys).StartsWith(Path.GetFullPath(owner) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Foundation keys require an explicit owned fixture scope.");
                RunnerIsolationPolicy.RequireNoReparsePoint(owner, owner);
                if (Directory.Exists(keys)) RunnerIsolationPolicy.RequireNoReparsePoint(owner, keys);
                return scope;
            }
            catch { scope.Dispose(); throw; }
        }
        public void Dispose()
        {
            if (!_changed) return;
            Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", _oldKeys);
            Environment.SetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT", _oldOwner);
            _changed = false;
        }
    }

    private static PhaseAPlatformOptions FoundationOptions(string root) => S206TestSupport.OwnedNodeOptions(new()
    {
        ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "w"),
        ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3"),
        ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage("synthetic-foundation-admin-not-a-real-credential")
    });

    private static async Task<object> ReadFoundationAsync(string input)
    {
        var owner = Environment.GetEnvironmentVariable("S206_OWNED_FIXTURE_ROOT") ?? throw new InvalidOperationException("Owned fixture parent required.");
        var full = Path.GetFullPath(input);
        if (!full.StartsWith(Path.GetFullPath(owner) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Readback path escapes the owned fixture.");
        RunnerIsolationPolicy.RequireNoReparsePoint(owner, full);
        using var document = JsonDocument.Parse(File.ReadAllBytes(full)); var state = document.RootElement;
        var root = state.GetProperty("root").GetString()!;
        if (Path.GetDirectoryName(full) != root) throw new InvalidOperationException("Readback root does not match its input.");
        var database = Path.Combine(root, "metadata.sqlite3");
        var connectionString = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
        var store = new PhaseAMetadataStore(connectionString, FoundationOptions(root));
        var context = await S206TestSupport.FixtureContextAsync(store, state.GetProperty("credential").GetString()!);
        var project = await store.GetProjectSnapshotAsync(state.GetProperty("projectId").GetString()!)
            ?? throw new InvalidOperationException("Persisted project readback is missing.");
        PhaseA.Platform.Workspaces.WorkspaceSnapshotRecord[] snapshots;
        using (S206TestSupport.EnterCurrentContext(context))
            snapshots = store.CreateWorkspaceStorageService().ListSnapshots(context.AccountId, project.ProjectId).ToArray();
        var snapshot = snapshots.Single();
        var manifestRaw = File.ReadAllBytes(snapshot.ManifestPath);
        var contentPath = Path.Combine(project.RepoPath, "persisted.txt");
        var payloadPath = Path.ChangeExtension(snapshot.ManifestPath, ".protected");
        var databases = new List<object>();
        await using (var connection = new SqliteConnection(connectionString))
        {
            await connection.OpenAsync(); await using var command = connection.CreateCommand(); command.CommandText = "PRAGMA database_list;";
            await using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync()) databases.Add(new { name = reader.GetString(1), file = reader.GetString(2) });
        }
        var header = new byte[16]; using (var file = new FileStream(database, FileMode.Open, FileAccess.Read, FileShare.ReadWrite)) file.ReadExactly(header);
        return new
        {
            processId = Environment.ProcessId, accountId = context.AccountId, projectId = project.ProjectId, workspaceId = project.WorkspaceId,
            expectedAccountId = state.GetProperty("accountId").GetString(), projectAccountId = project.AccountId,
            databasePath = database, databases, sqliteHeaderHex = Convert.ToHexString(header),
            databaseIdentity = FoundationFileIdentity(database), contentIdentity = FoundationFileIdentity(contentPath),
            contentSha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(contentPath))).ToLowerInvariant(),
            manifestIdentity = FoundationFileIdentity(snapshot.ManifestPath), manifestSha256 = Convert.ToHexString(SHA256.HashData(manifestRaw)).ToLowerInvariant(),
            payloadIdentity = FoundationFileIdentity(payloadPath), payloadSha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(payloadPath))).ToLowerInvariant(),
            snapshotId = snapshot.Manifest.SnapshotId, snapshotManifest = snapshot.Manifest,
            serviceType = store.CreateWorkspaceStorageService().GetType().FullName
        };
    }

    private static string FoundationFileIdentity(string path)
    {
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("This observation requires Windows file identity.");
        using var file = File.OpenHandle(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, FileOptions.None);
        if (!FoundationFileInformation(file, out var data)) throw new System.ComponentModel.Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error());
        if ((data.Attributes & 0x400) != 0 || data.Links != 1) throw new InvalidOperationException("Readback file is aliased.");
        return $"{data.Volume:X8}:{((ulong)data.High << 32) | data.Low}";
    }
    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
    private struct FoundationFileInfo
    {
        public uint Attributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME Creation, Access, Write;
        public uint Volume, SizeHigh, SizeLow, Links, High, Low;
    }
    [System.Runtime.InteropServices.DllImport("kernel32.dll", EntryPoint = "GetFileInformationByHandle", SetLastError = true)]
    [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
    private static extern bool FoundationFileInformation(Microsoft.Win32.SafeHandles.SafeFileHandle file, out FoundationFileInfo data);
    private static async Task<string> FoundationHeadAsync()
    {
        var start = new System.Diagnostics.ProcessStartInfo("git") { WorkingDirectory = S206TestSupport.RepositoryRoot,
            RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true };
        start.ArgumentList.Add("rev-parse"); start.ArgumentList.Add("HEAD");
        using var process = System.Diagnostics.Process.Start(start)!;
        var text = process.StandardOutput.ReadToEndAsync(); await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(10));
        if (process.ExitCode != 0) throw new InvalidOperationException("Source HEAD unavailable.");
        return (await text).Trim();
    }

    [Fact]
    public async Task O_B093CBB29DA6()
    {
        var root = Path.Combine(Path.GetTempPath(), "s206-home-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3")
        });
        await SqliteMetadataSchema.InitializeAsync("Data Source=" + options.MetadataDatabasePath);
        var store = new PhaseAMetadataStore("Data Source=" + options.MetadataDatabasePath, options);
        var observation=JsonSerializer.SerializeToNode(await ObserveAsync(root,store))!.AsObject();
        observation["bindingReentry"]=JsonSerializer.SerializeToNode(await ObserveBindingReentryAsync());
        output.WriteLine("S206_PERSISTENCE:"+observation.ToJsonString());
    }

    [Fact]
    public async Task O_B30BD7CEB94E()
    {
        var root = Path.Combine(Path.GetTempPath(), "s206-new-home-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3")
        });
        await SqliteMetadataSchema.InitializeAsync("Data Source=" + options.MetadataDatabasePath);
        var store = new PhaseAMetadataStore("Data Source=" + options.MetadataDatabasePath, options);
        output.WriteLine("S206_PERSISTENCE:" + JsonSerializer.Serialize(await ObserveAsync(root, store)));
    }

    [Fact]
    public async Task O_B77520560CA4()
    {
        var root = Path.Combine(Path.GetTempPath(), "s206-atomic-home-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3")
        });
        await SqliteMetadataSchema.InitializeAsync("Data Source=" + options.MetadataDatabasePath);
        var store = new PhaseAMetadataStore("Data Source=" + options.MetadataDatabasePath, options);
        output.WriteLine("S206_PERSISTENCE:" + JsonSerializer.Serialize(await ObserveAsync(root, store)));
    }

    [Fact]
    public void O_53E6DDB4537B()
    {
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-authority-options")
        });
        WriteAuthorityObservation(configuration);
    }

    internal void WriteAuthorityObservation(PhaseAPlatformOptions configuration)
    {
        // Read the real handoff and immutable owning source; these are not runtime pass flags.
        var root = S206TestSupport.RepositoryRoot;
        var adr = File.ReadAllText(Path.Combine(root, "docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md"));
        var spine = File.ReadAllBytes(Path.Combine(root, "_bmad-output/planning-artifacts/architecture/architecture-s2-06-20261028/ARCHITECTURE-SPINE.md"));
        var document = File.ReadAllText(Path.Combine(root, "docs/workflows/phase-service-node-identity-and-roles.md"));
        output.WriteLine("S206_AUTHORITY:" + JsonSerializer.Serialize(new
        {
            adr, document, phaseServiceState = configuration.PhaseServiceState,
            productionRoleEnabled = configuration.ProductionRoleEnabled, spineSha256 = Convert.ToHexString(SHA256.HashData(spine)).ToLowerInvariant(),
            ownerPaths = new[] { "PhaseA.Platform/Program.cs", "PhaseA.Platform/Data/PhaseAMetadataStore.cs", "PhaseA.Platform/Data/SqliteMetadataSchema.cs", "PhaseA.Platform/Security/RequestContext.cs" }
                .Select(path => new { path, present = File.Exists(Path.Combine(root, path)) }).ToArray()
        }));
    }

    private static async Task<object> ObserveBindingReentryAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"unchanged","missing-home","missing-project","missing-projection","stale-projection"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            if(mode!="unchanged")await f.FaultAsync(f.First,mode);
            var before=await f.OwnershipAsync(f.First);var hash=f.ContentHash(f.First);
            var rejected=false;
            try {await SqliteMetadataSchema.InitializeSingleNodeTestAsync(f.ConnectionString,f.Options);}
            catch(InvalidOperationException) {rejected=true;}
            var after=await f.OwnershipAsync(f.First);
            using var beforeDocument=JsonDocument.Parse(before);
            var beforeFields=beforeDocument.RootElement;
            using var afterDocument=JsonDocument.Parse(after);
            var afterFields=afterDocument.RootElement;
            rows.Add(new {mode,rejected,unchanged=before==after&&hash==f.ContentHash(f.First),
                authorityUnchanged=new[]{0,1,2,5}.All(i=>beforeFields[i].GetRawText()==afterFields[i].GetRawText())&&hash==f.ContentHash(f.First),
                projectionCurrent=afterFields[3].ValueKind!=JsonValueKind.Null&&afterFields[4].ValueKind!=JsonValueKind.Null
                    &&afterFields[3].GetString()==afterFields[0].GetString()&&afterFields[4].GetInt64()==afterFields[5].GetInt64()});
        }

        // Explicit revocation is a valid persisted state, not damaged ownership.
        // Real startup must retain that project without seeding it, while another
        // enabled local account still receives the existing harmless seed.
        await using var disabled=await S206AuthorityFixture.CreateAsync();
        foreach(var resource in new[]{disabled.First,disabled.Second,disabled.Admin})
            await disabled.Store.SetProjectBootstrapStatusAsync(resource.Project.ProjectId,"succeeded",null);
        await disabled.FaultAsync(disabled.First,"revoked");
        var prior=await disabled.OwnershipAsync(disabled.First);var sentinel=disabled.ContentHash(disabled.First);
        var source=Path.Combine(disabled.Root,"small-reentry-source");Directory.CreateDirectory(source);
        File.WriteAllText(Path.Combine(source,"Directory.Build.props"),"s206-disabled-owner-positive");
        bool started,firstSeeded,secondSeeded;
        await using(var host=await S206OwnedHost.StartAsync(disabled.Root,Guid.NewGuid().ToString("N"),repositoryRoot:source))
        {
            started=host.Started;
            firstSeeded=File.Exists(Path.Combine(disabled.First.Project.RepoPath,"Directory.Build.props"));
            var second=Path.Combine(disabled.Second.Project.RepoPath,"Directory.Build.props");
            secondSeeded=File.Exists(second)&&File.ReadAllText(second)=="s206-disabled-owner-positive";
        }
        return new {cases=rows,disabledOwner=new {started,firstSeeded,secondSeeded,
            unchanged=prior==await disabled.OwnershipAsync(disabled.First)&&sentinel==disabled.ContentHash(disabled.First),
            retained=await disabled.Store.GetProjectSnapshotAsync(disabled.First.Project.ProjectId) is not null}};
    }

    private static async Task<object> ObserveAsync(string root, PhaseAMetadataStore legacyStore)
    {
        Directory.CreateDirectory(root);
        var database = Path.Combine(root, "metadata.sqlite3");
        var first = await legacyStore.CreateUserAccountAsync("home-a", 2);
        var second = await legacyStore.CreateUserAccountAsync("home-b", 2);
        for (var index = 0; index < 4; index++)
            await legacyStore.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("synthetic-fixture-key-" + index, CredentialImported: true));
        var installedBeforeStartup = await ColumnsAsync(database, "accounts");
        var adminToken = Guid.NewGuid().ToString("N");
        var sessions = new List<object>();
        int adminListStatus, userAdminStatus, forgedCreateStatus, newStatus, disableStatus;
        JsonElement adminUsers = default;
        string? directAccountId = null;
        string? newAccountId = null;
        object initialState, changedState, faultBefore, faultAfter;
        bool projectionFaultReached = false;
        bool creationFaultReached = false;
        int? faultStatus = null;
        await using (var host = await S206OwnedHost.StartAsync(root, adminToken))
        {
            if (!host.Started) throw new InvalidOperationException("Valid persistence fixture host rejected startup.");
            var currentOptions = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
                ["PHASEA_METADATA_DB_PATH"] = database,
                ["PHASEA_NODE_ID"] = "test-physical-node",
                ["PHASEA_NODE_SCOPE"] = "single_node_test",
                ["PHASEA_NODE_TOPOLOGY"] = "single_service",
                ["PHASEA_ENABLED_ROLES"] = "entry,production",
                ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = "true"
            });
            var currentStore = new PhaseAMetadataStore("Data Source=" + database, currentOptions);
            using var admin = host.Client();
            using var a = host.Client(first.Token);
            using var b = host.Client(second.Token);
            foreach (var pair in new[] { (first.AccountId, a), (second.AccountId, b) })
            {
                using var response = await pair.Item2.GetAsync("/api/session?accountId=foreign&homeNodeId=foreign&nodeId=foreign");
                sessions.Add(new { accountId = pair.Item1, status = (int)response.StatusCode,
                    body = JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement.Clone() });
            }
            using (var response = await admin.GetAsync("/api/admin/users"))
            {
                adminListStatus = (int)response.StatusCode;
                adminUsers = JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement.Clone();
            }
            using (var response = await a.GetAsync("/api/admin/users")) userAdminStatus = (int)response.StatusCode;
            using (var response = await a.PostAsJsonAsync("/api/admin/users", new { username = "forged", projectLimit = 1, role = "admin", nodeId = "foreign", homeNodeId = "foreign" }))
                forgedCreateStatus = (int)response.StatusCode;
            using (var response = await admin.PostAsJsonAsync("/api/admin/users", new { username = "central-created", projectLimit = 1, nodeId = "foreign", homeNodeId = "foreign" }))
            {
                newStatus = (int)response.StatusCode;
                if (response.IsSuccessStatusCode)
                    newAccountId = JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement.GetProperty("accountId").GetString();
            }
            directAccountId = (await currentStore.CreateUserAccountAsync("direct-central", 1)).AccountId;
            initialState = await StateAsync(database);
            using (var response = await admin.PostAsJsonAsync("/api/admin/users/" + first.AccountId + "/status", new { disabled = true }))
                disableStatus = (int)response.StatusCode;
            changedState = await StateAsync(database);
            using (var response = await admin.PostAsJsonAsync("/api/admin/users/" + first.AccountId + "/status", new { disabled = false }))
                _ = await response.Content.ReadAsStringAsync();
            faultBefore = await StateAsync(database);
            var projectionColumns = await ColumnsAsync(database, "account_node_projections");
            if (projectionColumns.Count > 0)
            {
                await using var connection = new SqliteConnection("Data Source=" + database);
                await connection.OpenAsync();
                await using var fault = connection.CreateCommand();
                fault.CommandText = "CREATE TRIGGER s206_projection_insert_fault BEFORE INSERT ON account_node_projections BEGIN SELECT RAISE(ABORT,'s206_owned_projection_fault'); END; CREATE TRIGGER s206_projection_update_fault BEFORE UPDATE ON account_node_projections BEGIN SELECT RAISE(ABORT,'s206_owned_projection_fault'); END;";
                await fault.ExecuteNonQueryAsync();
                try
                {
                    try { await currentStore.SetUserDisabledAsync(first.AccountId, true); }
                    catch (SqliteException exception) when (exception.Message.Contains("s206_owned_projection_fault", StringComparison.Ordinal))
                    {
                        projectionFaultReached = true;
                        faultStatus = exception.SqliteErrorCode;
                    }
                    try { await currentStore.CreateUserAccountAsync("interrupted-new", 1); }
                    catch (SqliteException exception) when (exception.Message.Contains("s206_owned_projection_fault", StringComparison.Ordinal))
                    {
                        creationFaultReached = true;
                    }
                }
                finally
                {
                    fault.CommandText = "DROP TRIGGER s206_projection_insert_fault; DROP TRIGGER s206_projection_update_fault;";
                    await fault.ExecuteNonQueryAsync();
                }
            }
            faultAfter = await StateAsync(database);
        }
        var beforeConflict = await StateAsync(database);
        var conflicts = new List<object>();
        foreach (var candidate in new[] { "other-physical-node", "TEST-PHYSICAL-NODE", " test-physical-node " })
        {
            await using var conflict = await S206OwnedHost.StartAsync(root, adminToken, nodeId: candidate);
            conflicts.Add(new { candidate, conflict.Started, state = await StateAsync(database) });
        }
        int falsePolicyStatus;
        int falsePolicyControlStatus;
        string? falsePolicyAccountId = null;
        await using (var host = await S206OwnedHost.StartAsync(root, adminToken, acceptNewAccounts: false))
        {
            if (!host.Started) throw new InvalidOperationException("Policy-false fixture lost valid existing entry duties.");
            using var admin = host.Client();
            using (var control = await admin.GetAsync("/api/admin/users")) falsePolicyControlStatus = (int)control.StatusCode;
            using var response = await admin.PostAsJsonAsync("/api/admin/users", new { username = "policy-must-not-create", projectLimit = 1 });
            falsePolicyStatus = (int)response.StatusCode;
            if (response.IsSuccessStatusCode)
                falsePolicyAccountId = JsonDocument.Parse(await response.Content.ReadAsStringAsync()).RootElement.GetProperty("accountId").GetString();
        }
        var unsafeConsumers = new[] { "ArtifactReadbackService", "ProjectCreationService", "ProjectDraftImportService", "ProjectInitializationService", "ProjectInitializationRecoveryService", "ProjectWorkspaceMaintenanceService", "PrototypeWorkflowService", "ProjectWebPreviewService", "HostedProcessRunner", "SkillActionService", "ChatService" }
            .SelectMany(name => typeof(Program).Assembly.GetTypes().Where(type => type.Name == name))
            .Where(type => type.GetConstructors().Any(ctor => ctor.GetParameters().Any(parameter =>
                parameter.ParameterType == typeof(PhaseAMetadataStore) || parameter.ParameterType == typeof(PhaseAPlatformOptions) ||
                parameter.ParameterType == typeof(IServiceProvider) || parameter.ParameterType == typeof(SqliteConnection))))
            .Select(type => type.FullName).ToArray();
        return new
        {
            firstId = first.AccountId, secondId = second.AccountId, installedBeforeStartup, sessions,
            adminListStatus, adminUsers, userAdminStatus, forgedCreateStatus, newStatus, newAccountId, directAccountId,
            initialState, changedState, disableStatus, faultBefore, faultAfter, faultStatus, projectionFaultReached, creationFaultReached,
            beforeConflict, conflicts, falsePolicyStatus, falsePolicyControlStatus, falsePolicyAccountId,
            finalState = await StateAsync(database), unsafeConsumers
        };
    }

    private static async Task<List<object>> ColumnsAsync(string database, string table)
    {
        if (table is not "accounts" and not "account_node_projections") throw new ArgumentException("Unknown fixture table.");
        var rows = new List<object>();
        await using var connection = new SqliteConnection("Data Source=" + database);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "PRAGMA table_info(" + table + ");";
        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync()) rows.Add(new { name = reader.GetString(1), notNull = reader.GetInt64(3) != 0 });
        return rows;
    }

    private static async Task<object> StateAsync(string database)
    {
        await using var connection = new SqliteConnection("Data Source=" + database);
        await connection.OpenAsync();
        var columns = new HashSet<string>(StringComparer.Ordinal);
        await using (var command = connection.CreateCommand())
        {
            command.CommandText = "PRAGMA table_info(accounts);";
            await using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync()) columns.Add(reader.GetString(1));
        }
        var accounts = new List<Dictionary<string, object?>>();
        await using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT id,is_disabled," + (columns.Contains("home_node_id") ? "home_node_id" : "NULL AS home_node_id") +
                "," + (columns.Contains("authority_revision") ? "authority_revision" : "NULL AS authority_revision") + " FROM accounts ORDER BY id;";
            await using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync()) accounts.Add(Enumerable.Range(0, reader.FieldCount).ToDictionary(reader.GetName,
                index => reader.IsDBNull(index) ? null : reader.GetValue(index)));
        }
        var projections = new List<Dictionary<string, object?>>();
        await using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='account_node_projections';";
            if (Convert.ToInt64(await command.ExecuteScalarAsync()) > 0)
            {
                command.CommandText = "SELECT account_id,home_node_id,is_enabled,authority_revision FROM account_node_projections ORDER BY account_id;";
                await using var reader = await command.ExecuteReaderAsync();
                while (await reader.ReadAsync()) projections.Add(Enumerable.Range(0, reader.FieldCount).ToDictionary(reader.GetName,
                    index => reader.IsDBNull(index) ? null : reader.GetValue(index)));
            }
        }
        return new { accounts, projections };
    }
}
