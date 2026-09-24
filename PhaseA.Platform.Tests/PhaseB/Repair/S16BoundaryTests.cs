using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S16BoundaryTests
{
    [Fact]
    public void O_BBE96071CA81()
    {
        using var f = Fixture.Create();
        _ = new RestoreService(f.Connection).Restore(f.Context, f.Manifest, f.Source, f.Destination, f.Lease, "owner-initial");
        var before = File.ReadAllText(Path.Combine(f.Destination, "published.txt"));
        var revoked = f.Context with { PrincipalId = "revoked-owner", CredentialId = "revoked-credential" };
        var denied = Assert.Throws<UnauthorizedAccessException>(() => new RestoreService(f.Connection).Restore(revoked, f.Manifest, f.Source, f.Destination, f.Lease, "owner-change"));
        Assert.Contains("restore", denied.Message, StringComparison.OrdinalIgnoreCase);
        Assert.Equal(before, File.ReadAllText(Path.Combine(f.Destination, "published.txt")));
    }

    [Fact]
    public void O_F7C65E43B423()
    {
        using var f = Fixture.Create();
        _ = new RestoreService(f.Connection).Restore(f.Context, f.Manifest, f.Source, f.Destination, f.Lease, "initial");
        var revoked = f.Context with { CredentialId = "rotated-credential" };
        var denied = Assert.Throws<UnauthorizedAccessException>(() => new RestoreService(f.Connection).Restore(revoked, f.Manifest, f.Source, f.Destination, f.Lease, "credential-revoked"));
        Assert.Contains("credential", denied.Message, StringComparison.OrdinalIgnoreCase);
        Assert.False(Directory.Exists(Path.Combine(f.Destination, ".restore-current")));
    }

    private sealed class Fixture : IDisposable
    {
        public string Root { get; } = Directory.CreateTempSubdirectory("s16-").FullName;
        public string Connection { get; }
        public string Source { get; }
        public string Destination { get; }
        public SnapshotManifest Manifest { get; }
        public RunnerLease Lease { get; }
        public RequestContext Context { get; }
        private Fixture()
        {
            Connection = new SqliteConnectionStringBuilder { DataSource = Path.Combine(Root, "metadata.sqlite3"), Pooling = false }.ToString();
            SqliteMetadataSchema.InitializeAsync(Connection).GetAwaiter().GetResult();
            var account = new PhaseAMetadataStore(Connection, PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>())).CreateUserAccountAsync("s16-owner", 2).GetAwaiter().GetResult();
            Lease = new RunnerLease("s16-lease", account.AccountId, "s16-project", 1);
            Context = RequestContext.FromIdentity(new AccountIdentity(account.AccountId, "owner", PhaseAAuth.UserRole), "s16-owner", "s16-credential", "s16-correlation");
            using (var connection = new SqliteConnection(Connection))
            {
                connection.Open();
                using var command = connection.CreateCommand();
                command.CommandText = "CREATE TABLE IF NOT EXISTS runner_leases(lease_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,project_id TEXT NOT NULL,fence INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS restore_runtime_credentials(workspace_id TEXT PRIMARY KEY,credential_id TEXT NOT NULL); INSERT INTO runner_leases(lease_id,account_id,project_id,fence) VALUES($id,$account,$project,$fence); INSERT INTO restore_runtime_credentials(workspace_id,credential_id) VALUES('s16-workspace','s16-credential')";
                command.Parameters.AddWithValue("$id", Lease.LeaseId); command.Parameters.AddWithValue("$account", Lease.AccountId); command.Parameters.AddWithValue("$project", Lease.ProjectId); command.Parameters.AddWithValue("$fence", Lease.Fence); command.ExecuteNonQuery();
            }
            Source = Directory.CreateDirectory(Path.Combine(Root, "source")).FullName;
            Destination = Directory.CreateDirectory(Path.Combine(Root, "destination")).FullName;
            File.WriteAllText(Path.Combine(Source, "project.godot"), "s16-published");
            File.WriteAllText(Path.Combine(Destination, "published.txt"), "unchanged");
            Manifest = SnapshotManifest.Create("s16-snapshot", "s16-workspace", account.AccountId, "s16-project", "s16-policy", [("project.godot", "s16-published"u8.ToArray())]);
        }
        public static Fixture Create() => new();
        public void Dispose() { SqliteConnection.ClearAllPools(); try { Directory.Delete(Root, true); } catch { } }
    }
}
