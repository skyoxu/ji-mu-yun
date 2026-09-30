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
public sealed class S38BoundaryTests
{
    [Fact]
    public async Task O_24FE1B41FD41()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var requester = await fixture.CreateUserAsync("s38-lineage-requester");
        var alternate = await fixture.CreateUserAsync("s38-lineage-alternate");
        var projectId = await fixture.CreateLegacyProjectAsync($"{requester.AccountId}|{alternate.AccountId}");

        var firstReadback = await fixture.ResolveProjectAsync(projectId);
        var firstLineage = await fixture.ReadWorkspaceOwnershipLineageAsync(projectId);
        var secondReadback = await fixture.ResolveProjectAsync(projectId);
        var secondLineage = await fixture.ReadWorkspaceOwnershipLineageAsync(projectId);

        Require(
            firstReadback is { BootstrapStatus: "quarantined" } &&
            secondReadback is { BootstrapStatus: "quarantined" } &&
            firstLineage.Count >= 1 &&
            firstLineage.All(entry =>
                entry.Decision == "quarantined" &&
                !string.IsNullOrWhiteSpace(entry.CorrelationId) &&
                !string.IsNullOrWhiteSpace(entry.CreatedUtc)) &&
            secondLineage.Count >= firstLineage.Count &&
            secondLineage.Take(firstLineage.Count).SequenceEqual(firstLineage),
            "FAILURE-O-24FE1B41FD41",
            "The legacy Workspace ownership decision was not retained as append-only, correlated lineage.");
    }

    [Fact]
    public async Task O_31C3B2EDC77B()
    {
        await using var fixture = await BoundaryFixture.CreateAsync(startServer: true);
        var target = await fixture.CreateUserAsync("s38-inflight-target");

        using var disabled = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/status", "{\"disabled\":true}");
        var deniedPublication = await fixture.GetSessionAsync(target.Token);
        var events = await fixture.ListAuditEventsAsync(target.AccountId);

        Require(
            disabled.StatusCode == HttpStatusCode.OK &&
            deniedPublication == HttpStatusCode.Unauthorized &&
            events.Any(entry =>
                entry.Action == "user_disabled" &&
                entry.TargetAccountId == target.AccountId &&
                HasRequiredDisablementOutcome(entry.MetadataJson) &&
                !entry.MetadataJson.Contains(target.Token, StringComparison.Ordinal)),
            "FAILURE-O-31C3B2EDC77B",
            "The Account-disablement operation did not retain a correlated, typed denial or drain outcome without credentials.");
    }

    [Fact]
    public async Task O_6C84821C3DED()
    {
        await using var fixture = await BoundaryFixture.CreateAsync(startServer: true);
        var target = await fixture.CreateUserAsync("s38-lifecycle-target");
        var nonAdmin = await fixture.CreateUserAsync("s38-lifecycle-non-admin");

        using var deniedDisable = await fixture.PostAsUserAsync(nonAdmin.Token, $"/api/admin/users/{target.AccountId}/status", "{\"disabled\":true}");
        using var authorizedDisable = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/status", "{\"disabled\":true}");
        using var deniedEnable = await fixture.PostAsUserAsync(nonAdmin.Token, $"/api/admin/users/{target.AccountId}/status", "{\"disabled\":false}");
        using var authorizedEnable = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/status", "{\"disabled\":false}");
        using var deniedRevoke = await fixture.PostAsUserAsync(nonAdmin.Token, $"/api/admin/users/{target.AccountId}/rotate-token");
        using var authorizedRevoke = await fixture.PostAsAdminAsync($"/api/admin/users/{target.AccountId}/rotate-token");
        var events = await fixture.ListAuditEventsAsync(target.AccountId);

        Require(
            deniedDisable.StatusCode == HttpStatusCode.Forbidden &&
            authorizedDisable.StatusCode == HttpStatusCode.OK &&
            deniedEnable.StatusCode == HttpStatusCode.Forbidden &&
            authorizedEnable.StatusCode == HttpStatusCode.OK &&
            deniedRevoke.StatusCode == HttpStatusCode.Forbidden &&
            authorizedRevoke.StatusCode == HttpStatusCode.OK &&
            HasRedactedLifecycleAudit(events, target.AccountId, "user_disabled", "denied", target.Token, nonAdmin.Token) &&
            HasRedactedLifecycleAudit(events, target.AccountId, "user_disabled", "authorized", target.Token, nonAdmin.Token) &&
            HasRedactedLifecycleAudit(events, target.AccountId, "user_enabled", "denied", target.Token, nonAdmin.Token) &&
            HasRedactedLifecycleAudit(events, target.AccountId, "user_enabled", "authorized", target.Token, nonAdmin.Token) &&
            HasRedactedLifecycleAudit(events, target.AccountId, "user_token_rotated", "denied", target.Token, nonAdmin.Token) &&
            HasRedactedLifecycleAudit(events, target.AccountId, "user_token_rotated", "authorized", target.Token, nonAdmin.Token),
            "FAILURE-O-6C84821C3DED",
            "Administrator disable, enable, and revoke attempts did not all retain correlated, redacted authorized or denied audit outcomes.");
    }

    private static bool HasRequiredDisablementOutcome(string metadataJson)
    {
        using var document = JsonDocument.Parse(metadataJson);
        var metadata = document.RootElement;
        return HasString(metadata, "operation_id") &&
               HasString(metadata, "account_id") &&
               HasString(metadata, "correlation_id") &&
               HasString(metadata, "action") &&
               HasString(metadata, "status") &&
               (HasString(metadata, "denial_outcome") || HasString(metadata, "drain_outcome") || HasString(metadata, "cancellation_outcome"));
    }

    private static bool HasRedactedLifecycleAudit(
        IReadOnlyList<AdminAccountAuditEvent> events,
        string targetAccountId,
        string action,
        string outcome,
        params string[] secrets) =>
        events.Any(entry =>
            entry.TargetAccountId == targetAccountId &&
            entry.Action == action &&
            HasLifecycleOutcome(entry.MetadataJson, outcome) &&
            secrets.All(secret => !entry.MetadataJson.Contains(secret, StringComparison.Ordinal)));

    private static bool HasLifecycleOutcome(string metadataJson, string outcome)
    {
        using var document = JsonDocument.Parse(metadataJson);
        var metadata = document.RootElement;
        return metadata.TryGetProperty("outcome", out var outcomeValue) &&
               outcomeValue.ValueKind == JsonValueKind.String &&
               outcomeValue.GetString() == outcome &&
               HasString(metadata, "correlation_id");
    }

    private static bool HasString(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out var property) &&
        property.ValueKind == JsonValueKind.String &&
        !string.IsNullOrWhiteSpace(property.GetString());

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class BoundaryFixture : IAsyncDisposable
    {
        private const string AdminToken = "s38-valid-administrator-token";
        private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT")
            ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        private readonly string _root;
        private readonly string _databasePath;
        private readonly PhaseAMetadataStore _store;
        private readonly Process? _process;
        private readonly HttpClient? _client;

        private BoundaryFixture(string root, string databasePath, PhaseAMetadataStore store, Process? process, HttpClient? client)
        {
            _root = root;
            _databasePath = databasePath;
            _store = store;
            _process = process;
            _client = client;
        }

        public static async Task<BoundaryFixture> CreateAsync(bool startServer = false)
        {
            var root = Path.Combine(Path.GetTempPath(), $"s38-boundary-{Guid.NewGuid():N}");
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
            if (!startServer)
            {
                return new BoundaryFixture(root, databasePath, store, null, null);
            }

            var address = $"http://127.0.0.1:{FreePort()}";
            var process = StartServer(address, databasePath, workspaceRoot);
            var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(10) };
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

        public async Task<TestAccount> CreateUserAsync(string username)
        {
            var user = await _store.CreateUserAccountAsync(username, 1);
            return new TestAccount(user.AccountId, user.Token);
        }

        public async Task<string> CreateLegacyProjectAsync(string ownerAccountId)
        {
            var projectId = $"legacy-{Guid.NewGuid():N}";
            await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath, Pooling = false }.ToString());
            await connection.OpenAsync();
            await using (var foreignKeys = connection.CreateCommand())
            {
                foreignKeys.CommandText = "PRAGMA foreign_keys = OFF;";
                await foreignKeys.ExecuteNonQueryAsync();
            }
            await using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO projects (id, account_id, name, game_name, game_type_source, template_rule_id, created_utc) VALUES ($id, $account_id, 's38 legacy', 's38 legacy', 'legacy', 'legacy', $created_utc);";
            command.Parameters.AddWithValue("$id", projectId);
            command.Parameters.AddWithValue("$account_id", ownerAccountId);
            command.Parameters.AddWithValue("$created_utc", DateTimeOffset.UtcNow.ToString("O"));
            await command.ExecuteNonQueryAsync();
            return projectId;
        }

        public Task<ProjectSnapshot?> ResolveProjectAsync(string projectId) => _store.GetProjectSnapshotAsync(projectId);

        public async Task<IReadOnlyList<OwnershipLineageEntry>> ReadWorkspaceOwnershipLineageAsync(string projectId)
        {
            await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath, Pooling = false }.ToString());
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT decision, correlation_id, created_utc FROM project_ownership_lineage WHERE project_id = $project_id ORDER BY sequence_number ASC;";
            command.Parameters.AddWithValue("$project_id", projectId);
            try
            {
                await using var reader = await command.ExecuteReaderAsync();
                var entries = new List<OwnershipLineageEntry>();
                while (await reader.ReadAsync())
                {
                    entries.Add(new OwnershipLineageEntry(reader.GetString(0), reader.GetString(1), reader.GetString(2)));
                }
                return entries;
            }
            catch (SqliteException exception) when (exception.SqliteErrorCode == 1 && exception.Message.Contains("no such table", StringComparison.OrdinalIgnoreCase))
            {
                return [];
            }
        }

        public Task<IReadOnlyList<AdminAccountAuditEvent>> ListAuditEventsAsync(string accountId) =>
            _store.ListAdminAccountAuditEventsAsync(new AdminAccountAuditQuery(100, 0, null, accountId));

        public Task<HttpResponseMessage> PostAsAdminAsync(string path, string? body = null) => PostAsync(AdminToken, path, body);

        public Task<HttpResponseMessage> PostAsUserAsync(string token, string path, string? body = null) => PostAsync(token, path, body);

        public async Task<HttpStatusCode> GetSessionAsync(string token)
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, "/api/session");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await Client.SendAsync(request);
            return response.StatusCode;
        }

        public async ValueTask DisposeAsync()
        {
            _client?.Dispose();
            if (_process is not null)
            {
                if (!_process.HasExited)
                {
                    _process.Kill(entireProcessTree: true);
                    await _process.WaitForExitAsync();
                }
                _process.Dispose();
            }
            SqliteConnection.ClearAllPools();
            await DeleteDirectoryWithRetryAsync(_root);
        }

        private HttpClient Client => _client ?? throw new InvalidOperationException("S38 HTTP client was not started.");

        private async Task<HttpResponseMessage> PostAsync(string token, string path, string? body)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, path);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            if (body is not null)
            {
                request.Content = new StringContent(body, Encoding.UTF8, "application/json");
            }
            return await Client.SendAsync(request);
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
            return Process.Start(start) ?? throw new InvalidOperationException("S38 fixture could not start PhaseA.Platform.");
        }

        private static async Task WaitForHealthAsync(HttpClient client, Process process)
        {
            Exception? last = null;
            for (var attempt = 0; attempt < 40; attempt++)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"S38 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}");
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
            throw new InvalidOperationException("S38 temporary PhaseA.Platform did not become healthy.", last);
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
    private sealed record OwnershipLineageEntry(string Decision, string CorrelationId, string CreatedUtc);
}
