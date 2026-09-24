using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S8BoundaryTests
{
    [Fact]
    public async Task O_1939141A84C2()
    {
        using var scope = await S8Scope.CreateAsync();
        var project = await scope.CreateActiveProjectAsync("soft-deleted-listing");

        var deleted = await scope.Service.DeleteProjectAsync(
            scope.Owner.AccountId,
            project.ProjectId,
            new ProjectDeletionRequest("delete", "delete"));
        if (!deleted.Succeeded)
        {
            throw new InvalidOperationException($"S8 fixture could not soft-delete its disposable Project: {deleted.FailureCode}");
        }

        var normalProjectList = await scope.Readback.ListProjectsAsync(scope.Owner.AccountId);

        var softDeletedProjectIsAbsent = !normalProjectList.Any(item => item.ProjectId == project.ProjectId);

        Assert.True(
            softDeletedProjectIsAbsent,
            "FAILURE-O-1939141A84C2: the soft-deleted Project appeared in the normal Project list.");
    }

    private sealed class S8Scope : IDisposable
    {
        private readonly TempSqliteDatabase _database;

        private S8Scope(
            TempSqliteDatabase database,
            string workspaceRoot,
            PhaseAMetadataStore store,
            AdminCreateUserResult owner,
            ProjectCreationService service,
            ArtifactReadbackService readback)
        {
            _database = database;
            WorkspaceRoot = workspaceRoot;
            Store = store;
            Owner = owner;
            Service = service;
            Readback = readback;
        }

        public string WorkspaceRoot { get; }
        public PhaseAMetadataStore Store { get; }
        public AdminCreateUserResult Owner { get; }
        public ProjectCreationService Service { get; }
        public ArtifactReadbackService Readback { get; }

        public static async Task<S8Scope> CreateAsync()
        {
            var database = TempSqliteDatabase.Create();
            var workspaceRoot = Path.Combine(Path.GetTempPath(), $"phase-s8-{Guid.NewGuid():N}");
            Directory.CreateDirectory(workspaceRoot);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot()
            });

            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var owner = await store.CreateUserAccountAsync($"s8-owner-{Guid.NewGuid():N}", projectLimit: 1);
            var service = new ProjectCreationService(store, options, new ProjectRuleCatalog(), new DisposableWorkspaceSeeder());
            return new S8Scope(database, workspaceRoot, store, owner, service, new ArtifactReadbackService(store, options));
        }

        public async Task<ProjectSnapshot> CreateActiveProjectAsync(string gameName)
        {
            var created = await Service.CreateProjectAsync(Owner.AccountId, new ProjectCreationRequest(
                null, gameName, "manual", null, null, null, null));
            if (!created.Succeeded || string.IsNullOrWhiteSpace(created.ProjectId))
            {
                throw new InvalidOperationException($"S8 fixture could not create its disposable Project: {created.FailureCode}");
            }

            await Store.SetProjectBootstrapStatusAsync(created.ProjectId, "succeeded", null);
            return await Store.GetProjectSnapshotAsync(created.ProjectId)
                ?? throw new InvalidOperationException("S8 fixture could not resolve its disposable Project.");
        }

        public void Dispose()
        {
            _database.Dispose();
            try
            {
                if (Directory.Exists(WorkspaceRoot))
                {
                    Directory.Delete(WorkspaceRoot, recursive: true);
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        private sealed class DisposableWorkspaceSeeder : IProjectWorkspaceSeeder
        {
            public void EnsureSeeded(string projectRepoPath)
            {
            }
        }

        private static string RepositoryRoot() => Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory,
            "..",
            "..",
            "..",
            "Fixtures",
            "ProjectSeedRepository"));
    }
}
