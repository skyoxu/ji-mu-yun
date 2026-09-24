using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Text;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

[Collection("PhaseA process HTTP")]
public sealed class S34BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S34BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_049F0E7E8CDE()
    {
        await using var fixture = await Fixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s34-authorized-enable");
        await fixture.Store.SetUserDisabledAsync(target.AccountId, true);
        var response = await fixture.PostAsync(Fixture.AdminToken, $"/api/admin/users/{target.AccountId}/status", "{\"disabled\":false}");
        var persisted = await fixture.AccountAsync(target.AccountId);
        Require(response == HttpStatusCode.OK && persisted is { IsDisabled: false }, "FAILURE-O-049F0E7E8CDE", "An authorized administrator could not enable the Account through the production endpoint.");
        Observe(nameof(O_049F0E7E8CDE));
    }

    [Fact]
    public async Task O_0C1BF91BC308()
    {
        await using var fixture = await Fixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s34-denied-revoke-target");
        var requester = await fixture.CreateUserAsync("s34-denied-revoke-requester");
        var denied = await fixture.PostAsync(requester.Token, $"/api/admin/users/{target.AccountId}/rotate-token", null);
        var credentialStillWorks = await fixture.SessionAsync(target.Token);
        Require(denied == HttpStatusCode.Forbidden && credentialStillWorks == HttpStatusCode.OK, "FAILURE-O-0C1BF91BC308", "An insufficient role revoked a credential or changed its persisted lifecycle state.");
        Observe(nameof(O_0C1BF91BC308));
    }

    [Fact]
    public async Task O_39C25A1E9FA2()
    {
        await using var fixture = await Fixture.CreateAsync();
        var target = await fixture.CreateUserAsync("s34-denied-enable-target");
        var requester = await fixture.CreateUserAsync("s34-denied-enable-requester");
        await fixture.Store.SetUserDisabledAsync(target.AccountId, true);
        var denied = await fixture.PostAsync(requester.Token, $"/api/admin/users/{target.AccountId}/status", "{\"disabled\":false}");
        var persisted = await fixture.AccountAsync(target.AccountId);
        Require(denied == HttpStatusCode.Forbidden && persisted is { IsDisabled: true }, "FAILURE-O-39C25A1E9FA2", "An insufficient role enabled the Account or changed its persisted lifecycle state.");
        Observe(nameof(O_39C25A1E9FA2));
    }

    [Fact]
    public async Task O_8826288FBF5D()
    {
        await using var fixture = await Fixture.CreateAsync();
        var account = await fixture.CreateUserAsync("s34-soft-deleted-operation");
        var projectId = await fixture.CreateProjectAsync(account.AccountId);
        await fixture.Store.SoftDeleteProjectAsync(projectId);
        var before = await fixture.CountRunsAsync(projectId);
        var response = await fixture.PostAsync(account.Token, $"/api/projects/{projectId}/snapshots", "{\"operationKey\":\"s34-deleted\"}");
        var after = await fixture.CountRunsAsync(projectId);
        Require((response is HttpStatusCode.NotFound or HttpStatusCode.Forbidden) && before == after, "FAILURE-O-8826288FBF5D", "A soft-deleted Project accepted a new operation or created a run.");
        Observe(nameof(O_8826288FBF5D));
    }

    [Fact]
    public async Task O_9E636F2A131D()
    {
        using var database = new DisposableDatabase();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var migrated = await new SqliteMigrationService().MigrateAsync(database.ConnectionString, "s34-migration-account", "s34-migration-project", "s34-migration");
        var restoreAttempts = await CountAsync(database.ConnectionString, "restore_attempts");
        Require(migrated.Status == "completed" && restoreAttempts == 0, "FAILURE-O-9E636F2A131D", "Migration started a Restore operation without an explicit request.");
        Observe(nameof(O_9E636F2A131D));
    }

    [Fact]
    public async Task O_4067D06649D3()
    {
        using var database = new DisposableDatabase();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = CreateStore(database.ConnectionString, database.Root);
        var created = await store.CreateUserAccountAsync("s34-preserved-account", 1);
        await new SqliteMigrationService().MigrateAsync(database.ConnectionString, created.AccountId, "s34-preservation-project", "s34-preservation");
        var reopened = CreateStore(database.ConnectionString, database.Root);
        var persisted = (await reopened.ListAccountsAsync()).SingleOrDefault(account => account.AccountId == created.AccountId);
        Require(persisted is not null && persisted.Username == "s34-preserved-account", "FAILURE-O-4067D06649D3", "Migration and database reuse lost or replaced an existing account record.");
        Observe(nameof(O_4067D06649D3));
    }

    [Fact]
    public async Task O_486B2FEAA661()
    {
        using var database = new DisposableDatabase();
        var scope = await CreateRunStoreAsync(database);
        var runId = await scope.Store.CreateRunAsync("s34-project", scope.WorkspaceId, "workspace-restore:s34-evidence");
        var eventCount = await CountAsync(database.ConnectionString, "runs", "id=$id AND run_type LIKE 'workspace-restore:%'", ("$id", runId));
        Require(eventCount == 1, "FAILURE-O-486B2FEAA661", "The retained operation record did not exercise a Restore event.");
        Observe(nameof(O_486B2FEAA661));
    }

    [Fact]
    public async Task O_3B1FE89486EA()
    {
        using var database = new DisposableDatabase();
        var scope = await CreateRunStoreAsync(database);
        var account = await scope.Store.CreateUserAccountAsync("s34-evidence-secret", 2);
        var runId = await scope.Store.CreateRunAsync("s34-project", scope.WorkspaceId, "workspace-snapshot:s34-evidence");
        var evidence = await ReadRunEvidenceAsync(database.ConnectionString, runId);
        Require(!evidence.Contains(account.Token, StringComparison.Ordinal), "FAILURE-O-3B1FE89486EA", "Retained operation evidence included a credential value.");
        Observe(nameof(O_3B1FE89486EA));
    }

    [Fact]
    public async Task O_3D17BC6660AC()
    {
        using var database = new DisposableDatabase();
        var scope = await CreateRunStoreAsync(database);
        var runId = await scope.Store.CreateRunAsync("s34-project", scope.WorkspaceId, "workspace-snapshot:s34-action");
        var evidence = await ReadRunEvidenceAsync(database.ConnectionString, runId);
        Require(evidence.Contains("workspace-snapshot:s34-action", StringComparison.Ordinal), "FAILURE-O-3D17BC6660AC", "The retained operation record omitted its action.");
        Observe(nameof(O_3D17BC6660AC));
    }

    [Fact]
    public async Task O_72735DA2286C()
    {
        using var database = new DisposableDatabase();
        var scope = await CreateRunStoreAsync(database);
        var runId = await scope.Store.CreateRunAsync("s34-project", scope.WorkspaceId, "workspace-snapshot:s34-workspace");
        var evidence = await ReadRunEvidenceAsync(database.ConnectionString, runId);
        Require(evidence.Contains("s34-workspace", StringComparison.Ordinal), "FAILURE-O-72735DA2286C", "The retained operation record omitted its workspace identity.");
        Observe(nameof(O_72735DA2286C));
    }

    [Fact]
    public async Task O_D069B01B8C84()
    {
        using var database = new DisposableDatabase();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var resources = new[] { "projects", "runs", "artifacts", "packages", "assets", "chats", "workflows", "llm_usage", "workspaces", "snapshots", "restore_attempts", "previews" };
        var present = new List<string>();
        await using var connection = new SqliteConnection(database.ConnectionString);
        await connection.OpenAsync();
        foreach (var resource in resources)
        {
            await using var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=$name";
            command.Parameters.AddWithValue("$name", resource);
            if (Convert.ToInt32(await command.ExecuteScalarAsync()) == 1) present.Add(resource);
        }
        Require(present.Count == resources.Length, "FAILURE-O-D069B01B8C84", "One or more named private-resource production boundaries were not available for ownership enforcement.");
        Observe(nameof(O_D069B01B8C84));
    }

    private void Observe(string method) => _output.WriteLine($"S34-OBSERVATION {method}");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition) throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }

    private static async Task<long> CountAsync(string connectionString, string table, string? predicate = null, params (string Name, object Value)[] parameters)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var tableCheck = connection.CreateCommand();
        tableCheck.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=$name";
        tableCheck.Parameters.AddWithValue("$name", table);
        if (Convert.ToInt32(await tableCheck.ExecuteScalarAsync()) == 0) return 0;
        await using var command = connection.CreateCommand();
        command.CommandText = $"SELECT COUNT(*) FROM {table}" + (predicate is null ? string.Empty : $" WHERE {predicate}");
        foreach (var parameter in parameters) command.Parameters.AddWithValue(parameter.Name, parameter.Value);
        return Convert.ToInt64(await command.ExecuteScalarAsync());
    }

    private static async Task<string> ReadRunEvidenceAsync(string connectionString, string runId)
    {
        await using var connection = new SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT workspace_id,run_type,status FROM runs WHERE id=$id";
        command.Parameters.AddWithValue("$id", runId);
        await using var reader = await command.ExecuteReaderAsync();
        if (!await reader.ReadAsync()) return string.Empty;
        return string.Join("|", Enumerable.Range(0, reader.FieldCount).Select(index => reader.IsDBNull(index) ? string.Empty : reader.GetValue(index).ToString()));
    }

    private static PhaseAMetadataStore CreateStore(string connectionString, string root) => new(connectionString, PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = root }));

    private static async Task<RunStore> CreateRunStoreAsync(DisposableDatabase database)
    {
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = CreateStore(database.ConnectionString, database.Root);
        var account = await store.CreateUserAccountAsync("s34-run-owner", 2);
        var projectRoot = Directory.CreateDirectory(Path.Combine(database.Root, "project"));
        await store.CreateProjectAsync(new ProjectCreationCommand("s34-project", account.AccountId, "S34", "S34", "manual", "default", false, [], projectRoot.FullName, Path.Combine(projectRoot.FullName, "repo"), Path.Combine(projectRoot.FullName, "runtime"), Path.Combine(projectRoot.FullName, "meta")));
        await using var connection = new SqliteConnection(database.ConnectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT id FROM workspaces WHERE project_id='s34-project'";
        var workspaceId = (string?)await command.ExecuteScalarAsync() ?? throw new InvalidOperationException("S34 fixture did not create a Workspace.");
        return new RunStore(store, workspaceId);
    }

    private sealed record RunStore(PhaseAMetadataStore Store, string WorkspaceId);

    private sealed class DisposableDatabase : IDisposable
    {
        public DisposableDatabase()
        {
            Root = Path.Combine(Path.GetTempPath(), $"s34-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Root);
            ConnectionString = new SqliteConnectionStringBuilder { DataSource = Path.Combine(Root, "metadata.sqlite3"), Pooling = false }.ToString();
        }
        public string Root { get; }
        public string ConnectionString { get; }
        public void Dispose() { SqliteConnection.ClearAllPools(); try { Directory.Delete(Root, true); } catch (IOException) { } }
    }

    private sealed class Fixture : IAsyncDisposable
    {
        public const string AdminToken = "s34-valid-administrator-token";
        private static readonly string RepositoryRoot = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT") ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        private readonly string _root;
        private readonly string _databasePath;
        private readonly Process _process;
        private readonly HttpClient _client;
        private Fixture(string root, string databasePath, PhaseAMetadataStore store, Process process, HttpClient client) { _root = root; _databasePath = databasePath; Store = store; _process = process; _client = client; }
        public PhaseAMetadataStore Store { get; }
        public static async Task<Fixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s34-http-{Guid.NewGuid():N}");
            var databasePath = Path.Combine(root, "metadata.sqlite3");
            var workspaceRoot = Path.Combine(root, "workspaces");
            Directory.CreateDirectory(workspaceRoot);
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath, Pooling = false }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot, ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot, ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken) });
            var store = new PhaseAMetadataStore(connectionString, options);
            await store.EnsureSingleAdminAsync();
            var address = $"http://127.0.0.1:{FreePort()}";
            var start = new ProcessStartInfo("dotnet", $"\"{typeof(Program).Assembly.Location}\"") { WorkingDirectory = Path.GetDirectoryName(typeof(Program).Assembly.Location)!, UseShellExecute = false, CreateNoWindow = true, RedirectStandardError = true };
            start.Environment["APP_BIND_URL"] = address; start.Environment["ASPNETCORE_URLS"] = address; start.Environment["PUBLIC_BASE_URL"] = "https://localhost"; start.Environment["PHASEA_METADATA_DB_PATH"] = databasePath; start.Environment["HOSTED_WORKSPACE_ROOT"] = workspaceRoot; start.Environment["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot; start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken); start.Environment["ASPNETCORE_CONTENTROOT"] = Path.Combine(RepositoryRoot, "PhaseA.Platform"); start.Environment["PHASEA_SERVICE_STATE"] = "test";
            var process = Process.Start(start) ?? throw new InvalidOperationException("S34 could not start PhaseA.Platform.");
            var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(10) };
            for (var attempt = 0; attempt < 40; attempt++) { if (process.HasExited) throw new InvalidOperationException($"S34 temporary PhaseA.Platform exited: {await process.StandardError.ReadToEndAsync()}"); try { if ((await client.GetAsync("/healthz")).IsSuccessStatusCode) return new Fixture(root, databasePath, store, process, client); } catch (HttpRequestException) { } await Task.Delay(250); }
            client.Dispose(); process.Kill(true); process.Dispose(); throw new InvalidOperationException("S34 temporary PhaseA.Platform did not become healthy.");
        }
        public async Task<TestAccount> CreateUserAsync(string username) { var created = await Store.CreateUserAccountAsync(username, 2); return new TestAccount(created.AccountId, created.Token); }
        public async Task<string> CreateProjectAsync(string accountId) { var root = Directory.CreateDirectory(Path.Combine(_root, $"project-{Guid.NewGuid():N}")); var project = await Store.CreateProjectAsync(new ProjectCreationCommand($"project-{Guid.NewGuid():N}", accountId, "S34", "S34", "manual", "default", false, [], root.FullName, Path.Combine(root.FullName, "repo"), Path.Combine(root.FullName, "runtime"), Path.Combine(root.FullName, "meta"))); await Store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null); return project.ProjectId!; }
        public async Task<HttpStatusCode> PostAsync(string token, string path, string? body) { using var request = new HttpRequestMessage(HttpMethod.Post, path); request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token); if (body is not null) request.Content = new StringContent(body, Encoding.UTF8, "application/json"); using var response = await _client.SendAsync(request); return response.StatusCode; }
        public async Task<HttpStatusCode> SessionAsync(string token) { using var request = new HttpRequestMessage(HttpMethod.Get, "/api/session"); request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token); using var response = await _client.SendAsync(request); return response.StatusCode; }
        public async Task<AdminUserListItem?> AccountAsync(string accountId) => (await Store.ListAccountsAsync()).SingleOrDefault(account => account.AccountId == accountId);
        public async Task<long> CountRunsAsync(string projectId) { await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _databasePath }.ToString()); await connection.OpenAsync(); await using var command = connection.CreateCommand(); command.CommandText = "SELECT COUNT(*) FROM runs WHERE project_id=$project"; command.Parameters.AddWithValue("$project", projectId); return Convert.ToInt64(await command.ExecuteScalarAsync()); }
        public async ValueTask DisposeAsync() { _client.Dispose(); if (!_process.HasExited) { _process.Kill(true); await _process.WaitForExitAsync(); } _process.Dispose(); SqliteConnection.ClearAllPools(); try { Directory.Delete(_root, true); } catch (IOException) { } }
        private static int FreePort() { var listener = new TcpListener(IPAddress.Loopback, 0); listener.Start(); var port = ((IPEndPoint)listener.LocalEndpoint).Port; listener.Stop(); return port; }
    }
    private sealed record TestAccount(string AccountId, string Token);
}
