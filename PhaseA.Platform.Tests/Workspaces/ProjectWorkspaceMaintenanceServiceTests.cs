using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;
using Xunit;
using PhaseA.Platform.Tests.Data;

namespace PhaseA.Platform.Tests.Workspaces;

public sealed class ProjectWorkspaceMaintenanceServiceTests
{
    [Fact]
    public async Task EnsureAllWorkspacesSeededAsync_RepairsEveryKnownProjectWorkspace()
    {
        using var database = TempSqliteDatabase.Create();
        using var sourceRoot = TempDirectory.Create("phase-a-source");
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot.Path,
            ["HOSTED_PROJECT_LIMIT"] = "4"
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();

        Directory.CreateDirectory(Path.Combine(sourceRoot.Path, "Tests.Godot", "addons", "gdUnit4", "bin"));
        File.WriteAllText(Path.Combine(sourceRoot.Path, "Tests.Godot", "addons", "gdUnit4", "bin", "GdUnitCmdTool.gd"), "runner\n");

        var first = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", workspaceRoot.Path));
        first.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(first.ProjectId!, "succeeded", null);
        var second = await store.CreateProjectAsync(CreateCommand(accountId, "project-two", workspaceRoot.Path));
        second.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(second.ProjectId!, "succeeded", null);
        var firstProject = await store.GetProjectSnapshotAsync(first.ProjectId!);
        var secondProject = await store.GetProjectSnapshotAsync(second.ProjectId!);
        Directory.CreateDirectory(Path.Combine(firstProject!.RepoPath, "Tests.Godot", "addons", "gdUnit4"));
        Directory.CreateDirectory(Path.Combine(secondProject!.RepoPath, "Tests.Godot", "addons", "gdUnit4"));

        var service = new ProjectWorkspaceMaintenanceService(
            store,
            new ProjectWorkspaceSeeder(options),
            NullLogger<ProjectWorkspaceMaintenanceService>.Instance);

        await service.EnsureAllWorkspacesSeededAsync();

        File.Exists(Path.Combine(firstProject.RepoPath, "Tests.Godot", "addons", "gdUnit4", "bin", "GdUnitCmdTool.gd")).Should().BeTrue();
        File.Exists(Path.Combine(secondProject.RepoPath, "Tests.Godot", "addons", "gdUnit4", "bin", "GdUnitCmdTool.gd")).Should().BeTrue();
    }

    private static ProjectCreationCommand CreateCommand(string accountId, string projectName, string workspaceRoot)
    {
        var projectId = Guid.NewGuid().ToString("N");
        var root = Path.Combine(workspaceRoot, "account", projectName);
        return new ProjectCreationCommand(
            projectId,
            accountId,
            projectName,
            projectName,
            "admin-rule",
            "godot-prototype-default",
            true,
            ["chapter2-bootstrap"],
            root,
            Path.Combine(root, "repo"),
            Path.Combine(root, "runtime"),
            Path.Combine(root, "meta"));
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
