using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S58BoundaryTests
{
    [Fact]
    public async Task O_1A7E73D125DE()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateUserAsync("s58-wrong-account-requester");
        var owner = await fixture.CreateUserAsync("s58-wrong-account-owner");
        var projectId = await fixture.CreateProjectAsync(owner.AccountId, "s58-private-project");

        var targetExists = await fixture.ProjectExistsAsync(projectId);
        using var response = await fixture.GetAsUserAsync(requester.Token, $"/api/projects/{projectId}/chat-history");
        var body = await response.Content.ReadAsStringAsync();

        Require(
            targetExists &&
            response.StatusCode == HttpStatusCode.NotFound &&
            body.Contains("project_not_found", StringComparison.Ordinal) &&
            !body.Contains(projectId, StringComparison.Ordinal) &&
            !ResponseHeadersContain(response, projectId),
            "FAILURE-O-1A7E73D125DE",
            "The wrong-account private-resource boundary disclosed target existence or a target path.");
    }

    [Fact]
    public async Task O_23FD839F9318()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s58-fresh-predecessor");

        using var rotation = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/rotate-token");
        var rotatedAt = Stopwatch.GetTimestamp();
        await Task.Delay(TimeSpan.FromSeconds(5.1));
        var freshRequest = await fixture.GetSessionAsync(target.Token);
        var elapsed = Stopwatch.GetElapsedTime(rotatedAt);

        Require(
            rotation.StatusCode == HttpStatusCode.OK &&
            elapsed >= TimeSpan.FromSeconds(5) &&
            freshRequest == HttpStatusCode.Unauthorized,
            "FAILURE-O-23FD839F9318",
            "The predecessor credential authorized a fresh protected request after the five-second rotation bound.");
    }

    [Fact]
    public async Task O_2FF634492AF9()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s58-rotation-order");
        var predecessor = target.Token;
        var trace = new List<string> { "predecessor_captured" };

        using var rotation = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/rotate-token");
        trace.Add("rotation_completed");
        var cachedRequest = await fixture.GetSessionAsync(predecessor, browserCacheMarker: true);
        trace.Add("cached_predecessor_checked");
        var freshRequest = await fixture.GetSessionAsync(predecessor);
        trace.Add("fresh_predecessor_checked");

        Require(
            !string.IsNullOrWhiteSpace(predecessor) &&
            rotation.StatusCode == HttpStatusCode.OK &&
            trace.SequenceEqual([
                "predecessor_captured",
                "rotation_completed",
                "cached_predecessor_checked",
                "fresh_predecessor_checked"
            ]) &&
            cachedRequest == HttpStatusCode.Unauthorized &&
            freshRequest == HttpStatusCode.Unauthorized,
            "FAILURE-O-2FF634492AF9",
            "Credential rotation was not completed and recorded before cached and fresh predecessor-credential checks.");
    }

    [Fact]
    public async Task O_A043E6A86196()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s58-revoked-credential");

        using var rotation = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/rotate-token");
        var bearerRequest = await fixture.GetSessionAsync(target.Token);
        var existingCookieRequest = await fixture.GetSessionAsync(target.Token, cookieOnly: true);

        Require(
            rotation.StatusCode == HttpStatusCode.OK &&
            bearerRequest == HttpStatusCode.Unauthorized &&
            existingCookieRequest == HttpStatusCode.Unauthorized,
            "FAILURE-O-A043E6A86196",
            "A revoked credential remained authorized through a stale credential or cookie session.");
    }

    [Fact]
    public async Task O_B5F50FBA08EE()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateUserAsync("s58-cache-requester");
        var target = await fixture.CreateUserAsync("s58-cache-target");

        using var absentCache = await fixture.PostAsUserAsync(requester.Token, $"/api/admin/users/{target.AccountId}/status", "{\"disabled\":true}");
        using var staleCache = await fixture.PostAsUserAsync(
            requester.Token,
            $"/api/admin/users/{target.AccountId}/status",
            "{\"disabled\":true}",
            [new("X-Browser-Cached-Role", "admin"), new("X-Browser-Cached-Capability", "account:disable")]);
        using var conflictingCache = await fixture.PostAsUserAsync(
            requester.Token,
            $"/api/admin/users/{target.AccountId}/status",
            "{\"disabled\":true}",
            [new("X-Browser-Cached-Role", "user"), new("X-Browser-Cached-Capability", "denied")]);
        var account = await fixture.GetAccountAsync(target.AccountId);
        var audits = await fixture.ListAuditEventsAsync(target.AccountId);

        Require(
            absentCache.StatusCode == HttpStatusCode.Forbidden &&
            staleCache.StatusCode == HttpStatusCode.Forbidden &&
            conflictingCache.StatusCode == HttpStatusCode.Forbidden &&
            account is { IsDisabled: false } &&
            CountDeniedDisableAudits(audits, target.AccountId) >= 3,
            "FAILURE-O-B5F50FBA08EE",
            "Browser-cached role or capability data affected the server authorization decision.");
    }

    [Fact]
    public async Task O_BC46A5C1C348()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var insufficientRequester = await fixture.CreateUserAsync("s58-insufficient-administrator");
        var target = await fixture.CreateUserAsync("s58-disable-target");

        using var response = await fixture.PostAsUserAsync(
            insufficientRequester.Token,
            $"/api/admin/users/{target.AccountId}/status",
            "{\"disabled\":true}");
        var account = await fixture.GetAccountAsync(target.AccountId);

        Require(
            response.StatusCode == HttpStatusCode.Forbidden &&
            account is { IsDisabled: false },
            "FAILURE-O-BC46A5C1C348",
            "An insufficient administrator role disabled the account or changed its persisted lifecycle state.");
    }

    [Fact]
    public async Task O_DA02CE96AA87()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s58-cached-predecessor");

        using var rotation = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/rotate-token");
        var rotatedAt = Stopwatch.GetTimestamp();
        await Task.Delay(TimeSpan.FromSeconds(5.1));
        var cachedRequest = await fixture.GetSessionAsync(target.Token, browserCacheMarker: true);
        var elapsed = Stopwatch.GetElapsedTime(rotatedAt);

        Require(
            rotation.StatusCode == HttpStatusCode.OK &&
            elapsed >= TimeSpan.FromSeconds(5) &&
            cachedRequest == HttpStatusCode.Unauthorized,
            "FAILURE-O-DA02CE96AA87",
            "The predecessor credential authorized a cached protected request after the five-second rotation bound.");
    }

    [Fact]
    public async Task O_F0E150DB52C5()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateUserAsync("s58-hidden-control-requester");
        var target = await fixture.CreateUserAsync("s58-hidden-control-target");

        using var absentControl = await fixture.PostAsUserAsync(requester.Token, $"/api/admin/users/{target.AccountId}/status", "{\"disabled\":true}");
        using var presentControl = await fixture.PostAsUserAsync(
            requester.Token,
            $"/api/admin/users/{target.AccountId}/status",
            "{\"disabled\":true,\"hiddenAdminControl\":true}",
            [new("X-Hidden-Admin-Control", "true")]);
        using var forgedControl = await fixture.PostAsUserAsync(
            requester.Token,
            $"/api/admin/users/{target.AccountId}/status",
            "{\"disabled\":true,\"hiddenAdminControl\":false}",
            [new("X-Hidden-Admin-Control", "forged")]);
        var account = await fixture.GetAccountAsync(target.AccountId);
        var audits = await fixture.ListAuditEventsAsync(target.AccountId);

        Require(
            absentControl.StatusCode == HttpStatusCode.Forbidden &&
            presentControl.StatusCode == HttpStatusCode.Forbidden &&
            forgedControl.StatusCode == HttpStatusCode.Forbidden &&
            account is { IsDisabled: false } &&
            CountDeniedDisableAudits(audits, target.AccountId) >= 3,
            "FAILURE-O-F0E150DB52C5",
            "Hidden browser-control state changed or bypassed the server authorization decision.");
    }

    private static int CountDeniedDisableAudits(IReadOnlyList<AdminAccountAuditEvent> audits, string accountId) =>
        audits.Count(entry =>
            entry.Action == "user_disabled" &&
            entry.TargetAccountId == accountId &&
            HasAuditOutcome(entry.MetadataJson, "denied"));

    private static bool HasAuditOutcome(string metadataJson, string outcome)
    {
        using var document = JsonDocument.Parse(metadataJson);
        return document.RootElement.TryGetProperty("outcome", out var value) &&
               value.ValueKind == JsonValueKind.String &&
               value.GetString() == outcome;
    }

    private static bool ResponseHeadersContain(HttpResponseMessage response, string value) =>
        response.Headers.Concat(response.Content.Headers)
            .Any(header => string.Join(",", header.Value).Contains(value, StringComparison.Ordinal));

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class BoundaryFixture : IAsyncDisposable
    {
        private const string AdminToken = "s58-valid-administrator-token";
        private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));

        private readonly string _root;
        private readonly PhaseAMetadataStore _store;
        private readonly Process _process;
        private readonly HttpClient _client;

        private BoundaryFixture(string root, PhaseAMetadataStore store, Process process, HttpClient client)
        {
            _root = root;
            _store = store;
            _process = process;
            _client = client;
        }

        public static async Task<BoundaryFixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s58-boundary-{Guid.NewGuid():N}");
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var workspaceRoot = Path.Combine(root, "workspaces");
            Directory.CreateDirectory(workspaceRoot);

            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath, Pooling = false }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot,
                ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken)
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            await store.EnsureSingleAdminAsync();

            var address = $"http://127.0.0.1:{FreePort()}";
            var process = StartServer(address, databasePath, workspaceRoot);
            var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(15) };
            try
            {
                await WaitForHealthAsync(client, process);
                return new BoundaryFixture(root, store, process, client);
            }
            catch
            {
                client.Dispose();
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                    await process.WaitForExitAsync();
                }
                process.Dispose();
                SqliteConnection.ClearAllPools();
                Directory.Delete(root, recursive: true);
                throw;
            }
        }

        public async Task<TestAccount> CreateUserAsync(string username)
        {
            var account = await _store.CreateUserAccountAsync(username, 2);
            return new TestAccount(account.AccountId, account.Token);
        }

        public async Task<string> CreateProjectAsync(string ownerAccountId, string name)
        {
            var projectId = $"s58-project-{Guid.NewGuid():N}";
            var projectRoot = Path.Combine(_root, "workspaces", "projects", projectId);
            var project = await _store.CreateProjectAsync(new ProjectCreationCommand(
                projectId,
                ownerAccountId,
                name,
                name,
                "manual",
                "default",
                false,
                [],
                projectRoot,
                Path.Combine(projectRoot, "repo"),
                Path.Combine(projectRoot, "runtime"),
                Path.Combine(projectRoot, "meta")));
            return project.ProjectId ?? throw new InvalidOperationException("S58 fixture did not create a project identifier.");
        }

        public async Task<bool> ProjectExistsAsync(string projectId) =>
            await _store.GetProjectSnapshotAsync(projectId) is not null;

        public async Task<AdminUserListItem?> GetAccountAsync(string accountId) =>
            (await _store.ListAccountsAsync()).SingleOrDefault(account => account.AccountId == accountId);

        public Task<IReadOnlyList<AdminAccountAuditEvent>> ListAuditEventsAsync(string accountId) =>
            _store.ListAdminAccountAuditEventsAsync(new AdminAccountAuditQuery(100, 0, null, accountId));

        public Task<HttpResponseMessage> GetAsUserAsync(string token, string path) => GetAsync(token, path, false, false);

        public Task<HttpResponseMessage> PostAsAdminAsync(string path, string? body = null) =>
            PostAsync(AdminToken, path, body, null);

        public Task<HttpResponseMessage> PostAsUserAsync(
            string token,
            string path,
            string? body = null,
            IReadOnlyList<KeyValuePair<string, string>>? headers = null) =>
            PostAsync(token, path, body, headers);

        public async Task<HttpStatusCode> GetSessionAsync(
            string token,
            bool browserCacheMarker = false,
            bool cookieOnly = false)
        {
            using var response = await GetAsync(token, "/api/session", browserCacheMarker, cookieOnly);
            return response.StatusCode;
        }

        public async ValueTask DisposeAsync()
        {
            _client.Dispose();
            if (!_process.HasExited)
            {
                _process.Kill(entireProcessTree: true);
                await _process.WaitForExitAsync();
            }
            _process.Dispose();
            SqliteConnection.ClearAllPools();
            await DeleteDirectoryWithRetryAsync(_root);
        }

        private async Task<HttpResponseMessage> GetAsync(string token, string path, bool browserCacheMarker, bool cookieOnly)
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, path);
            if (cookieOnly)
            {
                request.Headers.Add("Cookie", $"{PhaseAAuth.AccessTokenCookieName}={token}");
            }
            else
            {
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            }
            if (browserCacheMarker)
            {
                request.Headers.Add("X-Browser-Cached-Authorization", "predecessor-credential");
            }
            return await _client.SendAsync(request);
        }

        private async Task<HttpResponseMessage> PostAsync(
            string token,
            string path,
            string? body,
            IReadOnlyList<KeyValuePair<string, string>>? headers)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, path);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            if (body is not null)
            {
                request.Content = new StringContent(body, Encoding.UTF8, "application/json");
            }
            if (headers is not null)
            {
                foreach (var (name, value) in headers)
                {
                    request.Headers.Add(name, value);
                }
            }
            return await _client.SendAsync(request);
        }

        private static Process StartServer(string address, string databasePath, string workspaceRoot)
        {
            var start = new ProcessStartInfo("dotnet", $"\"{Path.Combine(AppContext.BaseDirectory, "PhaseA.Platform.dll")}\"")
            {
                WorkingDirectory = Path.Combine(RepositoryRoot, "PhaseA.Platform"),
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            start.Environment["APP_BIND_URL"] = address;
            start.Environment["ASPNETCORE_URLS"] = address;
            start.Environment["PUBLIC_BASE_URL"] = "https://localhost";
            start.Environment["PHASEA_METADATA_DB_PATH"] = databasePath;
            start.Environment["HOSTED_WORKSPACE_ROOT"] = workspaceRoot;
            start.Environment["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot;
            start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken);
            start.Environment["PHASEA_SERVICE_STATE"] = "test";
            return Process.Start(start) ?? throw new InvalidOperationException("S58 fixture could not start PhaseA.Platform.");
        }

        private static async Task WaitForHealthAsync(HttpClient client, Process process)
        {
            Exception? last = null;
            for (var attempt = 0; attempt < 40; attempt++)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"S58 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
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
            throw new InvalidOperationException("S58 temporary PhaseA.Platform did not become healthy.", last);
        }

        private static int FreePort()
        {
            var listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start();
            var port = ((IPEndPoint)listener.LocalEndpoint).Port;
            listener.Stop();
            return port;
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
    }

    private sealed record TestAccount(string AccountId, string Token);
}
