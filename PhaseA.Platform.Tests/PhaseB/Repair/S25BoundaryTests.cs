using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S25BoundaryTests
{
    [Fact]
    public async Task O_A28DE8F2511B() => await RunHttpFixtureAsync("verify-admin", "FAILURE-O-A28DE8F2511B");

    [Fact]
    public async Task O_4367428FF3D3()
    {
        if (Environment.GetEnvironmentVariable("S25_INTERRUPTION_ROOT") is not null)
        {
            InterruptedRestoreWorker();
            return;
        }
        await RunHttpFixtureAsync("verify-failures", "FAILURE-O-4367428FF3D3");
    }

    private static async Task RunHttpFixtureAsync(string readerMode, string failureId)
    {
        // ADR-0061: all mutations target this invocation's disposable server/database.
        var repository = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var nonce = Guid.NewGuid().ToString("N");
        var root = Path.Combine(repository, "logs", "quick-dev", "s25-admin-invocations", nonce);
        var workspaceRoot = Path.Combine(root, "workspaces");
        Directory.CreateDirectory(workspaceRoot);
        var database = Path.Combine(root, "metadata.sqlite3");
        var connection = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
        await SqliteMetadataSchema.InitializeAsync(connection);
        var adminToken = "s25-disposable-admin-" + nonce;
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_REPOSITORY_ROOT"] = repository,
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken)
        });
        var store = new PhaseAMetadataStore(connection, options);
        await store.EnsureSingleAdminAsync();
        var admin = (await store.ListAccountsAsync()).Single(account => account.IsAdmin);
        var target = await store.CreateUserAccountAsync("s25-target", 1);
        var actor = await store.CreateUserAccountAsync("s25-non-admin", 1);
        var projectRoot = Path.Combine(workspaceRoot, "retained-project");
        var repo = Path.Combine(projectRoot, "repo");
        Directory.CreateDirectory(repo);
        File.WriteAllText(Path.Combine(repo, "retained.txt"), nonce);
        var project = await store.CreateProjectAsync(new ProjectCreationCommand(
            "s25-project-" + nonce, target.AccountId, "Retained", "Retained", "manual", "default", false, [],
            projectRoot, repo, Path.Combine(projectRoot, "runtime"), Path.Combine(projectRoot, "meta")));
        if (!project.Succeeded || project.ProjectId is null)
            throw new InvalidOperationException("S25 fixture project creation failed.");
        // Seed an already initialized project, not an abandoned bootstrap candidate.
        // This is fixture setup only; no Chapter 2 workflow or live state is invoked.
        await store.SetProjectBootstrapStatusAsync(project.ProjectId, "succeeded", null);
        if (readerMode == "verify-failures")
            await ObserveServiceFailuresAsync(root, repository);
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        var address = $"http://127.0.0.1:{port}";
        var start = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = Path.Combine(repository, "PhaseA.Platform"),
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
        };
        start.ArgumentList.Add(Path.Combine(AppContext.BaseDirectory, "PhaseA.Platform.dll"));
        start.Environment["APP_BIND_URL"] = address;
        start.Environment["ASPNETCORE_URLS"] = address;
        start.Environment["PUBLIC_BASE_URL"] = "https://localhost";
        start.Environment["PHASEA_METADATA_DB_PATH"] = database;
        start.Environment["HOSTED_WORKSPACE_ROOT"] = workspaceRoot;
        start.Environment["PHASEA_REPOSITORY_ROOT"] = repository;
        start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken);
        start.Environment["PHASEA_SERVICE_STATE"] = "test";
        using var host = Process.Start(start) ?? throw new InvalidOperationException("S25 disposable host did not start.");
        // Drain streams continuously, without persisting credential-bearing response bodies.
        host.OutputDataReceived += (_, _) => { };
        host.ErrorDataReceived += (_, _) => { };
        host.BeginOutputReadLine();
        host.BeginErrorReadLine();
        try
        {
            using var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(2) };
            var healthy = false;
            for (var attempt = 0; attempt < 40 && !host.HasExited; attempt++)
            {
                try
                {
                    using var health = await client.GetAsync("/healthz");
                    if (health.IsSuccessStatusCode) { healthy = true; break; }
                }
                catch (Exception error) when (error is HttpRequestException or TaskCanceledException) { }
                await Task.Delay(250);
            }
            if (!healthy) throw new InvalidOperationException("S25 disposable host failed health precondition.");
            var readerStart = new ProcessStartInfo("py")
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardInput = true,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            foreach (var argument in new[] { "-3", Path.Combine(repository, "tests", "phase_b_c_identity_isolation", "current", "s25_fixture.py"), readerMode })
                readerStart.ArgumentList.Add(argument);
            using var reader = Process.Start(readerStart) ?? throw new InvalidOperationException("S25 admin verifier did not start.");
            var stdout = reader.StandardOutput.ReadToEndAsync();
            var stderr = reader.StandardError.ReadToEndAsync();
            await reader.StandardInput.WriteAsync(JsonSerializer.Serialize(new
            {
                root, nonce, address, account_id = target.AccountId, project_id = project.ProjectId,
                admin_id = admin.AccountId, actor_id = actor.AccountId,
                admin_token = adminToken, user_token = target.Token, actor_token = actor.Token
            }));
            reader.StandardInput.Close();
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(90));
            try { await reader.WaitForExitAsync(timeout.Token); }
            catch (OperationCanceledException)
            {
                reader.Kill(entireProcessTree: true);
                await reader.WaitForExitAsync();
                throw new InvalidOperationException("S25 admin verifier timed out.");
            }
            var output = await stdout;
            File.WriteAllText(Path.Combine(root, "reader.stdout.json"), output);
            File.WriteAllText(Path.Combine(root, "reader.stderr.txt"), await stderr);
            if (reader.ExitCode is not (0 or 2))
                throw new InvalidOperationException("S25 admin verifier infrastructure failed: " + output);
            using var result = JsonDocument.Parse(output);
            if (result.RootElement.GetProperty("pid").GetInt32() == Environment.ProcessId)
                throw new InvalidOperationException("S25 admin verifier was not independent.");
            if (reader.ExitCode != 0 || !result.RootElement.GetProperty("ok").GetBoolean())
                throw new Xunit.Sdk.XunitException(failureId + ": Independent boundary verification rejected: " + output);
        }
        finally
        {
            if (!host.HasExited)
            {
                host.Kill(entireProcessTree: true);
                await host.WaitForExitAsync();
            }
        }
    }
    private static async Task ObserveServiceFailuresAsync(string root, string repository)
    {
        var observations = new List<object>();
        foreach (var family in new[] { "path_escape", "acl_invalid", "snapshot_corrupt", "schema_unsupported",
                     "quota_exceeded", "restore_conflict", "restore_interrupted", "stale_lease" })
        {
            var caseRoot = Path.Combine(root, family);
            var workspace = Path.Combine(caseRoot, "workspaces", "project");
            var source = Path.Combine(workspace, "repo");
            Directory.CreateDirectory(source);
            File.WriteAllText(Path.Combine(source, "retained.txt"), "S25 nonempty snapshot control");
            var database = Path.Combine(caseRoot, "metadata.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(caseRoot, "workspaces"),
                ["PHASEA_REPOSITORY_ROOT"] = repository
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var account = await store.CreateUserAccountAsync("s25-failure-owner", 1);
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                "s25-" + family, account.AccountId, "Failure fixture", "Failure fixture", "manual", "default", false, [],
                workspace, source, Path.Combine(workspace, "runtime"), Path.Combine(workspace, "meta")));
            if (!project.Succeeded || project.ProjectId is null)
                throw new InvalidOperationException("S25 service fixture project was not created.");
            await store.SetProjectBootstrapStatusAsync(project.ProjectId, "succeeded", null);
            var correlation = Guid.NewGuid().ToString("N");
            var context = new RequestContext("s25-principal", account.AccountId,
                new HashSet<string>(StringComparer.Ordinal) { "user" }, "s25-fixture-credential", correlation);
            var storage = new WorkspaceStorageService(connectionString);
            storage.SetQuota(account.AccountId, 100 * 1024 * 1024);
            var manifest = storage.CreateSnapshot(context, source, "snapshot-control", "workspace-control", project.ProjectId,
                "policy-s25", new HashSet<string>(StringComparer.OrdinalIgnoreCase)).Manifest;
            var restore = new RestoreService(connectionString);
            SeedRouteAuthorityEvidence(connectionString);
            var firstLease = new RunnerLease("control-lease", account.AccountId, project.ProjectId, 1);
            await SeedLeaseAsync(connectionString, firstLease);
            var controlDestination = Path.Combine(caseRoot, "control-restore");
            var control = restore.RestorePrepared(context, manifest, source, controlDestination, firstLease, "control-request");
            if (control.Status != RestoreAttemptStatus.Published ||
                File.ReadAllText(Path.Combine(controlDestination, ".restore-current", "retained.txt")) != "S25 nonempty snapshot control")
                throw new InvalidOperationException("S25 positive restore control failed before fault injection.");
            var lease = new RunnerLease("current-lease", account.AccountId, project.ProjectId, 2);
            await SeedLeaseAsync(connectionString, lease);
            string? exceptionType = null;
            string? exceptionMessage = null;
            object? result = null;
            var started = DateTimeOffset.UtcNow;
            var destination = Path.Combine(caseRoot, "fault-restore");
            // Only the operation under test is inside this catch; setup failures never become product evidence.
            try
            {
                switch (family)
                {
                    case "path_escape":
                        result = RunnerIsolationPolicy.RequireContainedPath(source, "../outside.txt");
                        break;
                    case "acl_invalid":
                        // The directory is intentionally not enrolled in the required ACL policy.
                        // This reads the real Windows policy boundary without changing accounts, registry or ACLs.
                        if (!OperatingSystem.IsWindows())
                            throw new PlatformNotSupportedException("S25 ACL validation requires Windows.");
                        result = RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(new RunnerIsolationDescriptor(
                            account.AccountId, project.ProjectId, "NT AUTHORITY\\LOCAL SERVICE", source, true, true, true));
                        break;
                    case "snapshot_corrupt":
                        var corrupt = manifest.ProtectedContent!.ToArray();
                        corrupt[^1] ^= 1;
                        result = restore.RestorePrepared(context, manifest with { ProtectedContent = corrupt }, source, destination, lease, correlation);
                        break;
                    case "schema_unsupported":
                        result = restore.RestorePrepared(context, manifest with { SchemaVersion = "snapshot-manifest/unsupported" }, source, destination, lease, correlation);
                        break;
                    case "quota_exceeded":
                        storage.SetQuota(account.AccountId, 0);
                        result = storage.CreateSnapshot(context, source, "snapshot-over-quota", "workspace-control", project.ProjectId,
                            "policy-s25", new HashSet<string>(StringComparer.OrdinalIgnoreCase));
                        break;
                    case "restore_conflict":
                        result = restore.RestorePrepared(context, manifest with { SnapshotId = "different-snapshot" }, source, destination, lease, "control-request");
                        break;
                    case "stale_lease":
                        result = new RestoreService(connectionString).RestorePrepared(context, manifest, source, destination, firstLease, correlation);
                        break;
                    case "restore_interrupted":
                        result = await InterruptOwnedRestoreAsync(caseRoot, repository, connectionString, context, lease);
                        break;
                }
            }
            catch (Exception error) when (error is UnauthorizedAccessException or InvalidDataException or IOException or InvalidOperationException)
            {
                exceptionType = error.GetType().FullName;
                exceptionMessage = error.Message;
            }
            observations.Add(new
            {
                family, correlation, database = Path.GetRelativePath(root, database),
                account_id = account.AccountId, project_id = project.ProjectId,
                started_utc = started, finished_utc = DateTimeOffset.UtcNow,
                exception_type = exceptionType, exception_message = exceptionMessage, result,
                positive_control = new { control.AttemptId, control.Status, retained_content = "S25 nonempty snapshot control" }
            });
            File.WriteAllText(Path.Combine(root, "service-failure-observations.json"), JsonSerializer.Serialize(observations));
        }
    }

    private static async Task SeedLeaseAsync(string connectionString, RunnerLease lease)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
        command.Parameters.AddWithValue("$id", lease.LeaseId);
        command.Parameters.AddWithValue("$account", lease.AccountId);
        command.Parameters.AddWithValue("$project", lease.ProjectId);
        command.Parameters.AddWithValue("$fence", lease.Fence);
        await command.ExecuteNonQueryAsync();
    }

    private static void SeedRouteAuthorityEvidence(string connectionString)
    {
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO route_recovery_evidence(recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue,source_order_json,blocker_json) VALUES($recorded,8,0,0,1,$sources,$blockers)";
        command.Parameters.AddWithValue("$recorded", DateTimeOffset.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("$sources", JsonSerializer.Serialize(HostedRouteRecoveryContract.SourceOrder));
        command.Parameters.AddWithValue("$blockers", "[]");
        command.ExecuteNonQuery();
    }

    private static async Task<object> InterruptOwnedRestoreAsync(
        string root, string repository, string connectionString, RequestContext context, RunnerLease lease)
    {
        var source = Path.Combine(root, "interrupt-source");
        Directory.CreateDirectory(source);
        for (var index = 0; index < 5000; index++)
            File.WriteAllText(Path.Combine(source, $"file-{index:D5}.txt"), "S25 interrupted restore content");
        var storage = new WorkspaceStorageService(connectionString);
        var manifest = storage.CreateSnapshot(context, source, "snapshot-interrupted", "workspace-control", lease.ProjectId,
            "policy-s25", new HashSet<string>(StringComparer.OrdinalIgnoreCase)).Manifest;
        var destination = Path.Combine(root, "interrupted-restore");
        Directory.CreateDirectory(destination);
        File.WriteAllText(Path.Combine(root, "interruption-input.json"), JsonSerializer.Serialize(new
        {
            connectionString, context, lease, manifest, source, destination
        }));
        var start = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = repository, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true
        };
        // ADR-0061: dispatch this exact built assembly, without a nested MSBuild invocation.
        foreach (var argument in new[] { "vstest", typeof(S25BoundaryTests).Assembly.Location,
                     "/TestCaseFilter:FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S25BoundaryTests.O_4367428FF3D3",
                     "/Logger:trx", "/ResultsDirectory:" + Path.Combine(root, "interrupted-worker-trx") })
            start.ArgumentList.Add(argument);
        start.Environment["S25_INTERRUPTION_ROOT"] = root;
        using var worker = Process.Start(start) ?? throw new Exception("S25 interruption worker did not start.");
        var stdout = worker.StandardOutput.ReadToEndAsync();
        var stderr = worker.StandardError.ReadToEndAsync();
        var interruptionObserved = false;
        string output;
        string errorOutput;
        try
        {
            // Use an owned dedicated thread: thread-pool callbacks/continuations can arrive after publication.
            interruptionObserved = await Task.Factory.StartNew(() =>
            {
                var elapsed = Stopwatch.StartNew();
                while (elapsed.Elapsed < TimeSpan.FromSeconds(30))
                {
                    if (worker.HasExited) return false;
                    if (Directory.EnumerateFiles(destination, "*.txt", SearchOption.AllDirectories).Any())
                    {
                        try { worker.Kill(entireProcessTree: true); }
                        catch (InvalidOperationException) { return false; }
                        return true;
                    }
                    Thread.Sleep(5);
                }
                return false;
            }, CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default);
            if (interruptionObserved) await worker.WaitForExitAsync();
        }
        finally
        {
            if (!worker.HasExited) { worker.Kill(entireProcessTree: true); await worker.WaitForExitAsync(); }
            output = await stdout;
            errorOutput = await stderr;
            File.WriteAllText(Path.Combine(root, "interrupted-worker.stdout.txt"), output);
            File.WriteAllText(Path.Combine(root, "interrupted-worker.stderr.txt"), errorOutput);
        }
        if (!interruptionObserved)
        {
            var outputTail = output.Length <= 4000 ? output : output[^4000..];
            var errorTail = errorOutput.Length <= 4000 ? errorOutput : errorOutput[^4000..];
            // Infrastructure failures are not caught as product failure evidence.
            throw new Exception($"S25 interruption was not observed during real file staging. Worker exit={worker.ExitCode}; stdout={outputTail}; stderr={errorTail}");
        }
        // Restart the real producer. Do not synthesize verification/history rows.
        _ = new RestoreService(connectionString);
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT status FROM restore_attempts WHERE idempotency_key='interrupted-request'";
        return new { worker_pid = worker.Id, worker_exit_code = worker.ExitCode,
            staged_files = Directory.EnumerateFiles(destination, "*.txt", SearchOption.AllDirectories).Count(),
            recovered_status = (await command.ExecuteScalarAsync())?.ToString() };
    }

    private static void InterruptedRestoreWorker()
    {
        var root = Environment.GetEnvironmentVariable("S25_INTERRUPTION_ROOT")
            ?? throw new InvalidOperationException("S25 interruption worker requires its parent fixture.");
        using var input = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "interruption-input.json")));
        var data = input.RootElement;
        var contextJson = data.GetProperty("context");
        var context = new RequestContext(contextJson.GetProperty("PrincipalId").GetString()!, contextJson.GetProperty("AccountId").GetString()!,
            new HashSet<string> { "user" }, contextJson.GetProperty("CredentialId").GetString()!, contextJson.GetProperty("CorrelationId").GetString()!);
        var service = new RestoreService(data.GetProperty("connectionString").GetString());
        service.RestorePrepared(context, data.GetProperty("manifest").Deserialize<SnapshotManifest>()!,
            data.GetProperty("source").GetString()!, data.GetProperty("destination").GetString()!,
            data.GetProperty("lease").Deserialize<RunnerLease>()!, "interrupted-request");
    }

    [Fact]
    public async Task O_E44EA22B607F()
    {
        // ADR-0061: verify retained legacy data through the real startup migration.
        var repository = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var nonce = Guid.NewGuid().ToString("N");
        var root = Path.Combine(repository, "logs", "quick-dev", "s25-migration-invocations", nonce);
        Directory.CreateDirectory(root);
        var database = Path.Combine(root, "metadata.sqlite3");
        var connectionString = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
        await using (var connection = new SqliteConnection(connectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                CREATE TABLE accounts (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NULL, token_hash TEXT NULL, is_admin INTEGER NOT NULL DEFAULT 0, created_utc TEXT NOT NULL);
                CREATE TABLE projects (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, name TEXT NOT NULL,
                    game_name TEXT NOT NULL, game_type_source TEXT NOT NULL, template_rule_id TEXT NOT NULL, created_utc TEXT NOT NULL);
                CREATE TABLE runs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NULL,
                    run_type TEXT NOT NULL, status TEXT NOT NULL, created_utc TEXT NOT NULL, started_utc TEXT NULL, finished_utc TEXT NULL);
                CREATE TABLE artifacts (id TEXT PRIMARY KEY, run_id TEXT NULL, project_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL, relative_path TEXT NOT NULL, summary TEXT NOT NULL, created_utc TEXT NOT NULL);
                INSERT INTO accounts VALUES ('s25-account', 's25-user', NULL, NULL, 0, '2026-08-01T00:00:00Z');
                INSERT INTO projects VALUES ('s25-project', 's25-account', 'Retained', 'Retained game', 'manual', 'legacy', '2026-08-01T00:00:00Z');
                INSERT INTO runs VALUES ('s25-run', 's25-project', NULL, 'repair', 'succeeded', '2026-08-01T00:00:00Z', NULL, NULL);
                INSERT INTO artifacts VALUES ('s25-artifact', 's25-run', 's25-project', 'report', 'reports/retained.json', $nonce, '2026-08-01T00:00:00Z');
                """;
            command.Parameters.AddWithValue("$nonce", nonce);
            await command.ExecuteNonQueryAsync();
        }
        var before = Path.Combine(root, "before.sqlite3");
        File.Copy(database, before);
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var beforeHash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(before))).ToLowerInvariant();
        var afterHash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(database))).ToLowerInvariant();
        var start = new ProcessStartInfo("py")
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true
        };
        foreach (var argument in new[] { "-3", Path.Combine(repository, "tests", "phase_b_c_identity_isolation", "current", "s25_fixture.py"),
                     "verify-migration", root, nonce, beforeHash, afterHash })
            start.ArgumentList.Add(argument);
        using var process = Process.Start(start) ?? throw new InvalidOperationException("S25 independent reader did not start.");
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        try { await process.WaitForExitAsync(timeout.Token); }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync();
            throw new InvalidOperationException("S25 independent reader timed out.");
        }
        var output = await stdout;
        File.WriteAllText(Path.Combine(root, "reader.stdout.json"), output);
        File.WriteAllText(Path.Combine(root, "reader.stderr.txt"), await stderr);
        if (process.ExitCode is not (0 or 2))
            throw new InvalidOperationException("S25 independent reader infrastructure failed.");
        using var result = JsonDocument.Parse(output);
        if (result.RootElement.GetProperty("pid").GetInt32() == Environment.ProcessId)
            throw new InvalidOperationException("S25 reader did not execute independently.");
        if (process.ExitCode != 0 || !result.RootElement.GetProperty("ok").GetBoolean())
            throw new Xunit.Sdk.XunitException("FAILURE-O-E44EA22B607F: Independent database inspection rejected migration: " + output);
    }

}
