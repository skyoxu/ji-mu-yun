using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S20BoundaryTests
{
    [Fact]
    public async Task O_0D256558EC1D()
    {
        using var scope = await S20Scope.CreateAsync(projectLimit: 1);
        var project = await scope.CreateActiveProjectAsync("retained-data");

        var deleted = await scope.Service.DeleteProjectAsync(
            scope.Owner.AccountId,
            project.ProjectId,
            new ProjectDeletionRequest("delete", "delete"));
        var protectedRecord = (await scope.Store.ListProjectDeleteTombstonesForAdminAsync())
            .SingleOrDefault(item => item.ProjectId == project.ProjectId);
        var ordinaryProjects = await scope.Store.ListProjectsAsync(scope.Owner.AccountId);

        var retainedOnlyForCleanup =
            deleted.Succeeded &&
            Directory.Exists(project.WorkspaceRootPath) &&
            protectedRecord is not null &&
            !ordinaryProjects.Any(item => item.ProjectId == project.ProjectId);

        Assert.True(
            retainedOnlyForCleanup,
            "FAILURE-O-0D256558EC1D: retained Project data was not available only through the protected cleanup lifecycle.");
    }

    [Fact]
    public async Task O_AE14D92CB000()
    {
        using var scope = await S20Scope.CreateAsync(projectLimit: 1);
        var project = await scope.CreateActiveProjectAsync("logical-quota");

        var initialDelete = await scope.Service.DeleteProjectAsync(
            scope.Owner.AccountId,
            project.ProjectId,
            new ProjectDeletionRequest("delete", "delete"));
        var retryDelete = await scope.Service.DeleteProjectAsync(
            scope.Owner.AccountId,
            project.ProjectId,
            new ProjectDeletionRequest("delete", "delete"));
        var replacement = await scope.Service.CreateProjectAsync(scope.Owner.AccountId, S20Scope.Request("replacement"));
        var overLimit = await scope.Service.CreateProjectAsync(scope.Owner.AccountId, S20Scope.Request("over-limit"));
        var tombstoneCount = (await scope.Store.ListProjectDeleteTombstonesForAdminAsync())
            .Count(item => item.ProjectId == project.ProjectId);

        var releasedExactlyOnceWithoutPhysicalReclamation =
            initialDelete.Succeeded &&
            retryDelete.Succeeded &&
            replacement.Succeeded &&
            !overLimit.Succeeded &&
            overLimit.FailureCode == "project_quota_exceeded" &&
            tombstoneCount == 1 &&
            Directory.Exists(project.WorkspaceRootPath);

        Assert.True(
            releasedExactlyOnceWithoutPhysicalReclamation,
            "FAILURE-O-AE14D92CB000: soft delete did not release exactly one logical quota share before protected physical cleanup.");
    }

    [Fact]
    public async Task O_ED5AFFFDE466()
    {
        using var scope = await S20Scope.CreateAsync(projectLimit: 1);
        var project = await scope.CreateActiveProjectAsync("soft-delete-state");

        var deleted = await scope.Service.DeleteProjectAsync(
            scope.Owner.AccountId,
            project.ProjectId,
            new ProjectDeletionRequest("delete", "delete"));
        var protectedRecord = (await scope.Store.ListProjectDeleteTombstonesForAdminAsync())
            .SingleOrDefault(item => item.ProjectId == project.ProjectId);
        var ordinaryProjects = await scope.Store.ListProjectsAsync(scope.Owner.AccountId);

        var serverOwnedSoftDeleteState =
            deleted.Succeeded &&
            protectedRecord is not null &&
            Directory.Exists(project.WorkspaceRootPath) &&
            !ordinaryProjects.Any(item => item.ProjectId == project.ProjectId);

        Assert.True(
            serverOwnedSoftDeleteState,
            "FAILURE-O-ED5AFFFDE466: the Project service entry did not retain server-owned soft-delete state and data for protected cleanup.");
    }

    [Fact]
    public async Task O_FD2C50597483()
    {
        using var scope = await S20Scope.CreateAsync(projectLimit: 1);
        var project = await scope.CreateActiveProjectAsync("retained-owner");

        var deleted = await scope.Service.DeleteProjectAsync(
            scope.Owner.AccountId,
            project.ProjectId,
            new ProjectDeletionRequest("delete", "delete"));
        var protectedRecord = (await scope.Store.ListProjectDeleteTombstonesForAdminAsync())
            .SingleOrDefault(item => item.ProjectId == project.ProjectId);

        var cleanupResolvesOriginalOwner =
            deleted.Succeeded &&
            protectedRecord is not null &&
            protectedRecord.AccountId == scope.Owner.AccountId &&
            Directory.Exists(project.WorkspaceRootPath);

        Assert.True(
            cleanupResolvesOriginalOwner,
            "FAILURE-O-FD2C50597483: protected cleanup could not resolve retained Project data to its original server-controlled owner.");
    }

    private sealed class S20Scope : IDisposable
    {
        private readonly TempSqliteDatabase _database;

        private S20Scope(
            TempSqliteDatabase database,
            string workspaceRoot,
            PhaseAMetadataStore store,
            AdminCreateUserResult owner,
            ProjectCreationService service)
        {
            _database = database;
            WorkspaceRoot = workspaceRoot;
            Store = store;
            Owner = owner;
            Service = service;
        }

        public string WorkspaceRoot { get; }
        public PhaseAMetadataStore Store { get; }
        public AdminCreateUserResult Owner { get; }
        public ProjectCreationService Service { get; }

        public static async Task<S20Scope> CreateAsync(int projectLimit)
        {
            var database = TempSqliteDatabase.Create();
            var workspaceRoot = Path.Combine(Path.GetTempPath(), $"phase-s20-{Guid.NewGuid():N}");
            Directory.CreateDirectory(workspaceRoot);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot()
            });

            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var owner = await store.CreateUserAccountAsync($"s20-owner-{Guid.NewGuid():N}", projectLimit);
            return new S20Scope(
                database,
                workspaceRoot,
                store,
                owner,
                new ProjectCreationService(store, options, new ProjectRuleCatalog(), new DisposableWorkspaceSeeder()));
        }

        public async Task<ProjectSnapshot> CreateActiveProjectAsync(string gameName)
        {
            var created = await Service.CreateProjectAsync(Owner.AccountId, Request(gameName));
            if (!created.Succeeded || string.IsNullOrWhiteSpace(created.ProjectId))
            {
                throw new InvalidOperationException($"S20 fixture could not create its disposable Project: {created.FailureCode}");
            }

            await Store.SetProjectBootstrapStatusAsync(created.ProjectId, "succeeded", null);
            var project = await Store.GetProjectSnapshotAsync(created.ProjectId);
            if (project is null)
            {
                throw new InvalidOperationException("S20 fixture could not resolve its disposable Project.");
            }

            File.WriteAllText(Path.Combine(project.RuntimePath, "retained.txt"), "retained for protected cleanup");
            return project;
        }

        public static ProjectCreationRequest Request(string gameName) =>
            new(null, gameName, "manual", null, null, null, null);

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
