using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Readback;

public sealed class ArtifactReadbackServiceTests
{
    [Fact]
    public async Task Readback_ListsProjectsRunsAndReadsArtifactContent()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runId = await store.CreateRunAsync(projectId, null, "prototype-tdd-green");
        await store.CompleteRunAsync(runId, "succeeded", 0, "stdout", "", "{}", CancellationToken.None);
        Write(repoRoot.Path, "logs/ci/sample-artifact.txt", "artifact text");
        await store.AddArtifactAsync(new ArtifactCreationCommand(runId, projectId, "sample", "logs/ci/sample-artifact.txt", "Sample artifact"));
        var service = new ArtifactReadbackService(store, options);

        var projects = await service.ListProjectsAsync((await store.GetProjectSnapshotAsync(projectId))!.AccountId);
        var runs = await service.GetProjectRunsAsync(projectId);
        var artifacts = await service.ListArtifactsForRunAsync(runId);
        var artifact = await service.ReadArtifactAsync(artifacts[0].ArtifactId);

        projects.Should().ContainSingle(p => p.ProjectId == projectId);
        runs!.Runs.Should().ContainSingle(r => r.RunId == runId);
        artifact!.Content.Should().Be("artifact text");
        artifact.RelativePath.Should().Be("logs/ci/sample-artifact.txt");
    }

    [Fact]
    public async Task Readback_WorksWhileRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runId = await store.CreateRunAsync(projectId, null, "prototype-tdd-red");
        (await store.TryAcquireRunnerLockAsync(projectId, runId)).Should().BeTrue();
        var service = new ArtifactReadbackService(store, options);

        var run = await service.GetRunAsync(runId);
        var projectRuns = await service.GetProjectRunsAsync(projectId);

        run!.Status.Should().Be("queued");
        projectRuns!.Runs.Should().ContainSingle(r => r.RunId == runId);
    }

    [Fact]
    public void ReadProjectHealth_ReturnsHtmlAndJson()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        Write(repoRoot.Path, "logs/ci/project-health/latest.html", "<html>health</html>");
        Write(repoRoot.Path, "logs/ci/project-health/latest.json", "{\"status\":\"ok\"}");
        var service = new ArtifactReadbackService(new PhaseAMetadataStore(database.ConnectionString, options), options);

        var html = service.ReadProjectHealth("logs/ci/project-health/latest.html");
        var json = service.ReadProjectHealth("logs/ci/project-health/latest.json");

        html!.Content.Should().Contain("health");
        html.ContentType.Should().Be("text/html; charset=utf-8");
        json!.Content.Should().Contain("\"status\"");
    }

    [Fact]
    public async Task ReadArtifactAsync_RejectsEscapingRelativePath()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runId = await store.CreateRunAsync(projectId, null, "readback-test");
        await store.AddArtifactAsync(new ArtifactCreationCommand(runId, projectId, "bad", "../outside.txt", "Bad artifact"));
        var artifactId = (await store.ListArtifactsForRunAsync(runId))[0].ArtifactId;
        var service = new ArtifactReadbackService(store, options);

        var act = async () => await service.ReadArtifactAsync(artifactId);

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    private static async Task<PhaseAMetadataStore> CreateStoreAsync(string connectionString, PhaseAPlatformOptions options)
    {
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var store = new PhaseAMetadataStore(connectionString, options);
        await store.EnsureSingleAdminAsync();
        return store;
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options)
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        return result.ProjectId!;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot
        });
    }

    private static void Write(string root, string relativePath, string content)
    {
        var path = Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
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
