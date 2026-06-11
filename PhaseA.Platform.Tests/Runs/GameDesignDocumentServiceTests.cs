using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class GameDesignDocumentServiceTests
{
    [Fact]
    public async Task CreateAsync_ShouldWriteGddWithBmadContextAndArtifact()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.AddProjectChatMessageAsync(accountId, projectId, "user", "I want a cozy RPG loop.", null, 50);
        await store.AddProjectChatMessageAsync(accountId, projectId, "assistant", "Focus on exploration and battles.", null, 50);
        await store.UpsertProjectChatMemoryAsync(accountId, projectId, "The project is a cozy RPG prototype.", "session-1");
        var runner = new FakeHostedProcessRunner();
        var service = new GameDesignDocumentService(
            store,
            options,
            runner,
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(5));

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new GameDesignDocumentRequest(
                "Create a complete GDD.",
                "gpt-5.4",
                [new TextAttachment("reference.txt", "Reference file says the village hub matters.")]));

        result.Status.Should().Be("succeeded");
        result.RelativePath.Should().Be("docs/gdd/GDD.md");
        var project = await store.GetProjectSnapshotAsync(projectId);
        File.Exists(Path.Combine(project!.RepoPath, "docs", "gdd", "gdd-outline.json")).Should().BeTrue();
        File.Exists(Path.Combine(project!.RepoPath, "docs", "gdd", "GDD.md")).Should().BeTrue();
        var outline = await service.ReadOutlineAsync(accountId, projectId);
        outline!.Sections.Should().ContainSingle(item => item.Id == "core-loop");
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].Arguments.Should().Contain("--sandbox");
        runner.Commands[0].Arguments.Should().Contain("workspace-write");
        runner.Commands[0].StandardInput.Should().Contain("$bmad-agent-game-designer");
        runner.Commands[0].StandardInput.Should().Contain("I want a cozy RPG loop.");
        runner.Commands[0].StandardInput.Should().Contain("Reference file says the village hub matters.");
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);
        artifacts.Should().Contain(item => item.ArtifactType == "game-design-gdd" && item.RelativePath == "docs/gdd/GDD.md");
        artifacts.Should().Contain(item => item.ArtifactType == "game-design-gdd-outline" && item.RelativePath == "docs/gdd/gdd-outline.json");
    }

    [Fact]
    public async Task CreateAsync_WhenCodexFails_ShouldNotReportSuccessFromStaleOutline()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var gddDir = Path.Combine(project!.RepoPath, "docs", "gdd");
        Directory.CreateDirectory(gddDir);
        File.WriteAllText(Path.Combine(gddDir, "gdd-outline.json"), """
            {
              "title": "Stale Outline",
              "summary": "This file existed before the failed run.",
              "sections": [
                { "id": "stale", "title": "Stale", "skeleton": "Old.", "content": "" }
              ]
            }
            """);
        var runner = new FakeHostedProcessRunner
        {
            ExitCode = 17,
            ShouldWriteOutline = false
        };
        var service = new GameDesignDocumentService(
            store,
            options,
            runner,
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(5));

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new GameDesignDocumentRequest("Create a complete GDD.", "gpt-5.4", []));

        result.Status.Should().Be("failed");
        result.FailureCode.Should().Be("codex_failed");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(17);
    }

    [Fact]
    public async Task ExportOutlineMarkdownAsync_ShouldWriteGddMarkdownFromOutline()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var gddDir = Path.Combine(project!.RepoPath, "docs", "gdd");
        Directory.CreateDirectory(gddDir);
        await File.WriteAllTextAsync(Path.Combine(gddDir, "gdd-outline.json"), """
            {
              "title": "Demo Outline",
              "summary": "A compact game plan.",
              "sections": [
                { "id": "core-loop", "title": "Core Loop", "skeleton": "Define loop.", "content": "Explore, fight, upgrade." }
              ]
            }
            """);
        var service = new GameDesignDocumentService(
            store,
            options,
            new FakeHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(5));

        var result = await service.ExportOutlineMarkdownAsync(accountId, projectId);

        result!.RelativePath.Should().Be("docs/gdd/GDD.md");
        var markdown = await File.ReadAllTextAsync(Path.Combine(gddDir, "GDD.md"));
        markdown.Should().Contain("# Demo Outline");
        markdown.Should().Contain("## Core Loop");
        markdown.Should().Contain("Explore, fight, upgrade.");
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
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

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        public int ExitCode { get; init; }
        public bool ShouldWriteOutline { get; init; } = true;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var gddDir = Path.Combine(command.WorkingDirectory, "docs", "gdd");
            Directory.CreateDirectory(gddDir);
            if (ShouldWriteOutline)
            {
                var outlinePath = Path.Combine(gddDir, "gdd-outline.json");
                File.WriteAllText(outlinePath, """
                    {
                      "title": "Demo GDD Outline",
                      "summary": "Generated by BMAD.",
                      "sections": [
                        { "id": "core-loop", "title": "Core Loop", "skeleton": "Define loop.", "content": "" }
                      ]
                    }
                    """);
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "GDD created.");
            return Task.FromResult(new HostedProcessResult(ExitCode, "codex stdout", ExitCode == 0 ? "" : "codex failed"));
        }
    }

    private sealed class TempWorkspace : IDisposable
    {
        public TempWorkspace()
        {
            Root = Path.Combine(Path.GetTempPath(), $"phase-a-gdd-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Root);
        }

        public string Root { get; }

        public void Dispose()
        {
            if (Directory.Exists(Root))
            {
                Directory.Delete(Root, recursive: true);
            }
        }
    }
}
