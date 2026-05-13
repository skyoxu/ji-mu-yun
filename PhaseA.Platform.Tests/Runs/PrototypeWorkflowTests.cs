using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeWorkflowTests
{
    [Fact]
    public void MissingRequiredFields_TracksPrototypeLaneIntakeFields()
    {
        var request = new PrototypeWorkflowRequest(null, null, null, null, null, null, null, null);

        var missing = PrototypeWorkflowValidation.MissingRequiredFields(request);

        missing.Should().Equal(
            "slug",
            "hypothesis",
            "core_player_fantasy",
            "minimum_playable_loop",
            "success_criteria",
            "game_feature",
            "core_gameplay_loop",
            "win_fail_conditions");
    }

    [Fact]
    public void CommandBuilder_DelegatesToRunPrototypeWorkflow()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeWorkflowCommandBuilder(options);

        var command = builder.Build(ValidRequest(confirm: true), "docs/prototypes/2026-05-11-demo.md", @"C:\project-repo");

        command.WorkingDirectory.Should().Be(@"C:\project-repo");
        command.Arguments.Should().ContainInOrder(
            "-3",
            "scripts/python/dev_cli.py",
            "run-prototype-workflow",
            "--prototype-file",
            "docs/prototypes/2026-05-11-demo.md",
            "--confirm",
            "--godot-bin",
            @"C:\Godot\Godot.exe");
        command.Environment["GODOT_BIN"].Should().Be(@"C:\Godot\Godot.exe");
        command.Environment["PHASEA_CODEX_DEFAULT_MODEL"].Should().Be("gpt-5.5");
        command.Environment["PHASEA_CODEX_REASONING_EFFORT"].Should().Be("high");
    }

    [Fact]
    public async Task RunAsync_WritesPrototypeRecord_RunsRouter_AndIndexesPrototypeArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId, ValidRequest(confirm: false));

        result.Status.Should().Be("succeeded");
        result.PrototypeRecordPath.Should().StartWith("docs/prototypes/");
        var project = await store.GetProjectSnapshotAsync(projectId);
        File.Exists(Path.Combine(project!.RepoPath, result.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar))).Should().BeTrue();
        runner.Commands.Should().HaveCount(2);
        runner.Commands[0].WorkingDirectory.Should().Be(project.RepoPath);
        runner.Commands[0].Arguments.Should().Contain("run-prototype-workflow");
        runner.Commands[1].WorkingDirectory.Should().Be(project.RepoPath);
        runner.Commands[1].Arguments.Should().Contain("scripts/python/smoke_headless.py");
        runner.Commands[1].Arguments.Should().Contain(["--strict"]);
        result.Artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-record",
            "prototype-sidecar-json",
            "active-prototype-json"
        ]);

        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.RunType.Should().Be("prototype-7day-playable");
        run.Status.Should().Be("succeeded");
        run.ProgressStep.Should().Be("succeeded");
        run.EvidenceJson.Should().Contain("prototype_artifacts");
        run.EvidenceJson.Should().Contain("godot_smoke");
        run.StdoutText.Should().Contain("SMOKE PASS");
    }

    [Fact]
    public async Task GetProgressAsync_ReturnsLatestPrototypeWorkflowProgress()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var idle = await service.GetProgressAsync(projectId);
        var result = await service.RunAsync(projectId, ValidRequest(confirm: false));
        var finished = await service.GetProgressAsync(projectId);

        idle.Status.Should().Be("idle");
        finished.Status.Should().Be("succeeded");
        finished.Step.Should().Be("succeeded");
        finished.RunId.Should().Be(result.RunId);
    }

    [Fact]
    public async Task QueueAsync_BlocksWhenProjectRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var lockRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        (await store.TryAcquireRunnerLockAsync(projectId, lockRunId)).Should().BeTrue();
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.QueueAsync(projectId, ValidRequest(confirm: true));

        result.Status.Should().Be("project_busy");
        result.ExitCode.Should().Be(423);
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RepairAsync_QueuesRepairFromLatestFailedPrototypeRecord()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var failedRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            1,
            "",
            "first failure",
            "{\"prototype_record\":\"docs/prototypes/2026-05-12-demo-prototype.md\",\"slug\":\"demo-prototype\"}");
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(projectId, new PrototypeRepairRequest("gpt-5.4"));
        await WaitForCommandsAsync(runner, 2);
        var repairRun = await WaitForRunStatusAsync(store, result.RunId, "succeeded", "succeeded");

        result.Status.Should().Be("queued");
        result.PrototypeRecordPath.Should().Be("docs/prototypes/2026-05-12-demo-prototype.md");
        runner.Commands[0].Arguments.Should().Contain("run-prototype-workflow");
        runner.Commands[0].Arguments.Should().Contain("docs/prototypes/2026-05-12-demo-prototype.md");
        runner.Commands[0].Environment["PHASEA_CODEX_DEFAULT_MODEL"].Should().Be("gpt-5.4");
        repairRun!.Status.Should().Be("succeeded");
        repairRun.EvidenceJson.Should().Contain("\"repair\":true");
    }

    [Fact]
    public async Task RepairAsync_RequiresLatestPrototypeRunToBeFailed()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var failedRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(failedRunId);
        await store.CompleteRunAsync(
            failedRunId,
            "failed",
            1,
            "",
            "first failure",
            "{\"prototype_record\":\"docs/prototypes/2026-05-12-demo-prototype.md\",\"slug\":\"demo-prototype\"}");
        var succeededRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(succeededRunId);
        await store.CompleteRunAsync(
            succeededRunId,
            "succeeded",
            0,
            "ok",
            "",
            "{\"prototype_record\":\"docs/prototypes/2026-05-12-demo-prototype.md\",\"slug\":\"demo-prototype\"}");
        var runner = new FakeHostedProcessRunner();
        var service = Service(store, options, runner);

        var result = await service.RepairAsync(projectId, new PrototypeRepairRequest("gpt-5.4"));

        result.Status.Should().Be("prototype_repair_not_available");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_RequiresLlmBinding_ForCodexScoring()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var service = Service(store, options, new FakeHostedProcessRunner());

        var result = await service.RunAsync(projectId, ValidRequest() with { ScoreEngine = "codex" });

        result.Status.Should().Be("llm_binding_required");
        result.ExitCode.Should().Be(402);
    }

    [Fact]
    public async Task RunAsync_RecordsLlmAudit_WhenCodexScoringIsBoundAndAllowed()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var accountId = (await store.GetProjectSnapshotAsync(projectId))!.AccountId;
        await new LlmBindingService(store, options).BindAsync(accountId, new LlmBindingRequest(
            "new-api",
            "https://new-api.example.com/v1",
            "new-api-user-1",
            "host-secret:new-api-user-1"));
        var service = Service(store, options, new FakeHostedProcessRunner());

        var result = await service.RunAsync(projectId, ValidRequest() with { ScoreEngine = "codex" });
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        run!.LlmGateway.Should().Be("new-api");
        run.LlmModel.Should().Be("codex");
        run.LlmCostJson.Should().Contain("estimated_cost_cny");
    }

    [Fact]
    public void ProjectRuleCatalog_DoesNotExposeChapter3ThroughChapter7()
    {
        var rule = new ProjectRuleCatalog().Find(ProjectRuleCatalog.DefaultRuleId)!;

        rule.AllowedWorkflows.Should().NotContain(["chapter3", "chapter4", "chapter5", "chapter6", "chapter7"]);
    }

    private static PrototypeWorkflowRequest ValidRequest(bool confirm = false)
    {
        return new PrototypeWorkflowRequest(
            Slug: "demo-prototype",
            Hypothesis: "A tiny loop can prove the combat fantasy.",
            CorePlayerFantasy: "Player feels tactical pressure in one minute.",
            MinimumPlayableLoop: "Enter room, fight one enemy, win or fail.",
            SuccessCriteria: ["Player completes one loop.", "Outcome is clear."],
            GameFeature: "One-room tactical combat.",
            CoreGameplayLoop: "Move, choose action, resolve enemy response.",
            WinFailConditions: "Win by defeating enemy; fail when health reaches zero.",
            Confirm: confirm);
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

    private static PrototypeWorkflowService Service(PhaseAMetadataStore store, PhaseAPlatformOptions options, IHostedProcessRunner runner)
    {
        return new PrototypeWorkflowService(
            store,
            options,
            runner,
            new PrototypeRecordWriter(options),
            new PrototypeWorkflowCommandBuilder(options),
            new PrototypeArtifactIndexer(),
            new LlmBindingService(store, options),
            new LlmStopLossService(store, options));
    }

    private static async Task WaitForCommandsAsync(FakeHostedProcessRunner runner, int expectedCount)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        while (runner.Commands.Count < expectedCount && DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(50);
        }

        runner.Commands.Should().HaveCount(expectedCount);
    }

    private static async Task<RunSnapshot> WaitForRunStatusAsync(
        PhaseAMetadataStore store,
        string runId,
        string expectedStatus,
        string? expectedProgressStep = null)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        RunSnapshot? run = null;
        while (DateTimeOffset.UtcNow < deadline)
        {
            run = await store.GetRunSnapshotAsync(runId);
            if (run?.Status == expectedStatus &&
                (expectedProgressStep is null || run.ProgressStep == expectedProgressStep))
            {
                return run;
            }

            await Task.Delay(50);
        }

        run.Should().NotBeNull();
        run!.Status.Should().Be(expectedStatus);
        if (expectedProgressStep is not null)
        {
            run.ProgressStep.Should().Be(expectedProgressStep);
        }

        return run;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (marker)\n", ""));
            }

            Write("docs/prototypes/demo-prototype.prototype.json", "{}");
            Write("logs/ci/active-prototypes/demo-prototype.active.json", "{}");
            Write("logs/ci/project-health/latest.html", "<html></html>");
            Write("logs/ci/project-health/latest.json", "{}");
            return Task.FromResult(new HostedProcessResult(0, "prototype workflow ok\n", ""));
        }

        private void Write(string relativePath, string text)
        {
            var path = Path.Combine(Commands[^1].WorkingDirectory, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, text);
        }
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
