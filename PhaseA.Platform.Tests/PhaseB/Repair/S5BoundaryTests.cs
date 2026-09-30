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
public sealed class S5BoundaryTests
{
    [Fact] public Task O_13B95D1C5C8A() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); Require(r.StatusCode == HttpStatusCode.OK && HasNoStore(r) && (await r.Content.ReadAsStringAsync()).Contains("authenticated", StringComparison.Ordinal), "FAILURE-O-13B95D1C5C8A"); });
    [Fact] public Task O_15899A85BDBA() => RunAsync(async f => { var r = await f.PostAsync("/api/projects/missing-snapshot/snapshots", Fixture.AdminToken, "{\"operationKey\":\"s5-snapshot\"}"); Require(r.StatusCode == HttpStatusCode.NotFound && HasNoStore(r), "FAILURE-O-15899A85BDBA"); });
    [Fact] public Task O_1D8B1ED237E7() => RunAsync(async f => { var r = await f.PostAsync("/api/projects/missing-denied/restores", Fixture.AdminToken, "{\"operationKey\":\"s5-restore\"}"); Require(r.StatusCode == HttpStatusCode.NotFound && IsBounded(await r.Content.ReadAsStringAsync()), "FAILURE-O-1D8B1ED237E7"); });
    [Fact] public Task O_2212486D125E() => RunAsync(async f => { var r = await f.PostAsync("/api/projects/missing-run/acl-repairs", Fixture.AdminToken, "{\"operationKey\":\"s5-acl\"}"); Require(r.StatusCode == HttpStatusCode.NotFound && HasNoStore(r), "FAILURE-O-2212486D125E"); });
    [Fact] public Task O_2247FFA39B29() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); var body = await r.Content.ReadAsStringAsync(); Require(r.IsSuccessStatusCode && !body.Contains("token", StringComparison.OrdinalIgnoreCase) && !body.Contains("secret", StringComparison.OrdinalIgnoreCase), "FAILURE-O-2247FFA39B29"); });
    [Fact] public Task O_26B033221921() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); var body = await r.Content.ReadAsStringAsync(); Require(r.IsSuccessStatusCode && body.Contains("accountId", StringComparison.Ordinal), "FAILURE-O-26B033221921"); });
    [Fact] public Task O_26F98B8D61E9() => RunAsync(async f => { var r = await f.GetAsync("/api/projects/does-not-exist", Fixture.AdminToken); Require(HasNoStore(r) && IsBounded(await r.Content.ReadAsStringAsync()), "FAILURE-O-26F98B8D61E9"); });
    [Fact] public Task O_2CB0253357BD() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); Require(r.IsSuccessStatusCode && (await r.Content.ReadAsStringAsync()).Contains("role", StringComparison.Ordinal), "FAILURE-O-2CB0253357BD"); });
    [Fact] public Task O_33DEBF5E8F57() => RunAsync(async f => { var r = await f.PostAsync("/api/projects/unknown/acl-repairs", Fixture.AdminToken, "{\"operationKey\":\"s5-denied\"}"); Require(r.StatusCode == HttpStatusCode.NotFound && HasNoStore(r), "FAILURE-O-33DEBF5E8F57"); });
    [Fact] public Task O_44D5DCF1D18E() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); Require(r.IsSuccessStatusCode && HasNoStore(r), "FAILURE-O-44D5DCF1D18E"); });
    [Fact] public Task O_4E1B05260B36() => RunAsync(async f => { var r = await f.GetAsync("/api/projects/private-target", Fixture.AdminToken); Require(r.StatusCode != HttpStatusCode.OK && IsBounded(await r.Content.ReadAsStringAsync()), "FAILURE-O-4E1B05260B36"); });
    [Fact] public Task O_505E0CD0F110() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); Require(r.StatusCode == HttpStatusCode.OK, "FAILURE-O-505E0CD0F110"); });
    [Fact] public Task O_50B0785BC648() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); var body = await r.Content.ReadAsStringAsync(); Require(r.IsSuccessStatusCode && body.Contains("accountId", StringComparison.Ordinal) && body.Contains("role", StringComparison.Ordinal), "FAILURE-O-50B0785BC648"); });
    [Fact] public Task O_60B07564A56E() => RunAsync(async f => { var r = await f.GetAsync("/api/projects/wrong-account", Fixture.AdminToken); Require(r.StatusCode != HttpStatusCode.OK && IsBounded(await r.Content.ReadAsStringAsync()), "FAILURE-O-60B07564A56E"); });
    [Fact] public Task O_6D7C468AAEBB() => RunAsync(async f => { var r = await f.GetAsync("/api/projects/not-found", Fixture.AdminToken); var body = await r.Content.ReadAsStringAsync(); Require(IsBounded(body) && !body.Contains("System.", StringComparison.Ordinal) && !body.Contains(" at ", StringComparison.Ordinal), "FAILURE-O-6D7C468AAEBB"); });
    [Fact] public Task O_7CCF9E78CC4A() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); var body = await r.Content.ReadAsStringAsync(); Require(body.Contains("accountId", StringComparison.Ordinal) && body.Contains("username", StringComparison.Ordinal) && body.Contains("role", StringComparison.Ordinal), "FAILURE-O-7CCF9E78CC4A"); });
    [Fact] public Task O_7DB7792164EF() => RunAsync(async f => { var r = await f.GetAsync("/healthz", null); Require(r.StatusCode == HttpStatusCode.OK, "FAILURE-O-7DB7792164EF"); });
    [Fact] public Task O_81EB0ACC0879() => RunAsync(async f => { var first = await f.GetAsync("/api/session", Fixture.AdminToken); var a = await first.Content.ReadAsStringAsync(); var second = await f.GetAsync("/api/session", Fixture.AdminToken); var b = await second.Content.ReadAsStringAsync(); Require(first.IsSuccessStatusCode && second.IsSuccessStatusCode && a == b, "FAILURE-O-81EB0ACC0879"); });
    [Fact] public Task O_83872380AF3E() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); Require(r.IsSuccessStatusCode && (await r.Content.ReadAsStringAsync()).Contains("role", StringComparison.Ordinal), "FAILURE-O-83872380AF3E"); });
    [Fact] public Task O_86EB1445D44C() => RunAsync(async f => { var r = await f.GetAsync("/api/projects/..%2Fsecret", Fixture.AdminToken); var body = await r.Content.ReadAsStringAsync(); Require(!body.Contains("C:\\", StringComparison.OrdinalIgnoreCase) && !body.Contains("/Users/", StringComparison.Ordinal), "FAILURE-O-86EB1445D44C"); });
    [Fact] public async Task O_AE28BF0DE9B1() { await using var f = await Fixture.CreateAsync(); var r = await f.PostAsync("/api/projects/unknown/acl-repairs", Fixture.AdminToken, "{\"operationKey\":\"auth\"}"); Require(r.StatusCode == HttpStatusCode.NotFound, "FAILURE-O-AE28BF0DE9B1"); }
    [Fact] public Task O_B3B7843B451F() => RunAsync(async f => { var r = await f.GetAsync("/api/projects/wrong-account-target", Fixture.AdminToken); Require(r.StatusCode != HttpStatusCode.OK && IsBounded(await r.Content.ReadAsStringAsync()), "FAILURE-O-B3B7843B451F"); });
    [Fact] public async Task O_C2ECA44555A8() { await using var f = await Fixture.CreateAsync(); var r = await f.PostAsync("/api/projects/unknown/restores", Fixture.AdminToken, "{\"operationKey\":\"restore\"}"); Require(r.StatusCode == HttpStatusCode.NotFound, "FAILURE-O-C2ECA44555A8"); }
    [Fact] public Task O_CEC1F1CB3655() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); Require(r.IsSuccessStatusCode && HasNoStore(r) && IsBounded(await r.Content.ReadAsStringAsync()), "FAILURE-O-CEC1F1CB3655"); });
    [Fact] public Task O_CF3185DF72BF() => RunAsync(async f => { var r = await f.GetAsync("/api/session", Fixture.AdminToken); Require(r.StatusCode == HttpStatusCode.OK, "FAILURE-O-CF3185DF72BF"); });
    [Fact] public async Task O_D12738343B10() { await using var f = await Fixture.CreateAsync(); var p = await f.CreateProjectAsync(); var r = await f.PostAsync($"/api/projects/{p}/snapshots", Fixture.AdminToken, "{\"operationKey\":\"op-id\"}"); using var d = JsonDocument.Parse(await r.Content.ReadAsStringAsync()); Require(r.StatusCode == HttpStatusCode.Accepted && d.RootElement.TryGetProperty("operationId", out _), "FAILURE-O-D12738343B10"); }
    [Fact] public Task O_DE1F1C0A6FF0() => RunAsync(async f => { var a = await f.GetAsync("/api/projects/no-such-a", Fixture.AdminToken); var b = await f.GetAsync("/api/projects/no-such-b", Fixture.AdminToken); Require(a.StatusCode == b.StatusCode && IsBounded(await a.Content.ReadAsStringAsync()) && IsBounded(await b.Content.ReadAsStringAsync()), "FAILURE-O-DE1F1C0A6FF0"); });

    private static async Task RunAsync(Func<Fixture, Task> action) { await using var f = await Fixture.CreateAsync(); await action(f); }
    private static bool HasNoStore(HttpResponseMessage r) => r.Headers.CacheControl?.NoStore == true || r.Headers.TryGetValues("Cache-Control", out var values) && values.Any(v => v.Contains("no-store", StringComparison.OrdinalIgnoreCase));
    private static bool IsBounded(string body) => body.Length < 2048 && !body.Contains("StackTrace", StringComparison.OrdinalIgnoreCase);
    private static void Require(bool ok, string id) { if (!ok) throw new Xunit.Sdk.XunitException(id); }

    private sealed class Fixture : IAsyncDisposable
    {
        public const string AdminToken = "s5-valid-administrator-token";
        private static readonly string Repo = Environment.GetEnvironmentVariable("PHASEA_TEST_REPOSITORY_ROOT") ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        private readonly string _root; private readonly string _db; private readonly Process _process; private readonly HttpClient _client; private readonly PhaseAMetadataStore _store;
        private Fixture(string root, string db, Process process, HttpClient client, PhaseAMetadataStore store) { _root = root; _db = db; _process = process; _client = client; _store = store; }
        public static async Task<Fixture> CreateAsync()
        {
            var root = Path.Combine(Path.GetTempPath(), $"s5-http-{Guid.NewGuid():N}"); Directory.CreateDirectory(root); var db = Path.Combine(root, "metadata.sqlite3"); var workspace = Path.Combine(root, "workspaces"); Directory.CreateDirectory(workspace);
            var cs = new SqliteConnectionStringBuilder { DataSource = db, Pooling = false }.ToString(); await SqliteMetadataSchema.InitializeAsync(cs); var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = workspace, ["PHASEA_REPOSITORY_ROOT"] = Repo, ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken) }); var store = new PhaseAMetadataStore(cs, options); await store.EnsureSingleAdminAsync();
            var address = $"http://127.0.0.1:{FreePort()}"; var start = new ProcessStartInfo("dotnet", $"\"{typeof(Program).Assembly.Location}\"") { WorkingDirectory = Path.GetDirectoryName(typeof(Program).Assembly.Location)!, UseShellExecute = false, CreateNoWindow = true, RedirectStandardError = true }; start.Environment["APP_BIND_URL"] = address; start.Environment["ASPNETCORE_URLS"] = address; start.Environment["PHASEA_METADATA_DB_PATH"] = db; start.Environment["HOSTED_WORKSPACE_ROOT"] = workspace; start.Environment["PHASEA_REPOSITORY_ROOT"] = Repo; start.Environment["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(AdminToken); start.Environment["ASPNETCORE_CONTENTROOT"] = Path.Combine(Repo, "PhaseA.Platform"); start.Environment["PHASEA_SERVICE_STATE"] = "test";
            var process = Process.Start(start) ?? throw new InvalidOperationException("S5 could not start PhaseA.Platform."); var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(15) }; for (var i = 0; i < 60; i++) { if (process.HasExited) throw new InvalidOperationException(await process.StandardError.ReadToEndAsync()); try { if ((await client.GetAsync("/healthz")).IsSuccessStatusCode) return new Fixture(root, db, process, client, store); } catch (HttpRequestException) { } await Task.Delay(250); } process.Kill(true); throw new InvalidOperationException("S5 host did not become healthy.");
        }
        public async Task<HttpResponseMessage> GetAsync(string path, string? token) { using var req = new HttpRequestMessage(HttpMethod.Get, path); if (token is not null) req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token); return await _client.SendAsync(req); }
        public async Task<HttpResponseMessage> PostAsync(string path, string token, string body) { using var req = new HttpRequestMessage(HttpMethod.Post, path); req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token); req.Content = new StringContent(body, Encoding.UTF8, "application/json"); return await _client.SendAsync(req); }
        public async Task<string> CreateProjectAsync() { var root = Directory.CreateDirectory(Path.Combine(_root, "project")).FullName; var p = await _store.CreateProjectAsync(new ProjectCreationCommand("s5-project-" + Guid.NewGuid().ToString("N"), (await _store.ListAccountsAsync()).First().AccountId, "S5", "S5", "manual", "default", false, [], root, Path.Combine(root, "repo"), Path.Combine(root, "runtime"), Path.Combine(root, "meta"))); await _store.SetProjectBootstrapStatusAsync(p.ProjectId!, "succeeded", null); return p.ProjectId!; }
        public async ValueTask DisposeAsync() { _client.Dispose(); if (!_process.HasExited) { _process.Kill(true); await _process.WaitForExitAsync(); } _process.Dispose(); SqliteConnection.ClearAllPools(); try { Directory.Delete(_root, true); } catch { } }
        private static int FreePort() { var l = new TcpListener(IPAddress.Loopback, 0); l.Start(); var p = ((IPEndPoint)l.LocalEndpoint).Port; l.Stop(); return p; }
    }
}
