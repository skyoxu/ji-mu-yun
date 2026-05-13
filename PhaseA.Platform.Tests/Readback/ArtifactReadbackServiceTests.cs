using FluentAssertions;
using System.IO.Compression;
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
        var project = await store.GetProjectSnapshotAsync(projectId);
        var runId = await store.CreateRunAsync(projectId, null, "prototype-tdd-green");
        await store.CompleteRunAsync(runId, "succeeded", 0, "stdout", "", "{}", CancellationToken.None);
        Write(project!.RepoPath, "logs/ci/sample-artifact.txt", "artifact text");
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
    public async Task Readback_ReturnsAccountActiveRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        await store.MarkRunStartedAsync(runId);
        await store.UpdateRunProgressAsync(runId, "analyzing", "", "正在分析草稿。");
        var service = new ArtifactReadbackService(store, options);

        var active = await service.GetActiveRunAsync(project.AccountId);

        active.Busy.Should().BeTrue();
        active.RunId.Should().Be(runId);
        active.RunType.Should().Be("prototype-draft-analysis");
        active.ProgressLabel.Should().Be("正在分析草稿。");
    }

    [Fact]
    public async Task ReadArtifactAsync_ResolvesArtifactsInsideOwningProjectRepo()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectOne = await CreateProjectAsync(store, options, accountId, "Game One");
        await store.SetProjectBootstrapStatusAsync(projectOne, "succeeded", null);
        var projectTwo = await CreateProjectAsync(store, options, accountId, "Game Two");
        var one = await store.GetProjectSnapshotAsync(projectOne);
        var two = await store.GetProjectSnapshotAsync(projectTwo);
        var runOne = await store.CreateRunAsync(projectOne, one!.WorkspaceId, "artifact-test");
        var runTwo = await store.CreateRunAsync(projectTwo, two!.WorkspaceId, "artifact-test");
        Write(one.RepoPath, "logs/ci/shared.txt", "project one");
        Write(two.RepoPath, "logs/ci/shared.txt", "project two");
        await store.AddArtifactAsync(new ArtifactCreationCommand(runOne, projectOne, "sample", "logs/ci/shared.txt", "Project one artifact"));
        await store.AddArtifactAsync(new ArtifactCreationCommand(runTwo, projectTwo, "sample", "logs/ci/shared.txt", "Project two artifact"));
        var service = new ArtifactReadbackService(store, options);

        var artifactOne = await service.ReadArtifactAsync((await store.ListArtifactsForRunAsync(runOne))[0].ArtifactId);
        var artifactTwo = await service.ReadArtifactAsync((await store.ListArtifactsForRunAsync(runTwo))[0].ArtifactId);

        one.RepoPath.Should().NotBe(two.RepoPath);
        artifactOne!.Content.Should().Be("project one");
        artifactTwo!.Content.Should().Be("project two");
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
    public void ReadProjectHealthSummary_ExtractsCurrentProjectCardFields()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        Write(repoRoot.Path, "logs/ci/project-health/latest.json", """
            {
              "status": "warn",
              "generated_at": "2026-05-11T15:17:27+08:00",
              "records": [
                { "kind": "detect-project-stage", "status": "warn", "stage": "triplet-missing", "summary": "real task triplet is missing" },
                { "kind": "doctor-project", "status": "warn", "summary": "doctor checks: fail=0 warn=1 ok=10" },
                { "kind": "check-directory-boundaries", "status": "ok", "summary": "boundary checks: fail=0 warn=0" }
              ],
              "report_catalog_summary": { "total_json": 12, "invalid_json": 1 },
              "active_task_summary": { "total": 2 }
            }
            """);
        Write(repoRoot.Path, "logs/ci/project-health/project-health-scan.latest.json", """
            {
              "kind": "project-health-scan",
              "status": "warn",
              "results": [
                {
                  "kind": "detect-project-stage",
                  "stage": "triplet-missing",
                  "signals": { "overlay_indexes": 3, "contract_files": 4, "unit_test_files": 5 }
                },
                {
                  "kind": "doctor-project",
                  "counts": { "fail": 0, "warn": 1, "ok": 10 },
                  "checks": [
                    { "id": "task-triplet-real", "status": "warn", "recommendation": "create real task triplet" }
                  ]
                },
                {
                  "kind": "check-directory-boundaries",
                  "violations": [],
                  "warnings": [ { "id": "sample" } ]
                }
              ]
            }
            """);
        var service = new ArtifactReadbackService(new PhaseAMetadataStore(database.ConnectionString, options), options);

        var summary = service.ReadProjectHealthSummary();

        summary.Should().NotBeNull();
        summary!.Status.Should().Be("warn");
        summary.Stage.Should().Be("triplet-missing");
        summary.DoctorWarnCount.Should().Be(1);
        summary.DoctorOkCount.Should().Be(10);
        summary.BoundaryStatus.Should().Be("ok");
        summary.BoundaryWarnCount.Should().Be(1);
        summary.ActiveTaskTotal.Should().Be(2);
        summary.JsonReportTotal.Should().Be(12);
        summary.InvalidJsonReportTotal.Should().Be(1);
        summary.OverlayIndexCount.Should().Be(3);
        summary.ContractFileCount.Should().Be(4);
        summary.UnitTestFileCount.Should().Be(5);
        summary.TopRecommendation.Should().Be("create real task triplet");
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

    [Fact]
    public async Task ProjectPackage_CreatesVersionedZip_WithProjectFilesOnly()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var prototypeRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(prototypeRunId, "succeeded", 0, "prototype complete", "", "{}", CancellationToken.None);
        Write(project.RepoPath, "Game.Core/Game.Core.csproj", "<Project />");
        Write(project.RepoPath, "Game.Core/Domain/Combat.cs", "public sealed class Combat {}");
        Write(project.RepoPath, "Game.Godot/Scenes/Main.tscn", "[gd_scene]");
        Write(project.RepoPath, "docs/prototypes/demo.md", "prototype");
        Write(project.RepoPath, "PhaseA.Platform/Program.cs", "platform");
        Write(project.RepoPath, "scripts/python/dev_cli.py", "script");
        Write(project.RepoPath, "logs/ci/run.log", "log");
        Write(project.RepoPath, ".agents/skills/demo/SKILL.md", "skill");
        var service = new ProjectPackageService(store, options);

        var first = await service.CreatePackageAsync(accountId, projectId);
        var second = await service.CreatePackageAsync(accountId, projectId);
        var download = await service.ReadPackageAsync(accountId, projectId, first.FileName);
        var packages = await service.ListPackagesAsync(accountId, projectId);

        first.Status.Should().Be("succeeded");
        first.Version.Should().MatchRegex(@"^v0\.1\.\d{8}\.001$");
        first.FileName.Should().EndWith($"{first.Version}.zip");
        second.Version.Should().MatchRegex(@"^v0\.1\.\d{8}\.002$");
        packages!.CanCreatePackage.Should().BeTrue();
        packages.Packages.Should().HaveCount(2);
        packages.Packages[0].Version.Should().Be(second.Version);
        packages.Packages[1].Version.Should().Be(first.Version);
        download.Should().NotBeNull();
        download!.FileName.Should().Be(first.FileName);
        var names = ZipEntryNames(download.Content);
        names.Should().Contain("PACKAGE-MANIFEST.json");
        names.Should().Contain("Game.Core/Domain/Combat.cs");
        names.Should().Contain("Game.Godot/Scenes/Main.tscn");
        names.Should().Contain("docs/prototypes/demo.md");
        names.Should().NotContain(name => name.StartsWith("PhaseA.Platform/", StringComparison.OrdinalIgnoreCase));
        names.Should().NotContain(name => name.StartsWith("scripts/", StringComparison.OrdinalIgnoreCase));
        names.Should().NotContain(name => name.StartsWith("logs/", StringComparison.OrdinalIgnoreCase));
        names.Should().NotContain(name => name.StartsWith(".agents/", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task ProjectPackage_BlocksBeforePrototypeSucceeded()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var service = new ProjectPackageService(store, options);

        var created = await service.CreatePackageAsync(accountId, projectId);
        var packages = await service.ListPackagesAsync(accountId, projectId);

        created.Status.Should().Be("prototype_not_created");
        packages!.CanCreatePackage.Should().BeFalse();
        packages.DisabledReason.Should().Be("prototype_not_created");
    }

    [Fact]
    public async Task ProjectPackage_BlocksWhileProjectHasActiveRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var activeRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(activeRunId);
        var service = new ProjectPackageService(store, options);

        var result = await service.CreatePackageAsync(accountId, projectId);

        result.Status.Should().Be("project_busy");
        result.FailureCode.Should().Be("project_busy");
    }

    [Fact]
    public void ProjectPackageDownloadTicketService_CreatesBoundExpiringTicket()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(Path.GetTempPath(), "phase-a-ticket-test.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = Directory.GetCurrentDirectory(),
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath(),
            ["PHASEA_ADMIN_TOKEN_HASH"] = "test-secret"
        });
        var service = new ProjectPackageDownloadTicketService(options);

        var ticket = service.CreateTicket("project-a", "package.zip");

        service.IsValid(ticket, "project-a", "package.zip").Should().BeTrue();
        service.IsValid(ticket, "project-b", "package.zip").Should().BeFalse();
        service.IsValid(ticket, "project-a", "other.zip").Should().BeFalse();
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
        return await CreateProjectAsync(store, options, accountId, "Demo Game");
    }

    private static async Task<string> CreateProjectAsync(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        string accountId,
        string gameName)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, gameName, "manual", null, null, null, null));
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

    private static IReadOnlyList<string> ZipEntryNames(byte[] content)
    {
        using var memory = new MemoryStream(content);
        using var archive = new ZipArchive(memory, ZipArchiveMode.Read);
        return archive.Entries.Select(entry => entry.FullName).ToArray();
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
