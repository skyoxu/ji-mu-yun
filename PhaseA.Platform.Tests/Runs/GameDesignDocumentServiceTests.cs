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
        runner.Commands[0].StandardInput.Should().Contain("gdd-outline.generated.json");
        runner.Commands[0].StandardInput.Should().Contain("PrototypeRoot");
        runner.Commands[0].StandardInput.Should().Contain("HudView");
        runner.Commands[0].StandardInput.Should().Contain("not ECS");
        var outlineJson = await File.ReadAllTextAsync(Path.Combine(project!.RepoPath, "docs", "gdd", "gdd-outline.json"));
        outlineJson.Should().NotContain("???");
        outline!.Title.Should().Be("演示策划大纲");
        outline.Sections.Should().ContainSingle(item => item.Id == "core-loop" && item.Title == "核心循环");
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);
        artifacts.Should().Contain(item => item.ArtifactType == "game-design-gdd" && item.RelativePath == "docs/gdd/GDD.md");
        artifacts.Should().Contain(item => item.ArtifactType == "game-design-gdd-outline" && item.RelativePath == "docs/gdd/gdd-outline.json");
        artifacts.Should().Contain(item => item.ArtifactType == "game-design-gdd-outline-draft" && item.RelativePath.EndsWith("gdd-outline.generated.json", StringComparison.Ordinal));
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
    public async Task CreateAsync_WhenUserCancelsRun_ShouldReturnCancelInsteadOfTimeout()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new UserCancelHostedProcessRunner(store, accountId);
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

        result.Status.Should().Be("cancel");
        result.FailureCode.Should().Be("cancel");
        result.Summary.Should().Be("\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u5df2\u53d6\u6d88\u3002");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("cancel");
        run.ExitCode.Should().Be(499);
        run.ProgressStep.Should().NotBe("failed");
        run.ProgressSubstep.Should().NotBe("timeout");
    }

    [Fact]
    public async Task CreateAsync_WhenGeneratedOutlineIsGarbled_ShouldFailInsteadOfPublishingQuestionMarks()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner
        {
            OutlineMode = FakeOutlineMode.GarbledDraft
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
        result.FailureCode.Should().Be("gdd_outline_garbled_text");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ProgressSubstep.Should().Be("gdd_outline_garbled_text");
        var project = await store.GetProjectSnapshotAsync(projectId);
        File.Exists(Path.Combine(project!.RepoPath, "docs", "gdd", "GDD.md")).Should().BeFalse();
    }

    [Fact]
    public async Task CreateAsync_WhenGeneratedOutlineIsTooThin_ShouldFailInsteadOfPublishingPlaceholder()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner
        {
            OutlineMode = FakeOutlineMode.ThinDraft
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
        result.FailureCode.Should().Be("gdd_outline_too_thin");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ProgressSubstep.Should().Be("gdd_outline_too_thin");
        var project = await store.GetProjectSnapshotAsync(projectId);
        File.Exists(Path.Combine(project!.RepoPath, "docs", "gdd", "GDD.md")).Should().BeFalse();
    }

    [Fact]
    public async Task CreateAsync_WhenGeneratedOutlineUsesPlaceholderFields_ShouldFail()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner
        {
            OutlineMode = FakeOutlineMode.PlaceholderDraft
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
        result.FailureCode.Should().Be("gdd_outline_placeholder");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ProgressSubstep.Should().Be("gdd_outline_placeholder");
        var project = await store.GetProjectSnapshotAsync(projectId);
        File.Exists(Path.Combine(project!.RepoPath, "docs", "gdd", "GDD.md")).Should().BeFalse();
    }

    [Fact]
    public async Task CreateAsync_WhenGeneratedOutlineUsesGenericTitleWithRealSections_ShouldSucceed()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var accountId = account.AccountId;
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner
        {
            OutlineMode = FakeOutlineMode.GenericTitleRealDraft
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

        result.Status.Should().Be("succeeded");
        var outline = await service.ReadOutlineAsync(accountId, projectId);
        outline!.Title.Should().Be("游戏策划大纲");
        outline.Sections.Should().Contain(section => section.Id == "core-loop" && section.Skeleton.Contains("重复行动", StringComparison.Ordinal));
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

    [Fact]
    public async Task ReadOutlineAsync_WhenExistingOutlineIsGarbled_ShouldReturnSafeEmptyOutline()
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
              "title": "????????????",
              "summary": "????????????????????",
              "sections": [
                { "id": "core-loop", "title": "????", "skeleton": "????????????????", "content": "" }
              ]
            }
            """);
        var service = new GameDesignDocumentService(
            store,
            options,
            new FakeHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(5));

        var result = await service.ReadOutlineAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Title.Should().Be("策划大纲需要重新生成");
        result.Summary.Should().Contain("连续问号乱码");
        result.Sections.Should().BeEmpty();
    }

    [Fact]
    public async Task ExportOutlineMarkdownAsync_WhenExistingOutlineIsGarbled_ShouldFail()
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
              "title": "????????????",
              "summary": "????????????????????",
              "sections": [
                { "id": "core-loop", "title": "????", "skeleton": "????????????????", "content": "" }
              ]
            }
            """);
        var service = new GameDesignDocumentService(
            store,
            options,
            new FakeHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(5));

        var action = async () => await service.ExportOutlineMarkdownAsync(accountId, projectId);

        await action.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("GDD outline contains garbled question-mark text.");
    }

    [Fact]
    public async Task DeleteOutlineAsync_ShouldRemoveOutlineAndExportedGdd()
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
        await File.WriteAllTextAsync(Path.Combine(gddDir, "gdd-outline.json"), """{"title":"Outline","summary":"Summary","sections":[]}""");
        await File.WriteAllTextAsync(Path.Combine(gddDir, "GDD.md"), "# Old GDD");
        var service = new GameDesignDocumentService(
            store,
            options,
            new FakeHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(5));

        var result = await service.DeleteOutlineAsync(accountId, projectId);

        result!.Status.Should().Be("deleted");
        result.DeletedPaths.Should().Contain("docs/gdd/gdd-outline.json");
        result.DeletedPaths.Should().Contain("docs/gdd/GDD.md");
        File.Exists(Path.Combine(gddDir, "gdd-outline.json")).Should().BeFalse();
        File.Exists(Path.Combine(gddDir, "GDD.md")).Should().BeFalse();
        (await service.ReadOutlineAsync(accountId, projectId)).Should().BeNull();
        (await service.ReadAsync(accountId, projectId)).Should().BeNull();
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
        public FakeOutlineMode OutlineMode { get; init; } = FakeOutlineMode.ValidDraft;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (ShouldWriteOutline)
            {
                var draftRelativePath = ExtractDraftRelativePath(command.StandardInput ?? "");
                var outlinePath = Path.Combine(command.WorkingDirectory, draftRelativePath.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(Path.GetDirectoryName(outlinePath)!);
                File.WriteAllText(outlinePath, OutlineMode switch
                {
                    FakeOutlineMode.GarbledDraft => """
                        {
                          "title": "????????????",
                          "summary": "????????????????????",
                          "sections": [
                            { "id": "core-loop", "title": "????", "skeleton": "????????????????", "content": "" }
                          ]
                        }
                        """,
                    FakeOutlineMode.ThinDraft => """
                        {
                          "title": "\u8fc7\u8584\u7b56\u5212\u5927\u7eb2",
                          "summary": "\u53ea\u6709\u4e00\u4e2a\u6761\u76ee\u3002",
                          "sections": [
                            { "id": "core-loop", "title": "\u6838\u5fc3\u5faa\u73af", "skeleton": "\u5b9a\u4e49\u73a9\u5bb6\u91cd\u590d\u884c\u52a8\u3002", "content": "" }
                          ]
                        }
                        """,
                    FakeOutlineMode.PlaceholderDraft => """
                        {
                          "title": "",
                          "summary": "",
                          "sections": [
                            { "id": "vision", "title": "", "skeleton": "", "content": "" },
                            { "id": "target-player", "title": "", "skeleton": "", "content": "" },
                            { "id": "core-loop", "title": "", "skeleton": "", "content": "" },
                            { "id": "progression", "title": "", "skeleton": "", "content": "" },
                            { "id": "ui-hud", "title": "", "skeleton": "", "content": "" },
                            { "id": "acceptance", "title": "", "skeleton": "", "content": "" }
                          ]
                        }
                        """,
                    FakeOutlineMode.GenericTitleRealDraft => """
                        {
                          "title": "\u6e38\u620f\u7b56\u5212\u5927\u7eb2",
                          "summary": "\u805a\u7126\u4e00\u4e2a\u53ef\u73a9\u7684\u9996\u8f6e\u539f\u578b\u5faa\u73af\u3002",
                          "sections": [
                            { "id": "core-loop", "title": "\u6838\u5fc3\u5faa\u73af", "skeleton": "\u5b9a\u4e49\u73a9\u5bb6\u91cd\u590d\u884c\u52a8\u3001\u53cd\u9988\u548c\u80dc\u5229\u6761\u4ef6\u3002", "content": "" },
                            { "id": "vision", "title": "\u4f53\u9a8c\u613f\u666f", "skeleton": "\u8bf4\u660e\u6e38\u620f\u60c5\u7eea\u548c\u9996\u5c4f\u4f53\u9a8c\u3002", "content": "" },
                            { "id": "target-player", "title": "\u76ee\u6807\u73a9\u5bb6", "skeleton": "\u63cf\u8ff0\u73a9\u5bb6\u7c7b\u578b\u548c\u9884\u671f\u8282\u594f\u3002", "content": "" },
                            { "id": "progression", "title": "\u6210\u957f\u4e0e\u5956\u52b1", "skeleton": "\u63cf\u8ff0\u80fd\u529b\u6210\u957f\u548c\u77ed\u671f\u5956\u52b1\u3002", "content": "" },
                            { "id": "ui-hud", "title": "\u754c\u9762\u548cHUD", "skeleton": "\u5217\u51fa\u9996\u8f6e\u539f\u578b\u9700\u8981\u7684\u4fe1\u606f\u5c42\u7ea7\u3002", "content": "" },
                            { "id": "acceptance", "title": "\u539f\u578b\u9a8c\u6536", "skeleton": "\u5b9a\u4e49\u53ef\u8fd0\u884c\u3001\u53ef\u73a9\u548c\u53ef\u9a8c\u6536\u6807\u51c6\u3002", "content": "" }
                          ]
                        }
                        """,
                    _ => """
                        {
                          "title": "\u6f14\u793a\u7b56\u5212\u5927\u7eb2",
                          "summary": "\u7531 BMAD \u751f\u6210\u3002",
                          "sections": [
                            { "id": "core-loop", "title": "\u6838\u5fc3\u5faa\u73af", "skeleton": "\u5b9a\u4e49\u73a9\u5bb6\u91cd\u590d\u884c\u52a8\u3002", "content": "" },
                            { "id": "vision", "title": "\u613f\u666f", "skeleton": "\u5b9a\u4e49\u6e38\u620f\u4f53\u9a8c\u76ee\u6807\u3002", "content": "" },
                            { "id": "target-player", "title": "\u76ee\u6807\u73a9\u5bb6", "skeleton": "\u63cf\u8ff0\u6838\u5fc3\u73a9\u5bb6\u3002", "content": "" },
                            { "id": "progression", "title": "\u6210\u957f", "skeleton": "\u63cf\u8ff0\u6210\u957f\u548c\u5956\u52b1\u3002", "content": "" },
                            { "id": "ui-hud", "title": "\u754c\u9762", "skeleton": "\u63cf\u8ff0 UI \u548c HUD\u3002", "content": "" },
                            { "id": "acceptance", "title": "\u9a8c\u6536", "skeleton": "\u63cf\u8ff0\u539f\u578b\u9a8c\u6536\u6807\u51c6\u3002", "content": "" }
                          ]
                        }
                        """
                });
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "GDD created.");
            return Task.FromResult(new HostedProcessResult(ExitCode, "codex stdout", ExitCode == 0 ? "" : "codex failed"));
        }

        private static string ExtractDraftRelativePath(string prompt)
        {
            var marker = "logs/phase-a-gdd/";
            var index = prompt.IndexOf(marker, StringComparison.Ordinal);
            if (index < 0)
            {
                return "logs/phase-a-gdd/test/gdd-outline.generated.json";
            }

            var end = prompt.IndexOfAny(['\r', '\n'], index);
            return (end < 0 ? prompt[index..] : prompt[index..end]).Trim();
        }
    }

    private enum FakeOutlineMode
    {
        ValidDraft,
        GarbledDraft,
        ThinDraft,
        PlaceholderDraft,
        GenericTitleRealDraft
    }

    private sealed class UserCancelHostedProcessRunner : IHostedProcessRunner
    {
        private readonly PhaseAMetadataStore _store;
        private readonly string _accountId;

        public UserCancelHostedProcessRunner(PhaseAMetadataStore store, string accountId)
        {
            _store = store;
            _accountId = accountId;
        }

        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            command.RunId.Should().NotBeNullOrWhiteSpace();
            await _store.CancelRunAsync(_accountId, command.RunId!, CancellationToken.None);
            throw new OperationCanceledException(cancellationToken);
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
