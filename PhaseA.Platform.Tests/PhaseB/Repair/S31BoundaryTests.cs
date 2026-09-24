using System.Text.Json;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Net.Http.Headers;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S31BoundaryTests
{
    [Fact]
    public async Task O_AB4321DB8007()
    {
        // ADR-0061: observe actual restore failures independently of caller-supplied keys.
        var repository = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var root = Path.Combine(repository, "logs", "quick-dev", "s31-restore-invocations", Guid.NewGuid().ToString("N"));
        var source = Path.Combine(root, "workspaces", "project", "repo");
        Directory.CreateDirectory(source);
        var nonce = Guid.NewGuid().ToString("N");
        File.WriteAllText(Path.Combine(source, "retained.txt"), nonce);
        var connectionString = new SqliteConnectionStringBuilder { DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false }.ToString();
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"), ["PHASEA_REPOSITORY_ROOT"] = repository
        });
        var store = new PhaseAMetadataStore(connectionString, options);
        var account = await store.CreateUserAccountAsync("s31-owner", 1);
        var workspace = Path.GetDirectoryName(source)!;
        var project = await store.CreateProjectAsync(new ProjectCreationCommand("s31-" + nonce, account.AccountId, "Restore fixture", "Restore fixture", "manual", "default", false, [], workspace, source, Path.Combine(workspace, "runtime"), Path.Combine(workspace, "meta")));
        if (!project.Succeeded || project.ProjectId is null) throw new InvalidOperationException("S31 fixture project creation failed.");
        var context = new RequestContext("s31-owner", account.AccountId, new HashSet<string> { "user" }, "s31-disposable-credential", "s31-" + nonce);
        var storage = new WorkspaceStorageService(connectionString);
        storage.SetQuota(account.AccountId, 1024 * 1024);
        var manifest = storage.CreateSnapshot(context, source, "snapshot-control", "workspace-control", project.ProjectId, "s31-policy", new HashSet<string>(StringComparer.OrdinalIgnoreCase)).Manifest;
        var service = new RestoreService(connectionString);
        var issues = new List<string>();
        var observations = new List<object>();
        var controlLease = new RunnerLease("lease-control", account.AccountId, project.ProjectId, 1);
        await SeedLeaseAsync(connectionString, controlLease);
        var destination = Path.Combine(root, "control");
        var control = service.Restore(context, manifest, source, destination, controlLease, "control");
        if (control.Status != RestoreAttemptStatus.Published || File.ReadAllText(Path.Combine(destination, ".restore-current", "retained.txt")) != nonce) throw new InvalidOperationException("S31 positive nonempty restore control failed.");
        var controlRow = ReadFailure(connectionString, control.AttemptId);
        if (controlRow.Category is not null || controlRow.Envelope is not null) issues.Add("published-control:unexpected-failure-fields");
        var families = new[] { "snapshot_corrupt", "schema_unsupported", "quota_exceeded" };
        for (var index = 0; index < families.Length; index++)
        {
            var family = families[index];
            var lease = new RunnerLease("lease-" + family, account.AccountId, project.ProjectId, index + 2);
            await SeedLeaseAsync(connectionString, lease);
            var damaged = manifest;
            if (family == "snapshot_corrupt") { var payload = manifest.ProtectedContent!.ToArray(); payload[^1] ^= 1; damaged = manifest with { ProtectedContent = payload }; }
            else if (family == "schema_unsupported") damaged = manifest with { SchemaVersion = "snapshot-manifest/unsupported" };
            else storage.SetQuota(account.AccountId, 0);
            var request = context with { CorrelationId = "s31-" + family + "-" + nonce };
            var target = Path.Combine(root, family);
            var result = service.Restore(request, damaged, source, target, lease, Guid.NewGuid().ToString("N"));
            var row = ReadFailure(connectionString, result.AttemptId);
            if (result.Status != RestoreAttemptStatus.Quarantined) issues.Add(family + ":not-quarantined");
            if (Directory.Exists(Path.Combine(target, ".restore-current"))) issues.Add(family + ":invalid-content-published");
            if (row.Category != family) issues.Add(family + ":missing-or-wrong-typed-category");
            if (row.Envelope is null) issues.Add(family + ":missing-safe-envelope");
            else
            {
                try
                {
                    using var envelope = JsonDocument.Parse(row.Envelope);
                    var body = envelope.RootElement;
                    if (!body.TryGetProperty("code", out var code) || code.GetString() != family) issues.Add(family + ":wrong-envelope-code");
                    if (!body.TryGetProperty("requestId", out var requestId) || requestId.GetString() != request.CorrelationId) issues.Add(family + ":missing-request-correlation");
                    if (!body.TryGetProperty("message", out var message) || string.IsNullOrWhiteSpace(message.GetString())) issues.Add(family + ":missing-safe-message");
                }
                catch (JsonException) { issues.Add(family + ":unstructured-envelope"); }
                if (row.Envelope.Contains(root, StringComparison.OrdinalIgnoreCase) || row.Envelope.Contains("System.", StringComparison.Ordinal) || row.Envelope.Contains(context.CredentialId, StringComparison.Ordinal)) issues.Add(family + ":unsafe-envelope");
            }
            observations.Add(new { family, result.AttemptId, result.Status, category = row.Category, envelope = row.Envelope });
        }
        issues.AddRange(await ObserveHttpFailuresAsync(repository, Path.Combine(root, "http")));
        File.WriteAllText(Path.Combine(root, "observations.json"), JsonSerializer.Serialize(new { observations, issues }));
        if (issues.Count > 0) throw new Xunit.Sdk.XunitException("FAILURE-O-AB4321DB8007: " + string.Join("; ", issues));
    }

    private static async Task<List<string>> ObserveHttpFailuresAsync(string repository, string root)
    {
        // ADR-0061/0038: request-aware producer evidence, never test-written diagnostic rows.
        var data = Path.Combine(root, "data");
        var workspace = Path.Combine(root, "workspaces", "owned-project");
        var repo = Path.Combine(workspace, "repo");
        Directory.CreateDirectory(data);
        Directory.CreateDirectory(repo);
        var database = Path.Combine(data, "metadata.sqlite3");
        var connectionString = new SqliteConnectionStringBuilder { DataSource = database, Pooling = false }.ToString();
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var adminToken = "s31-disposable-admin-" + Guid.NewGuid().ToString("N");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            ["PHASEA_REPOSITORY_ROOT"] = repository,
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken)
        });
        var store = new PhaseAMetadataStore(connectionString, options);
        await store.EnsureSingleAdminAsync();
        var owner = await store.CreateUserAccountAsync("s31-http-owner", 1);
        var stranger = await store.CreateUserAccountAsync("s31-http-stranger", 1);
        var project = await store.CreateProjectAsync(new ProjectCreationCommand(
            "s31-http-" + Guid.NewGuid().ToString("N"), owner.AccountId, "HTTP fixture", "HTTP fixture", "manual", "default", false, [],
            workspace, repo, Path.Combine(workspace, "runtime"), Path.Combine(workspace, "meta")));
        if (!project.Succeeded || project.ProjectId is null) throw new InvalidOperationException("S31 HTTP project setup failed.");
        await store.SetProjectBootstrapStatusAsync(project.ProjectId, "succeeded", null);
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        var address = $"http://127.0.0.1:{((IPEndPoint)listener.LocalEndpoint).Port}";
        listener.Stop();
        var start = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = Path.Combine(repository, "PhaseA.Platform"), UseShellExecute = false,
            CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true
        };
        start.ArgumentList.Add(Path.Combine(AppContext.BaseDirectory, "PhaseA.Platform.dll"));
        start.Environment["APP_BIND_URL"] = address;
        start.Environment["ASPNETCORE_URLS"] = address;
        start.Environment["PUBLIC_BASE_URL"] = "https://localhost";
        start.Environment["PHASEA_METADATA_DB_PATH"] = database;
        start.Environment["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces");
        start.Environment["PHASEA_REPOSITORY_ROOT"] = repository;
        start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken);
        start.Environment["PHASEA_SERVICE_STATE"] = "test";
        using var host = Process.Start(start) ?? throw new InvalidOperationException("S31 HTTP host failed to start.");
        host.OutputDataReceived += (_, _) => { };
        host.ErrorDataReceived += (_, _) => { };
        host.BeginOutputReadLine();
        host.BeginErrorReadLine();
        var issues = new List<string>();
        var observations = new List<object>();
        var requests = new List<(string Family, string? RequestId, int Status)>();
        try
        {
            using var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(5) };
            var healthy = false;
            for (var attempt = 0; attempt < 40 && !host.HasExited; attempt++)
            {
                try { using var response = await client.GetAsync("/healthz"); if (response.IsSuccessStatusCode) { healthy = true; break; } }
                catch (Exception error) when (error is HttpRequestException or TaskCanceledException) { }
                await Task.Delay(250);
            }
            if (!healthy) throw new InvalidOperationException("S31 HTTP host health precondition failed.");
            using var controlRequest = new HttpRequestMessage(HttpMethod.Get, "/api/projects");
            controlRequest.Headers.Authorization = new AuthenticationHeaderValue("Bearer", owner.Token);
            using var control = await client.SendAsync(controlRequest);
            if (!control.IsSuccessStatusCode || !(await control.Content.ReadAsStringAsync()).Contains(project.ProjectId, StringComparison.Ordinal))
                throw new InvalidOperationException("S31 owned project inventory HTTP control failed.");

            async Task Observe(string family, string path, string? token, int expectedStatus, string expectedError)
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, path);
                if (token is not null) request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
                using var response = await client.SendAsync(request);
                var text = await response.Content.ReadAsStringAsync();
                var unsafePayload = new[] { adminToken, owner.Token, stranger.Token, root, "System.", "StackTrace", "no such table" }
                    .Any(value => text.Contains(value, StringComparison.Ordinal));
                if (unsafePayload) { issues.Add(family + ":unsafe-public-payload"); return; }
                using var payload = JsonDocument.Parse(text);
                var body = payload.RootElement;
                var requestId = body.TryGetProperty("requestId", out var id) ? id.GetString() : null;
                if ((int)response.StatusCode != expectedStatus) issues.Add(family + ":wrong-status");
                if (!body.TryGetProperty("error", out var error) || error.GetString() != expectedError) issues.Add(family + ":legacy-error-changed");
                if (string.IsNullOrWhiteSpace(requestId)) issues.Add(family + ":missing-request-id");
                if (!response.Headers.CacheControl?.NoStore ?? true) issues.Add(family + ":missing-no-store");
                requests.Add((family, requestId, (int)response.StatusCode));
                observations.Add(new { family, status = (int)response.StatusCode, requestId, error = expectedError });
            }
            await Observe("unauthenticated", "/api/session", null, 401, "authentication_required");
            await Observe("ownership_mismatch", "/api/projects/" + project.ProjectId, stranger.Token, 404, "project_not_found");
            // A real read fails against this disposable database; never against live metadata.
            await using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync();
                await using var command = connection.CreateCommand();
                command.CommandText = "ALTER TABLE project_limits RENAME TO s31_fault_project_limits";
                await command.ExecuteNonQueryAsync();
                try { await Observe("internal_failure", "/api/admin/users", adminToken, 500, "unhandled_request_failed"); }
                finally { command.CommandText = "ALTER TABLE s31_fault_project_limits RENAME TO project_limits"; await command.ExecuteNonQueryAsync(); }
            }
            var diagnosticPath = Path.Combine(root, "runtime", "request-failure-diagnostics.jsonl");
            var rows = File.Exists(diagnosticPath) ? File.ReadAllLines(diagnosticPath) : [];
            foreach (var observed in requests)
            {
                var matches = 0;
                foreach (var line in rows)
                {
                    if (new[] { adminToken, owner.Token, stranger.Token, PhaseAAuth.HashTokenForStorage(owner.Token) }.Any(secret => line.Contains(secret, StringComparison.Ordinal)))
                        issues.Add("diagnostic:credential-leak");
                    using var row = JsonDocument.Parse(line);
                    var value = row.RootElement;
                    if (observed.RequestId is not null && value.TryGetProperty("requestId", out var id) && id.GetString() == observed.RequestId &&
                        value.TryGetProperty("failureFamily", out var family) && family.GetString() == observed.Family &&
                        value.TryGetProperty("statusCode", out var status) && status.GetInt32() == observed.Status) matches++;
                }
                if (matches != 1) issues.Add(observed.Family + ":missing-or-duplicate-correlated-diagnostic");
            }
            if (requests.Count != 3 || requests.Where(x => x.RequestId is not null).Select(x => x.RequestId).Distinct().Count() != 3)
                issues.Add("http:request-identities-not-distinct");
            File.WriteAllText(Path.Combine(root, "observations.json"), JsonSerializer.Serialize(new { observations, issues }));
        }
        finally
        {
            if (!host.HasExited) { host.Kill(entireProcessTree: true); await host.WaitForExitAsync(); }
        }
        return issues;
    }

    private static (string? Category, string? Envelope) ReadFailure(string connectionString, string attemptId)
    {
        using var connection = new SqliteConnection(connectionString); connection.Open(); using var command = connection.CreateCommand();
        command.CommandText = "SELECT failure_category,error_envelope FROM restore_attempts WHERE attempt_id=$id"; command.Parameters.AddWithValue("$id", attemptId);
        using var reader = command.ExecuteReader(); if (!reader.Read()) throw new InvalidOperationException("S31 producer did not persist its returned attempt.");
        return (reader.IsDBNull(0) ? null : reader.GetString(0), reader.IsDBNull(1) ? null : reader.GetString(1));
    }

    private static async Task SeedLeaseAsync(string connectionString, RunnerLease lease)
    {
        await using var connection = new SqliteConnection(connectionString); await connection.OpenAsync(); await using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence)";
        command.Parameters.AddWithValue("$id", lease.LeaseId); command.Parameters.AddWithValue("$account", lease.AccountId); command.Parameters.AddWithValue("$project", lease.ProjectId); command.Parameters.AddWithValue("$fence", lease.Fence); await command.ExecuteNonQueryAsync();
    }
}
