using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeQuickFixServiceTests
{
    [Fact]
    public async Task SubmitAsync_CreatesQuickFixRun_AndArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.AssistantMessage.Should().Contain("快速修复已完成");
        run!.RunType.Should().Be("prototype-quick-fix");
        run.Status.Should().Be("completed");
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].Arguments.Should().Contain(["exec", "--sandbox", "workspace-write", "-m", "gpt-5.4"]);
        runner.Commands[0].Arguments.Should().Contain(["-c", "model_reasoning_effort=\"low\""]);
        artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-quick-fix-submission",
            "prototype-quick-fix-result-log",
            "prototype-quick-fix-codex-output"
        ]);
    }

    [Fact]
    public async Task SubmitAsync_ReturnsTimeoutFailure_WhenRunnerDoesNotFinishInTime()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var runner = new TimeoutHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.AssistantMessage.Should().Contain("快速修复超时");
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
    }

    [Fact]
    public async Task SubmitAsync_ShouldCompleteEvenWhenCallerTokenIsCanceledAfterRunStarts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        using var callerCancellation = new CancellationTokenSource();
        var runner = new CancelCallerThenReturnHostedProcessRunner(callerCancellation);
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(
            projectId,
            new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"),
            callerCancellation.Token);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        run!.Status.Should().Be("completed");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPromoteNeedsFixGoal_WhenCurrentGoalBecomesReady()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new GoalRepairSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
        refreshed.Session.Status.Should().Be("paused_for_review");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldHonorStructuredCompletedStatus()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Stabilize map movement and first encounter trigger."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "still blocked", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "goal 1 needs fix");
        var runner = new StructuredCompletedHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepNeedsFix_WhenCurrentGoalIsStillBlocked()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new GoalRepairNeedsFixHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPersistNeedsFixSummary_WhenRepairTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new TimeoutHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("failed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Goals[0].ResultSummary.Should().Contain("修复超时");
        refreshed.Session.Status.Should().Be("needs_fix");
        refreshed.Session.LatestSummary.Should().Contain("修复超时");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRejectOffTopicSuccessOutput()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId, bool prototypeSucceeded)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        if (prototypeSucceeded)
        {
            var runId = await store.CreateRunAsync(result.ProjectId!, null, "prototype-7day-playable");
            await store.MarkRunStartedAsync(runId);
            await store.CompleteRunAsync(runId, "succeeded", 0, "prototype ok", "", "{}");
        }

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

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "Quick fix applied.");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class GoalRepairSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前目标修复已完成。
玩家现在可以稳定移动，并且能够明确触发第一次遇敌。
地图中的第一次遇敌入口已经接通，本 step 现在已可继续。
ready to continue
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class StructuredCompletedHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Current step is repaired through structured status.
CHANGED: Step repair completed.
VERIFY: Route can continue.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairNeedsFixHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前 step 仍需修复。
还有 remaining blocker。
not ready
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class TimeoutHostedProcessRunner : IHostedProcessRunner
    {
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
            return new HostedProcessResult(0, "", "");
        }
    }

    private sealed class OffTopicSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前目标修复已完成。
本 step 现在已可继续。
我更新了部署脚本、文档和安全测试。
ready to continue
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class CancelCallerThenReturnHostedProcessRunner : IHostedProcessRunner
    {
        private readonly CancellationTokenSource _callerCancellation;

        public CancelCallerThenReturnHostedProcessRunner(CancellationTokenSource callerCancellation)
        {
            _callerCancellation = callerCancellation;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            _callerCancellation.Cancel();
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "Quick fix applied after caller disconnect.");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
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
