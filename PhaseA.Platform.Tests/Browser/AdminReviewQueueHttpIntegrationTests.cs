using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Net.Sockets;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.Browser;

[CollectionDefinition("PhaseA process HTTP", DisableParallelization = true)]
public sealed class PhaseAProcessHttpCollection
{
}

[Collection("PhaseA process HTTP")]
public sealed class AdminReviewQueueHttpIntegrationTests
{
    private static readonly string RepositoryRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));

    [Fact]
    public async Task AdminReviewQueueEndpoints_EnforceAuthValidationConflictAndNoStoreOverHttp()
    {
        var root = Path.Combine(Path.GetTempPath(), "phasea-admin-review-http-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var databasePath = Path.Combine(root, "metadata.sqlite3");
        var workspaceRoot = Path.Combine(root, "workspaces");
        Directory.CreateDirectory(workspaceRoot);
        var connectionString = $"Data Source={databasePath}";
        const string adminToken = "integration-admin-token";
        Process? process = null;
        try
        {
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var adminId = await store.EnsureSingleAdminAsync();
            var user = await store.CreateUserAccountAsync("http-user", 1);
            var projectRoot = Path.Combine(workspaceRoot, "project-http");
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                "project-http", adminId, "HTTP", "HTTP", "manual", "default", false, [],
                projectRoot, Path.Combine(projectRoot, "repo"), Path.Combine(projectRoot, "runtime"), Path.Combine(projectRoot, "repo", "meta")));
            await store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null);
            var projectSnapshot = await store.GetProjectSnapshotAsync(project.ProjectId!);
            var decisionEvidencePath = Path.Combine(projectSnapshot!.RepoPath, "meta", "reviews", "http-decision.json");
            Directory.CreateDirectory(Path.GetDirectoryName(decisionEvidencePath)!);
            await File.WriteAllTextAsync(decisionEvidencePath, "{}");
            File.Exists(decisionEvidencePath).Should().BeTrue();
            var entry = await store.UpsertProjectAdminReviewQueueEntryAsync(new ProjectAdminReviewQueueCommand(
                adminId, project.ProjectId!, "gdd-requirements", "REQ-HTTP", "P1", "HTTP blocker",
                "meta/routes/gdd-requirements/latest.json", "[]"));

            var port = FreePort();
            var url = $"http://127.0.0.1:{port}";
            process = StartServer(url, databasePath, workspaceRoot, adminToken);
            using var client = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(10) };
            await WaitForHealthAsync(client, process);
            File.Exists(decisionEvidencePath).Should().BeTrue();

            var unauthorized = await client.GetAsync("/api/admin/project-admin-review-queue");
            unauthorized.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
            AssertNoStore(unauthorized);

            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", user.Token);
            var forbidden = await client.GetAsync("/api/admin/project-admin-review-queue");
            forbidden.StatusCode.Should().Be(HttpStatusCode.Forbidden);
            AssertNoStore(forbidden);

            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", adminToken);
            var ok = await client.GetAsync("/api/admin/project-admin-review-queue?status=open&severity=P1&limit=100");
            ok.StatusCode.Should().Be(HttpStatusCode.OK);
            AssertNoStore(ok);

            var invalid = await client.GetAsync("/api/admin/project-admin-review-queue?status=looks_complete&minimumAgeMinutes=-1&limit=501");
            invalid.StatusCode.Should().Be(HttpStatusCode.BadRequest);
            (await invalid.Content.ReadAsStringAsync()).Should().Contain("validation_failed");
            AssertNoStore(invalid);

            var missing = await client.PostAsJsonAsync("/api/admin/project-admin-review-queue/missing/decision",
                new ProjectAdminReviewDecisionRequest("approved", "missing", 0));
            missing.StatusCode.Should().Be(HttpStatusCode.NotFound);
            AssertNoStore(missing);

            var noEvidence = await client.PostAsJsonAsync($"/api/admin/project-admin-review-queue/{entry.Id}/decision",
                new ProjectAdminReviewDecisionRequest("approved", "accepted", 0));
            noEvidence.StatusCode.Should().Be(HttpStatusCode.BadRequest);
            (await noEvidence.Content.ReadAsStringAsync()).Should().Contain("admin_review_decision_evidence_required");
            AssertNoStore(noEvidence);

            var decided = await client.PostAsJsonAsync($"/api/admin/project-admin-review-queue/{entry.Id}/decision",
                new
                {
                    decisionStatus = "approved",
                    decisionReason = "accepted",
                    expectedDecisionVersion = 0,
                    decisionEvidenceRefs = new[] { "meta/reviews/http-decision.json" }
                });
            var decidedBody = await decided.Content.ReadAsStringAsync();
            decided.StatusCode.Should().Be(HttpStatusCode.OK, decidedBody);
            AssertNoStore(decided);

            var conflict = await client.PostAsJsonAsync($"/api/admin/project-admin-review-queue/{entry.Id}/decision",
                new ProjectAdminReviewDecisionRequest("rejected", "different stale payload", 0));
            conflict.StatusCode.Should().Be(HttpStatusCode.Conflict);
            AssertNoStore(conflict);
        }
        finally
        {
            if (process is { HasExited: false })
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync();
            }
            process?.Dispose();
            Microsoft.Data.Sqlite.SqliteConnection.ClearAllPools();
            if (Directory.Exists(root))
            {
                await DeleteDirectoryWithRetryAsync(root);
            }
        }
    }

    private static Process StartServer(string url, string databasePath, string workspaceRoot, string adminToken)
    {
        var start = new ProcessStartInfo("dotnet", $"\"{Path.Combine(AppContext.BaseDirectory, "PhaseA.Platform.dll")}\"")
        {
            WorkingDirectory = Path.Combine(RepositoryRoot, "PhaseA.Platform"),
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
        start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken);
        var process = Process.Start(start) ?? throw new InvalidOperationException("Failed to start PhaseA.Platform.");
        return process;
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

    private static void AssertNoStore(HttpResponseMessage response)
    {
        response.Headers.CacheControl.Should().NotBeNull();
        response.Headers.CacheControl!.NoStore.Should().BeTrue();
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
                Microsoft.Data.Sqlite.SqliteConnection.ClearAllPools();
                await Task.Delay(100);
            }
        }
    }
}
