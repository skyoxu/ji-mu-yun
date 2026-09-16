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
            var user = await store.CreateUserAccountAsync("s14-user", 1);
            var projectRoot = Path.Combine(workspaceRoot, "project-s14");
            var project = await store.CreateProjectAsync(new ProjectCreationCommand(
                "project-s14", user.AccountId, "S14", "S14", "manual", "default", false, [],
                projectRoot, Path.Combine(projectRoot, "repo"), Path.Combine(projectRoot, "runtime"), Path.Combine(projectRoot, "repo", "meta")));
            await store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null);

            var url = $"http://127.0.0.1:{FreePort()}";
            process = StartServer(url, databasePath, workspaceRoot);
            using var healthClient = new HttpClient { BaseAddress = new Uri(url), Timeout = TimeSpan.FromSeconds(10) };
            await WaitForHealthAsync(healthClient, process);

            var operations = new[]
            {
                new OperationRequest("snapshot", $"/api/projects/{project.ProjectId}/snapshots", "s14-snapshot"),
                new OperationRequest("restore", $"/api/projects/{project.ProjectId}/restores", "s14-restore"),
                new OperationRequest("acl-repair", $"/api/projects/{project.ProjectId}/acl-repairs", "s14-acl-repair")
            };

            var admitted = new List<OperationObservation>();
            var reentered = new List<OperationObservation>();
            foreach (var operation in operations)
            {
                admitted.Add(await InvokeThenDisconnectAsync(url, user.Token, operation));
                reentered.Add(await InvokeThenDisconnectAsync(url, user.Token, operation));
            }

            var allAdmitted = admitted.All(observation =>
                observation.StatusCode == HttpStatusCode.Accepted &&
                !string.IsNullOrWhiteSpace(observation.OperationId) &&
                !string.IsNullOrWhiteSpace(observation.Result));
            var stableReentry = admitted.Zip(reentered).All(pair =>
                pair.First.StatusCode == HttpStatusCode.Accepted &&
                pair.Second.StatusCode == HttpStatusCode.Accepted &&
                string.Equals(pair.First.OperationId, pair.Second.OperationId, StringComparison.Ordinal) &&
                string.Equals(pair.First.Result, pair.Second.Result, StringComparison.Ordinal));

            Require(allAdmitted, "FAILURE-O-11DDC0AAE540", "Snapshot, Restore, and ACL repair were not all admitted as durable authenticated operations.");
            Require(stableReentry, "FAILURE-O-11DDC0AAE540", "Authorized re-entry did not return each durable operation identity and result after client disconnection.");
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
            Content = JsonContent.Create(new { operationKey = operation.Key })
        };
        request.Headers.ConnectionClose = true;
        using var response = await client.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();
        var (operationId, result) = ReadOperationFields(body);
        return new OperationObservation(operation.Name, response.StatusCode, operationId, result);
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

    private sealed record OperationRequest(string Name, string Path, string Key);
    private sealed record OperationObservation(string Name, HttpStatusCode StatusCode, string? OperationId, string? Result);
}
