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
public sealed class S26BoundaryTests
{
    [Fact]
    public async Task O_13BEA926B50D()
    {
        await using var fixture = await DisablementFixture.CreateAsync();
        var account = await fixture.CreateUserWithProjectAsync("s26-restore-user");
        var restoreRunsBefore = await fixture.CountRestoreOperationRunsAsync(account.ProjectId, "s26-disabled-restore");
        var writeLeasesBefore = await fixture.CountWriteLeasesAsync(account.ProjectId);
        await fixture.DisableAccountAsync(account.AccountId);
        await fixture.AdvancePastControlPlaneCacheWindowAsync();

        var restoreRequest = await fixture.PostAsUserAsync(
            account.Token,
            $"/api/projects/{account.ProjectId}/restores",
            "{\"operationKey\":\"s26-disabled-restore\"}");
        var restoreRunsAfter = await fixture.CountRestoreOperationRunsAsync(account.ProjectId, "s26-disabled-restore");
        var writeLeasesAfter = await fixture.CountWriteLeasesAsync(account.ProjectId);

        Require(
            IsDenied(restoreRequest) &&
            restoreRunsBefore == 0 &&
            restoreRunsAfter == 0 &&
            writeLeasesAfter == writeLeasesBefore,
            "FAILURE-O-13BEA926B50D",
            "A disabled account could request Restore or created an executable Restore operation or write-lease admission record after the control-plane cache window.");
    }

    private static bool IsDenied(ResponseObservation response)
    {
        return response.StatusCode == HttpStatusCode.Unauthorized &&
            string.Equals(response.ErrorCode, PhaseAAuth.AuthFailureCode, StringComparison.Ordinal);
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class DisablementFixture : IAsyncDisposable
    {
        private const string AdminToken = "s26-admin-bearer-token";
        private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));

        private readonly string _root;
        private readonly string _databasePath;
        private readonly PhaseAMetadataStore _store;
        private readonly Process _process;
        private readonly HttpClient _client;

        private DisablementFixture(string root, string databasePath, PhaseAMetadataStore store, Process process, HttpClient client)
        {
            _root = root;
            _databasePath = databasePath;
            _store = store;
            _process = process;
            _client = client;
        }

        public static async Task<DisablementFixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s26-disablement-{Guid.NewGuid():N}");
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var workspaceRoot = Path.Combine(root, "workspaces");
            Directory.CreateDirectory(workspaceRoot);

            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot,
                ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken),
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            await store.EnsureSingleAdminAsync();

            var address = $"http://127.0.0.1:{FreePort()}";
            var process = StartServer(address, databasePath, workspaceRoot);
            var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(10) };
            try
            {
                await WaitForHealthAsync(client, process);
                return new DisablementFixture(root, databasePath, store, process, client);
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

        public async Task<TestAccount> CreateUserWithProjectAsync(string username)
        {
            var issued = await _store.CreateUserAccountAsync(username, 1);
            var projectRoot = Path.Combine(_root, $"project-{Guid.NewGuid():N}");
            var repoPath = Path.Combine(projectRoot, "repo");
            Directory.CreateDirectory(repoPath);
            var project = await _store.CreateProjectAsync(new ProjectCreationCommand(
                $"project-{Guid.NewGuid():N}",
                issued.AccountId,
                "S26 boundary",
                "S26 boundary",
                "manual",
                "default",
                false,
                [],
                projectRoot,
                repoPath,
                Path.Combine(projectRoot, "runtime"),
                Path.Combine(projectRoot, "meta")));
            return new TestAccount(issued.AccountId, issued.Token, project.ProjectId);
        }

        public async Task DisableAccountAsync(string accountId)
        {
            var response = await SendAsync(HttpMethod.Post, AdminToken, $"/api/admin/users/{accountId}/status", "{\"disabled\":true}");
            if (response.StatusCode != HttpStatusCode.OK)
            {
                throw new InvalidOperationException("S26 fixture could not disable its disposable account.");
            }
        }

        public Task AdvancePastControlPlaneCacheWindowAsync() => Task.Delay(TimeSpan.FromMilliseconds(5100));

        public Task<ResponseObservation> PostAsUserAsync(string token, string path, string body) =>
            SendAsync(HttpMethod.Post, token, path, body);

        public async Task<long> CountRestoreOperationRunsAsync(string projectId, string operationKey)
        {
            await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(*) FROM runs WHERE project_id = $project_id AND run_type = $run_type;";
            command.Parameters.AddWithValue("$project_id", projectId);
            command.Parameters.AddWithValue("$run_type", $"workspace-restore:{operationKey}");
            return (long)(await command.ExecuteScalarAsync() ?? 0L);
        }

        public async Task<long> CountWriteLeasesAsync(string projectId)
        {
            await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(*) FROM runner_leases WHERE project_id = $project_id;";
            command.Parameters.AddWithValue("$project_id", projectId);
            try
            {
                return (long)(await command.ExecuteScalarAsync() ?? 0L);
            }
            catch (SqliteException exception) when (exception.SqliteErrorCode == 1 && exception.Message.Contains("no such table", StringComparison.OrdinalIgnoreCase))
            {
                return 0L;
            }
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

        private async Task<ResponseObservation> SendAsync(HttpMethod method, string token, string path, string? body)
        {
            using var request = new HttpRequestMessage(method, path);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            if (body is not null)
            {
                request.Content = new StringContent(body, Encoding.UTF8, "application/json");
            }
            using var response = await _client.SendAsync(request);
            return new ResponseObservation(response.StatusCode, ReadErrorCode(await response.Content.ReadAsStringAsync()));
        }

        private static string? ReadErrorCode(string content)
        {
            try
            {
                using var document = JsonDocument.Parse(content);
                return document.RootElement.TryGetProperty("error", out var error) ? error.GetString() : null;
            }
            catch (JsonException)
            {
                return null;
            }
        }

        private static Process StartServer(string address, string databasePath, string workspaceRoot)
        {
            var start = new ProcessStartInfo("dotnet", $"\"{Path.Combine(AppContext.BaseDirectory, "PhaseA.Platform.dll")}\"")
            {
                WorkingDirectory = Path.Combine(RepositoryRoot, "PhaseA.Platform"),
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            start.Environment["APP_BIND_URL"] = address;
            start.Environment["ASPNETCORE_URLS"] = address;
            start.Environment["PUBLIC_BASE_URL"] = "https://localhost";
            start.Environment["PHASEA_METADATA_DB_PATH"] = databasePath;
            start.Environment["HOSTED_WORKSPACE_ROOT"] = workspaceRoot;
            start.Environment["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot;
            start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken);
            start.Environment["PHASEA_SERVICE_STATE"] = "test";
            return Process.Start(start) ?? throw new InvalidOperationException("S26 fixture could not start PhaseA.Platform.");
        }

        private static async Task WaitForHealthAsync(HttpClient client, Process process)
        {
            Exception? last = null;
            for (var attempt = 0; attempt < 40; attempt++)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"S26 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
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
            throw new InvalidOperationException("S26 temporary PhaseA.Platform did not become healthy.", last);
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

    private sealed record TestAccount(string AccountId, string Token, string ProjectId);
    private sealed record ResponseObservation(HttpStatusCode StatusCode, string? ErrorCode);
}
