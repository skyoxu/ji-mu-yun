using System.Net;
using System.Diagnostics;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Net.Sockets;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S14BoundaryTests
{
    private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
        ?? FindRepositoryRoot(Directory.GetCurrentDirectory());
    private static readonly string PlatformAssemblyPath = typeof(Program).Assembly.Location;
    private readonly ITestOutputHelper _output;

    public S14BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public async Task O_11DDC0AAE540()
    {
        var root = Path.Combine(Path.GetTempPath(), "s14-durable-operations-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var databasePath = Path.Combine(root, "metadata.sqlite3");
        var workspaceRoot = Path.Combine(root, "workspaces");
        Directory.CreateDirectory(workspaceRoot);
        var previousKeyRoot = Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT");
        Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", Path.Combine(root, "snapshot-keys"));
        Process? process = null;
        RunnerIsolationHandle? isolationHandle = null;
        try
        {
            var connectionString = $"Data Source={databasePath}";
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var user = await store.CreateUserAccountAsync("s14-user", 1);
            var projectRoot = Path.Combine(workspaceRoot, "project-s14");
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                "project-s14", user.AccountId, "S14", "S14", "manual", "default", false, [],
                projectRoot, Path.Combine(projectRoot, "repo"), Path.Combine(projectRoot, "runtime"), Path.Combine(projectRoot, "repo", "meta")));
            await store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null);
            SeedRouteRecoverySources(connectionString, project.ProjectId!, projectRoot);
            _ = new RestoreService(connectionString);
            _ = new WorkspaceStorageService(connectionString).SetQuota(user.AccountId, 1_000_000_000);
            using (var leaseConnection = new SqliteConnection(connectionString))
            {
                leaseConnection.Open();
                using var leaseCommand = leaseConnection.CreateCommand();
                leaseCommand.CommandText = """
                    INSERT INTO runner_leases(lease_id, account_id, project_id, fence)
                    VALUES($lease, $account, $project, 1);
                    INSERT INTO restore_runtime_credentials(workspace_id, credential_id)
                    VALUES($workspace, $credential);
                    """;
                leaseCommand.Parameters.AddWithValue("$lease", "s14-lease");
                leaseCommand.Parameters.AddWithValue("$account", user.AccountId);
                leaseCommand.Parameters.AddWithValue("$project", project.ProjectId!);
                leaseCommand.Parameters.AddWithValue("$workspace", project.WorkspaceId);
                leaseCommand.Parameters.AddWithValue("$credential", user.Token);
                leaseCommand.ExecuteNonQuery();
            }
            var seededAuthority = new RouteRecoveryAuthorityResolver(connectionString).Resolve(user.AccountId, project.ProjectId!);
            _output.WriteLine($"S14-AUTHORITY canContinue={seededAuthority.CanContinue} count={seededAuthority.AuthorityCount} blockers={string.Join(',', seededAuthority.Blockers)} sources={string.Join('|', seededAuthority.SourceEvidence)}");
            isolationHandle = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
                user.AccountId,
                project.ProjectId!,
                "NT AUTHORITY\\LOCAL SERVICE",
                projectRoot,
                LowPrivilegeRequired: true,
                JobObjectRequired: OperatingSystem.IsWindows(),
                NtfsAclRequired: OperatingSystem.IsWindows()));
            File.WriteAllText(Path.Combine(projectRoot, "s14-content.txt"), "S14");

            var url = $"http://127.0.0.1:{FreePort()}";
            process = StartServer(url, databasePath, workspaceRoot);
            using var healthClient = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(10) };
            await WaitForHealthAsync(healthClient, process);

            var snapshotRequest = new OperationRequest("snapshot", $"/api/projects/{project.ProjectId}/snapshots", "s14-snapshot");
            var snapshotAdmission = await InvokeThenDisconnectAsync(url, user.Token, snapshotRequest);
            var snapshotRun = await WaitForRunAsync(url, user.Token, snapshotAdmission.OperationId!);
            _output.WriteLine($"S14-SNAPSHOT status={snapshotRun.Status} progress={snapshotRun.ProgressLabel} exit={snapshotRun.ExitCode} stderr={snapshotRun.Stderr}");
            var snapshotReentry = await InvokeThenDisconnectAsync(url, user.Token, snapshotRequest);
            Require(snapshotAdmission.StatusCode == HttpStatusCode.Accepted &&
                    snapshotAdmission.OperationId == snapshotReentry.OperationId,
                "FAILURE-O-11DDC0AAE540", "Snapshot admission was not idempotent after client disconnect.");
            Require(snapshotRun.Status == "succeeded" && !string.IsNullOrWhiteSpace(snapshotRun.SnapshotId),
                "FAILURE-O-11DDC0AAE540", "Snapshot operation did not produce a persisted business result.");

            var queuedBeforeRestart = await store.GetOrCreateProjectOperationRunAsync(
                project.ProjectId!, project.WorkspaceId!, "workspace-snapshot:s14-restart-queued");
            var runningBeforeRestart = await store.GetOrCreateProjectOperationRunAsync(
                project.ProjectId!, project.WorkspaceId!, "workspace-restore:s14-restart-running");
            await store.MarkRunStartedAsync(runningBeforeRestart.RunId);
            Require(queuedBeforeRestart.Status == "queued" &&
                    (await store.GetRunSnapshotAsync(runningBeforeRestart.RunId))?.Status == "running",
                "FAILURE-O-11DDC0AAE540", "Restart fixture did not persist both interrupted operation states.");

            process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync();
            process.Dispose();
            process = StartServer(url, databasePath, workspaceRoot);
            await WaitForHealthAsync(healthClient, process);
            foreach (var interrupted in new[] { queuedBeforeRestart, runningBeforeRestart })
            {
                var recovered = await WaitForRunAsync(url, user.Token, interrupted.RunId);
                Require(recovered.Status == "failed" &&
                        recovered.ExitCode == 500 &&
                        recovered.Stderr.Contains("service restarted", StringComparison.Ordinal),
                    "FAILURE-O-11DDC0AAE540", "Restart did not durably fail an interrupted workspace operation.");
            }
            var queuedReentry = await InvokeThenDisconnectAsync(
                url, user.Token,
                new OperationRequest("snapshot", $"/api/projects/{project.ProjectId}/snapshots", "s14-restart-queued"));
            Require(queuedReentry.OperationId == queuedBeforeRestart.RunId &&
                    (await WaitForRunAsync(url, user.Token, queuedReentry.OperationId!)).Status == "failed",
                "FAILURE-O-11DDC0AAE540", "Interrupted operation reentry did not retain its stable failed result.");
            _output.WriteLine("S14-OBSERVATION durable-operation-state-survives-application-restart");

            var alternateRoot = Path.Combine(projectRoot, "alternate-restore-root");
            var restoreRequest = new OperationRequest("restore", $"/api/projects/{project.ProjectId}/restores", "s14-restore", snapshotRun.SnapshotId, alternateRoot);
            var restoreAdmission = await InvokeThenDisconnectAsync(url, user.Token, restoreRequest);
            RunObservation restoreRun;
            try
            {
                restoreRun = await WaitForRunAsync(url, user.Token, restoreAdmission.OperationId!);
            }
            catch (Exception error)
            {
                var checkpoints = Directory.Exists(Path.Combine(alternateRoot, ".restore-checkpoints"))
                    ? string.Join('|', Directory.EnumerateFiles(Path.Combine(alternateRoot, ".restore-checkpoints"), "*.json", SearchOption.AllDirectories).Select(Path.GetFileName))
                    : "";
                _output.WriteLine($"S14-RESTORE-TIMEOUT checkpoints={checkpoints} error={error.GetType().Name}");
                throw;
            }
            _output.WriteLine($"S14-RESTORE status={restoreRun.Status} progress={restoreRun.ProgressLabel} exit={restoreRun.ExitCode} failure={restoreRun.FailureCategory} detail={restoreRun.FailureDetail} stderr={restoreRun.Stderr}");
            Require(restoreRun.Status == "succeeded" &&
                    File.Exists(Path.Combine(alternateRoot, ".restore-current", "s14-content.txt")),
                "FAILURE-O-11DDC0AAE540", "Restore did not publish the selected Snapshot to the alternate root.");

            var aclRequest = new OperationRequest("acl-repair", $"/api/projects/{project.ProjectId}/acl-repairs", "s14-acl-repair");
            var aclAdmission = await InvokeThenDisconnectAsync(url, user.Token, aclRequest);
            var aclRun = await WaitForRunAsync(url, user.Token, aclAdmission.OperationId!);
            _output.WriteLine($"S14-ACL status={aclRun.Status} progress={aclRun.ProgressLabel} exit={aclRun.ExitCode} failure={aclRun.FailureCategory} detail={aclRun.FailureDetail} stderr={aclRun.Stderr}");
            Require(aclRun.Status == "succeeded", "FAILURE-O-11DDC0AAE540", "ACL repair did not persist a successful business result.");
            _output.WriteLine("S14-OBSERVATION O-11DDC0AAE540 durable-operations-survive-browser-disconnect");
        }
        finally
        {
            if (process is { HasExited: false })
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync();
            }
            process?.Dispose();
            isolationHandle?.Dispose();
            Environment.SetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT", previousKeyRoot);
            SqliteConnection.ClearAllPools();
            if (Directory.Exists(root))
            {
                await DeleteDirectoryWithRetryAsync(root);
            }
        }
    }

    private static async Task<OperationObservation> InvokeThenDisconnectAsync(string url, string token, OperationRequest operation)
    {
        using var client = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(10) };
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        using var request = new HttpRequestMessage(HttpMethod.Post, operation.Path)
        {
            Content = JsonContent.Create(new { operationKey = operation.Key, snapshotId = operation.SnapshotId, targetRoot = operation.TargetRoot })
        };
        request.Headers.ConnectionClose = true;
        using var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
        var location = response.Headers.Location?.ToString();
        var operationId = location?.Split('/', StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
        return new OperationObservation(operation.Name, response.StatusCode, operationId, "accepted");
    }

    private static async Task<RunObservation> WaitForRunAsync(string url, string token, string runId)
    {
        using var client = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(60) };
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        var lastStatus = "unknown";
        for (var attempt = 0; attempt < 240; attempt++)
        {
            using var response = await client.GetAsync($"/api/runs/{runId}");
            if (response.IsSuccessStatusCode)
            {
                using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
                var run = document.RootElement.GetProperty("run");
                var evidence = run.TryGetProperty("evidenceJson", out var evidenceNode) ? evidenceNode.GetString() : null;
                string? snapshotId = null;
                string? failureCategory = null;
                string? failureDetail = null;
                if (!string.IsNullOrWhiteSpace(evidence))
                {
                    using var evidenceDocument = JsonDocument.Parse(evidence);
                    if (evidenceDocument.RootElement.TryGetProperty("snapshotId", out var snapshotNode))
                        snapshotId = snapshotNode.GetString();
                    if (evidenceDocument.RootElement.TryGetProperty("failureCategory", out var failureNode) && failureNode.ValueKind == JsonValueKind.String)
                        failureCategory = failureNode.GetString();
                    if (evidenceDocument.RootElement.TryGetProperty("failureDetail", out var detailNode) && detailNode.ValueKind == JsonValueKind.String)
                        failureDetail = detailNode.GetString();
                }
                var status = run.GetProperty("status").GetString() ?? "";
                lastStatus = status;
                if (run.TryGetProperty("progressLabel", out var progress) && progress.ValueKind == JsonValueKind.String)
                    lastStatus += "/" + progress.GetString();
                if (status is "succeeded" or "failed")
                    return new RunObservation(
                        status,
                        snapshotId,
                        run.TryGetProperty("progressLabel", out var progressLabelNode) && progressLabelNode.ValueKind == JsonValueKind.String ? progressLabelNode.GetString() ?? "" : "",
                        run.TryGetProperty("exitCode", out var exitCodeNode) && exitCodeNode.ValueKind == JsonValueKind.Number ? exitCodeNode.GetInt32() : null,
                        run.TryGetProperty("stderrText", out var stderrNode) && stderrNode.ValueKind == JsonValueKind.String ? stderrNode.GetString() ?? "" : "",
                        failureCategory,
                        failureDetail);
            }
            await Task.Delay(250);
        }
        throw new TimeoutException($"Run {runId} did not complete; last status={lastStatus}.");
    }

    private static (string? OperationId, string? Result) ReadOperationFields(string body)
    {
        try
        {
            using var document = JsonDocument.Parse(body);
            var root = document.RootElement;
            return (
                root.TryGetProperty("operationId", out var operationId) ? operationId.GetString() : null,
                root.TryGetProperty("result", out var result) ? result.GetRawText() : null);
        }
        catch (JsonException)
        {
            return (null, null);
        }
    }

    private static void SeedRouteRecoverySources(string connectionString, string projectId, string projectRoot)
    {
        Directory.CreateDirectory(Path.Combine(projectRoot, "repo", "meta"));
        Directory.CreateDirectory(Path.Combine(projectRoot, "repo", "routes", "prototype-contract"));
        Directory.CreateDirectory(Path.Combine(projectRoot, "repo", "meta", "routes", "prototype"));
        File.WriteAllText(Path.Combine(projectRoot, "repo", "meta", "project-execution-guide.md"), "S14 execution guide");
        File.WriteAllText(Path.Combine(projectRoot, "repo", "routes", "prototype-contract", "latest.json"), "{}");
        File.WriteAllText(Path.Combine(projectRoot, "repo", "meta", "routes", "prototype", "latest.json"), "{}");
        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using var update = connection.CreateCommand();
        update.CommandText = "UPDATE projects SET game_type_match_json=$match WHERE id=$project";
        update.Parameters.AddWithValue("$match", "{\"game_type\":\"manual\"}");
        update.Parameters.AddWithValue("$project", projectId);
        update.ExecuteNonQuery();
        using var binding = connection.CreateCommand();
        binding.CommandText = "INSERT INTO project_route_prompt_evidence_bindings(project_id,route_id,execution_prompt_hash,persisted_prompt_hash,prompt_artifact_ref,prompt_evidence_ref,updated_utc) VALUES($project,'s14-route','hash-a','hash-b','meta/prompt.json','meta/prompt-evidence.json',$utc)";
        binding.Parameters.AddWithValue("$project", projectId);
        binding.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O"));
        binding.ExecuteNonQuery();
    }

    private static Process StartServer(string url, string databasePath, string workspaceRoot)
    {
        var start = new ProcessStartInfo("dotnet", $"\"{PlatformAssemblyPath}\"")
        {
            WorkingDirectory = Path.GetDirectoryName(PlatformAssemblyPath)!,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        start.Environment["APP_BIND_URL"] = url;
        start.Environment["ASPNETCORE_URLS"] = url;
        start.Environment["PUBLIC_BASE_URL"] = "https://localhost";
        start.Environment["PHASEA_METADATA_DB_PATH"] = databasePath;
        start.Environment["HOSTED_WORKSPACE_ROOT"] = workspaceRoot;
        start.Environment["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot;
        start.Environment["ASPNETCORE_CONTENTROOT"] = Path.Combine(RepositoryRoot, "PhaseA.Platform");
        return Process.Start(start) ?? throw new InvalidOperationException("Failed to start PhaseA.Platform.");
    }

    private static async Task WaitForHealthAsync(HttpClient client, Process process)
    {
        Exception? last = null;
        for (var attempt = 0; attempt < 40; attempt++)
        {
            if (process.HasExited)
            {
                throw new InvalidOperationException($"Temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
            }
            try
            {
                if ((await client.GetAsync("/healthz")).IsSuccessStatusCode)
                {
                    return;
                }
            }
            catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException)
            {
                last = exception;
            }
            await Task.Delay(250);
        }
        throw new InvalidOperationException("Temporary PhaseA.Platform did not become healthy.", last);
    }

    private static int FreePort()
    {
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        return port;
    }

    private static string FindRepositoryRoot(string startingDirectory)
    {
        for (var directory = new DirectoryInfo(startingDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "PhaseA.Platform", "PhaseA.Platform.csproj")))
            {
                return directory.FullName;
            }
        }

        throw new DirectoryNotFoundException("Repository root containing PhaseA.Platform was not found.");
    }

    private static async Task DeleteDirectoryWithRetryAsync(string path)
    {
        for (var attempt = 0; attempt < 30; attempt++)
        {
            try
            {
                Directory.Delete(path, recursive: true);
                return;
            }
            catch (IOException) when (attempt < 29)
            {
                SqliteConnection.ClearAllPools();
                await Task.Delay(100);
            }
        }
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed record OperationRequest(string Name, string Path, string Key, string? SnapshotId = null, string? TargetRoot = null);
    private sealed record OperationObservation(string Name, HttpStatusCode StatusCode, string? OperationId, string? Result);
    private sealed record RunObservation(string Status, string? SnapshotId, string ProgressLabel, int? ExitCode, string Stderr, string? FailureCategory, string? FailureDetail);
}
