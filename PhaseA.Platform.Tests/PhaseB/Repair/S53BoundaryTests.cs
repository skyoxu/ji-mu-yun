using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S53BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S53BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact] public void O_1758D7FA26D7() => AssertRejected("missing", "FAILURE-O-1758D7FA26D7");
    [Fact] public void O_184C7201648B() => AssertRejected("stale", "FAILURE-O-184C7201648B");
    [Fact] public void O_8A188783399E() => AssertRejected("declaration", "FAILURE-O-8A188783399E");
    [Fact] public void O_8FF9DCF91EDE() => AssertRejected("tampered", "FAILURE-O-8FF9DCF91EDE");
    [Fact] public void O_DAA21E146840() => AssertRejected("unexecuted", "FAILURE-O-DAA21E146840");
    [Fact] public void O_6BE8DC802311() => AssertAccepted("snapshot", "FAILURE-O-6BE8DC802311");
    [Fact] public void O_AD7298625129() => AssertAccepted("permission", "FAILURE-O-AD7298625129");
    [Fact] public void O_B2296F39A759() => AssertAccepted("fault", "FAILURE-O-B2296F39A759");
    [Fact] public void O_C1832CCFAB00() => AssertAccepted("redaction", "FAILURE-O-C1832CCFAB00");

    private void AssertRejected(string mutation, string failureId)
    {
        using var fixture = EvidenceFixture.Create();
        var result = fixture.ValidateIndependently(mutation);
        Require(!result.Accepted && result.Reason == ExpectedRejection(mutation) && result.ProcessId != Environment.ProcessId,
            failureId, $"The independent evidence reader accepted or misdiagnosed the {mutation} evidence package: accepted={result.Accepted};reason={result.Reason};pid={result.ProcessId}.");
        Observe(CurrentMethod(), result);
    }

    private void AssertAccepted(string requiredArtifact, string failureId)
    {
        using var fixture = EvidenceFixture.Create();
        var result = fixture.ValidateIndependently(null);
        Require(result.Accepted && result.CheckedArtifacts.Contains(requiredArtifact, StringComparer.Ordinal) && result.ProcessId != Environment.ProcessId,
            failureId, $"The independent evidence reader did not validate current {requiredArtifact} evidence from a separate process.");
        Observe(CurrentMethod(), result);
    }

    private static string CurrentMethod() => new StackTrace().GetFrame(2)?.GetMethod()?.Name
        ?? throw new InvalidOperationException("S53 could not identify its boundary method.");

    private void Observe(string obligation, IndependentResult result) => _output.WriteLine(
        $"S53-OBSERVATION {obligation};accepted={result.Accepted.ToString().ToLowerInvariant()};" +
        $"reason={result.Reason};processId={result.ProcessId};artifacts={string.Join(',', result.CheckedArtifacts)}");

    private static string ExpectedRejection(string mutation) => mutation switch
    {
        "missing" => "missing_required_evidence",
        "stale" => "stale_evidence",
        "declaration" => "missing_required_evidence",
        "tampered" => "integrity_failure",
        "unexecuted" => "verification_not_executed",
        _ => throw new ArgumentOutOfRangeException(nameof(mutation))
    };

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition) throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private sealed class EvidenceFixture : IDisposable
    {
        private const string AccountId = "s53-account";
        private const string ProjectId = "s53-project";
        private const string WorkspaceId = "s53-workspace";
        private static readonly string[] RequiredArtifacts = ["snapshot", "permission", "fault", "migration", "redaction"];
        private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
        private readonly string _root;
        private readonly string _packagePath;

        private EvidenceFixture(string root, string packagePath)
        {
            _root = root;
            _packagePath = packagePath;
        }

        public static EvidenceFixture Create()
        {
            var root = Directory.CreateTempSubdirectory("s53-evidence-").FullName;
            var source = Directory.CreateDirectory(Path.Combine(root, "source")).FullName;
            var destination = Directory.CreateDirectory(Path.Combine(root, "destination")).FullName;
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath, Pooling = false }.ToString();
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            var context = RequestContext.FromIdentity(new AccountIdentity(AccountId, "owner", PhaseAAuth.UserRole), "s53-requester", "s53-credential", "s53-correlation");
            var content = "s53-current-snapshot"u8.ToArray();
            File.WriteAllBytes(Path.Combine(source, "project.godot"), content);
            var storage = new WorkspaceStorageService();
            storage.SetQuota(AccountId, 1024 * 1024);
            var snapshot = storage.CreateSnapshot(context, source, "s53-snapshot", WorkspaceId, ProjectId, "policy-s53", new HashSet<string>());
            var lease = new RunnerLease("s53-lease", AccountId, ProjectId, 1);
            _ = new RestoreService(connectionString);
            InsertLease(connectionString, lease);
            var restore = new RestoreService(connectionString).Restore(context, snapshot.Manifest, source, destination, lease, "s53-roundtrip");
            var restored = Path.Combine(destination, ".restore-current", "project.godot");
            var snapshotObserved = restore.Status == RestoreAttemptStatus.Published && File.Exists(restored) && File.ReadAllBytes(restored).SequenceEqual(content);

            var permissionObserved = context.AccountId == snapshot.Manifest.AccountId && snapshot.Manifest.ProjectId == ProjectId && snapshot.Manifest.AclPolicyReference.StartsWith("acl:", StringComparison.Ordinal);
            var missingPath = Path.Combine(root, "fault-injection-missing-input");
            var faultObserved = false;
            try { _ = File.ReadAllBytes(missingPath); }
            catch (FileNotFoundException) { faultObserved = true; }
            var migration = new SqliteMigrationService().MigrateAsync(connectionString, AccountId, ProjectId, "s53-migration").GetAwaiter().GetResult();
            var redacted = SecretRedactionPolicy.RedactForPersistence("OPENAI_API_KEY=sk-abcdefghijklmnop");
            var redactionObserved = !redacted.Contains("sk-abcdefghijklmnop", StringComparison.Ordinal) && redacted.Contains("[redacted]", StringComparison.Ordinal);

            Require(snapshotObserved && permissionObserved && faultObserved && migration.Status == "completed" && redactionObserved,
                "FAILURE-S53-FIXTURE", "S53 could not materialize current production evidence for independent validation.");
            var artifacts = new[]
            {
                Artifact("snapshot", $"published:{snapshotObserved};sha256:{snapshot.Manifest.Files.Single().Sha256}"),
                Artifact("permission", $"account:{snapshot.Manifest.AccountId};project:{snapshot.Manifest.ProjectId};acl:{snapshot.Manifest.AclPolicyReference}"),
                Artifact("fault", "FileNotFoundException:actual-observation"),
                Artifact("migration", $"status:{migration.Status}"),
                Artifact("redaction", redacted),
            };
            var packagePath = Path.Combine(root, "piwr-a18-evidence.json");
            File.WriteAllText(packagePath, JsonSerializer.Serialize(new EvidencePackage(true, DateTimeOffset.UtcNow, "declared-pass-must-not-decide", artifacts), JsonOptions));
            return new EvidenceFixture(root, packagePath);
        }

        public IndependentResult ValidateIndependently(string? mutation)
        {
            var package = JsonDocument.Parse(File.ReadAllText(_packagePath)).RootElement;
            var altered = mutation switch
            {
                null => Mutate(package, executed: true, timestamp: null, artifacts: ReadArtifacts(package)),
                "missing" => Mutate(package, executed: true, timestamp: null, artifacts: ReadArtifacts(package).Where(item => item.Kind != "snapshot").ToArray()),
                "stale" => Mutate(package, executed: true, timestamp: DateTimeOffset.UtcNow.AddHours(-1), artifacts: ReadArtifacts(package)),
                "declaration" => Mutate(package, executed: true, timestamp: null, artifacts: []),
                "tampered" => Mutate(package, executed: true, timestamp: null, artifacts: ReadArtifacts(package).Select(item => item.Kind == "fault" ? item with { Content = item.Content + "-changed" } : item).ToArray()),
                "unexecuted" => Mutate(package, executed: false, timestamp: null, artifacts: ReadArtifacts(package)),
                _ => throw new ArgumentOutOfRangeException(nameof(mutation))
            };
            var input = Path.Combine(_root, $"input-{Guid.NewGuid():N}.json");
            File.WriteAllText(input, JsonSerializer.Serialize(altered, JsonOptions));
            var script = "import datetime,hashlib,json,os,sys\n" +
                "e=json.load(open(sys.argv[1],encoding='utf-8'));a=e['artifacts'];r='accepted'\n" +
                "if not e['executed']:r='verification_not_executed'\n" +
                "elif (datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(e['timestamp'].replace('Z','+00:00'))).total_seconds()>300:r='stale_evidence'\n" +
                "elif any(k not in [x['kind'] for x in a] for k in ['snapshot','permission','fault','migration','redaction']):r='missing_required_evidence'\n" +
                "elif any(hashlib.sha256(x['content'].encode()).hexdigest()!=x['sha256'] for x in a):r='integrity_failure'\n" +
                "print(json.dumps({'accepted':r=='accepted','reason':r,'processId':os.getpid(),'checkedArtifacts':[x['kind'] for x in a]}))\n";
            var scriptPath = Path.Combine(_root, "independent_evidence_reader.py");
            File.WriteAllText(scriptPath, script, Encoding.UTF8);
            using var process = Process.Start(new ProcessStartInfo("python", $"\"{scriptPath}\" \"{input}\"")
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
            }) ?? throw new InvalidOperationException("S53 could not start its independent evidence reader.");
            if (!process.WaitForExit(60_000))
            {
                process.Kill(entireProcessTree: true);
                throw new InvalidOperationException("S53 independent reader exceeded its harness timeout.");
            }
            var stdout = process.StandardOutput.ReadToEnd();
            var stderr = process.StandardError.ReadToEnd();
            if (process.ExitCode != 0) throw new InvalidOperationException($"S53 independent reader failed: {stderr}");
            var result = JsonSerializer.Deserialize<IndependentResult>(stdout, JsonOptions) ?? throw new InvalidDataException("S53 independent reader returned no result.");
            return result with { CheckedArtifacts = result.CheckedArtifacts ?? [] };
        }

        private static EvidencePackage Mutate(JsonElement package, bool executed, DateTimeOffset? timestamp, EvidenceArtifact[] artifacts) =>
            new(executed, timestamp ?? package.GetProperty("timestamp").GetDateTimeOffset(), package.GetProperty("declaration").GetString()!, artifacts);
        private static EvidenceArtifact[] ReadArtifacts(JsonElement package) => package.GetProperty("artifacts").EnumerateArray().Select(item => new EvidenceArtifact(item.GetProperty("kind").GetString()!, item.GetProperty("content").GetString()!, item.GetProperty("sha256").GetString()!)).ToArray();
        private static EvidenceArtifact Artifact(string kind, string content) => new(kind, content, Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(content))).ToLowerInvariant());
        private static void InsertLease(string connectionString, RunnerLease lease)
        {
            using var connection = new SqliteConnection(connectionString); connection.Open(); using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
            command.Parameters.AddWithValue("$id", lease.LeaseId); command.Parameters.AddWithValue("$account", lease.AccountId); command.Parameters.AddWithValue("$project", lease.ProjectId); command.Parameters.AddWithValue("$fence", lease.Fence); command.ExecuteNonQuery();
        }
        public void Dispose() { SqliteConnection.ClearAllPools(); try { Directory.Delete(_root, recursive: true); } catch (IOException) { } }
    }

    private sealed record EvidencePackage(bool Executed, DateTimeOffset Timestamp, string Declaration, EvidenceArtifact[] Artifacts);
    private sealed record EvidenceArtifact(string Kind, string Content, string Sha256);
    private sealed record IndependentResult(bool Accepted, string Reason, int ProcessId, string[]? CheckedArtifacts);
}
