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
public sealed class S37BoundaryTests
{
    [Fact]
    public async Task O_3891AA894A7D()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var account = await fixture.CreateUserWithProjectAsync("s37-snapshot-http");
        const string operationKey = "s37-authenticated-snapshot";

        var response = await fixture.PostAsync(
            account.Token,
            $"/api/projects/{account.ProjectId}/snapshots",
            JsonSerializer.Serialize(new { operationKey }));
        var recordedRequests = await fixture.CountSnapshotRunsAsync(account.ProjectId, operationKey);

        Require(
            response.StatusCode == HttpStatusCode.Accepted &&
            response.Body.Contains("workspace-snapshot", StringComparison.Ordinal) &&
            recordedRequests == 1,
            "FAILURE-O-3891AA894A7D",
            "An authenticated HTTP Snapshot request did not create its recorded workspace-snapshot operation.");
    }

    [Fact]
    public async Task O_47916B4565D3()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var account = await fixture.CreateUserWithProjectAsync("s37-explicit-snapshot");
        const string operationKey = "s37-explicit-snapshot";
        var before = await fixture.CountSnapshotRunsAsync(account.ProjectId, operationKey);

        var response = await fixture.PostAsync(
            account.Token,
            $"/api/projects/{account.ProjectId}/snapshots",
            JsonSerializer.Serialize(new { operationKey }));
        var after = await fixture.CountSnapshotRunsAsync(account.ProjectId, operationKey);

        Require(
            before == 0 &&
            response.StatusCode == HttpStatusCode.Accepted &&
            after == 1,
            "FAILURE-O-47916B4565D3",
            "The authorized explicit Snapshot request did not persist exactly one new snapshot operation.");
    }

    [Fact]
    public async Task O_565263FA671C()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var restoredAccount = await fixture.CreateUserWithProjectAsync("s37-restored-account");
        var otherAccount = await fixture.CreateUserWithProjectAsync("s37-other-account");

        var scopedReadback = await fixture.GetAsync(restoredAccount.Token, "/api/projects");
        var anonymousReadback = await fixture.GetAnonymousAsync("/api/projects");

        Require(
            scopedReadback.StatusCode == HttpStatusCode.OK &&
            scopedReadback.Body.Contains(restoredAccount.ProjectId, StringComparison.Ordinal) &&
            !scopedReadback.Body.Contains(otherAccount.ProjectId, StringComparison.Ordinal) &&
            anonymousReadback.StatusCode == HttpStatusCode.Unauthorized,
            "FAILURE-O-565263FA671C",
            "Hosted readback was not limited to the authenticated restored Account or allowed anonymous access.");
    }

    [Fact]
    public async Task O_57B8A8A9EC54()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var policyBefore = await fixture.GetAsync(AdminToken, "/api/admin/extension-policy");
        var unauthorizedChange = await fixture.PostAnonymousAsync(
            "/api/admin/extension-policy",
            "{\"blacklist\":[\"s37-untrusted-extension\"]}");
        var policyAfter = await fixture.GetAsync(AdminToken, "/api/admin/extension-policy");

        Require(
            (unauthorizedChange.StatusCode == HttpStatusCode.Unauthorized || unauthorizedChange.StatusCode == HttpStatusCode.Forbidden) &&
            policyBefore.StatusCode == HttpStatusCode.OK &&
            policyAfter.StatusCode == HttpStatusCode.OK &&
            string.Equals(policyBefore.Body, policyAfter.Body, StringComparison.Ordinal),
            "FAILURE-O-57B8A8A9EC54",
            "An unauthorized extension-policy change was not denied with an unchanged readable active policy.");
    }

    [Fact]
    public async Task O_CE9948D0DD76()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var user = await fixture.CreateUserWithProjectAsync("s37-policy-user");
        const string policyChange = "{\"blacklist\":[\"s37-admin-extension\"]}";

        var spoofedUserChange = await fixture.PostAsync(
            user.Token,
            "/api/admin/extension-policy",
            policyChange,
            new Dictionary<string, string> { ["X-PhaseA-Role"] = PhaseAAuth.AdminRole });
        var administratorChange = await fixture.PostAsync(AdminToken, "/api/admin/extension-policy", policyChange);

        Require(
            spoofedUserChange.StatusCode == HttpStatusCode.Forbidden &&
            administratorChange.StatusCode is HttpStatusCode.OK or HttpStatusCode.Accepted,
            "FAILURE-O-CE9948D0DD76",
            "The extension-policy administration endpoint did not reject client-spoofed authorization and accept the server-authenticated administrator.");
    }

    private const string AdminToken = "s37-administrator-token";

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class BoundaryFixture : IAsyncDisposable
    {
        private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? FindRepositoryRoot(Directory.GetCurrentDirectory());
        private static readonly string PlatformAssemblyPath = typeof(Program).Assembly.Location;
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
            var root = Path.Combine(Path.GetTempPath(), $"s37-boundary-{Guid.NewGuid():N}");
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var workspaceRoot = Path.Combine(root, "workspaces");
            Directory.CreateDirectory(workspaceRoot);
            Process? process = null;
            HttpClient? client = null;
            try
            {
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
                process = StartServer(address, databasePath, workspaceRoot);
                client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(10) };
                await WaitForHealthAsync(client, process);
                return new BoundaryFixture(root, databasePath, store, process, client);
            }
            catch
            {
                client?.Dispose();
                if (process is { HasExited: false })
                {
                    process.Kill(entireProcessTree: true);
                    await process.WaitForExitAsync();
                }
                process?.Dispose();
                SqliteConnection.ClearAllPools();
                if (Directory.Exists(root))
                {
                    Directory.Delete(root, recursive: true);
                }
                throw;
            }
        }

        public async Task<TestAccount> CreateUserWithProjectAsync(string username)
        {
            var account = await _store.CreateUserAccountAsync(username, 1);
            var projectRoot = Path.Combine(_root, $"project-{Guid.NewGuid():N}");
            Directory.CreateDirectory(projectRoot);
            var project = await _store.CreateProjectAsync(new ProjectCreationCommand(
                $"project-{Guid.NewGuid():N}",
                account.AccountId,
                "S37 boundary",
                "S37 boundary",
                "manual",
                "default",
                false,
                [],
                projectRoot,
                Path.Combine(projectRoot, "repo"),
                Path.Combine(projectRoot, "runtime"),
                Path.Combine(projectRoot, "meta")));
            return new TestAccount(account.Token, project.ProjectId!);
        }

        public Task<HttpObservation> GetAsync(string token, string path) => SendAsync(HttpMethod.Get, token, path, null, null);

        public Task<HttpObservation> GetAnonymousAsync(string path) => SendAsync(HttpMethod.Get, null, path, null, null);

        public Task<HttpObservation> PostAnonymousAsync(string path, string body) => SendAsync(HttpMethod.Post, null, path, body, null);

        public Task<HttpObservation> PostAsync(string token, string path, string body, IReadOnlyDictionary<string, string>? headers = null) =>
            SendAsync(HttpMethod.Post, token, path, body, headers);

        public async Task<long> CountSnapshotRunsAsync(string projectId, string operationKey)
        {
            await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(*) FROM runs WHERE project_id = $project_id AND run_type = $run_type;";
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$run_type", $"workspace-snapshot:{operationKey}");
            return (long)(await command.ExecuteScalarAsync() ?? 0L);
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

        private async Task<HttpObservation> SendAsync(
            HttpMethod method,
            string? token,
            string path,
            string? body,
            IReadOnlyDictionary<string, string>? headers)
        {
            using var request = new HttpRequestMessage(method, path);
            if (!string.IsNullOrWhiteSpace(token))
            {
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            }
            if (body is not null)
            {
                request.Content = new StringContent(body, Encoding.UTF8, "application/json");
            }
            if (headers is not null)
            {
                foreach (var header in headers)
                {
                    request.Headers.TryAddWithoutValidation(header.Key, header.Value);
                }
            }
            using var response = await _client.SendAsync(request);
            return new HttpObservation(response.StatusCode, await response.Content.ReadAsStringAsync());
        }

        private static Process StartServer(string address, string databasePath, string workspaceRoot)
        {
            var start = new ProcessStartInfo("dotnet", $"\"{PlatformAssemblyPath}\"")
            {
                WorkingDirectory = Path.GetDirectoryName(PlatformAssemblyPath)!,
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
            start.Environment["ASPNETCORE_CONTENTROOT"] = Path.Combine(RepositoryRoot, "PhaseA.Platform");
            start.Environment["PHASEA_SERVICE_STATE"] = "test";
            return Process.Start(start) ?? throw new InvalidOperationException("S37 fixture could not start PhaseA.Platform.");
        }

        private static async Task WaitForHealthAsync(HttpClient client, Process process)
        {
            Exception? last = null;
            for (var attempt = 0; attempt < 40; attempt++)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"S37 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
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
            throw new InvalidOperationException("S37 temporary PhaseA.Platform did not become healthy.", last);
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
    }

    private sealed record TestAccount(string Token, string ProjectId);
    private sealed record HttpObservation(HttpStatusCode StatusCode, string Body);
}
