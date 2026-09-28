using System.Diagnostics;
using System.Security.Cryptography;
using System.Security.Principal;
using PhaseA.Platform.Runs;
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
    public void O_A18_PERSISTED_PLATFORM_RUN_BINDING() => AssertAccepted("permission", "FAILURE-S53-PERSISTED-RUN");

    [Fact]
    public void O_A18_REJECTS_REHASHED_NON_BEHAVIOR() => AssertRejected("fabricated", "FAILURE-S53-FABRICATED");

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
        "fabricated" => "behavior_evidence_invalid",
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
        private readonly string _runId;

        private EvidenceFixture(string root, string packagePath, string runId)
        {
            _root = root;
            _packagePath = packagePath;
            _runId = runId;
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
            RouteAuthorityFixture.Seed(connectionString, account.AccountId, ProjectId, projectRoot.FullName);
            RestoreAttempt restore;
            using (RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
                account.AccountId, ProjectId, "phase-r-a-p", destination, true, true, true)))
            {
                restore = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString)).Restore(context, snapshot.Manifest, source, destination, lease, "s53-roundtrip");
            }
            var restored = Path.Combine(destination, ".restore-current", "project.godot");
            var snapshotObserved = restore.Status == RestoreAttemptStatus.Published && File.Exists(restored) && File.ReadAllBytes(restored).SequenceEqual(content);

            if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("S53 requires the Windows Runner boundary.");
            // Reuse S54's provisioned test credential target; the metadata owner is generated per fixture.
            var probeRoot = Directory.CreateDirectory(Path.Combine(root, "runner-probe")).FullName;
            using var probeIsolation = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
                "account-a", "project-a", "phase-r-a-p", probeRoot, true, true, true));
            var owned = Path.Combine(destination, ".restore-current", "runner-owned.txt");
            var secretRoot = Directory.CreateDirectory(Path.Combine(root, "platform-secret")).FullName;
            var secret = Path.Combine(secretRoot, "secret.txt");
            File.WriteAllText(secret, "platform-only");
            using (var acl = Process.Start(new ProcessStartInfo("icacls.exe", $"\"{secretRoot}\" /inheritance:r /grant:r \"*S-1-5-32-544:(OI)(CI)F\"") { UseShellExecute = false, CreateNoWindow = true }))
            {
                Require(acl is not null, "FAILURE-S53-PERMISSION", "ACL preparation did not launch.");
                acl!.WaitForExit();
                Require(acl.ExitCode == 0, "FAILURE-S53-PERMISSION", "ACL preparation failed.");
            }
            var script = $"whoami /user /fo csv /nh & echo S53_OPERATION_ATTEMPTED & echo runner-owned>{owned} & type {secret} >nul 2>&1 & if errorlevel 1 (echo S53_ACCESS_DENIED:5 & exit /b 5) else (exit /b 6)";
            var probe = new HostedProcessRunner().RunAsync(new HostedProcessCommand("cmd.exe",
                ["/d", "/s", "/c", script],
                probeRoot, new Dictionary<string, string>())).GetAwaiter().GetResult();
            var runnerSid = ((SecurityIdentifier)new NTAccount(Environment.MachineName, "phase-r-a-p").Translate(typeof(SecurityIdentifier))).Value;
            var platformSid = WindowsIdentity.GetCurrent().User!.Value;
            var permissionObserved = probe.ExitCode == 5 && probe.Stdout.Contains(runnerSid, StringComparison.Ordinal) &&
                runnerSid != platformSid && probe.Stdout.Contains("S53_ACCESS_DENIED:5", StringComparison.Ordinal) && File.ReadAllText(owned).Trim() == "runner-owned";

            var faultRoot = Directory.CreateDirectory(Path.Combine(root, "fault-destination")).FullName;
            using var faultIsolation = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
                account.AccountId, ProjectId, "phase-r-a-p", faultRoot, true, true, true));
            var corrupt = snapshot.Manifest with { ProtectedContent = [0, 1, 2] };
            var faultLease = new RunnerLease("s53-fault-lease", account.AccountId, ProjectId, 2);
            InsertLease(connectionString, faultLease);
            var fault = new RestoreService(connectionString, new RouteRecoveryAuthorityResolver(connectionString))
                .Restore(context, corrupt, source, faultRoot, faultLease, "s53-fault");
            var faultObserved = fault.Status == RestoreAttemptStatus.Quarantined && fault.FailureCategory == "snapshot_corrupt" &&
                !Directory.Exists(Path.Combine(faultRoot, ".restore-current"));
            var migration = new SqliteMigrationService().MigrateAsync(connectionString, account.AccountId, ProjectId, "s53-migration").GetAwaiter().GetResult();
            var redacted = SecretRedactionPolicy.RedactForPersistence("OPENAI_API_KEY=sk-abcdefghijklmnop");
            var redactionObserved = !redacted.Contains("sk-abcdefghijklmnop", StringComparison.Ordinal) && redacted.Contains("[redacted]", StringComparison.Ordinal);

            Require(snapshotObserved && permissionObserved && faultObserved && migration.Status == "completed" && redactionObserved,
                "FAILURE-S53-FIXTURE", $"S53 could not materialize current production evidence for independent validation: snapshot={snapshotObserved};permission={permissionObserved};fault={faultObserved};migration={migration.Status};redaction={redactionObserved};probeExit={probe.ExitCode};probeOut={probe.Stdout}");
            var artifacts = new[]
            {
                Artifact(root, "snapshot", JsonSerializer.Serialize(new { status = restore.Status.ToString(), restoredPath = Path.GetRelativePath(root, restored), expectedSha256 = snapshot.Manifest.Files.Single().Sha256 })),
                Artifact(root, "permission", JsonSerializer.Serialize(new { platformSid, runnerSid, exitCode = probe.ExitCode, stdout = probe.Stdout, ownedPath = Path.GetRelativePath(root, owned) })),
                Artifact(root, "fault", JsonSerializer.Serialize(new { status = fault.Status.ToString(), failureCategory = fault.FailureCategory, publishedPath = Path.GetRelativePath(root, Path.Combine(faultRoot, ".restore-current")), quarantinePath = Path.GetRelativePath(root, Path.Combine(faultRoot, ".restore-quarantine", fault.AttemptId)) })),
                Artifact(root, "migration", JsonSerializer.Serialize(new { status = migration.Status })),
                Artifact(root, "redaction", redacted),
            };
            var packagePath = Path.Combine(root, "piwr-a18-evidence.json");
            string workspaceId;
            using (var db = new SqliteConnection(connectionString))
            {
                db.Open(); using var query = db.CreateCommand();
                query.CommandText = "SELECT id FROM workspaces WHERE project_id=$project";
                query.Parameters.AddWithValue("$project", ProjectId);
                workspaceId = (string)query.ExecuteScalar()!;
            }
            var runId = store.GetOrCreateProjectOperationRunAsync(ProjectId, workspaceId, "s53-evidence").GetAwaiter().GetResult().RunId;
            store.TryMarkRunStartedAsync(runId, null).GetAwaiter().GetResult();
            var evidence = JsonSerializer.Serialize(new { producerRunId = runId, independentEvidence = new {
                executionSource = "platform-run", artifacts = artifacts.Select(a => new { kind = a.Kind, path = a.Path, sha256 = a.Sha256 }) } });
            store.CompleteRunAsync(runId, "succeeded", 0, "", "", evidence).GetAwaiter().GetResult();
            File.WriteAllText(packagePath, JsonSerializer.Serialize(new EvidencePackage(true, DateTimeOffset.UtcNow, runId, "declared-pass-must-not-decide", artifacts), JsonOptions));
            return new EvidenceFixture(root, packagePath, runId);
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
                "fabricated" => Mutate(package, executed: true, timestamp: null, artifacts: ReadArtifacts(package).Select(a =>
                    a.Kind == "permission" ? Artifact(_root, "permission", "persisted-run:permission") : a).ToArray()),
                _ => throw new ArgumentOutOfRangeException(nameof(mutation))
            };
            if (mutation == "fabricated")
            {
                // Even a correctly hashed, DB-bound declaration is not behavioral evidence.
                using var db = new SqliteConnection($"Data Source={Path.Combine(_root, "metadata.sqlite3")}");
                db.Open(); using var update = db.CreateCommand();
                update.CommandText = "UPDATE runs SET evidence_json=$evidence WHERE id=$run";
                update.Parameters.AddWithValue("$run", _runId);
                update.Parameters.AddWithValue("$evidence", JsonSerializer.Serialize(new { producerRunId = _runId,
                    independentEvidence = new { executionSource = "platform-run", artifacts = altered.Artifacts.Select(a => new { kind = a.Kind, path = a.Path, sha256 = a.Sha256 }) } }));
                update.ExecuteNonQuery();
            }
            var input = Path.Combine(_root, $"input-{Guid.NewGuid():N}.json");
            File.WriteAllText(input, JsonSerializer.Serialize(altered, JsonOptions));
            using var process = Process.Start(new ProcessStartInfo("dotnet", $"\"{typeof(Program).Assembly.Location}\" --independent-evidence-run \"{input}\" {_runId} \"{Path.Combine(_root, "metadata.sqlite3")}\"")
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
        public void Dispose() { SqliteConnection.ClearAllPools(); try { Directory.Delete(_root, recursive: true); } catch (IOException) { } }
    }

    private sealed record EvidencePackage(bool Executed, DateTimeOffset Timestamp, string ProducerRunId, string Declaration, EvidenceArtifact[] Artifacts);
    private sealed record EvidenceArtifact(string Kind, string Path, string Content, string Sha256);
    private sealed record IndependentResult(bool Accepted, string Reason, int ProcessId, string[]? CheckedArtifacts);
}
