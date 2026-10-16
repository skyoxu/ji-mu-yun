using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S65BoundaryTests
{
    [Fact]
    public async Task O_9FB2427DA00F()
    {
        await using var fixture = await OrdinaryEditFixture.CreateAsync();
        var account = await fixture.CreateUserWithProjectAsync("s65-ordinary-edit");
        var restoreStartsBefore = await fixture.CountRestoreStartsAsync(account.ProjectId);

        var edit = await fixture.SendAsUserAsync(
            HttpMethod.Post,
            account.Token,
            $"/api/projects/{account.ProjectId}/ui-state",
            "{\"selectedTab\":\"s65-ordinary-edit\"}");
        var readback = await fixture.SendAsUserAsync(
            HttpMethod.Get,
            account.Token,
            $"/api/projects/{account.ProjectId}/ui-state",
            null);
        var restoreStartsAfter = await fixture.CountRestoreStartsAsync(account.ProjectId);

        Require(
            restoreStartsBefore == 0 &&
            edit.StatusCode == HttpStatusCode.OK &&
            readback.StatusCode == HttpStatusCode.OK &&
            readback.Body.Contains("s65-ordinary-edit", StringComparison.Ordinal) &&
            restoreStartsAfter == 0,
            "FAILURE-O-9FB2427DA00F",
            "The ordinary Project edit was not present without starting a Restore operation.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class OrdinaryEditFixture : IAsyncDisposable
    {
        private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? FindRepositoryRoot(Directory.GetCurrentDirectory());
        private static readonly string PlatformAssemblyPath = typeof(Program).Assembly.Location;

        private readonly string _root;
        private readonly string _databasePath;
        private readonly PhaseAMetadataStore _store;
        private readonly Process _process;
        private readonly HttpClient _client;

        private OrdinaryEditFixture(string root, string databasePath, PhaseAMetadataStore store, Process process, HttpClient client)
        {
            _root = root;
            _databasePath = databasePath;
            _store = store;
            _process = process;
            _client = client;
        }

        public static async Task<OrdinaryEditFixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s65-ordinary-edit-{Guid.NewGuid():N}");
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var workspaceRoot = Path.Combine(root, "workspaces");
            Directory.CreateDirectory(workspaceRoot);

            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot,
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var address = $"http://127.0.0.1:{FreePort()}";
            var process = StartServer(address, databasePath, workspaceRoot);
            var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(15) };
            try
            {
                await WaitForHealthAsync(client, process);
                return new OrdinaryEditFixture(root, databasePath, store, process, client);
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
                if (Directory.Exists(root))
                {
                    Directory.Delete(root, recursive: true);
                }
                throw;
            }
        }

        public async Task<TestAccount> CreateUserWithProjectAsync(string username)
        {
            var issued = await _store.CreateUserAccountAsync(username, 1);
            var projectRoot = Path.Combine(_root, "workspaces", $"project-{Guid.NewGuid():N}");
            var repositoryPath = Path.Combine(projectRoot, "repo");
            Directory.CreateDirectory(repositoryPath);
            var project = await _store.CreateProjectAsync(new ProjectCreationCommand(
                $"project-{Guid.NewGuid():N}",
                issued.AccountId,
                "S65 ordinary edit",
                "S65 ordinary edit",
                "manual",
                "default",
                false,
                [],
                projectRoot,
                repositoryPath,
                Path.Combine(projectRoot, "runtime"),
                Path.Combine(projectRoot, "meta")));
            await _store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null);
            return new TestAccount(issued.Token, project.ProjectId!);
        }

        public async Task<ResponseObservation> SendAsUserAsync(HttpMethod method, string token, string path, string? body)
        {
            using var request = new HttpRequestMessage(method, path);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            if (body is not null)
            {
                request.Content = new StringContent(body, Encoding.UTF8, "application/json");
            }

            using var response = await _client.SendAsync(request);
            return new ResponseObservation(response.StatusCode, await response.Content.ReadAsStringAsync());
        }

        public async Task<long> CountRestoreStartsAsync(string projectId)
        {
            await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(*) FROM runs WHERE project_id = $project_id AND run_type LIKE 'workspace-restore:%';";
            command.Parameters.AddWithValue("$project_id", projectId);
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

        private static Process StartServer(string address, string databasePath, string workspaceRoot)
        {
            var start = new ProcessStartInfo("dotnet", $"\"{PlatformAssemblyPath}\"")
            {
                WorkingDirectory = Path.GetDirectoryName(PlatformAssemblyPath)!,
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
            start.Environment["ASPNETCORE_CONTENTROOT"] = Path.Combine(RepositoryRoot, "PhaseA.Platform");
            start.Environment["PHASEA_SERVICE_STATE"] = "test";
            return Process.Start(start) ?? throw new InvalidOperationException("S65 fixture could not start PhaseA.Platform.");
        }

        private static async Task WaitForHealthAsync(HttpClient client, Process process)
        {
            Exception? last = null;
            for (var attempt = 0; attempt < 40; attempt++)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"S65 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
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
            throw new InvalidOperationException("S65 temporary PhaseA.Platform did not become healthy.", last);
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
    private sealed record ResponseObservation(HttpStatusCode StatusCode, string Body);
}
