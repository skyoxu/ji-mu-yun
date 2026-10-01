using Microsoft.AspNetCore.Http;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S15BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S15BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
    }

    [Fact]
    public void O_4708C4D8EFAA()
    {
        const string adminBearer = "s15-declared-admin-bearer";
        var options = LoadOptions(adminBearer);

        var bearerRole = PhaseAAuth.GetRole(CreateRequest($"Bearer {adminBearer}"), options);
        var oidcRole = PhaseAAuth.GetRole(CreateRequest($"Oidc {adminBearer}"), options);
        var basicRole = PhaseAAuth.GetRole(CreateRequest("Basic czE1LXVuZGVjbGFyZWQ="), options);

        Require(
            bearerRole == PhaseAAuth.AdminRole && oidcRole is null && basicRole is null,
            "FAILURE-O-4708C4D8EFAA",
            "The declared bearer compatibility boundary did not reject undeclared OIDC and Basic credential schemes.");
        _output.WriteLine("S15-OBSERVATION O-4708C4D8EFAA oidc-first-declared-credential-compatibility-without-provider-deployment");
    }

    [Fact]
    public void O_4BA49CF633BC()
    {
        const string passwordOnly = "s15-password-only";
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_PASSWORD_HASH"] = PhaseAAuth.HashTokenForStorage(passwordOnly)
        });

        var passwordRole = PhaseAAuth.GetRole(CreateRequest($"Bearer {passwordOnly}"), options);

        Require(
            passwordRole is null && !PhaseAAuth.IsConfigured(options),
            "FAILURE-O-4BA49CF633BC",
            "A password hash was accepted as an authentication credential by the declared compatibility boundary.");
        _output.WriteLine("S15-OBSERVATION O-4BA49CF633BC no-password-authentication-system-required");
    }

    [Fact]
    public void O_701386E2D77D()
    {
        const string adminBearer = "s15-no-provider-deployment";
        var options = LoadOptions(adminBearer);

        var bearerRole = PhaseAAuth.GetRole(CreateRequest($"Bearer {adminBearer}"), options);
        var providerNamedRole = PhaseAAuth.GetRole(CreateRequest($"ExternalProvider {adminBearer}"), options);

        Require(
            bearerRole == PhaseAAuth.AdminRole && providerNamedRole is null,
            "FAILURE-O-701386E2D77D",
            "The compatibility boundary accepted an invented external provider credential scheme.");
        _output.WriteLine("S15-OBSERVATION O-701386E2D77D no-external-provider-deployment-or-runtime-claim");
    }

    [Fact]
    public async Task O_9FDA0B49E011()
    {
        const string adminBearer = "s15-admin-bearer-general-human-use";
        var root = Path.Combine(Path.GetTempPath(), "s15-admin-cookie-" + Guid.NewGuid().ToString("N"));
        var databasePath = Path.Combine(root, "metadata.sqlite3");
        var workspaceRoot = Path.Combine(root, "workspaces");
        Process? process = null;
        try
        {
            Directory.CreateDirectory(workspaceRoot);
            // ADR-0061: do not pool the parent fixture connection across child-server cleanup.
            await SqliteMetadataSchema.InitializeAsync(new Microsoft.Data.Sqlite.SqliteConnectionStringBuilder
            { DataSource = databasePath, Pooling = false }.ToString());
            var port = FreePort();
            var address = $"http://127.0.0.1:{port}";
            process = StartServer(address, databasePath, workspaceRoot, adminBearer);
            using var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(10) };
            await WaitForHealthAsync(client, process);
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", adminBearer);

            var response = await client.GetAsync("/api/session");
            var persistsAdminCredential = response.Headers.TryGetValues("Set-Cookie", out var cookies) &&
                cookies.Any(value => value.StartsWith($"{PhaseAAuth.AccessTokenCookieName}=", StringComparison.Ordinal));

            Require(
                response.StatusCode == HttpStatusCode.OK && !persistsAdminCredential,
                "FAILURE-O-9FDA0B49E011",
                "An administrator bearer credential was persisted as a general human browser access credential.");
            _output.WriteLine("S15-OBSERVATION O-9FDA0B49E011 admin-bearer-not-persisted-as-general-human-browser-credential");
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
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static PhaseAPlatformOptions LoadOptions(string adminBearer)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminBearer)
        });
    }

    private static HttpRequest CreateRequest(string authorization)
    {
        var context = new DefaultHttpContext();
        context.Request.Headers.Authorization = authorization;
        return context.Request;
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private static Process StartServer(string address, string databasePath, string workspaceRoot, string adminToken)
    {
        var repositoryRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var start = new ProcessStartInfo("dotnet", $"\"{Path.Combine(AppContext.BaseDirectory, "PhaseA.Platform.dll")}\"")
        {
            WorkingDirectory = Path.Combine(repositoryRoot, "PhaseA.Platform"),
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true,
        };
        start.Environment["APP_BIND_URL"] = address;
        start.Environment["ASPNETCORE_URLS"] = address;
        start.Environment["PUBLIC_BASE_URL"] = "https://localhost";
        start.Environment["PHASEA_METADATA_DB_PATH"] = databasePath;
        start.Environment["HOSTED_WORKSPACE_ROOT"] = workspaceRoot;
        start.Environment["PHASEA_REPOSITORY_ROOT"] = repositoryRoot;
        start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken);
        return Process.Start(start) ?? throw new InvalidOperationException("Failed to start PhaseA.Platform.");
    }

    private static async Task WaitForHealthAsync(HttpClient client, Process process)
    {
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
            catch (HttpRequestException)
            {
            }
            await Task.Delay(250);
        }
        throw new InvalidOperationException("Temporary PhaseA.Platform did not become healthy.");
    }

    private static int FreePort()
    {
        var listener = new TcpListener(System.Net.IPAddress.Loopback, 0);
        listener.Start();
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        return port;
    }
}
