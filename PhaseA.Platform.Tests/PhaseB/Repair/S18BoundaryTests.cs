using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S18BoundaryTests
{
    private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
        ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));

    [Fact]
    public async Task O_A9245A7F9268()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var authenticated = await fixture.CreateUserAsync("s18-account-authenticated", withProject: true);
        var conflicting = await fixture.CreateUserAsync("s18-account-conflicting", withProject: true);

        var session = await fixture.GetSessionAsync(authenticated, new Dictionary<string, string>
        {
            ["X-PhaseA-Account"] = conflicting.AccountId
        }, $"?accountId={conflicting.AccountId}");
        var foreignProject = await fixture.GetAsync(
            authenticated,
            $"/api/projects/{conflicting.ProjectId}/ui-state?accountId={conflicting.AccountId}",
            new Dictionary<string, string> { ["X-PhaseA-Account"] = conflicting.AccountId });

        Require(
            session.StatusCode == HttpStatusCode.OK &&
            session.AccountId == authenticated.AccountId &&
            session.AccountId != conflicting.AccountId &&
            foreignProject.StatusCode == HttpStatusCode.NotFound,
            "FAILURE-O-A9245A7F9268",
            "The protected HTTP route did not retain the credential-derived account scope when a client account field conflicted.");
    }

    [Fact]
    public async Task O_ACFFD4AF755A()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var authenticated = await fixture.CreateUserAsync("s18-principal-authenticated");
        const string conflictingPrincipal = "client-principal-override";

        var session = await fixture.GetSessionAsync(authenticated, new Dictionary<string, string>
        {
            ["X-PhaseA-Principal"] = conflictingPrincipal
        }, $"?principalId={conflictingPrincipal}");

        Require(
            session.StatusCode == HttpStatusCode.OK &&
            session.AccountId == authenticated.AccountId &&
            session.Username == authenticated.Username &&
            session.Username != conflictingPrincipal,
            "FAILURE-O-ACFFD4AF755A",
            "The protected HTTP session did not retain the credential-derived principal when a client principal field conflicted.");
    }

    [Fact]
    public async Task O_3E90E18CC0AD()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var authenticated = await fixture.CreateUserAsync("s18-role-authenticated");

        var session = await fixture.GetSessionAsync(authenticated, new Dictionary<string, string>
        {
            ["X-PhaseA-Role"] = PhaseAAuth.AdminRole
        }, "?role=admin");
        var adminRoute = await fixture.GetAsync(
            authenticated,
            "/api/admin/llm-usage?role=admin",
            new Dictionary<string, string> { ["X-PhaseA-Role"] = PhaseAAuth.AdminRole });

        Require(
            session.StatusCode == HttpStatusCode.OK &&
            session.Role == PhaseAAuth.UserRole &&
            adminRoute.StatusCode == HttpStatusCode.Forbidden,
            "FAILURE-O-3E90E18CC0AD",
            "The protected HTTP route accepted a client-supplied role instead of the server-derived role.");
    }

    [Fact]
    public async Task O_A7A82D9D64AA()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var authenticated = await fixture.CreateUserAsync("s18-scope-authenticated");
        var conflicting = await fixture.CreateUserAsync("s18-scope-conflicting", withProject: true);
        const string conflictingPrincipal = "client-principal-override";

        var fields = new Dictionary<string, string>
        {
            ["X-PhaseA-Account"] = conflicting.AccountId,
            ["X-PhaseA-Principal"] = conflictingPrincipal,
            ["X-PhaseA-Role"] = PhaseAAuth.AdminRole
        };
        var session = await fixture.GetSessionAsync(
            authenticated,
            fields,
            $"?accountId={conflicting.AccountId}&principalId={conflictingPrincipal}&role=admin");
        var adminRoute = await fixture.GetAsync(authenticated, "/api/admin/llm-usage?role=admin", fields);
        var foreignProject = await fixture.GetAsync(
            authenticated,
            $"/api/projects/{conflicting.ProjectId}/ui-state?accountId={conflicting.AccountId}",
            fields);

        Require(
            session.StatusCode == HttpStatusCode.OK &&
            session.AccountId == authenticated.AccountId &&
            session.Username == authenticated.Username &&
            session.Role == PhaseAAuth.UserRole &&
            adminRoute.StatusCode == HttpStatusCode.Forbidden &&
            foreignProject.StatusCode == HttpStatusCode.NotFound,
            "FAILURE-O-A7A82D9D64AA",
            "The protected HTTP routes allowed conflicting client scope fields to alter authorization context.");
    }

    [Fact]
    public async Task O_AA616F4EA4F8()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var authenticated = await fixture.CreateUserAsync("s18-role-removal");
        await fixture.SetAdminRoleAsync(authenticated.AccountId, true);

        var createdSession = await fixture.GetSessionAsync(authenticated);
        await fixture.SetAdminRoleAsync(authenticated.AccountId, false);
        var currentSession = await fixture.GetSessionAsync(authenticated);
        var protectedRoute = await fixture.GetAsync(authenticated, "/api/admin/llm-usage");

        Require(
            createdSession.StatusCode == HttpStatusCode.OK &&
            createdSession.Role == PhaseAAuth.AdminRole &&
            currentSession.StatusCode == HttpStatusCode.OK &&
            currentSession.Role == PhaseAAuth.UserRole &&
            protectedRoute.StatusCode == HttpStatusCode.Forbidden,
            "FAILURE-O-AA616F4EA4F8",
            "The protected HTTP route retained a removed role instead of evaluating the current server role set.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class BoundaryFixture : IAsyncDisposable
    {
        private readonly string _root;
        private readonly string _databasePath;
        private readonly PhaseAMetadataStore _store;
        private readonly Process _process;
        private readonly HttpClient _client;

        private BoundaryFixture(string root, string databasePath, PhaseAMetadataStore store, Process process, HttpClient client)
        {
            _root = root;
            _databasePath = databasePath;
            _store = store;
            _process = process;
            _client = client;
        }

        public static async Task<BoundaryFixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s18-http-{Guid.NewGuid():N}");
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var workspaceRoot = Path.Combine(root, "workspaces");
            Directory.CreateDirectory(workspaceRoot);

            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            await store.EnsureSingleAdminAsync();

            var port = FreePort();
            var url = $"http://127.0.0.1:{port}";
            var process = StartServer(url, databasePath, workspaceRoot);
            var client = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(10) };
            try
            {
                await WaitForHealthAsync(client, process);
                return new BoundaryFixture(root, databasePath, store, process, client);
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

        public async Task<TestAccount> CreateUserAsync(string username, bool withProject = false)
        {
            var issued = await _store.CreateUserAccountAsync(username, 2);
            string? projectId = null;
            if (withProject)
            {
                var projectRoot = Path.Combine(_root, $"project-{Guid.NewGuid():N}");
                var project = await _store.CreateProjectAsync(new ProjectCreationCommand(
                    $"project-{Guid.NewGuid():N}",
                    issued.AccountId,
                    "S18 boundary",
                    "S18 boundary",
                    "manual",
                    "default",
                    false,
                    [],
                    projectRoot,
                    Path.Combine(projectRoot, "repo"),
                    Path.Combine(projectRoot, "runtime"),
                    Path.Combine(projectRoot, "meta")));
                projectId = project.ProjectId;
            }

            return new TestAccount(issued.AccountId, issued.Username, issued.Token, projectId);
        }

        public async Task SetAdminRoleAsync(string accountId, bool isAdmin)
        {
            await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "UPDATE accounts SET is_admin = $is_admin WHERE id = $account_id;";
            command.Parameters.AddWithValue("$is_admin", isAdmin ? 1 : 0);
            command.Parameters.AddWithValue("$account_id", accountId);
            if (await command.ExecuteNonQueryAsync() != 1)
            {
                throw new InvalidOperationException("S18 fixture could not update its disposable account role.");
            }
        }

        public async Task<SessionObservation> GetSessionAsync(
            TestAccount account,
            IReadOnlyDictionary<string, string>? fields = null,
            string query = "")
        {
            var response = await GetAsync(account, $"/api/session{query}", fields);
            var body = await response.Content.ReadAsStringAsync();
            using var document = JsonDocument.Parse(body);
            var root = document.RootElement;
            return new SessionObservation(
                response.StatusCode,
                root.TryGetProperty("accountId", out var accountId) ? accountId.GetString() : null,
                root.TryGetProperty("username", out var username) ? username.GetString() : null,
                root.TryGetProperty("role", out var role) ? role.GetString() : null);
        }

        public async Task<HttpResponseMessage> GetAsync(
            TestAccount account,
            string path,
            IReadOnlyDictionary<string, string>? fields = null)
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, path);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", account.Token);
            if (fields is not null)
            {
                foreach (var field in fields)
                {
                    request.Headers.TryAddWithoutValidation(field.Key, field.Value);
                }
            }

            return await _client.SendAsync(request);
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

        private static Process StartServer(string url, string databasePath, string workspaceRoot)
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
            start.Environment["PHASEA_SERVICE_STATE"] = "test";
            return Process.Start(start) ?? throw new InvalidOperationException("S18 fixture could not start PhaseA.Platform.");
        }

        private static async Task WaitForHealthAsync(HttpClient client, Process process)
        {
            Exception? last = null;
            for (var attempt = 0; attempt < 40; attempt++)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"S18 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
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
            throw new InvalidOperationException("S18 temporary PhaseA.Platform did not become healthy.", last);
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

    private sealed record TestAccount(string AccountId, string Username, string Token, string? ProjectId);
    private sealed record SessionObservation(HttpStatusCode StatusCode, string? AccountId, string? Username, string? Role);
}
