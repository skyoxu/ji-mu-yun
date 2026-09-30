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
public sealed class S55BoundaryTests
{
    [Fact]
    public async Task O_42E454AE0E75()
    {
        await using var fixture = await AdminLifecycleFixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s55-disable-target");

        var denied = await fixture.PostAsUserAsync(target.Token, $"/api/admin/users/{target.AccountId}/status", "{\"disabled\":true}");
        var authorized = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/status", "{\"disabled\":true}");
        var account = await fixture.GetAccountAsync(target.AccountId);

        Require(
            denied.StatusCode == HttpStatusCode.Forbidden &&
            authorized.StatusCode == HttpStatusCode.OK &&
            account is { IsDisabled: true },
            "FAILURE-O-42E454AE0E75",
            "The administrator account-disable boundary did not deny a non-administrator or persist the authorized disabled state.");
    }

    [Fact]
    public async Task O_7CC72D4784EA()
    {
        await using var fixture = await AdminLifecycleFixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s55-revoke-target");

        var denied = await fixture.PostAsUserAsync(target.Token, $"/api/admin/users/{target.AccountId}/rotate-token");
        var authorized = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/rotate-token");
        var oldCredential = await fixture.GetSessionAsync(target.Token);
        var replacementToken = await ReadTokenAsync(authorized);
        var replacementCredential = string.IsNullOrWhiteSpace(replacementToken)
            ? HttpStatusCode.Unauthorized
            : await fixture.GetSessionAsync(replacementToken);

        Require(
            denied.StatusCode == HttpStatusCode.Forbidden &&
            authorized.StatusCode == HttpStatusCode.OK &&
            oldCredential == HttpStatusCode.Unauthorized &&
            replacementCredential == HttpStatusCode.OK,
            "FAILURE-O-7CC72D4784EA",
            "The administrator credential-revocation boundary did not deny a non-administrator or revoke the prior credential after authorized rotation.");
    }

    private static async Task<string?> ReadTokenAsync(HttpResponseMessage response)
    {
        if (!response.IsSuccessStatusCode)
        {
            return null;
        }

        using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        return document.RootElement.TryGetProperty("token", out var token) ? token.GetString() : null;
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class AdminLifecycleFixture : IAsyncDisposable
    {
        private const string AdminToken = "s55-valid-administrator-token";
        private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));

        private readonly string _root;
        private readonly PhaseAMetadataStore _store;
        private readonly Process _process;
        private readonly HttpClient _client;

        private AdminLifecycleFixture(string root, PhaseAMetadataStore store, Process process, HttpClient client)
        {
            _root = root;
            _store = store;
            _process = process;
            _client = client;
        }

        public static async Task<AdminLifecycleFixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s55-admin-lifecycle-{Guid.NewGuid():N}");
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var workspaceRoot = Path.Combine(root, "workspaces");
            Directory.CreateDirectory(workspaceRoot);

            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
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
            var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(10) };
            try
            {
                await WaitForHealthAsync(client, process);
                return new AdminLifecycleFixture(root, store, process, client);
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
            var issued = await _store.CreateUserAccountAsync(username, 1);
            return new TestAccount(issued.AccountId, issued.Token);
        }

        public Task<HttpResponseMessage> PostAsAdminAsync(string path, string? body = null)
        {
            return PostAsync(AdminToken, path, body);
        }

        public Task<HttpResponseMessage> PostAsUserAsync(string token, string path, string? body = null)
        {
            return PostAsync(token, path, body);
        }

        public async Task<HttpStatusCode> GetSessionAsync(string token)
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, "/api/session");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await _client.SendAsync(request);
            return response.StatusCode;
        }

        public async Task<AdminUserListItem?> GetAccountAsync(string accountId)
        {
            return (await _store.ListAccountsAsync()).SingleOrDefault(account => account.AccountId == accountId);
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

        private async Task<HttpResponseMessage> PostAsync(string token, string path, string? body)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, path);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            if (body is not null)
            {
                request.Content = new StringContent(body, Encoding.UTF8, "application/json");
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
            return Process.Start(start) ?? throw new InvalidOperationException("S55 fixture could not start PhaseA.Platform.");
        }

        private static async Task WaitForHealthAsync(HttpClient client, Process process)
        {
            Exception? last = null;
            for (var attempt = 0; attempt < 40; attempt++)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"S55 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
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
            throw new InvalidOperationException("S55 temporary PhaseA.Platform did not become healthy.", last);
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
