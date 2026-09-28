using System.Net;
using System.Diagnostics;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S51BoundaryTests
{
    [Fact]
    public async Task O_E9499880E6EF()
    {
        if (Environment.GetEnvironmentVariable("S51_INTERRUPTION_ROOT") is not null)
        {
            InterruptedWorker();
            return;
        }
        var repository = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var root = Path.Combine(repository, "logs", "quick-dev", "s51-family-invocations", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var observed = new Dictionary<string, object>(StringComparer.Ordinal);
        var valid = new HashSet<string>(StringComparer.Ordinal);
        await ObserveServiceFamiliesAsync(repository, root, observed, valid);
        await ObserveHttpFamiliesAsync(repository, root, observed, valid);
        File.WriteAllText(Path.Combine(root, "failure-family-observations.json"), JsonSerializer.Serialize(observed));
        var expected = new[] { "unauthenticated", "forbidden", "account_disabled", "credential_revoked", "ownership_mismatch", "path_escape", "acl_invalid", "snapshot_corrupt", "schema_unsupported", "quota_exceeded", "restore_conflict", "restore_interrupted", "stale_lease", "internal_failure" };
        var missing = expected.Where(name => !valid.Contains(name)).ToArray();
        if (missing.Length > 0)
            throw new Xunit.Sdk.XunitException("FAILURE-O-E9499880E6EF: missing valid owning-boundary inductions: " + string.Join(",", missing));
    }

    [Fact]
    public async Task O_R4_PERSISTED_FAULT_POINT_MATRIX()
    {
        var repository = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var root = Path.Combine(repository, "logs", "quick-dev", "s51-fault-matrix", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var checkpoints = new[] { "staging-written", "post-verification", "previous-moved", "current-switched", "metadata-committed" };
        var observations = new List<object>();
        try
        {
            foreach (var checkpoint in checkpoints)
            {
                var result = await ObserveFaultCheckpointAsync(repository, root, checkpoint);
                observations.Add(new { checkpoint, result });
                var safeStatus = checkpoint == "metadata-committed"
                    ? result.RecoveredStatus is "Published" or "Quarantined" or "Failed"
                    : result.RecoveredStatus is "Quarantined" or "Failed";
                if (!result.TerminatedAtCheckpoint || !safeStatus || result.StagingFiles != 0)
                    throw new Xunit.Sdk.XunitException($"FAILURE-R4-{checkpoint}: independent fault-point recovery did not produce a typed safe state (terminated={result.TerminatedAtCheckpoint}, status={result.RecoveredStatus ?? "<null>"}, stagingFiles={result.StagingFiles}).");
                if (checkpoint == "staging-written")
                    await VerifyConcurrentRetryPublicationAsync(repository, Path.Combine(root, checkpoint));
            }
            File.WriteAllText(Path.Combine(root, "fault-matrix-observations.json"), JsonSerializer.Serialize(observations));
        }
        finally
        {
            try { Directory.Delete(root, recursive: true); } catch (IOException) { }
        }
    }

    private static async Task ObserveServiceFamiliesAsync(string repository, string root, Dictionary<string, object> observed, HashSet<string> valid)
    {
        var source = Path.Combine(root, "service", "workspace", "repo");
        Directory.CreateDirectory(source);
        File.WriteAllText(Path.Combine(source, "retained.txt"), "S51 control content");
        var db = Path.Combine(root, "service", "metadata.sqlite3");
        Directory.CreateDirectory(Path.GetDirectoryName(db)!);
        var cs = new SqliteConnectionStringBuilder { DataSource = db, Pooling = false }.ToString();
        await SqliteMetadataSchema.InitializeAsync(cs);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "service", "workspace"), ["PHASEA_REPOSITORY_ROOT"] = repository });
        var store = new PhaseAMetadataStore(cs, options);
        var account = await store.CreateUserAccountAsync("s51-owner", 1);
        var workspace = Path.GetDirectoryName(source)!;
        var project = await store.CreateProjectAsync(new ProjectCreationCommand("s51-project", account.AccountId, "S51", "S51", "manual", "default", false, [], workspace, source, Path.Combine(workspace, "runtime"), Path.Combine(workspace, "meta")));
        if (!project.Succeeded || project.ProjectId is null) throw new InvalidOperationException("S51 service fixture project setup failed.");
        var context = new RequestContext("s51-principal", account.AccountId, new HashSet<string> { "user" }, "s51-credential", "s51-correlation");
        var storage = new WorkspaceStorageService(cs); storage.SetQuota(account.AccountId, 1024 * 1024);
        var manifest = storage.CreateSnapshot(context, source, "s51-snapshot", "s51-workspace", project.ProjectId, "s51-policy", new HashSet<string>(StringComparer.OrdinalIgnoreCase)).Manifest;
        var service = new RestoreService(cs);
        var lease = new RunnerLease("s51-lease", account.AccountId, project.ProjectId, 1);
        await InsertLeaseAsync(cs, lease);
        await InsertRouteAuthorityAsync(cs);
        var control = service.RestorePrepared(context, manifest, source, Path.Combine(root, "service", "control"), lease, "s51-control");
        if (control.Status != RestoreAttemptStatus.Published) throw new InvalidOperationException("S51 service control restore failed.");

        try { RunnerIsolationPolicy.RequireContainedPath(source, "../escape"); observed["path_escape"] = new { induced = false }; }
        catch (UnauthorizedAccessException error) { observed["path_escape"] = new { exception = error.GetType().Name, message = error.Message }; valid.Add("path_escape"); }
        Observe("acl_invalid", () => OperatingSystem.IsWindows() && !RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(new RunnerIsolationDescriptor(account.AccountId, project.ProjectId, "NT AUTHORITY\\LOCAL SERVICE", source, true, true, true)), observed, valid, value => value is bool flag && flag);
        var cases = new (string Name, SnapshotManifest Manifest, string Key, RunnerLease Lease)[]
        {
            ("snapshot_corrupt", manifest with { ProtectedContent = Corrupt(manifest.ProtectedContent!) }, "s51-corrupt", lease),
            ("schema_unsupported", manifest with { SchemaVersion = "snapshot-manifest/unsupported" }, "s51-schema", lease),
            ("quota_exceeded", manifest, "s51-quota", lease),
            ("restore_conflict", manifest with { SnapshotId = "different" }, "s51-control", lease),
            ("stale_lease", manifest, "s51-stale", new RunnerLease("s51-old", account.AccountId, project.ProjectId, 0)),
        };
        var caseIndex = 0;
        foreach (var item in cases)
        {
            if (item.Name == "quota_exceeded") storage.SetQuota(account.AccountId, 0);
            try
            {
                var requestLease = item.Lease;
                if (item.Name is "snapshot_corrupt" or "schema_unsupported" or "quota_exceeded")
                {
                    requestLease = new RunnerLease("s51-" + item.Name, account.AccountId, project.ProjectId, caseIndex + 2);
                    await InsertLeaseAsync(cs, requestLease);
                }
                var result = service.RestorePrepared(context with { CorrelationId = "s51-" + item.Name }, item.Manifest, source, Path.Combine(root, "service", item.Name), requestLease, item.Key);
                var category = ReadCategory(cs, result.AttemptId);
                observed[item.Name] = new { status = result.Status.ToString(), category };
                if (category == item.Name) valid.Add(item.Name);
            }
            catch (Exception error)
            {
                var rejectionKey = item.Name == "restore_conflict" ? item.Key + ":conflict" : item.Key;
                var category = ReadCategoryByKey(cs, rejectionKey);
                observed[item.Name] = new { exception = error.GetType().Name, category };
                if (item.Name == "restore_conflict" && error is UnauthorizedAccessException && category == item.Name) valid.Add(item.Name);
                if (item.Name == "stale_lease" && error is InvalidOperationException && category == item.Name) valid.Add(item.Name);
            }
            caseIndex++;
        }
        storage.SetQuota(account.AccountId, 1024 * 1024 * 1024);
        var interruptionLease = new RunnerLease("s51-interruption-lease", account.AccountId, project.ProjectId, 1000);
        await InsertLeaseAsync(cs, interruptionLease);
        var interruption = await ObserveInterruptedAsync(root, cs, context, interruptionLease, manifest);
        observed["restore_interrupted"] = interruption;
        using (var interruptionDocument = JsonDocument.Parse(JsonSerializer.Serialize(interruption)))
        {
            if (interruptionDocument.RootElement.TryGetProperty("recoveredStatus", out var status) && status.GetString() is "Quarantined" or "Failed") valid.Add("restore_interrupted");
        }
    }

    private static async Task<object> ObserveInterruptedAsync(string root, string cs, RequestContext context, RunnerLease lease, SnapshotManifest manifest)
    {
        var source = Path.Combine(root, "service", "interrupt-source"); Directory.CreateDirectory(source);
        for (var index = 0; index < 1500; index++) File.WriteAllText(Path.Combine(source, $"file-{index:D4}.txt"), "S51 interrupted content");
        var destination = Path.Combine(root, "service", "interrupted"); Directory.CreateDirectory(destination);
        var interruptedManifest = new WorkspaceStorageService(cs).CreateSnapshot(context, source, "s51-interrupted-snapshot", manifest.WorkspaceId, lease.ProjectId, "s51-policy", new HashSet<string>(StringComparer.OrdinalIgnoreCase)).Manifest;
        var input = Path.Combine(root, "service", "interruption-input.json");
        File.WriteAllText(input, JsonSerializer.Serialize(new { cs, context, lease, manifest = interruptedManifest, source, destination }));
        var watcher = new FileSystemWatcher(destination) { IncludeSubdirectories = true, NotifyFilter = NotifyFilters.FileName, EnableRaisingEvents = true };
        var staged = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        watcher.Created += (_, args) => { if (args.FullPath.EndsWith(".txt", StringComparison.OrdinalIgnoreCase)) staged.TrySetResult(); };
        var repository = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var start = new System.Diagnostics.ProcessStartInfo("dotnet") { WorkingDirectory = repository, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in new[] { "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-build", "--no-restore", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S51BoundaryTests.O_E9499880E6EF", "--logger", "trx", "--results-directory", Path.Combine(root, "service", "interrupted-trx") }) start.ArgumentList.Add(argument);
        start.Environment["S51_INTERRUPTION_ROOT"] = root;
        using var worker = System.Diagnostics.Process.Start(start) ?? throw new InvalidOperationException("S51 interruption worker did not start.");
        var winner = await Task.WhenAny(staged.Task, worker.WaitForExitAsync(), Task.Delay(TimeSpan.FromSeconds(30)));
        if (winner != staged.Task || worker.HasExited) throw new InvalidOperationException("S51 interruption was not observed during real staging.");
        worker.Kill(entireProcessTree: true); await worker.WaitForExitAsync(); watcher.Dispose();
        _ = new RestoreService(cs);
        await using var connection = new SqliteConnection(cs); await connection.OpenAsync(); await using var command = connection.CreateCommand(); command.CommandText = "SELECT status FROM restore_attempts WHERE idempotency_key='s51-interrupted-request'";
        return new { stagedFiles = Directory.EnumerateFiles(destination, "*.txt", SearchOption.AllDirectories).Count(), workerExitCode = worker.ExitCode, recoveredStatus = (await command.ExecuteScalarAsync())?.ToString() };
    }

    private static async Task<FaultPointObservation> ObserveFaultCheckpointAsync(string repository, string root, string checkpoint)
    {
        var caseRoot = Path.Combine(root, checkpoint);
        Directory.CreateDirectory(caseRoot);
        var source = Path.Combine(caseRoot, "source");
        Directory.CreateDirectory(source);
        for (var index = 0; index < 800; index++) File.WriteAllText(Path.Combine(source, $"file-{index:D4}.txt"), "R4 fault matrix content");
        var destination = Path.Combine(caseRoot, "destination");
        Directory.CreateDirectory(destination);
        var database = Path.Combine(caseRoot, "metadata.sqlite3");
        var cs = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
        await SqliteMetadataSchema.InitializeAsync(cs);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = caseRoot, ["PHASEA_REPOSITORY_ROOT"] = repository });
        var store = new PhaseAMetadataStore(cs, options);
        var account = await store.CreateUserAccountAsync("s51-r4-owner-" + checkpoint, 1);
        var workspace = Path.Combine(caseRoot, "workspace");
        var project = await store.CreateProjectAsync(new ProjectCreationCommand("s51-r4-" + checkpoint, account.AccountId, "R4", "R4", "manual", "default", false, [], workspace, source, Path.Combine(workspace, "runtime"), Path.Combine(workspace, "meta")));
        if (!project.Succeeded || project.ProjectId is null) throw new InvalidOperationException("R4 matrix project setup failed.");
        var context = new RequestContext("s51-r4-principal", account.AccountId, new HashSet<string> { "user" }, "s51-r4-credential", "s51-r4-correlation-" + checkpoint);
        var storage = new WorkspaceStorageService(cs); storage.SetQuota(account.AccountId, 100 * 1024 * 1024);
        var manifest = storage.CreateSnapshot(context, source, "s51-r4-snapshot-" + checkpoint, "s51-r4-workspace", project.ProjectId, "s51-r4-policy", new HashSet<string>(StringComparer.OrdinalIgnoreCase)).Manifest;
        var lease = new RunnerLease("s51-r4-lease-" + checkpoint, account.AccountId, project.ProjectId, 1);
        _ = new RestoreService(cs);
        await InsertLeaseAsync(cs, lease); await InsertRouteAuthorityAsync(cs);
        var input = Path.Combine(caseRoot, "input.json");
        File.WriteAllText(input, JsonSerializer.Serialize(new { cs, context, lease, manifest, source, destination, checkpoint }));
        var watcherRoot = Path.Combine(destination, ".restore-checkpoints", manifest.SnapshotId);
        using var watcher = new FileSystemWatcher(destination) { IncludeSubdirectories = true, Filter = checkpoint + ".json", NotifyFilter = NotifyFilters.FileName, EnableRaisingEvents = true };
        var reached = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        watcher.Created += (_, args) => { if (args.FullPath.Contains(checkpoint, StringComparison.OrdinalIgnoreCase)) reached.TrySetResult(); };
        var start = new ProcessStartInfo("dotnet") { WorkingDirectory = repository, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in new[] { "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-build", "--no-restore", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S51BoundaryTests.O_R4_INTERRUPTION_WORKER", "--logger", "trx", "--results-directory", Path.Combine(caseRoot, "trx") }) start.ArgumentList.Add(argument);
        start.Environment["S51_R4_INPUT"] = input;
        start.Environment["PHASEA_RESTORE_FAULT_POINT"] = checkpoint;
        using var worker = Process.Start(start) ?? throw new InvalidOperationException("R4 matrix worker did not start.");
        var winner = await Task.WhenAny(reached.Task, worker.WaitForExitAsync(), Task.Delay(TimeSpan.FromSeconds(45)));
        var terminated = winner == reached.Task && !worker.HasExited;
        if (terminated) { worker.Kill(entireProcessTree: true); await worker.WaitForExitAsync(); }
        watcher.Dispose();
        _ = new RestoreService(cs);
        string? status;
        await using (var connection = new SqliteConnection(cs)) { await connection.OpenAsync(); await using var command = connection.CreateCommand(); command.CommandText = "SELECT status FROM restore_attempts WHERE idempotency_key=$key"; command.Parameters.AddWithValue("$key", "s51-r4-request-" + checkpoint); status = (await command.ExecuteScalarAsync())?.ToString(); }
        var stagingRoot = Path.Combine(destination, ".restore-staging");
        var stagingFiles = Directory.Exists(stagingRoot) ? Directory.EnumerateFiles(stagingRoot, "*", SearchOption.AllDirectories).Count() : 0;
        return new FaultPointObservation(terminated, status, stagingFiles);
    }

    private static async Task VerifyConcurrentRetryPublicationAsync(string repository, string caseRoot)
    {
        var input = Path.Combine(caseRoot, "input.json");
        var workers = new List<Process>();
        try
        {
            for (var index = 0; index < 2; index++)
            {
                var start = new ProcessStartInfo("dotnet")
                {
                    WorkingDirectory = repository,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                foreach (var argument in new[]
                {
                    "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-build", "--no-restore",
                    "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S51BoundaryTests.O_R4_INTERRUPTION_WORKER",
                    "--logger", "trx", "--results-directory", Path.Combine(caseRoot, "retry-trx-" + index)
                }) start.ArgumentList.Add(argument);
                start.Environment["S51_R4_INPUT"] = input;
                start.Environment["S51_R4_REQUIRE_PUBLISHED"] = "1";
                start.Environment["S51_R4_RESULT_FILE"] = Path.Combine(caseRoot, "retry-result-" + index + ".json");
                workers.Add(Process.Start(start) ?? throw new InvalidOperationException("R4 concurrent retry worker did not start."));
            }
            await Task.WhenAll(workers.Select(worker => worker.WaitForExitAsync()))
                .WaitAsync(TimeSpan.FromSeconds(90));
            if (workers.Any(worker => worker.ExitCode != 0))
                throw new Xunit.Sdk.XunitException("FAILURE-R4-CONCURRENT: a same-key retry worker failed.");

            using var data = JsonDocument.Parse(File.ReadAllText(input));
            var item = data.RootElement;
            var cs = item.GetProperty("cs").GetString()!;
            var destination = item.GetProperty("destination").GetString()!;
            var checkpoint = item.GetProperty("checkpoint").GetString()!;
            var workerResults = Enumerable.Range(0, 2).Select(index =>
            {
                var resultFile = Path.Combine(caseRoot, "retry-result-" + index + ".json");
                if (!File.Exists(resultFile))
                    throw new Xunit.Sdk.XunitException("FAILURE-R4-CONCURRENT: a retry worker produced no result artifact.");
                using var result = JsonDocument.Parse(File.ReadAllText(resultFile));
                return (
                    AttemptId: result.RootElement.GetProperty("attemptId").GetString(),
                    Status: result.RootElement.GetProperty("status").GetString());
            }).ToArray();
            await using var connection = new SqliteConnection(cs);
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                SELECT attempt_id, status,
                       (SELECT COUNT(*) FROM restore_attempt_history h
                        WHERE h.attempt_id=a.attempt_id AND h.stage='publish' AND h.outcome='published')
                FROM restore_attempts a WHERE idempotency_key=$key
                """;
            command.Parameters.AddWithValue("$key", "s51-r4-request-" + checkpoint);
            await using var reader = await command.ExecuteReaderAsync();
            var publishedOnce = await reader.ReadAsync() &&
                                reader.GetString(1) == "Published" &&
                                reader.GetInt64(2) == 1 &&
                                workerResults.All(result =>
                                    result.Status == "Published" &&
                                    result.AttemptId == reader.GetString(0));
            if (!publishedOnce ||
                !File.Exists(Path.Combine(destination, ".restore-current", "file-0000.txt")))
                throw new Xunit.Sdk.XunitException("FAILURE-R4-CONCURRENT: same-key processes did not converge on one published result.");
        }
        finally
        {
            foreach (var worker in workers)
            {
                if (!worker.HasExited) worker.Kill(entireProcessTree: true);
                worker.Dispose();
            }
        }
    }

    [Fact]
    public void O_R4_INTERRUPTION_WORKER()
    {
        var input = Environment.GetEnvironmentVariable("S51_R4_INPUT");
        if (string.IsNullOrWhiteSpace(input)) return;
        using var data = JsonDocument.Parse(File.ReadAllText(input));
        var item = data.RootElement;
        var contextNode = item.GetProperty("context");
        var context = new RequestContext(contextNode.GetProperty("PrincipalId").GetString()!, contextNode.GetProperty("AccountId").GetString()!, new HashSet<string> { "user" }, contextNode.GetProperty("CredentialId").GetString()!, contextNode.GetProperty("CorrelationId").GetString()!);
        var service = new RestoreService(item.GetProperty("cs").GetString());
        var result = service.RestorePrepared(context, item.GetProperty("manifest").Deserialize<SnapshotManifest>()!, item.GetProperty("source").GetString()!, item.GetProperty("destination").GetString()!, item.GetProperty("lease").Deserialize<RunnerLease>()!, "s51-r4-request-" + item.GetProperty("checkpoint").GetString());
        if (Environment.GetEnvironmentVariable("S51_R4_REQUIRE_PUBLISHED") == "1" &&
            result.Status != RestoreAttemptStatus.Published)
            throw new Xunit.Sdk.XunitException("FAILURE-R4-CONCURRENT: retry worker did not observe the published result.");
        var resultFile = Environment.GetEnvironmentVariable("S51_R4_RESULT_FILE");
        if (!string.IsNullOrWhiteSpace(resultFile))
            File.WriteAllText(resultFile, JsonSerializer.Serialize(new { attemptId = result.AttemptId, status = result.Status.ToString() }));
    }

    private static void InterruptedWorker()
    {
        var root = Environment.GetEnvironmentVariable("S51_INTERRUPTION_ROOT")!;
        using var data = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "service", "interruption-input.json")));
        var item = data.RootElement; var contextJson = item.GetProperty("context");
        var context = new RequestContext(contextJson.GetProperty("PrincipalId").GetString()!, contextJson.GetProperty("AccountId").GetString()!, new HashSet<string> { "user" }, contextJson.GetProperty("CredentialId").GetString()!, contextJson.GetProperty("CorrelationId").GetString()!);
        var service = new RestoreService(item.GetProperty("cs").GetString());
        service.RestorePrepared(context, item.GetProperty("manifest").Deserialize<SnapshotManifest>()!, item.GetProperty("source").GetString()!, item.GetProperty("destination").GetString()!, item.GetProperty("lease").Deserialize<RunnerLease>()!, "s51-interrupted-request");
    }

    private static async Task ObserveHttpFamiliesAsync(string repository, string root, Dictionary<string, object> observed, HashSet<string> valid)
    {
        var db = Path.Combine(root, "http", "metadata.sqlite3"); Directory.CreateDirectory(Path.GetDirectoryName(db)!);
        var workspace = Path.Combine(root, "http", "workspace", "owned"); Directory.CreateDirectory(Path.Combine(workspace, "repo"));
        var cs = new SqliteConnectionStringBuilder { DataSource = db, Pooling = false }.ToString(); await SqliteMetadataSchema.InitializeAsync(cs);
        var adminToken = "s51-admin-" + Guid.NewGuid().ToString("N");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "http", "workspace"), ["PHASEA_REPOSITORY_ROOT"] = repository, ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken) });
        var store = new PhaseAMetadataStore(cs, options); await store.EnsureSingleAdminAsync();
        var owner = await store.CreateUserAccountAsync("s51-http-owner", 1); var stranger = await store.CreateUserAccountAsync("s51-http-stranger", 1);
        var project = await store.CreateProjectAsync(new ProjectCreationCommand("s51-http-project", owner.AccountId, "S51 HTTP", "S51 HTTP", "manual", "default", false, [], workspace, Path.Combine(workspace, "repo"), Path.Combine(workspace, "runtime"), Path.Combine(workspace, "meta")));
        if (!project.Succeeded || project.ProjectId is null) throw new InvalidOperationException("S51 HTTP project setup failed."); await store.SetProjectBootstrapStatusAsync(project.ProjectId, "succeeded", null);
        var listener = new TcpListener(IPAddress.Loopback, 0); listener.Start(); var address = $"http://127.0.0.1:{((IPEndPoint)listener.LocalEndpoint).Port}"; listener.Stop();
        var start = new System.Diagnostics.ProcessStartInfo("dotnet") { WorkingDirectory = Path.Combine(repository, "PhaseA.Platform"), UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
        start.ArgumentList.Add(Path.Combine(AppContext.BaseDirectory, "PhaseA.Platform.dll")); start.Environment["APP_BIND_URL"] = address; start.Environment["ASPNETCORE_URLS"] = address; start.Environment["PUBLIC_BASE_URL"] = "https://localhost"; start.Environment["PHASEA_METADATA_DB_PATH"] = db; start.Environment["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "http", "workspace"); start.Environment["PHASEA_REPOSITORY_ROOT"] = repository; start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken); start.Environment["PHASEA_SERVICE_STATE"] = "test";
        using var host = System.Diagnostics.Process.Start(start) ?? throw new InvalidOperationException("S51 HTTP host failed to start."); host.OutputDataReceived += (_, _) => { }; host.ErrorDataReceived += (_, _) => { }; host.BeginOutputReadLine(); host.BeginErrorReadLine();
        try
        {
            using var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(5) }; for (var i = 0; i < 40; i++) { try { using var health = await client.GetAsync("/healthz"); if (health.IsSuccessStatusCode) break; } catch { } await Task.Delay(250); }
            await ObserveHttp(client, "unauthenticated", "/api/session", null, 401, "authentication_required", observed, valid);
            await ObserveHttp(client, "forbidden", "/api/admin/users", stranger.Token, 403, "admin_required", observed, valid);
            await ObserveHttp(client, "ownership_mismatch", "/api/projects/" + project.ProjectId, stranger.Token, 404, "project_not_found", observed, valid);

            var disable = await PostAdminAsync(client, "/api/admin/users/" + owner.AccountId + "/status", adminToken, new { disabled = true });
            if (disable.StatusCode != HttpStatusCode.OK) throw new InvalidOperationException("S51 account disable induction failed.");
            await ObserveHttp(client, "account_disabled", "/api/session", owner.Token, 401, "authentication_required", observed, valid);

            var enable = await PostAdminAsync(client, "/api/admin/users/" + owner.AccountId + "/status", adminToken, new { disabled = false });
            if (enable.StatusCode != HttpStatusCode.OK) throw new InvalidOperationException("S51 account re-enable induction failed.");
            var rotated = await PostAdminAsync(client, "/api/admin/users/" + owner.AccountId + "/rotate-token", adminToken, null);
            if (rotated.StatusCode != HttpStatusCode.OK) throw new InvalidOperationException("S51 credential rotation induction failed.");
            await ObserveHttp(client, "credential_revoked", "/api/session", owner.Token, 401, "authentication_required", observed, valid);

            await using (var connection = new SqliteConnection(cs))
            {
                await connection.OpenAsync();
                await using var command = connection.CreateCommand();
                command.CommandText = "ALTER TABLE project_limits RENAME TO s51_fault_project_limits";
                await command.ExecuteNonQueryAsync();
                try { await ObserveHttp(client, "internal_failure", "/api/admin/users", adminToken, 500, "unhandled_request_failed", observed, valid); }
                finally { command.CommandText = "ALTER TABLE s51_fault_project_limits RENAME TO project_limits"; await command.ExecuteNonQueryAsync(); }
            }
        }
        finally { if (!host.HasExited) { host.Kill(true); await host.WaitForExitAsync(); } }
    }

    private static async Task<HttpResponseMessage> PostAdminAsync(HttpClient client, string path, string token, object? payload)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        if (payload is not null) request.Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
        return await client.SendAsync(request);
    }

    private static async Task ObserveHttp(HttpClient client, string family, string path, string? token, int expectedStatus, string expectedError, Dictionary<string, object> observed, HashSet<string> valid)
    { using var request = new HttpRequestMessage(HttpMethod.Get, path); if (token is not null) request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token); using var response = await client.SendAsync(request); var body = await response.Content.ReadAsStringAsync(); observed[family] = new { status = (int)response.StatusCode, body }; try { using var document = JsonDocument.Parse(body); if ((int)response.StatusCode == expectedStatus && document.RootElement.TryGetProperty("error", out var error) && error.GetString() == expectedError && document.RootElement.TryGetProperty("requestId", out var requestId) && !string.IsNullOrWhiteSpace(requestId.GetString())) valid.Add(family); } catch (JsonException) { } }
    private static void Observe(string family, Func<object> action, Dictionary<string, object> observed, HashSet<string> valid, Func<object, bool> predicate) { try { var value = action(); observed[family] = new { value }; if (predicate(value)) valid.Add(family); } catch (Exception error) { observed[family] = new { exception = error.GetType().Name, message = error.Message }; } }
    private static byte[] Corrupt(byte[] value) { var copy = value.ToArray(); copy[^1] ^= 1; return copy; }
    private static string? ReadCategory(string cs, string attemptId) { using var connection = new SqliteConnection(cs); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "SELECT failure_category FROM restore_attempts WHERE attempt_id=$id"; command.Parameters.AddWithValue("$id", attemptId); return command.ExecuteScalar()?.ToString(); }
    private static string? ReadCategoryByKey(string cs, string key) { using var connection = new SqliteConnection(cs); connection.Open(); using var command = connection.CreateCommand(); command.CommandText = "SELECT failure_category FROM restore_attempts WHERE idempotency_key=$key"; command.Parameters.AddWithValue("$key", key); return command.ExecuteScalar()?.ToString(); }
    private static async Task InsertLeaseAsync(string cs, RunnerLease lease) { await using var connection = new SqliteConnection(cs); await connection.OpenAsync(); await using var command = connection.CreateCommand(); command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)"; command.Parameters.AddWithValue("$id", lease.LeaseId); command.Parameters.AddWithValue("$account", lease.AccountId); command.Parameters.AddWithValue("$project", lease.ProjectId); command.Parameters.AddWithValue("$fence", lease.Fence); await command.ExecuteNonQueryAsync(); }
    private static async Task InsertRouteAuthorityAsync(string cs) { await using var connection = new SqliteConnection(cs); await connection.OpenAsync(); await using var command = connection.CreateCommand(); command.CommandText = "INSERT INTO route_recovery_evidence(recorded_utc,authority_count,has_current_blocker,is_blocked,can_continue,source_order_json,blocker_json) VALUES($utc,8,0,0,1,$sources,'[]')"; command.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O")); command.Parameters.AddWithValue("$sources", JsonSerializer.Serialize(PhaseA.Platform.Workflow.HostedRouteRecoveryContract.SourceOrder)); await command.ExecuteNonQueryAsync(); }

    private sealed record FaultPointObservation(bool TerminatedAtCheckpoint, string? RecoveredStatus, int StagingFiles);
}
