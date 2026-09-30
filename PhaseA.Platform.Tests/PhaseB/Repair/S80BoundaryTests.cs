using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S80BoundaryTests
{
    [Fact]
    public async Task O_D92173A93038()
    {
        using var scope = await S80Scope.CreateAsync();
        var project = await scope.CreateProjectAsync("restore-not-implicit");

        var projectExists = await scope.Store.GetProjectSnapshotAsync(project.ProjectId) is not null;
        var restoreAttemptCount = scope.CountRestoreAttempts(project.ProjectId);

        Assert.True(
            projectExists && restoreAttemptCount == 0,
            "FAILURE-O-D92173A93038: project creation started a Restore operation without an explicit Restore request.");
    }

    [Fact]
    public async Task O_FCAFEB88277C()
    {
        using var scope = await S80Scope.CreateAsync();
        var project = await scope.CreateProjectAsync("snapshot-not-implicit");

        var projectExists = await scope.Store.GetProjectSnapshotAsync(project.ProjectId) is not null;
        var persistedSnapshots = new WorkspaceStorageService(scope.ConnectionString)
            .ListSnapshots(scope.Owner.AccountId, project.ProjectId, includeDeleted: true);
        var manifests = Directory.EnumerateFiles(
            project.WorkspaceRootPath,
            ".snapshots-*.json",
            SearchOption.AllDirectories);

        Assert.True(
            projectExists && persistedSnapshots.Count == 0 && !manifests.Any(),
            "FAILURE-O-FCAFEB88277C: project creation created a Snapshot without an explicit Snapshot request.");
    }

    private sealed class S80Scope : IDisposable
    {
        private readonly TempSqliteDatabase _database;

        private S80Scope(
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
        public string ConnectionString => _database.ConnectionString;
        public PhaseAMetadataStore Store { get; }
        public AdminCreateUserResult Owner { get; }
        public ProjectCreationService Service { get; }

        public static async Task<S80Scope> CreateAsync()
        {
            var database = TempSqliteDatabase.Create();
            var workspaceRoot = Path.Combine(Path.GetTempPath(), $"phase-s80-{Guid.NewGuid():N}");
            Directory.CreateDirectory(workspaceRoot);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
                ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
                ["PHASEA_REPOSITORY_ROOT"] = RepositoryRoot()
            });

            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var owner = await store.CreateUserAccountAsync($"s80-owner-{Guid.NewGuid():N}", projectLimit: 1);
            var service = new ProjectCreationService(store, options, new ProjectRuleCatalog(), new DisposableWorkspaceSeeder());
            return new S80Scope(database, workspaceRoot, store, owner, service);
        }

        public async Task<ProjectSnapshot> CreateProjectAsync(string gameName)
        {
            var created = await Service.CreateProjectAsync(Owner.AccountId, new ProjectCreationRequest(
                null, gameName, "manual", null, null, null, null));
            if (!created.Succeeded || string.IsNullOrWhiteSpace(created.ProjectId))
            {
                throw new InvalidOperationException($"S80 fixture could not create its disposable Project: {created.FailureCode}");
            }

            return await Store.GetProjectSnapshotAsync(created.ProjectId)
                ?? throw new InvalidOperationException("S80 fixture could not resolve its disposable Project.");
        }

        public int CountRestoreAttempts(string projectId)
        {
            using var connection = new SqliteConnection(ConnectionString);
            connection.Open();
            using var table = connection.CreateCommand();
            table.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='restore_attempts'";
            if (Convert.ToInt32(table.ExecuteScalar()) == 0)
            {
                return 0;
            }

            using var records = connection.CreateCommand();
            records.CommandText = "SELECT COUNT(*) FROM restore_attempts WHERE project_id=$project";
            records.Parameters.AddWithValue("$project", projectId);
            return Convert.ToInt32(records.ExecuteScalar());
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
