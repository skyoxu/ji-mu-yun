using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061: narrow deletion/capture consumers retain current identity and canonical roots.
public sealed class NodeDeletionAndSnapshotRegressionTests
{
    [Fact]
    public async Task AdminDeletionDoesNotGrantOrdinaryCrossOwnerReadOrTrustTheAdminFlag()
    {
        var f = await Fixture.CreateAsync();
        using (S206TestSupport.EnterCurrentContext(f.FirstContext))
        {
            Assert.Equal("project_not_found", (await f.Service.DeleteProjectAsync(f.First.AccountId,
                f.SecondProject.ProjectId, new("delete", "delete"))).FailureCode);
            await Assert.ThrowsAsync<UnauthorizedAccessException>(() => f.Service.DeleteProjectAsync(f.First.AccountId,
                true, f.SecondProject.ProjectId, new("delete", "delete")));
        }
        using (S206TestSupport.EnterCurrentContext(f.AdminContext))
        {
            NodeProjectMetadata ordinary = f.Store;
            await Assert.ThrowsAsync<UnauthorizedAccessException>(() => ordinary.GetProjectSnapshotAsync(f.FirstProject.ProjectId));
            Assert.True((await f.Service.DeleteProjectAsync(f.AdminContext.AccountId, true,
                f.FirstProject.ProjectId, new("delete", "delete"))).Succeeded);
            Assert.True((await f.Service.DeleteProjectAsync(f.AdminContext.AccountId, true,
                f.FirstProject.ProjectId, new("delete", "delete"))).Succeeded);
        }
        Assert.NotNull(await f.Store.GetProjectSnapshotAsync(f.SecondProject.ProjectId));
    }

    [Fact]
    public async Task OwnerRetryIsIdempotentWithoutAdminTombstoneEnumeration()
    {
        var f = await Fixture.CreateAsync();
        using (S206TestSupport.EnterCurrentContext(f.FirstContext))
        {
            Assert.True((await f.Service.DeleteProjectAsync(f.First.AccountId, f.FirstProject.ProjectId, new("delete", "delete"))).Succeeded);
            Assert.True((await f.Service.DeleteProjectAsync(f.First.AccountId, f.FirstProject.ProjectId, new("delete", "delete"))).Succeeded);
            NodeProjectMetadata node = f.Store;
            await Assert.ThrowsAsync<UnauthorizedAccessException>(() => node.ListProjectDeleteTombstonesForAdminAsync());
        }
        using (S206TestSupport.EnterCurrentContext(f.SecondContext))
            Assert.Equal("project_not_found", (await f.Service.DeleteProjectAsync(f.Second.AccountId,
                f.FirstProject.ProjectId, new("delete", "delete"))).FailureCode);
        await f.Store.SetUserDisabledAsync(f.First.AccountId, true);
        using (S206TestSupport.EnterCurrentContext(f.FirstContext))
            await Assert.ThrowsAsync<UnauthorizedAccessException>(() => f.Service.DeleteProjectAsync(f.First.AccountId,
                f.FirstProject.ProjectId, new("delete", "delete")));
    }

    [Fact]
    public async Task WorkspaceCaptureIsExactAndDoesNotWidenRepositorySnapshotAuthority()
    {
        var f = await Fixture.CreateAsync();
        var storage = f.Store.CreateWorkspaceStorageService();
        var p = f.FirstProject;
        using (S206TestSupport.EnterCurrentContext(f.FirstContext))
        {
            var repo = storage.CreateSnapshot(f.FirstContext, p.RepoPath, "repo-control", p.WorkspaceId, p.ProjectId, "test", new HashSet<string>());
            Assert.Contains(repo.Manifest.Files, file => file.RelativePath == "owned.txt");
            Assert.Throws<UnauthorizedAccessException>(() => storage.CreateSnapshot(f.FirstContext, p.WorkspaceRootPath,
                "wrong-public-root", p.WorkspaceId, p.ProjectId, "test", new HashSet<string>()));
            var workspace = storage.CreateProjectWorkspaceSnapshot(f.FirstContext, p.WorkspaceRootPath,
                "workspace-control", p.WorkspaceId, p.ProjectId, "test", new HashSet<string>());
            Assert.Contains(workspace.Manifest.Files, file => file.RelativePath == "repo/owned.txt");
            Assert.Throws<UnauthorizedAccessException>(() => storage.CreateProjectWorkspaceSnapshot(f.FirstContext,
                f.SecondProject.WorkspaceRootPath, "other-root", p.WorkspaceId, p.ProjectId, "test", new HashSet<string>()));
        }
        using (S206TestSupport.EnterCurrentContext(f.SecondContext))
            Assert.Throws<UnauthorizedAccessException>(() => storage.CreateProjectWorkspaceSnapshot(f.SecondContext,
                p.WorkspaceRootPath, "other-owner", p.WorkspaceId, p.ProjectId, "test", new HashSet<string>()));
    }

    [Fact]
    public async Task PermissionRechecksDoNotWriteAuthenticationUsage()
    {
        var f = await Fixture.CreateAsync();
        using var connection = new SqliteConnection(f.ConnectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE fixture_auth_usage_writes(id INTEGER);
            CREATE TRIGGER fixture_auth_usage AFTER UPDATE OF last_used_utc ON accounts
            BEGIN INSERT INTO fixture_auth_usage_writes VALUES(1); END;
            """;
        command.ExecuteNonQuery();
        using (S206TestSupport.EnterCurrentContext(f.FirstContext))
        {
            NodeProjectMetadata node = f.Store;
            Assert.NotNull(await node.GetProjectSnapshotAsync(f.FirstProject.ProjectId));
            var queue = new HeavyRunnerQueueService(null, 1, node);
            await using var lease = await queue.EnterAsync("owned-run", f.First.AccountId, f.FirstProject.ProjectId, "test");
        }
        command.CommandText = "SELECT count(*) FROM fixture_auth_usage_writes;";
        Assert.Equal(0L, Convert.ToInt64(command.ExecuteScalar()));
        Assert.NotNull(await f.Store.ResolveAccountByTokenHashAsync(f.FirstContext.CredentialId));
        Assert.Equal(1L, Convert.ToInt64(command.ExecuteScalar()));
    }

    [Fact]
    public async Task MetadataSeedDoesNotMaterializeTestHostLibraries()
    {
        var f = await Fixture.CreateAsync();
        using var current = S206TestSupport.EnterCurrentContext(f.FirstContext);
        var created = await f.Service.CreateProjectAsync(f.First.AccountId,
            new ProjectCreationRequest(null, "Minimal metadata seed", "manual", null, null, null, null));
        Assert.True(created.Succeeded, created.FailureCode);
        var project = (await f.Store.GetProjectSnapshotAsync(created.ProjectId!))!;
        Assert.True(File.Exists(Path.Combine(project.RepoPath, "README.md")));
        Assert.Empty(Directory.EnumerateFiles(project.WorkspaceRootPath, "*.dll", SearchOption.AllDirectories));
    }

    private sealed class Fixture
    {
        public string ConnectionString = "";
        public PhaseAMetadataStore Store = null!;
        public PhaseAPlatformOptions Options = null!;
        public RequestContext AdminContext = null!, FirstContext = null!, SecondContext = null!;
        public AdminCreateUserResult First = null!, Second = null!;
        public ProjectSnapshot FirstProject = null!, SecondProject = null!;
        public ProjectCreationService Service = null!;
        public static async Task<Fixture> CreateAsync()
        {
            var root = S206TestSupport.CreateOwnedFixtureRoot("ci-deletion-capture-");
            Directory.CreateDirectory(root);
            var f = new Fixture { ConnectionString = new SqliteConnectionStringBuilder
                { DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false }.ToString() };
            f.Options = S206TestSupport.OwnedNodeOptions(new() { ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces") });
            await SqliteMetadataSchema.InitializeSingleNodeTestAsync(f.ConnectionString, f.Options);
            f.Store = new PhaseAMetadataStore(f.ConnectionString, f.Options);
            f.AdminContext = await S206TestSupport.FixtureContextAsync(f.Store, f.Options.AdminTokenHash);
            f.First = await f.Store.CreateUserAccountAsync("first", 2);
            f.Second = await f.Store.CreateUserAccountAsync("second", 2);
            f.FirstContext = await S206TestSupport.FixtureContextAsync(f.Store, PhaseAAuth.HashTokenForStorage(f.First.Token));
            f.SecondContext = await S206TestSupport.FixtureContextAsync(f.Store, PhaseAAuth.HashTokenForStorage(f.Second.Token));
            f.FirstProject = await f.CreateProjectAsync(f.First.AccountId);
            f.SecondProject = await f.CreateProjectAsync(f.Second.AccountId);
            f.Service = new ProjectCreationService(f.Store, f.Options, new ProjectRuleCatalog(), new ProjectWorkspaceSeeder(f.Options, f.Store));
            return f;
        }
        private async Task<ProjectSnapshot> CreateProjectAsync(string owner)
        {
            var id = Guid.NewGuid().ToString("N");
            var layout = WorkspaceLayoutBuilder.Build(Options.HostedWorkspaceRoot, owner, id);
            foreach (var directory in new[] { layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath }) Directory.CreateDirectory(directory);
            File.WriteAllText(Path.Combine(layout.RepoPath, "owned.txt"), owner);
            Assert.True((await Store.CreateProjectAsync(new(id, owner, "Owned", "Owned", "manual", "default", false, [],
                layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath))).Succeeded);
            await Store.SetProjectBootstrapStatusAsync(id, "succeeded", null);
            return (await Store.GetProjectSnapshotAsync(id))!;
        }
    }
}
