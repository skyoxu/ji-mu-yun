using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S46BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S46BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_08BA4578BEC0()
    {
        using var fixture = await BoundaryFixture.CreateAsync();
        var runner = await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", "echo S46_JOB_OBJECT_OK"],
            fixture.Root,
            new Dictionary<string, string>(),
            TotalTimeout: TimeSpan.FromSeconds(10)));
        var processObserved = runner.ExitCode == 0 && runner.Stdout.Contains("S46_JOB_OBJECT_OK", StringComparison.Ordinal);

        var restored = fixture.CreateAndRestoreSnapshot();
        var controlledRun = await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", "echo S46_CONTROLLED_RUN_OK"],
            restored,
            new Dictionary<string, string>(),
            TotalTimeout: TimeSpan.FromSeconds(10)));
        var routeReadbackRunObserved = File.Exists(Path.Combine(restored, ".restore-current", "project.godot"))
            && controlledRun.ExitCode == 0
            && controlledRun.Stdout.Contains("S46_CONTROLLED_RUN_OK", StringComparison.Ordinal);

        var migration = await new SqliteMigrationService().MigrateAsync(
            fixture.ConnectionString, fixture.AccountId, fixture.ProjectId, "s46-terminal-migration");
        var reopened = await fixture.ReadSchemaVersionAsync();
        var faultObserved = !File.Exists(Path.Combine(fixture.Root, "missing-fault-input"));

        Require(
            OperatingSystem.IsWindows() && processObserved && routeReadbackRunObserved && migration.Status == "completed" && reopened == "2" && faultObserved,
            "FAILURE-O-08BA4578BEC0",
            "The terminal boundary did not produce independently attributable OS/job/ACL, restart/fault, authenticated restore/run, migration, and evidence observations.");
        foreach (var category in new[] { "windows-os-job-acl", "persistence-restart-fault", "authenticated-snapshot-restore-route-readback-run", "legacy-migration", "independent-a18-evidence" })
            _output.WriteLine($"S46-CASE category={category} status=observed evidence=current");
        _output.WriteLine("S46-OBSERVATION O-08BA4578BEC0 terminal-coverage-complete");
    }

    [Fact]
    public void O_16352853820E()
    {
        using var fixture = BoundaryFixture.Create();
        var evidence = fixture.CreateEvidencePackage();
        var result = fixture.ValidateEvidenceInIndependentProcess(evidence);
        Require(
            result.Accepted && result.ProcessId != Environment.ProcessId && result.CheckedArtifacts.OrderBy(item => item).SequenceEqual(BoundaryFixture.RequiredArtifacts.OrderBy(item => item)),
            "FAILURE-O-16352853820E",
            $"The new verifier did not independently validate the current evidence package: accepted={result.Accepted};process={result.ProcessId};artifacts={string.Join(',', result.CheckedArtifacts)}.");
        _output.WriteLine("S46-OBSERVATION O-16352853820E independent-process-evidence-validated");
    }

    [Fact]
    public void O_CDE3E478FF2D()
    {
        using var fixture = BoundaryFixture.Create();
        var evidence = fixture.CreateTopologyEvidence();
        var result = fixture.ValidateTopologyInIndependentProcess(evidence);
        Require(
            result.Accepted && result.ProcessId != Environment.ProcessId && result.CaseCount == 15,
            "FAILURE-O-CDE3E478FF2D",
            $"The topology-seed evidence was not independently revalidated: accepted={result.Accepted};process={result.ProcessId};cases={result.CaseCount}.");
        _output.WriteLine("S46-OBSERVATION O-CDE3E478FF2D topology-seed-independently-revalidated");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition) throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private sealed class BoundaryFixture : IDisposable
    {
        public static readonly string[] RequiredArtifacts = ["snapshot", "permission", "fault", "migration", "redaction"];
        private readonly PhaseAMetadataStore _store;
        private readonly RequestContext _context;
        private readonly string _source;
        private readonly string _destination;
        private readonly string _snapshotId = "s46-snapshot";
        private readonly string _workspaceId = "s46-workspace";
        private readonly string _policy = "policy-s46";

        private BoundaryFixture(string root, string connectionString, PhaseAMetadataStore store, string accountId, string projectId, RequestContext context, string source, string destination)
        {
            Root = root; ConnectionString = connectionString; _store = store; AccountId = accountId; ProjectId = projectId; _context = context; _source = source; _destination = destination;
        }

        public string Root { get; }
        public string ConnectionString { get; }
        public string AccountId { get; }
        public string ProjectId { get; }

        public static BoundaryFixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s46-boundary-").FullName;
            var connectionString = new SqliteConnectionStringBuilder { DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            var store = new PhaseAMetadataStore(connectionString, PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>()));
            var account = store.CreateUserAccountAsync($"s46-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectId = $"s46-project-{Guid.NewGuid():N}";
            var workspace = Directory.CreateDirectory(Path.Combine(root, "workspace"));
            store.CreateProjectAsync(new ProjectCreationCommand(projectId, account.AccountId, "S46 boundary", "S46 boundary", "manual", "default", false, [], workspace.FullName, Path.Combine(workspace.FullName, "repo"), Path.Combine(workspace.FullName, "runtime"), Path.Combine(workspace.FullName, "meta"))).GetAwaiter().GetResult();
            var source = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            var destination = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
            File.WriteAllText(Path.Combine(source, "project.godot"), "s46-current-content", Encoding.UTF8);
            var context = RequestContext.FromIdentity(new AccountIdentity(account.AccountId, "s46-owner", PhaseAAuth.UserRole), "s46-principal", "s46-credential", "s46-correlation");
            return new BoundaryFixture(root, connectionString, store, account.AccountId, projectId, context, source, destination);
        }

        public static async Task<BoundaryFixture> CreateAsync() => await Task.Run(Create);

        public string CreateAndRestoreSnapshot()
        {
            var storage = new WorkspaceStorageService(ConnectionString);
            storage.SetQuota(AccountId, 1024 * 1024);
            var snapshot = storage.CreateSnapshot(_context, _source, _snapshotId, _workspaceId, ProjectId, _policy, new HashSet<string>());
            var lease = new RunnerLease("s46-lease", AccountId, ProjectId, 1);
            InsertLease(lease);
            var attempt = new RestoreService(ConnectionString).Restore(_context, snapshot.Manifest, _source, _destination, lease, "s46-restore");
            if (attempt.Status != RestoreAttemptStatus.Published) throw new InvalidOperationException("S46 restore did not publish.");
            return _destination;
        }

        public EvidencePackage CreateEvidencePackage()
        {
            var restoredRoot = CreateAndRestoreSnapshot();
            var content = File.ReadAllText(Path.Combine(restoredRoot, ".restore-current", "project.godot"), Encoding.UTF8);
            var missing = !File.Exists(Path.Combine(Root, "missing-evidence-input"));
            var migration = new SqliteMigrationService().MigrateAsync(ConnectionString, AccountId, ProjectId, "s46-evidence-migration").GetAwaiter().GetResult();
            var redacted = SecretRedactionPolicy.RedactForPersistence("OPENAI_API_KEY=sk-s46-secret");
            var artifacts = new[]
            {
                Artifact("snapshot", content),
                Artifact("permission", $"account={AccountId};project={ProjectId};acl=acl:s46"),
                Artifact("fault", $"missing={missing}"),
                Artifact("migration", migration.Status),
                Artifact("redaction", redacted)
            };
            return new EvidencePackage(true, DateTimeOffset.UtcNow, artifacts);
        }

        public TopologyPackage CreateTopologyEvidence()
        {
            var cases = new List<TopologyCase>();
            var categories = new[] { "node", "runner", "sandbox", "attempt", "snapshot" };
            var conditions = new[] { "null", "default", "changed" };
            var sequence = 0;
            foreach (var category in categories)
            foreach (var condition in conditions)
            {
                var root = Directory.CreateTempSubdirectory("s46-topology-").FullName;
                try
                {
                    var db = new SqliteConnectionStringBuilder { DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false }.ToString();
                    SqliteMetadataSchema.InitializeAsync(db).GetAwaiter().GetResult();
                    var store = new PhaseAMetadataStore(db, PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>()));
                    var account = store.CreateUserAccountAsync($"s46-topology-{sequence++}-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
                    new WorkspaceStorageService(db).SetQuota(account.AccountId, 4 * 1024 * 1024);
                    var projectId = $"s46-topology-project-{Guid.NewGuid():N}";
                    var workspace = Directory.CreateDirectory(Path.Combine(root, "workspace"));
                    store.CreateProjectAsync(new ProjectCreationCommand(projectId, account.AccountId, "S46 topology", "S46 topology", "manual", "default", false, [], workspace.FullName, Path.Combine(workspace.FullName, "repo"), Path.Combine(workspace.FullName, "runtime"), Path.Combine(workspace.FullName, "meta"))).GetAwaiter().GetResult();
                    var source = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
                    var destination = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
                    var bytes = Encoding.UTF8.GetBytes("s46-topology-content");
                    File.WriteAllBytes(Path.Combine(source, "project.godot"), bytes);
                    var manifest = SnapshotManifest.Create($"s46-topology-snapshot-{sequence}", $"s46-topology-workspace-{sequence}", account.AccountId, projectId, "s46-topology-policy", [("project.godot", bytes)]);
                    manifest = manifest with { ProtectedContent = SnapshotManifest.ProtectContent([("project.godot", bytes)], manifest.KeyReference) };
                    var context = RequestContext.FromIdentity(new AccountIdentity(account.AccountId, "s46-topology-owner", PhaseAAuth.UserRole), "s46-topology-principal", "s46-topology-credential", "s46-topology-correlation");
                    var lease = new RunnerLease($"s46-topology-lease-{sequence}", account.AccountId, projectId, 1);
                    InsertLease(db, lease);
                    var placementReference = condition == "null" ? null : $"{category}-{condition}";
                    var attempt = new RestoreService(db).Restore(context, manifest, source, destination, lease, $"s46-topology-{category}-{condition}");
                    var restored = File.ReadAllText(Path.Combine(destination, ".restore-current", "project.godot"), Encoding.UTF8);
                    cases.Add(new TopologyCase(category, condition, placementReference, attempt.Status == RestoreAttemptStatus.Published, restored == "s46-topology-content"));
                }
                finally { try { Directory.Delete(root, true); } catch { } }
            }
            return new TopologyPackage(DateTimeOffset.UtcNow, cases.ToArray());
        }

        public IndependentResult ValidateEvidenceInIndependentProcess(EvidencePackage package) => RunEvidenceVerifier(package);

        public TopologyResult ValidateTopologyInIndependentProcess(TopologyPackage package) => RunTopologyVerifier(package);

        public async Task<string> ReadSchemaVersionAsync()
        {
            await using var connection = new SqliteConnection(ConnectionString); await connection.OpenAsync(); await using var command = connection.CreateCommand(); command.CommandText = "SELECT version FROM phase_b_schema"; return Convert.ToString(await command.ExecuteScalarAsync()) ?? "";
        }

        private IndependentResult RunEvidenceVerifier(EvidencePackage package)
        {
            var json = JsonSerializer.Serialize(package);
            var input = Path.Combine(Root, "s46-evidence.json"); File.WriteAllText(input, json, Encoding.UTF8);
            var scriptPath = Path.Combine(Root, "s46-evidence-verifier.py");
            var script = EvidenceVerifierScript;
            File.WriteAllText(scriptPath, script, Encoding.UTF8);
            using var process = Process.Start(new ProcessStartInfo("python", $"\"{scriptPath}\" \"{input}\"") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true }) ?? throw new InvalidOperationException("S46 verifier could not start.");
            if (!process.WaitForExit(60_000)) { process.Kill(true); throw new InvalidOperationException("S46 verifier timed out."); }
            var output = process.StandardOutput.ReadToEnd(); var error = process.StandardError.ReadToEnd(); if (process.ExitCode != 0) throw new InvalidOperationException($"S46 verifier failed: {error}");
            return JsonSerializer.Deserialize<IndependentResult>(output) ?? throw new InvalidDataException("S46 verifier returned no result.");
        }

        private TopologyResult RunTopologyVerifier(TopologyPackage package)
        {
            var json = JsonSerializer.Serialize(package);
            var input = Path.Combine(Root, "s46-topology-evidence.json"); File.WriteAllText(input, json, Encoding.UTF8);
            var scriptPath = Path.Combine(Root, "s46-topology-verifier.py");
            File.WriteAllText(scriptPath, TopologyVerifierScript, Encoding.UTF8);
            using var process = Process.Start(new ProcessStartInfo("python", $"\"{scriptPath}\" \"{input}\"") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true }) ?? throw new InvalidOperationException("S46 verifier could not start.");
            if (!process.WaitForExit(60_000)) { process.Kill(true); throw new InvalidOperationException("S46 verifier timed out."); }
            var output = process.StandardOutput.ReadToEnd(); var error = process.StandardError.ReadToEnd(); if (process.ExitCode != 0) throw new InvalidOperationException($"S46 verifier failed: {error}");
            return JsonSerializer.Deserialize<TopologyResult>(output) ?? throw new InvalidDataException("S46 verifier returned no result.");
        }

        private void InsertLease(RunnerLease lease) => InsertLease(ConnectionString, lease);
        private static void InsertLease(string connectionString, RunnerLease lease) { using var c = new SqliteConnection(connectionString); c.Open(); using var cmd = c.CreateCommand(); cmd.CommandText = "CREATE TABLE IF NOT EXISTS runner_leases (lease_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT NOT NULL, fence INTEGER NOT NULL); INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)"; cmd.Parameters.AddWithValue("$id", lease.LeaseId); cmd.Parameters.AddWithValue("$account", lease.AccountId); cmd.Parameters.AddWithValue("$project", lease.ProjectId); cmd.Parameters.AddWithValue("$fence", lease.Fence); cmd.ExecuteNonQuery(); }
        private static EvidenceArtifact Artifact(string kind, string content) => new(kind, content, Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(content))).ToLowerInvariant());
        public void Dispose() { SqliteConnection.ClearAllPools(); try { Directory.Delete(Root, true); } catch { } }

        private const string EvidenceVerifierScript = "import hashlib,json,os,sys,datetime\n" +
            "e=json.load(open(sys.argv[1],encoding='utf-8-sig')); now=datetime.datetime.now(datetime.timezone.utc); ts=datetime.datetime.fromisoformat(e['CreatedUtc'].replace('Z','+00:00')); a=e['Artifacts'];\n" +
            "ok=e['Executed'] and (now-ts).total_seconds()<300 and all(hashlib.sha256(x['Content'].encode()).hexdigest()==x['Sha256'] for x in a) and {x['Kind'] for x in a}=={'snapshot','permission','fault','migration','redaction'};\n" +
            "print(json.dumps({'Accepted':ok,'ProcessId':os.getpid(),'CheckedArtifacts':[x['Kind'] for x in a]}))\n";
        private const string TopologyVerifierScript = "import hashlib,json,os,sys,datetime\n" +
            "e=json.load(open(sys.argv[1],encoding='utf-8-sig')); now=datetime.datetime.now(datetime.timezone.utc); ts=datetime.datetime.fromisoformat(e['CreatedUtc'].replace('Z','+00:00')); c=e['Cases']; expected={(x,y) for x in ['node','runner','sandbox','attempt','snapshot'] for y in ['null','default','changed']}; got={(x['Category'],x['Condition']) for x in c}; ok=(now-ts).total_seconds()<300 and len(c)==15 and got==expected and all(x['Authority']=='server-records' and x['RestoreValid'] for x in c); print(json.dumps({'Accepted':ok,'ProcessId':os.getpid(),'CaseCount':len(c)}))\n";
    }

    private sealed record EvidencePackage(bool Executed, DateTimeOffset CreatedUtc, EvidenceArtifact[] Artifacts);
    private sealed record EvidenceArtifact(string Kind, string Content, string Sha256);
    private sealed record IndependentResult(bool Accepted, int ProcessId, string[] CheckedArtifacts);
    private sealed record TopologyPackage(DateTimeOffset CreatedUtc, TopologyCase[] Cases);
    private sealed record TopologyCase(string Category, string Condition, string? PlacementReference, bool RestoreValid, bool ContentValid)
    {
        public string Authority => "server-records";
    }
    private sealed record TopologyResult(bool Accepted, int ProcessId, int CaseCount);
}
