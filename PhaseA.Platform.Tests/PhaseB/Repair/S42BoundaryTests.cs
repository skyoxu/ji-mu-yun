using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Net.Sockets;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S42BoundaryTests
{
    private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
        ?? FindRepositoryRoot(Directory.GetCurrentDirectory());
    private static readonly string PlatformAssemblyPath = typeof(Program).Assembly.Location;
    private readonly ITestOutputHelper _output;

    public S42BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_605D7CAE42F3()
    {
        var root = Path.Combine(Path.GetTempPath(), "s42-evidence-pointer-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var databasePath = Path.Combine(root, "metadata.sqlite3");
        var workspaceRoot = Path.Combine(root, "workspaces");
        Directory.CreateDirectory(workspaceRoot);
        Process? process = null;
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
            var user = await store.CreateUserAccountAsync("s42-user-" + Guid.NewGuid().ToString("N"), 1);
            var projectRoot = Path.Combine(workspaceRoot, "project-s42");
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                "project-s42-" + Guid.NewGuid().ToString("N"), user.AccountId, "S42", "S42", "manual", "default", false, [],
                projectRoot, Path.Combine(projectRoot, "repo"), Path.Combine(projectRoot, "runtime"), Path.Combine(projectRoot, "repo", "meta")));
            await store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null);

            var url = $"http://127.0.0.1:{FreePort()}";
            process = StartServer(url, databasePath, workspaceRoot);
            using var client = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(15) };
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", user.Token);
            await WaitForHealthAsync(client, process);

            var operationPaths = new[]
            {
                $"/api/projects/{project.ProjectId}/snapshots",
                $"/api/projects/{project.ProjectId}/restores",
                $"/api/projects/{project.ProjectId}/acl-repairs"
            };
            var pointers = new List<string>();
            foreach (var path in operationPaths)
            {
                using var response = await client.PostAsJsonAsync(path, new { operationKey = "s42-" + Guid.NewGuid().ToString("N") });
                var body = await response.Content.ReadAsStringAsync();
                Require(response.StatusCode == HttpStatusCode.Accepted, "FAILURE-O-605D7CAE42F3", "Durable operation was not accepted.");
                using var document = JsonDocument.Parse(body);
                var pointer = document.RootElement.TryGetProperty("evidencePointer", out var pointerElement)
                    ? pointerElement.GetString()
                    : null;
                Require(!string.IsNullOrWhiteSpace(pointer), "FAILURE-O-605D7CAE42F3", "Operation response omitted a non-empty evidence pointer.");
                pointers.Add(pointer!);
            }

            foreach (var pointer in pointers)
            {
                Require(Uri.TryCreate(pointer, UriKind.Relative, out var relative) && relative!.OriginalString.StartsWith("/api/", StringComparison.Ordinal),
                    "FAILURE-O-605D7CAE42F3", "Evidence pointer was not an authorized API-relative readback address.");
                using var readback = await client.GetAsync(relative);
                Require(readback.IsSuccessStatusCode, "FAILURE-O-605D7CAE42F3", "Evidence pointer did not resolve through the authorized readback boundary.");
            }

            _output.WriteLine("S42-OBSERVATION O-605D7CAE42F3 evidence-pointer-resolves-through-authorized-readback");
        }
        finally
        {
            if (process is { HasExited: false })
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync();
            }
            process?.Dispose();
            SqliteConnection.ClearAllPools();
            if (Directory.Exists(root))
            {
                await DeleteDirectoryWithRetryAsync(root);
            }
        }
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
}
