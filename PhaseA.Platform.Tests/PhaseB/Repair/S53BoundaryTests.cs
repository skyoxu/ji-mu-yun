using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
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

    [Fact]
    public async Task O_A18_PERSISTED_PLATFORM_RUN_BINDING()
    {
        var root = Directory.CreateTempSubdirectory("s53-persisted-run-").FullName;
        try
        {
            var database = Path.Combine(root, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = root });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = await store.CreateUserAccountAsync("s53-run-owner", 1);
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                "s53-run-project", account.AccountId, "S53", "S53", "manual", "default", false, [],
                projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta")));
            Require(project.Succeeded && project.ProjectId is not null, "FAILURE-S53-PERSISTED-SETUP", "S53 persisted-run project setup failed.");

            var package = Path.Combine(root, "evidence.json");
            var artifacts = new List<object>();
            foreach (var kind in new[] { "snapshot", "permission", "fault", "migration", "redaction" })
            {
                var relative = Path.Combine("artifacts", kind + ".txt");
                var path = Path.Combine(root, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                var content = "persisted-run:" + kind;
                File.WriteAllText(path, content);
                artifacts.Add(new { kind, path = relative, content, sha256 = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(content))).ToLowerInvariant() });
            }
            string workspaceId;
            await using (var workspaceConnection = new SqliteConnection(connectionString))
            {
                await workspaceConnection.OpenAsync();
                await using var workspaceCommand = workspaceConnection.CreateCommand();
                workspaceCommand.CommandText = "SELECT id FROM workspaces WHERE project_id = $project";
                workspaceCommand.Parameters.AddWithValue("$project", project.ProjectId!);
                workspaceId = (string?)await workspaceCommand.ExecuteScalarAsync() ?? throw new InvalidOperationException("S53 workspace row was not created.");
            }
            var runId = (await store.GetOrCreateProjectOperationRunAsync(project.ProjectId!, workspaceId, "s53-evidence")).RunId;
            await store.TryMarkRunStartedAsync(runId, null);
            var evidence = JsonSerializer.Serialize(new { producerRunId = runId });
            await store.CompleteRunAsync(runId, "succeeded", 0, "", "", evidence);
            File.WriteAllText(package, JsonSerializer.Serialize(new { executed = true, producerRunId = runId, timestamp = DateTimeOffset.UtcNow, artifacts }));

            using var process = Process.Start(new ProcessStartInfo("dotnet", $"\"{typeof(Program).Assembly.Location}\" --independent-evidence-run \"{package}\" {runId} \"{database}\"")
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
            }) ?? throw new InvalidOperationException("S53 persisted evidence reader did not start.");
            await process.WaitForExitAsync();
            var output = await process.StandardOutput.ReadToEndAsync();
            Require(process.ExitCode == 0, "FAILURE-S53-PERSISTED-RUN", "Independent persisted-run reader failed: " + await process.StandardError.ReadToEndAsync());
            using var result = JsonDocument.Parse(output);
            var accepted = result.RootElement.TryGetProperty("Accepted", out var acceptedNode)
                ? acceptedNode.GetBoolean()
                : result.RootElement.GetProperty("accepted").GetBoolean();
            Require(accepted, "FAILURE-S53-PERSISTED-RUN", "Persisted platform run was not accepted by the independent reader.");
            Observe("O-A18-PERSISTED-PLATFORM-RUN", new IndependentResult(true, "accepted", process.Id, []));
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(root, recursive: true); } catch (IOException) { }
        }
    }

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
            // ADR-0061: exercise evidence validation with production account and project metadata.
            SqliteMetadataSchema.InitializeAsync(connectionString).GetAwaiter().GetResult();
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = store.CreateUserAccountAsync($"s53-user-{Guid.NewGuid():N}", 1).GetAwaiter().GetResult();
            var projectRoot = Directory.CreateDirectory(Path.Combine(root, "project"));
            _ = store.CreateProjectAsync(new ProjectCreationCommand(
                ProjectId, account.AccountId, "S53 boundary", "S53 boundary", "manual", "default", false, [],
                projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"),
                Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta"))).GetAwaiter().GetResult();
            var context = RequestContext.FromIdentity(new AccountIdentity(account.AccountId, "owner", PhaseAAuth.UserRole), "s53-requester", "s53-credential", "s53-correlation");
            var content = "s53-current-snapshot"u8.ToArray();
            File.WriteAllBytes(Path.Combine(source, "project.godot"), content);
            var storage = new WorkspaceStorageService();
            storage.SetQuota(account.AccountId, 1024 * 1024);
            var snapshot = storage.CreateSnapshot(context, source, "s53-snapshot", WorkspaceId, ProjectId, "policy-s53", new HashSet<string>());
            var lease = new RunnerLease("s53-lease", account.AccountId, ProjectId, 1);
            _ = new RestoreService(connectionString);
            InsertLease(connectionString, lease);
            InsertRouteAuthority(connectionString);
            var restore = new RestoreService(connectionString).Restore(context, snapshot.Manifest, source, destination, lease, "s53-roundtrip");
            var restored = Path.Combine(destination, ".restore-current", "project.godot");
            var snapshotObserved = restore.Status == RestoreAttemptStatus.Published && File.Exists(restored) && File.ReadAllBytes(restored).SequenceEqual(content);

            var permissionObserved = context.AccountId == snapshot.Manifest.AccountId && snapshot.Manifest.ProjectId == ProjectId && snapshot.Manifest.AclPolicyReference.StartsWith("acl:", StringComparison.Ordinal);
            var missingPath = Path.Combine(root, "fault-injection-missing-input");
            var faultObserved = false;
            try { _ = File.ReadAllBytes(missingPath); }
            catch (FileNotFoundException) { faultObserved = true; }
            var migration = new SqliteMigrationService().MigrateAsync(connectionString, account.AccountId, ProjectId, "s53-migration").GetAwaiter().GetResult();
            var redacted = SecretRedactionPolicy.RedactForPersistence("OPENAI_API_KEY=sk-abcdefghijklmnop");
            var redactionObserved = !redacted.Contains("sk-abcdefghijklmnop", StringComparison.Ordinal) && redacted.Contains("[redacted]", StringComparison.Ordinal);

            Require(snapshotObserved && permissionObserved && faultObserved && migration.Status == "completed" && redactionObserved,
                "FAILURE-S53-FIXTURE", "S53 could not materialize current production evidence for independent validation.");
            var artifacts = new[]
            {
                Artifact(root, "snapshot", $"published:{snapshotObserved};sha256:{snapshot.Manifest.Files.Single().Sha256}"),
                Artifact(root, "permission", $"account:{snapshot.Manifest.AccountId};project:{snapshot.Manifest.ProjectId};acl:{snapshot.Manifest.AclPolicyReference}"),
                Artifact(root, "fault", "FileNotFoundException:actual-observation"),
                Artifact(root, "migration", $"status:{migration.Status}"),
                Artifact(root, "redaction", redacted),
            };
            var packagePath = Path.Combine(root, "piwr-a18-evidence.json");
            File.WriteAllText(packagePath, JsonSerializer.Serialize(new EvidencePackage(true, DateTimeOffset.UtcNow, "s53-roundtrip", "declared-pass-must-not-decide", artifacts), JsonOptions));
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
            using var process = Process.Start(new ProcessStartInfo("dotnet", $"\"{typeof(Program).Assembly.Location}\" --independent-evidence-reader \"{input}\" s53-roundtrip")
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
            new(executed, timestamp ?? package.GetProperty("timestamp").GetDateTimeOffset(), package.GetProperty("producerRunId").GetString()!, package.GetProperty("declaration").GetString()!, artifacts);
        private static EvidenceArtifact[] ReadArtifacts(JsonElement package) => package.GetProperty("artifacts").EnumerateArray().Select(item => new EvidenceArtifact(item.GetProperty("kind").GetString()!, item.GetProperty("path").GetString()!, item.GetProperty("content").GetString()!, item.GetProperty("sha256").GetString()!)).ToArray();
        private static EvidenceArtifact Artifact(string root, string kind, string content)
        {
            var relative = Path.Combine("artifacts", kind + ".txt");
            var path = Path.Combine(root, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, content, Encoding.UTF8);
            return new(kind, relative, content, Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(content))).ToLowerInvariant());
        }
        private static void InsertLease(string connectionString, RunnerLease lease)
        {
            using var connection = new SqliteConnection(connectionString); connection.Open(); using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
            command.Parameters.AddWithValue("$id", lease.LeaseId); command.Parameters.AddWithValue("$account", lease.AccountId); command.Parameters.AddWithValue("$project", lease.ProjectId); command.Parameters.AddWithValue("$fence", lease.Fence); command.ExecuteNonQuery();
        }
        private static void InsertRouteAuthority(string connectionString)
        {
            using var connection = new SqliteConnection(connectionString); connection.Open(); using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO route_recovery_evidence(recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue,source_order_json,blocker_json) VALUES($utc,8,0,0,1,$sources,'[]')";
            command.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O"));
            command.Parameters.AddWithValue("$sources", JsonSerializer.Serialize(PhaseA.Platform.Workflow.HostedRouteRecoveryContract.SourceOrder)); command.ExecuteNonQuery();
        }
        public void Dispose() { SqliteConnection.ClearAllPools(); try { Directory.Delete(_root, recursive: true); } catch (IOException) { } }
    }

    private sealed record EvidencePackage(bool Executed, DateTimeOffset Timestamp, string ProducerRunId, string Declaration, EvidenceArtifact[] Artifacts);
    private sealed record EvidenceArtifact(string Kind, string Path, string Content, string Sha256);
    private sealed record IndependentResult(bool Accepted, string Reason, int ProcessId, string[]? CheckedArtifacts);
}
