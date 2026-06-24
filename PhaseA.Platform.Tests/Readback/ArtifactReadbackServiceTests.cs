using FluentAssertions;
using System.IO.Compression;
using System.Net;
using System.Text;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
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
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
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
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-draft-analysis");
        await store.MarkRunStartedAsync(runId);
        await store.UpdateRunProgressAsync(runId, "analyzing", "", "正在分析草稿。");
        var service = new ArtifactReadbackService(store, options);

        var active = await service.GetActiveRunAsync(project.AccountId);

        active.Busy.Should().BeTrue();
        active.RunId.Should().Be(runId);
        active.RunType.Should().Be("prototype-draft-analysis");
        active.ProgressLabel.Should().Be("正在分析草稿。");
        active.CreatedUtc.Should().NotBeNullOrWhiteSpace();
        active.StartedUtc.Should().NotBeNullOrWhiteSpace();
        active.ProgressUpdatedUtc.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task Readback_IgnoresActiveChatRunForBusyBanner()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var chatRunId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-chat");
        await store.MarkRunStartedAsync(chatRunId);
        var service = new ArtifactReadbackService(store, options);

        var active = await service.GetActiveRunAsync(project.AccountId);

        active.Busy.Should().BeFalse();
        active.RunId.Should().BeNull();
        active.RunType.Should().BeNull();
    }

    [Fact]
    public async Task Readback_IncludesDedicatedPrototypeAndAssetQueues()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var prototypeQueue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
        var assetQueue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(10), maxConcurrentRuns: 1);
        await using var prototypeLease = await prototypeQueue.EnterAsync(
            "prototype-run",
            project!.AccountId,
            project.ProjectId,
            "prototype-7day-playable");
        await using var assetLease = await assetQueue.EnterAsync(
            "asset-current",
            "other-account",
            "other-project",
            "asset-generation");
        using var queuedAssetCancellation = new CancellationTokenSource();
        var queuedAssetRun = assetQueue.ExecuteAsync(
            "asset-run",
            project.AccountId,
            project.ProjectId,
            "asset-generation",
            _ => Task.FromResult(true),
            queuedAssetCancellation.Token);
        var service = new ArtifactReadbackService(
            store,
            options,
            new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1),
            prototypeQueue,
            assetQueue);

        var active = await service.GetActiveRunAsync(project.AccountId);
        var queue = service.GetHeavyRunnerQueue(project.AccountId, includeAll: false);
        var fullQueue = service.GetHeavyRunnerQueue(project.AccountId, includeAll: true);

        active.Busy.Should().BeTrue();
        active.HeavyRunnerRunning.Should().BeTrue();
        queue.Running.Should().BeTrue();
        queue.Current!.RunId.Should().Be("prototype-run");
        fullQueue.Running.Should().BeTrue();
        fullQueue.Items.Select(item => item.RunId).Should().Contain("asset-run");
        fullQueue.CurrentAccountPosition.Should().Be(1);

        await queuedAssetCancellation.CancelAsync();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => queuedAssetRun);
    }

    [Fact]
    public void ExportAdminLlmUsageCsv_ExcludesSecrets()
    {
        var usage = new AdminLlmUsageReadback(
            "2026-05-22",
            1,
            2,
            3.50m,
            new[] { new AdminLlmAccountUsageItem("account-1", "user,one", false, false, 2, 2, 3.50m) });

        var csv = ArtifactReadbackService.ExportAdminLlmUsageCsv(usage);

        csv.Should().Contain("utc_day,account_id,username,is_admin,is_disabled,project_count,llm_call_count,estimated_cost_cny");
        csv.Should().Contain("\"user,one\"");
        csv.Contains("token", StringComparison.OrdinalIgnoreCase).Should().BeFalse();
        csv.Contains("secret", StringComparison.OrdinalIgnoreCase).Should().BeFalse();
    }

    [Fact]
    public void ExportAdminAccountAuditCsv_EscapesMetadataAndKeepsTokenMaterialOut()
    {
        var events = new[]
        {
            new AdminAccountAuditEvent(
                "event-1",
                "admin-1",
                "user_created",
                "account-1",
                "{\"username\":\"user,one\"}",
                "2026-05-22T00:00:00.0000000Z")
        };

        var csv = ArtifactReadbackService.ExportAdminAccountAuditCsv(events);

        csv.Should().Contain("event_id,actor_account_id,action,target_account_id,created_utc,metadata_json");
        csv.Should().Contain("\"{\"\"username\"\":\"\"user,one\"\"}\"");
        csv.Contains("phasea_", StringComparison.OrdinalIgnoreCase).Should().BeFalse();
        csv.Contains("token_hash", StringComparison.OrdinalIgnoreCase).Should().BeFalse();
    }

    [Fact]
    public async Task Readback_ReturnsAdminLlmRunAuditWithoutProcessOutput()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, owner, "Owner Game");
        var runId = await store.CreateRunAsync(projectId, null, "prototype-chat");
        await store.CompleteRunAsync(runId, "succeeded", 0, "secret stdout", "secret stderr", "{}", CancellationToken.None);
        await store.RecordRunLlmAuditAsync(runId, "new-api", "req-owner", "gpt-5.4", """{"estimated_cost_cny":1.25}""");
        var service = new ArtifactReadbackService(store, options);

        var audit = await service.GetAdminLlmRunAuditAsync();

        var item = audit.Runs.Should().ContainSingle(run => run.RunId == runId).Subject;
        item.Username.Should().NotBeNullOrWhiteSpace();
        item.LlmCostJson.Should().Contain("estimated_cost_cny");
        item.ToString().Should().NotContain("secret stdout");
        item.ToString().Should().NotContain("secret stderr");
    }

    [Fact]
    public async Task Readback_ReturnsAdminRunMetricsWithFiltersAndChatAverages()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var admin = await store.EnsureSingleAdminAsync();
        var user = await store.CreateUserAccountAsync("metrics-user", 1);
        var otherUser = await store.CreateUserAccountAsync("metrics-other", 1);
        var adminProject = await CreateProjectAsync(store, options, admin, "Admin Game");
        var projectId = await CreateProjectAsync(store, options, user.AccountId, "Metrics Game");
        var otherProject = await CreateProjectAsync(store, options, otherUser.AccountId, "Other Game");
        var adminRun = await store.CreateRunAsync(adminProject, null, "prototype-iteration-goal");
        var workflowRun = await store.CreateRunAsync(projectId, null, "prototype-iteration-goal");
        var packageRun = await store.CreateRunAsync(projectId, null, "project-package");
        var otherRun = await store.CreateRunAsync(otherProject, null, "prototype-iteration-goal");
        var chatOne = await store.CreateRunAsync(projectId, null, "prototype-chat");
        var chatTwo = await store.CreateRunAsync(projectId, null, "prototype-chat");
        var assetRun = await store.CreateRunAsync(projectId, null, "project-asset-generation");
        var otherAssetRun = await store.CreateRunAsync(otherProject, null, "project-asset-generation");
        await CompleteRunWithTimingAsync(database.ConnectionString, store, adminRun, "2026-06-01T00:00:00.0000000Z", "2026-06-01T00:00:01.0000000Z", "2026-06-01T00:00:02.0000000Z", 1);
        await CompleteRunWithTimingAsync(database.ConnectionString, store, workflowRun, "2026-06-01T00:00:00.0000000Z", "2026-06-01T00:00:05.0000000Z", "2026-06-01T00:00:17.0000000Z", 3);
        await CompleteRunWithTimingAsync(database.ConnectionString, store, packageRun, "2026-06-01T00:00:00.0000000Z", "2026-06-01T00:00:03.0000000Z", "2026-06-01T00:00:09.0000000Z", 2);
        await CompleteRunWithTimingAsync(database.ConnectionString, store, otherRun, "2026-06-01T00:00:00.0000000Z", "2026-06-01T00:00:02.0000000Z", "2026-06-01T00:00:04.0000000Z", 1);
        await CompleteRunWithTimingAsync(database.ConnectionString, store, chatOne, "2026-06-01T00:00:00.0000000Z", "2026-06-01T00:00:02.0000000Z", "2026-06-01T00:00:07.0000000Z", null);
        await CompleteRunWithTimingAsync(database.ConnectionString, store, chatTwo, "2026-06-01T00:00:10.0000000Z", "2026-06-01T00:00:14.0000000Z", "2026-06-01T00:00:23.0000000Z", null);
        await CompleteRunWithTimingAsync(database.ConnectionString, store, assetRun, "2026-06-01T00:00:20.0000000Z", "2026-06-01T00:00:21.0000000Z", "2026-06-01T00:00:31.0000000Z", null);
        await CompleteRunWithTimingAsync(database.ConnectionString, store, otherAssetRun, "2026-06-01T00:00:30.0000000Z", "2026-06-01T00:00:31.0000000Z", "2026-06-01T00:00:41.0000000Z", null);
        var service = new ArtifactReadbackService(store, options);

        var metrics = await service.GetAdminRunMetricsAsync(user.AccountId, "prototype-iteration-goal");
        var userMetrics = await service.GetAdminRunMetricsAsync(user.AccountId, null, limit: 1);
        await store.DeleteProjectAsync(projectId);
        var afterDelete = await service.GetAdminRunMetricsAsync(user.AccountId, "prototype-iteration-goal");

        var item = metrics.Runs.Should().ContainSingle().Subject;
        item.AccountId.Should().Be(user.AccountId);
        item.ProjectId.Should().Be(projectId);
        item.RunId.Should().Be(workflowRun);
        item.QueuePositionAtStart.Should().Be(3);
        item.QueueSeconds.Should().Be(5);
        item.RuntimeSeconds.Should().Be(12);
        metrics.Runs.Should().NotContain(run => run.RunId == adminRun);
        metrics.Runs.Should().NotContain(run => run.RunId == packageRun);
        metrics.Runs.Should().NotContain(run => run.RunId == otherRun);
        var chat = userMetrics.ChatAverages.Should().ContainSingle().Subject;
        chat.AccountId.Should().Be(user.AccountId);
        chat.RunCount.Should().Be(2);
        chat.AverageQueueSeconds.Should().Be(3);
        chat.AverageRuntimeSeconds.Should().Be(7);
        userMetrics.ChatRuns.Should().HaveCount(2);
        userMetrics.AssetRuns.Should().ContainSingle(run => run.RunId == assetRun);
        userMetrics.AssetRuns.Should().NotContain(run => run.RunId == otherAssetRun);
        afterDelete.Runs.Should().ContainSingle(run => run.RunId == workflowRun);
        afterDelete.Runs.Single().ProjectName.Should().Be("Metrics Game");
    }

    [Fact]
    public async Task Readback_PrunesRunDurationMetricsByBucketPolicy()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var user = await store.CreateUserAccountAsync("metrics-prune-user", 1);
        var projectId = await CreateProjectAsync(store, options, user.AccountId, "Metrics Prune Game");

        for (var index = 0; index < 505; index++)
        {
            var runId = await store.CreateRunAsync(projectId, null, "prototype-iteration-goal");
            await CompleteRunWithTimingAsync(
                database.ConnectionString,
                store,
                runId,
                $"2026-06-01T00:{index / 60:00}:{index % 60:00}.0000000Z",
                $"2026-06-01T01:{index / 60:00}:{index % 60:00}.0000000Z",
                $"2026-06-01T02:{index / 60:00}:{index % 60:00}.0000000Z",
                index + 1);
        }

        for (var index = 0; index < 505; index++)
        {
            var chatRunId = await store.CreateRunAsync(projectId, null, "prototype-chat");
            await CompleteRunWithTimingAsync(
                database.ConnectionString,
                store,
                chatRunId,
                $"2026-06-02T00:{index / 60:00}:{index % 60:00}.0000000Z",
                $"2026-06-02T01:{index / 60:00}:{index % 60:00}.0000000Z",
                $"2026-06-02T02:{index / 60:00}:{index % 60:00}.0000000Z",
                null);
            var assetRunId = await store.CreateRunAsync(projectId, null, "project-asset-generation");
            await CompleteRunWithTimingAsync(
                database.ConnectionString,
                store,
                assetRunId,
                $"2026-06-03T00:{index / 60:00}:{index % 60:00}.0000000Z",
                $"2026-06-03T01:{index / 60:00}:{index % 60:00}.0000000Z",
                $"2026-06-03T02:{index / 60:00}:{index % 60:00}.0000000Z",
                null);
        }

        var service = new ArtifactReadbackService(store, options);
        var metrics = await service.GetAdminRunMetricsAsync(user.AccountId, null, limit: 500);

        metrics.Runs.Should().HaveCount(500);
        metrics.ChatRuns.Should().HaveCount(500);
        metrics.AssetRuns.Should().HaveCount(500);
        metrics.Runs.Should().OnlyContain(run => run.RunType == "prototype-iteration-goal");
        metrics.ChatRuns.Should().OnlyContain(run => run.RunType == "prototype-chat");
        metrics.AssetRuns.Should().OnlyContain(run => run.RunType == "project-asset-generation");
    }

    [Fact]
    public async Task Readback_ReturnsAdminLlmUsageAcrossAccounts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("audit-user", 1);
        var ownerProject = await CreateProjectAsync(store, options, owner, "Owner Game");
        var otherProject = await CreateProjectAsync(store, options, other.AccountId, "Other Game");
        var ownerRun = await store.CreateRunAsync(ownerProject, null, "prototype-chat");
        var otherRun = await store.CreateRunAsync(otherProject, null, "prototype-chat");
        await store.RecordRunLlmAuditAsync(ownerRun, "new-api", "req-owner", "gpt-5.4", """{"estimated_cost_cny":1.25}""");
        await store.RecordRunLlmAuditAsync(otherRun, "new-api", "req-other", "gpt-5.5", """{"estimated_cost_cny":2.75}""");
        var service = new ArtifactReadbackService(store, options);

        var usage = await service.GetAdminLlmUsageAsync();

        usage.AccountCount.Should().BeGreaterThanOrEqualTo(2);
        usage.CallCount.Should().Be(2);
        usage.EstimatedCostCny.Should().Be(4.00m);
        usage.Accounts.Should().Contain(account => account.AccountId == owner && account.CallCount == 1 && account.EstimatedCostCny == 1.25m);
        usage.Accounts.Should().Contain(account => account.AccountId == other.AccountId && account.CallCount == 1 && account.EstimatedCostCny == 2.75m);
    }

    [Fact]
    public async Task Readback_ReturnsAdminLlmUsageAggregateByProject()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("aggregate-project-user", 1);
        var firstProject = await CreateProjectAsync(store, options, owner, "First Game");
        var secondProject = await CreateProjectAsync(store, options, other.AccountId, "Second Game");
        var firstRun = await store.CreateRunAsync(firstProject, null, "prototype-chat");
        var secondRun = await store.CreateRunAsync(secondProject, null, "prototype-chat");
        await store.RecordRunLlmAuditAsync(firstRun, "codex-cli", null, "gpt-5.4", """{"estimated_cost_cny":1.25}""");
        await store.RecordRunLlmAuditAsync(secondRun, "codex-cli", null, "gpt-5.5", """{"estimated_cost_cny":2.75}""");
        var service = new ArtifactReadbackService(store, options);

        var usage = await service.GetAdminLlmUsageAggregateAsync("day", "project", null, null);

        usage.Grain.Should().Be("day");
        usage.Split.Should().Be("project");
        usage.CallCount.Should().Be(2);
        usage.EstimatedCostCny.Should().Be(4.00m);
        usage.Items.Should().Contain(item => item.ProjectId == firstProject && item.ProjectName == "First Game" && item.EstimatedCostCny == 1.25m);
        usage.Items.Should().Contain(item => item.ProjectId == secondProject && item.ProjectName == "Second Game" && item.EstimatedCostCny == 2.75m);
    }

    [Fact]
    public async Task GetProjectRunsForAccountAsync_RejectsProjectOwnedByAnotherAccount()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("runs-readback-other", 1);
        var ownerProject = await CreateProjectAsync(store, options, owner, "Owner Game");
        var ownerRun = await store.CreateRunAsync(ownerProject, null, "prototype-chat");
        var service = new ArtifactReadbackService(store, options);

        var result = await service.GetProjectRunsForAccountAsync(other.AccountId, ownerProject);

        result.Should().BeNull();
        (await service.GetProjectRunsForAccountAsync(owner, ownerProject))!.Runs.Should().Contain(run => run.RunId == ownerRun);
    }

    [Fact]
    public async Task Readback_ReturnsAccountScopedLlmUsage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("other-llm-user", 1);
        var ownerProject = await CreateProjectAsync(store, options, owner, "Owner Game");
        var otherProject = await CreateProjectAsync(store, options, other.AccountId, "Other Game");
        var ownerRun = await store.CreateRunAsync(ownerProject, null, "prototype-chat");
        var otherRun = await store.CreateRunAsync(otherProject, null, "prototype-chat");
        await store.RecordRunLlmAuditAsync(ownerRun, "new-api", "req-owner", "gpt-5.4", """{"estimated_cost_cny":1.25}""");
        await store.RecordRunLlmAuditAsync(otherRun, "new-api", "req-other", "gpt-5.4", """{"estimated_cost_cny":9.99}""");
        var service = new ArtifactReadbackService(store, options);

        var usage = await service.GetAccountLlmUsageAsync(owner);

        usage.CallCount.Should().Be(1);
        usage.EstimatedCostCny.Should().Be(1.25m);
        usage.RecentRuns.Should().ContainSingle(run => run.RunId == ownerRun);
        usage.RecentRuns.Should().NotContain(run => run.RunId == otherRun);
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
    public async Task Readback_HidesRecoveredInterruptedRunAfterStartupReconcile()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-feedback-iteration");
        await store.MarkRunStartedAsync(runId);
        (await store.TryAcquireRunnerLockAsync(projectId, runId)).Should().BeTrue();
        var service = new ArtifactReadbackService(store, options);

        var recovered = await store.ReconcileInterruptedRunsAsync("Run was interrupted because the service restarted before completion.");
        var active = await service.GetActiveRunAsync(project.AccountId);
        var run = await store.GetRunSnapshotAsync(runId);

        recovered.Should().Be(1);
        active.Busy.Should().BeFalse();
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("service restarted before completion");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
    }

    [Fact]
    public async Task StartupReconcile_ShouldRestoreInterruptedIterationGoalToPending()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Iteration Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "test",
            "test",
            "test",
            [
                new ProjectIterationGoalCreateCommand(1, "step1", "step1", null),
                new ProjectIterationGoalCreateCommand(2, "step2", "step2", null)
            ]);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var first = details!.Goals.Single(goal => goal.GoalIndex == 1);
        var second = details.Goals.Single(goal => goal.GoalIndex == 2);
        await store.UpdateProjectIterationGoalStatusAsync(first.GoalId, "succeeded", "done", DateTimeOffset.UtcNow.ToString("O"));
        await store.UpdateProjectIterationGoalStatusAsync(second.GoalId, "running", null, null);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "running", 2, "running step2");
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-iteration-goal");
        await store.MarkRunStartedAsync(runId);
        (await store.TryAcquireRunnerLockAsync(projectId, runId)).Should().BeTrue();

        var recovered = await store.ReconcileInterruptedRunsAsync("Run was interrupted because the service restarted before completion.");
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        var run = await store.GetRunSnapshotAsync(runId);

        recovered.Should().Be(1);
        run!.Status.Should().Be("failed");
        refreshed!.Session.Status.Should().Be("paused_for_review");
        refreshed.Session.CurrentGoalIndex.Should().Be(2);
        refreshed.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("succeeded");
        refreshed.Goals.Single(goal => goal.GoalIndex == 2).Status.Should().Be("pending");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
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
        await SeedPackagePrerequisitesAsync(store, accountId, projectId);
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
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
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
    public async Task ProjectPackage_WhenQueuedRunIsCancelled_ShouldReturnCancelNotPackageFailed()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(projectId);
        await SeedPackagePrerequisitesAsync(store, accountId, projectId);
        Write(project.RepoPath, "Game.Core/Game.Core.csproj", "<Project />");
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(1), maxConcurrentRuns: 1);
        await using var lease = await queue.EnterAsync("held-package-run", accountId, projectId, "project-package");
        var service = new ProjectPackageService(store, options, queue);
        var packageTask = service.CreatePackageAsync(accountId, projectId);
        string runId = "";
        for (var attempt = 0; attempt < 50; attempt++)
        {
            var active = (await store.ListRunsForProjectAsync(projectId))
                .FirstOrDefault(run => run.RunType == "project-package" && run.Status == "queued");
            if (active is not null)
            {
                runId = active.RunId;
                break;
            }

            await Task.Delay(20);
        }
        runId.Should().NotBeEmpty();

        (await store.CancelRunAsync(accountId, runId)).Should().Be(RunCancelResult.Cancelled);
        queue.CancelRun(runId).Should().BeTrue();

        var result = await packageTask;

        result.Status.Should().Be("cancel");
        result.FailureCode.Should().Be("cancel");
        var run = await store.GetRunSnapshotAsync(runId);
        run!.Status.Should().Be("cancel");
        run.ExitCode.Should().Be(499);
    }

    [Fact]
    public async Task ProjectPackage_BlocksAndCompletesRun_WhenRunnerLockIsHeld()
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
        var heldRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "held-run");
        (await store.TryAcquireRunnerLockAsync(projectId, heldRunId)).Should().BeTrue();
        var service = new ProjectPackageService(store, options);

        var result = await service.CreatePackageAsync(accountId, projectId);

        result.Status.Should().Be("project_busy");
        result.FailureCode.Should().Be("project_busy");
        result.RunId.Should().BeEmpty();
        await store.ReleaseRunnerLockAsync(projectId, heldRunId);
    }

    [Fact]
    public async Task ProjectPackage_AppliesSelectedAssetLibraryEntryBeforeZipping()
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
        await SeedPackagePrerequisitesAsync(store, accountId, projectId);
        WriteBytes(project.RepoPath, "Game.Godot/Assets/player-old.png", MinimalPng(16, 16));
        WriteBytes(project.RepoPath, "Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png", MinimalPng(16, 16));
        Write(project.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Assets/player-old.png" id="1"]
            [node name="PlayerSprite" type="Sprite2D"]
            texture = ExtResource("1")
            [node name="PlayerBody" type="CharacterBody2D"]
            [node name="CollisionShape2D" type="CollisionShape2D" parent="PlayerBody"]
            """);
        Write(project.RepoPath, "meta/assets/library.json", """
            {
              "projectId": "PROJECT_ID",
              "units": [
                {
                  "key": "player-unit",
                  "instanceName": "PlayerSprite",
                  "nodeType": "Sprite2D",
                  "scenePath": "res://Game.Godot/Scenes/Main.tscn",
                  "resourcePath": "res://Game.Godot/Assets/player-old.png",
                  "kind": "player_sprite",
                  "intendedUse": "player",
                  "reason": "selected replacement",
                  "selectedEntryId": "entry-1",
                  "entries": [
                    {
                      "entryId": "entry-1",
                      "createdUtc": "2026-06-06T00:00:00Z",
                      "runId": "run-1",
                      "actionId": "character-making-master",
                      "skillName": "generate2dsprite",
                      "prompt": "new player",
                      "status": "succeeded",
                      "assistantMessage": "",
                      "artifactPaths": [
                        "Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png"
                      ],
                      "previewResourcePath": "res://Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png",
                      "selected": true
                    }
                  ]
                }
              ]
            }
            """.Replace("PROJECT_ID", projectId, StringComparison.Ordinal));
        var service = new ProjectPackageService(store, options);

        var result = await service.CreatePackageAsync(accountId, projectId);
        var download = await service.ReadPackageAsync(accountId, projectId, result.FileName);

        result.Status.Should().Be("succeeded");
        var sceneText = ZipEntryText(download!.Content, "Game.Godot/Scenes/Main.tscn");
        sceneText.Should().Contain("res://Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png");
        sceneText.Should().NotContain("res://Game.Godot/Assets/player-old.png");
        ZipEntryNames(download.Content).Should().Contain("Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png");
    }

    [Fact]
    public async Task ProjectPackage_AppliesSelectedCandidateAssetToExistingTextureNode()
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
        await SeedPackagePrerequisitesAsync(store, accountId, projectId);
        WriteBytes(project.RepoPath, "Game.Godot/Prototypes/ProjectAssetLibrary/player-candidate/entry-1/player-generated.png", MinimalPng(16, 16));
        Write(project.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene format=3]
            [node name="PlayerToken" type="Sprite2D"]
            """);
        Write(project.RepoPath, "meta/assets/library.json", """
            {
              "projectId": "PROJECT_ID",
              "units": [
                {
                  "key": "player-candidate",
                  "instanceName": "PlayerToken",
                  "nodeType": "Sprite2D",
                  "scenePath": "res://Game.Godot/Scenes/Main.tscn",
                  "resourcePath": "",
                  "kind": "player_sprite",
                  "intendedUse": "player",
                  "reason": "selected candidate",
                  "selectedEntryId": "entry-1",
                  "entries": [
                    {
                      "entryId": "entry-1",
                      "createdUtc": "2026-06-06T00:00:00Z",
                      "runId": "run-1",
                      "actionId": "character-making-master",
                      "skillName": "generate2dsprite",
                      "prompt": "new player",
                      "status": "succeeded",
                      "assistantMessage": "",
                      "artifactPaths": [
                        "Game.Godot/Prototypes/ProjectAssetLibrary/player-candidate/entry-1/player-generated.png"
                      ],
                      "previewResourcePath": "res://Game.Godot/Prototypes/ProjectAssetLibrary/player-candidate/entry-1/player-generated.png",
                      "selected": true
                    }
                  ]
                }
              ]
            }
            """.Replace("PROJECT_ID", projectId, StringComparison.Ordinal));
        var service = new ProjectPackageService(store, options);

        var result = await service.CreatePackageAsync(accountId, projectId);
        var download = await service.ReadPackageAsync(accountId, projectId, result.FileName);

        result.Status.Should().Be("succeeded");
        var sceneText = ZipEntryText(download!.Content, "Game.Godot/Scenes/Main.tscn");
        sceneText.Should().Contain("[ext_resource type=\"Texture2D\" path=\"res://Game.Godot/Prototypes/ProjectAssetLibrary/player-candidate/entry-1/player-generated.png\"");
        sceneText.Should().Contain("texture = ExtResource(\"phasea_asset_");
    }

    [Fact]
    public async Task ProjectPackage_RunsAssetReplacementSmoke_WhenGodotBinConfigured()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, godotBin: @"C:\Godot\Godot.exe");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(projectId);
        await SeedPackagePrerequisitesAsync(store, accountId, projectId);
        WriteBytes(project!.RepoPath, "Game.Godot/Assets/player-old.png", MinimalPng(16, 16));
        WriteBytes(project.RepoPath, "Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png", MinimalPng(16, 16));
        Write(project.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Assets/player-old.png" id="1"]
            [node name="PlayerSprite" type="Sprite2D"]
            texture = ExtResource("1")
            [node name="PlayerBody" type="CharacterBody2D"]
            [node name="CollisionShape2D" type="CollisionShape2D" parent="PlayerBody"]
            """);
        Write(project.RepoPath, "meta/assets/library.json", AssetLibraryJson(projectId));
        var runner = new FakeHostedProcessRunner("SMOKE PASS\n");
        var service = new ProjectPackageService(store, options, processRunner: runner);

        var result = await service.CreatePackageAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        runner.Commands.Should().ContainSingle(command => command.Arguments.Any(argument => Path.GetFileName(argument).Equals("smoke_headless.py", StringComparison.OrdinalIgnoreCase)));
        run!.EvidenceJson.Should().Contain("asset_replacement_scene_smoke_passed");
    }

    [Fact]
    public async Task ProjectPackage_Fails_WhenAssetReplacementSmokeFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, godotBin: @"C:\Godot\Godot.exe");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(projectId);
        await SeedPackagePrerequisitesAsync(store, accountId, projectId);
        WriteBytes(project!.RepoPath, "Game.Godot/Assets/player-old.png", MinimalPng(16, 16));
        WriteBytes(project.RepoPath, "Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png", MinimalPng(16, 16));
        Write(project.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Assets/player-old.png" id="1"]
            [node name="PlayerSprite" type="Sprite2D"]
            texture = ExtResource("1")
            [node name="PlayerBody" type="CharacterBody2D"]
            [node name="CollisionShape2D" type="CollisionShape2D" parent="PlayerBody"]
            """);
        Write(project.RepoPath, "meta/assets/library.json", AssetLibraryJson(projectId));
        var runner = new FakeHostedProcessRunner("ERROR: missing imported texture", exitCode: 0);
        var service = new ProjectPackageService(store, options, processRunner: runner);

        var result = await service.CreatePackageAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.FailureCode.Should().Be("asset_replacement_smoke_failed");
        runner.Commands.Should().ContainSingle(command => command.Arguments.Any(argument => Path.GetFileName(argument).Equals("smoke_headless.py", StringComparison.OrdinalIgnoreCase)));
        run!.EvidenceJson.Should().Contain("asset_replacement_scene_smoke_failed");
        Directory.EnumerateFiles(Path.Combine(project.RepoPath, "exports"), "*.zip").Should().BeEmpty();
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
    public async Task ProjectPackage_AllowsPackageAfterPrototypeSkeletonSucceedsWithoutIterationPlan()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        await SeedPrototypeCreationRunAsync(store, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = new ProjectPackageService(store, options);

        Write(project!.RepoPath, "Game.Core/Game.Core.csproj", "<Project />");
        var created = await service.CreatePackageAsync(accountId, projectId);
        var packages = await service.ListPackagesAsync(accountId, projectId);

        created.Status.Should().Be("succeeded");
        packages!.CanCreatePackage.Should().BeTrue();
        packages.DisabledReason.Should().BeNull();
    }

    [Fact]
    public async Task ProjectPackage_DoesNotRequirePrototypeAcceptanceAfterSkeletonSucceeds()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        await SeedPrototypeCreationRunAsync(store, projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = new ProjectPackageService(store, options);

        Write(project!.RepoPath, "Game.Core/Game.Core.csproj", "<Project />");
        var created = await service.CreatePackageAsync(accountId, projectId);
        var packages = await service.ListPackagesAsync(accountId, projectId);

        created.Status.Should().Be("succeeded");
        packages!.CanCreatePackage.Should().BeTrue();
        packages.DisabledReason.Should().BeNull();
    }

    [Fact]
    public async Task ProjectPackage_IgnoresStaleValidationOnlyRunWhenSkeletonSucceeded()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        await SeedPrototypeCreationRunAsync(store, projectId);
        await SeedPrototypeAcceptanceRunAsync(store, projectId);
        await Task.Delay(20);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = new ProjectPackageService(store, options);

        Write(project!.RepoPath, "Game.Core/Game.Core.csproj", "<Project />");
        var created = await service.CreatePackageAsync(accountId, projectId);
        var packages = await service.ListPackagesAsync(accountId, projectId);

        created.Status.Should().Be("succeeded");
        packages!.CanCreatePackage.Should().BeTrue();
        packages.DisabledReason.Should().BeNull();
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

    [Fact]
    public async Task ProjectAssetInventory_BlocksUntilFinalStepCompleted()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var service = new ProjectAssetInventoryService(store, options, new FakeCodexChatClient());

        var result = await service.GetInventoryAsync(accountId, projectId);

        result!.CanReadInventory.Should().BeFalse();
        result.DisabledReason.Should().Be("final_step_not_completed");
    }

    [Fact]
    public async Task ProjectAssetInventory_ListsUsedAssetsAndCandidatesAfterFinalStep()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        WriteBytes(project!.RepoPath, "Game.Godot/Assets/player.png", MinimalPng(32, 48));
        Write(project.RepoPath, "Game.Godot/Scenes/MapScene.tscn", """
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Texture2D" path="res://Game.Godot/Assets/player.png" id="1_player"]

            [node name="MapScene" type="Node2D"]

            [node name="PlayerSprite" type="Sprite2D" parent="."]
            texture = ExtResource("1_player")

            [node name="EnemySprite" type="Sprite2D" parent="."]
            """);
        var codex = new FakeCodexChatClient("""
            {
              "items": [
                {
                  "instanceName": "EnemySprite",
                  "scenePath": "res://Game.Godot/Scenes/MapScene.tscn",
                  "shouldGenerate": true,
                  "suggestedAssetKind": "enemy_sprite",
                  "intendedUse": "用于敌人在地图遭遇或战斗场景中的视觉表现。",
                  "reason": "敌人需要独立视觉表现。"
                }
              ]
            }
            """);
        var service = new ProjectAssetInventoryService(store, options, codex, new NoopWorkspaceSeeder());

        var result = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.4");
        var preview = await service.ReadPreviewAsync(accountId, projectId, "res://Game.Godot/Assets/player.png");

        result!.CanReadInventory.Should().BeTrue();
        result.UsedAssets.Should().ContainSingle(item =>
            item.InstanceName == "PlayerSprite" &&
            item.ResourcePath == "res://Game.Godot/Assets/player.png" &&
            item.IntendedUse == "用于玩家角色在地图或战斗场景中的视觉表现。" &&
            item.PixelWidth == 32 &&
            item.PixelHeight == 48 &&
            item.PreviewUrl.Contains("asset-preview", StringComparison.Ordinal));
        result.GenerationCandidates.Should().Contain(item =>
            item.InstanceName == "EnemySprite" &&
            item.SuggestedAssetKind == "enemy_sprite" &&
            item.LlmJudgementStatus == "llm_keep" &&
            item.IntendedUse == "用于敌人在地图遭遇或战斗场景中的视觉表现。" &&
            item.Reason == "敌人需要独立视觉表现。");
        codex.LastPrompt.Should().Contain("Inventory payload");
        codex.LastPrompt.Should().Contain("lightweight prototype component slots");
        codex.LastPrompt.Should().Contain("HudView");
        codex.LastPrompt.Should().Contain("not ECS");
        preview!.ContentType.Should().Be("image/png");
        preview.FileName.Should().Be("player.png");
    }

    [Fact]
    public async Task ProjectAssetInventory_UsesCachedJudgementUnlessForceRefresh()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        Write(project!.RepoPath, "Game.Godot/Scenes/MapScene.tscn", """
            [gd_scene format=3]
            [node name="PlayerToken" type="Sprite2D"]
            """);
        var codex = new FakeCodexChatClient("""
            {
              "items": [
                {
                  "instanceName": "PlayerToken",
                  "scenePath": "res://Game.Godot/Scenes/MapScene.tscn",
                  "shouldGenerate": true,
                  "suggestedAssetKind": "player_sprite",
                  "intendedUse": "用于玩家角色显示。",
                  "reason": "玩家需要视觉表现。"
                }
              ]
            }
            """);
        var service = new ProjectAssetInventoryService(store, options, codex, new NoopWorkspaceSeeder());

        var first = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.5");
        var second = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.5");
        var forced = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.5", forceRefresh: true);

        first!.GenerationCandidates.Should().ContainSingle(item => item.LlmJudgementStatus == "llm_keep");
        second!.GenerationCandidates.Should().ContainSingle(item => item.LlmJudgementStatus == "llm_keep");
        forced!.GenerationCandidates.Should().ContainSingle(item => item.LlmJudgementStatus == "llm_keep");
        codex.CallCount.Should().Be(2);
        var runs = await store.ListRunsForProjectAsync(projectId);
        runs.Where(run => run.RunType == "project-asset-inventory").Should().HaveCount(2);
    }

    [Fact]
    public async Task ProjectAssetInventory_RecordsRefreshRun_WhenJudgementHasNoCandidates()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        Write(project!.RepoPath, "Game.Godot/Scenes/MapScene.tscn", """
            [gd_scene format=3]
            [node name="MapScene" type="Node2D"]
            """);
        var service = new ProjectAssetInventoryService(store, options, new FakeCodexChatClient(), new NoopWorkspaceSeeder());

        var result = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.5", forceRefresh: true);
        var second = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.5", forceRefresh: true);

        result!.CanReadInventory.Should().BeTrue();
        second!.CanReadInventory.Should().BeTrue();
        result.GenerationCandidates.Should().BeEmpty();
        var runs = await store.ListRunsForProjectAsync(projectId);
        var run = runs.Single(item => item.RunType == "project-asset-inventory");
        run.Status.Should().Be("succeeded");
        run.EvidenceJson.Should().Contain("judgement_skipped");
    }

    [Fact]
    public async Task ProjectAssetInventory_ScansPrototypeScenesAndKeepsCandidatesWhenLlmDoesNotReturnJson()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        Write(project!.RepoPath, "Game.Godot/Prototypes/dq-rpg/Assets/Map/showcase_map_overworld.png", "fake image");
        Write(project.RepoPath, "Game.Godot/Prototypes/dq-rpg/MapScene.tscn", """
            [gd_scene load_steps=2 format=3]

            [ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Map/showcase_map_overworld.png" id="2"]

            [node name="MapScene" type="Control"]
            [node name="RpgMapAsset" type="TextureRect" parent="."]
            texture = ExtResource("2")
            [node name="PlayerToken" type="Sprite2D" parent="."]
            [node name="RewardChest" type="TextureRect" parent="."]
            """);
        var service = new ProjectAssetInventoryService(store, options, new FakeCodexChatClient("not json"), new NoopWorkspaceSeeder());

        var result = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.4");

        result!.UsedAssets.Should().ContainSingle(item =>
            item.InstanceName == "RpgMapAsset" &&
            item.ScenePath == "res://Game.Godot/Prototypes/dq-rpg/MapScene.tscn");
        result.GenerationCandidates.Should().Contain(item =>
            item.InstanceName == "PlayerToken" &&
            item.LlmJudgementStatus == "llm_json_parse_failed" &&
            item.IntendedUse == "用于玩家角色在地图或战斗场景中的视觉表现。");
        result.GenerationCandidates.Should().Contain(item =>
            item.InstanceName == "RewardChest" &&
            item.LlmJudgementStatus == "llm_json_parse_failed");
    }

    [Fact]
    public async Task ProjectAssetInventory_KeepsLlmRejectedCandidatesForReview()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        Write(project!.RepoPath, "Game.Godot/Prototypes/dq-rpg/MapScene.tscn", """
            [gd_scene format=3]
            [node name="PlayerToken" type="Sprite2D"]
            """);
        var service = new ProjectAssetInventoryService(store, options, new FakeCodexChatClient("""{"items":[]}"""), new NoopWorkspaceSeeder());

        var result = await service.GetInventoryAsync(accountId, projectId, includeLlmJudgement: true, model: "gpt-5.4");

        result!.GenerationCandidates.Should().ContainSingle(item =>
            item.InstanceName == "PlayerToken" &&
            item.LlmJudgementStatus == "llm_reject");
    }

    [Fact]
    public async Task ProjectAssetInventory_LimitsApplicableGenerationCandidatesToTen()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        var nodes = string.Join(Environment.NewLine, Enumerable.Range(1, 12).Select(index => $"[node name=\"EnemySprite{index:00}\" type=\"Sprite2D\"]"));
        Write(project!.RepoPath, "Game.Godot/Prototypes/dq-rpg/MapScene.tscn", $"""
            [gd_scene format=3]
            {nodes}
            [node name="RewardPanel" type="PanelContainer"]
            """);
        var service = new ProjectAssetInventoryService(store, options, new FakeCodexChatClient("not json"), new NoopWorkspaceSeeder());

        var result = await service.GetInventoryAsync(accountId, projectId);

        result!.GenerationCandidates.Should().HaveCount(10);
        result.GenerationCandidates.Should().OnlyContain(item => item.NodeType == "Sprite2D");
    }

    [Fact]
    public async Task ProjectAssetInventory_SkipsSeededDefaultRpgTemplate()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        Write(project!.RepoPath, "Game.Godot/Prototypes/DefaultRpgTemplate/Assets/template.png", "template");
        Write(project.RepoPath, "Game.Godot/Prototypes/DefaultRpgTemplate/MapScene.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/DefaultRpgTemplate/Assets/template.png" id="1"]
            [node name="TemplateMapAsset" type="TextureRect"]
            texture = ExtResource("1")
            """);
        Write(project.RepoPath, "Game.Godot/Prototypes/dq-rpg/Assets/map.png", "real");
        Write(project.RepoPath, "Game.Godot/Prototypes/dq-rpg/MapScene.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map.png" id="1"]
            [node name="RpgMapAsset" type="TextureRect"]
            texture = ExtResource("1")
            """);
        var service = new ProjectAssetInventoryService(store, options, new FakeCodexChatClient(), new NoopWorkspaceSeeder());

        var result = await service.GetInventoryAsync(accountId, projectId);

        result!.UsedAssets.Should().ContainSingle(item => item.InstanceName == "RpgMapAsset");
        result.UsedAssets.Should().NotContain(item => item.ResourcePath.Contains("DefaultRpgTemplate", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task ProjectAssetInventory_RejectsPreviewPathEscape()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var service = new ProjectAssetInventoryService(store, options, new FakeCodexChatClient());

        var act = async () => await service.ReadPreviewAsync(accountId, projectId, "res://../outside.png");

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    [Fact]
    public void ProjectAssetPreviewTicketService_CreatesBoundExpiringTicket()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(Path.GetTempPath(), "phase-a-asset-ticket-test.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = Directory.GetCurrentDirectory(),
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath(),
            ["PHASEA_ADMIN_TOKEN_HASH"] = "test-secret"
        });
        var service = new ProjectAssetPreviewTicketService(options);

        var ticket = service.CreateTicket("project-a", "res://Game.Godot/Prototypes/demo/Assets/player.png");

        service.IsValid(ticket, "project-a", "res://Game.Godot/Prototypes/demo/Assets/player.png").Should().BeTrue();
        service.IsValid(ticket, "project-b", "res://Game.Godot/Prototypes/demo/Assets/player.png").Should().BeFalse();
        service.IsValid(ticket, "project-a", "res://Game.Godot/Prototypes/demo/Assets/enemy.png").Should().BeFalse();
    }

    [Fact]
    public async Task ProjectAssetLibrary_GeneratesHistoryWithResolvedSkill_AndSelectsEntry()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var runner = new FakeHostedProcessRunner("asset generation output");
        var imageGenerator = new ProjectAssetImageGenerator(options, runner);
        var routeEngine = new FakeLlmRouteEngine("""{"actionId":"map-making-master","reason":"map unit"}""");
        var service = new ProjectAssetLibraryService(store, options, imageGenerator, routeEngine);

        var generated = await service.GenerateAsync(accountId, projectId, new ProjectAssetGenerationRunRequest(
            "make it like a 16-bit overworld",
            new ProjectAssetUnitRequest(
                null,
                "RpgMapAsset",
                "TextureRect",
                "res://Game.Godot/Prototypes/dq-rpg/MapScene.tscn",
                "res://Game.Godot/Prototypes/dq-rpg/Assets/Map/map.png",
                "map_or_tile_asset",
                "field map background",
                "needs stronger map art"),
            "image-to-image",
            2,
            "reference.png",
            Convert.ToBase64String(MinimalPng(16, 16)),
            "image/png"));

        generated!.ActionId.Should().Be("map-making-master");
        generated.Entry.SkillName.Should().Be("generate2dmap");
        generated.Entry.AssistantMessage.Should().Contain("轻量图片生成链路");
        generated.Entry.PreviewResourcePath.Should().StartWith("res://Game.Godot/Prototypes/ProjectAssetLibrary/");
        generated.Entry.ArtifactPaths.Should().Contain(path => path.Contains("ProjectAssetLibrary", StringComparison.Ordinal));
        routeEngine.LastPrompt.Should().Contain("Decide the correct asset generation skill");
        routeEngine.LastPrompt.Should().Contain("RpgMapAsset");
        routeEngine.LastPrompt.Should().Contain("HudView");
        routeEngine.LastPrompt.Should().Contain("not ECS");
        generated.Library.Units.Should().ContainSingle(unit =>
            unit.InstanceName == "RpgMapAsset" &&
            unit.Entries.Count == 2);
        var assetsManifest = Path.Combine((await store.GetProjectSnapshotAsync(projectId))!.RepoPath, "docs", "prototype", "ASSETS.md");
        File.Exists(assetsManifest).Should().BeTrue();
        var manifestText = File.ReadAllText(assetsManifest);
        manifestText.Should().Contain("source: map-making-master");
        manifestText.Should().Contain("bound_to_scene: none");
        Directory.EnumerateFiles(Path.Combine((await store.GetProjectSnapshotAsync(projectId))!.RepoPath, "logs", "prototype-evidence", projectId), "evidence.json", SearchOption.AllDirectories)
            .Should().NotBeEmpty();
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].FileName.Should().Be(options.PythonCommand);
        runner.Commands[0].Arguments.Should().Contain(arg => arg.EndsWith("aiartmirror_image_cli.py", StringComparison.Ordinal));
        runner.Commands[0].Arguments.Should().Contain(["--quality", "low"]);
        runner.Commands[0].Arguments.Should().Contain(["--n", "2"]);
        runner.Commands[0].Arguments.Should().Contain("--reference-image");
        runner.Commands[0].Arguments.Should().NotContain("exec");
        generated.Entry.Prompt.Should().Contain("make it like a 16-bit overworld");
        generated.Entry.Prompt.Should().Contain("Prompt isolation rules:");
        generated.Entry.Prompt.Should().Contain("Treat User generation direction as the highest-priority style source.");
        generated.Entry.Prompt.Should().Contain("classification only");

        var selected = await service.SelectAsync(accountId, projectId, new ProjectAssetSelectionRequest(
            generated.Library.Units.Single().Key,
            generated.Entry.EntryId));

        selected!.Units.Single().SelectedEntryId.Should().Be(generated.Entry.EntryId);
        selected.Units.Single().Entries.Should().ContainSingle(entry => entry.Selected);
        selected.Units.Single().Entries.Single(entry => entry.Selected).EntryId.Should().Be(generated.Entry.EntryId);
        selected.Units.Single().Entries.Single(entry => entry.Selected).SelectionValidation.Should().NotBeNull();
    }

    [Fact]
    public async Task ProjectAssetLibrary_DoesNotPersistFailedGenerationWithoutGeneratedFiles()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var runner = new FakeHostedProcessRunner("asset generation failed", exitCode: 1, writeGeneratedAsset: false);
        var imageGenerator = new ProjectAssetImageGenerator(options, runner);
        var routeEngine = new FakeLlmRouteEngine("""{"actionId":"character-making-master","reason":"sprite unit"}""");
        var service = new ProjectAssetLibraryService(store, options, imageGenerator, routeEngine);

        var generated = await service.GenerateAsync(accountId, projectId, new ProjectAssetGenerationRunRequest(
            "make a red slime",
            new ProjectAssetUnitRequest(
                null,
                "EnemyToken",
                "ColorRect",
                "res://Game.Godot/Prototypes/dq-rpg/BattleScene.tscn",
                "",
                "enemy_sprite",
                "battle enemy sprite",
                "placeholder needs art")));
        var library = await service.ReadAsync(accountId, projectId);

        generated!.Status.Should().Be("failed");
        generated.Library.Units.Should().BeEmpty();
        library!.Units.Should().BeEmpty();
    }

    [Fact]
    public async Task ProjectAssetLibrary_DoesNotPersistSucceededGenerationWithoutImageFiles()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var runner = new FakeHostedProcessRunner("asset spec only", generatedAssetFileName: "asset-spec.md");
        var imageGenerator = new ProjectAssetImageGenerator(options, runner);
        var routeEngine = new FakeLlmRouteEngine("""{"actionId":"character-making-master","reason":"sprite unit"}""");
        var service = new ProjectAssetLibraryService(store, options, imageGenerator, routeEngine);

        var generated = await service.GenerateAsync(accountId, projectId, new ProjectAssetGenerationRunRequest(
            "make a red slime",
            new ProjectAssetUnitRequest(
                null,
                "EnemyToken",
                "ColorRect",
                "res://Game.Godot/Prototypes/dq-rpg/BattleScene.tscn",
                "",
                "enemy_sprite",
                "battle enemy sprite",
                "placeholder needs art")));
        var library = await service.ReadAsync(accountId, projectId);

        generated!.Status.Should().Be("no_image_generated");
        generated.Entry.PreviewResourcePath.Should().BeNull();
        generated.Entry.ArtifactPaths.Should().NotContain(path => path.Contains("asset-spec.md", StringComparison.Ordinal));
        generated.Library.Units.Should().BeEmpty();
        library!.Units.Should().BeEmpty();
    }

    [Fact]
    public async Task ProjectAssetLibrary_RejectsWhenAccountAssetGenerationLimitIsReached()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var runner = new FakeHostedProcessRunner("asset generation output");
        var imageGenerator = new ProjectAssetImageGenerator(options, runner);
        var routeEngine = new FakeLlmRouteEngine("""{"actionId":"character-making-master","reason":"sprite unit"}""");
        var limiter = new AssetGenerationConcurrencyLimiter(maxConcurrentAssetGenerationsPerAccount: 1);
        var acquired = await limiter.TryAcquireAsync(accountId);
        await using var lease = acquired.Lease;
        var service = new ProjectAssetLibraryService(
            store,
            options,
            imageGenerator,
            routeEngine,
            assetConcurrencyLimiter: limiter);

        var act = () => service.GenerateAsync(accountId, projectId, new ProjectAssetGenerationRunRequest(
            "make a red slime",
            new ProjectAssetUnitRequest(
                null,
                "EnemyToken",
                "ColorRect",
                "res://Game.Godot/Prototypes/dq-rpg/BattleScene.tscn",
                "",
                "enemy_sprite",
                "battle enemy sprite",
                "placeholder needs art")));

        await act.Should().ThrowAsync<AssetGenerationConcurrencyLimitException>()
            .Where(ex => ex.FailureCode == "user_asset_generation_concurrency_limit_exceeded");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task ProjectAssetLibrary_RejectsInvalidReferenceImageContentType()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var runner = new FakeHostedProcessRunner("asset generation output");
        var imageGenerator = new ProjectAssetImageGenerator(options, runner);
        var routeEngine = new FakeLlmRouteEngine("""{"actionId":"character-making-master","reason":"sprite unit"}""");
        var service = new ProjectAssetLibraryService(store, options, imageGenerator, routeEngine);

        var generated = await service.GenerateAsync(accountId, projectId, new ProjectAssetGenerationRunRequest(
            "make a red slime",
            new ProjectAssetUnitRequest(
                null,
                "EnemyToken",
                "ColorRect",
                "res://Game.Godot/Prototypes/dq-rpg/BattleScene.tscn",
                "",
                "enemy_sprite",
                "battle enemy sprite",
                "placeholder needs art"),
            "image-to-image",
            1,
            "reference.png",
            Convert.ToBase64String(MinimalPng(16, 16)),
            "text/plain"));

        generated!.Status.Should().Be("failed");
        generated.Library.Units.Should().BeEmpty();
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task ProjectAssetLibrary_ImportsOnlyWhitelistedUrls_AndKeepsOtherUrlsAsKeywords()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, assetAllowedUrls: "https://assets.example.com/kaykit/");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        Write(project!.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Assets/old-crate.png" id="1"]
            [node name="Crate" type="Sprite2D"]
            texture = ExtResource("1")
            [node name="CrateBody" type="StaticBody2D"]
            [node name="CollisionShape2D" type="CollisionShape2D" parent="CrateBody"]
            """);
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, new FakeHostedProcessRunner("unused")),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new FakeAssetHttpHandler(MinimalPng(16, 16))));
        var unit = new ProjectAssetUnitRequest(
            "crate-unit",
            "Crate",
            "Sprite2D",
            "res://Game.Godot/Scenes/Main.tscn",
            "res://Game.Godot/Assets/old-crate.png",
            "blocking_prop",
            "solid dungeon prop",
            "replace visual and preserve collision");

        var imported = await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit/crate.png", unit));
        var keywordOnly = await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://evil.example.com/crate.png", unit));
        var adjacentPrefix = await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit-evil/crate.png", unit));
        var selected = await service.SelectAsync(accountId, projectId, new ProjectAssetSelectionRequest("crate-unit", imported!.Entry.EntryId));

        imported.Status.Should().Be("imported");
        imported.SourceUrlAllowed.Should().BeTrue();
        imported.Entry.PreviewResourcePath.Should().StartWith("res://Game.Godot/Prototypes/ProjectAssetLibrary/crate-unit/");
        File.Exists(Path.Combine(project.RepoPath, imported.Entry.ArtifactPaths.Single().Replace('/', Path.DirectorySeparatorChar))).Should().BeTrue();
        var assetsManifest = Path.Combine(project.RepoPath, "docs", "prototype", "ASSETS.md");
        File.Exists(assetsManifest).Should().BeTrue();
        var manifestText = File.ReadAllText(assetsManifest);
        manifestText.Should().Contain("source: whitelist_url");
        manifestText.Should().Contain("bound_to_scene: none");
        manifestText.Should().Contain("bound_to_scene: res://Game.Godot/Scenes/Main.tscn");
        var evidenceFiles = Directory.EnumerateFiles(Path.Combine(project.RepoPath, "logs", "prototype-evidence", project.ProjectId), "evidence.json", SearchOption.AllDirectories)
            .ToArray();
        evidenceFiles.Should().NotBeEmpty();
        evidenceFiles.Select(File.ReadAllText).Should().Contain(payload => payload.Contains("\"status\": \"passed\"", StringComparison.Ordinal) && payload.Contains("keyword-only import does not download assets", StringComparison.Ordinal));
        keywordOnly!.Status.Should().Be("keyword_only");
        keywordOnly.SourceUrlAllowed.Should().BeFalse();
        keywordOnly.Entry.PreviewResourcePath.Should().BeNull();
        keywordOnly.Entry.SourceKeyword.Should().Contain("evil.example.com");
        adjacentPrefix!.Status.Should().Be("keyword_only");
        adjacentPrefix.SourceUrlAllowed.Should().BeFalse();
        adjacentPrefix.Entry.SourceKeyword.Should().Contain("kaykit evil");
        var selectedEntry = selected!.Units.Single().Entries.Single(entry => entry.EntryId == imported.Entry.EntryId);
        selectedEntry.Selected.Should().BeTrue();
        selectedEntry.SelectionValidation.Should().NotBeNull();
        selectedEntry.SelectionValidation!.Status.Should().Be("ready_for_package_smoke");
        selectedEntry.SelectionValidation.SmokeRequired.Should().BeTrue();
        selectedEntry.SelectionValidation.Checks.Select(check => check.Name).Should().Contain([
            "replacement_resource_exists",
            "scene_patchable",
            "collision_preserved",
            "post_replace_smoke_required"
        ]);
    }

    [Fact]
    public async Task ProjectAssetLibrary_WhitelistedModelImport_CanBeUsedAsReplacementResource()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, assetAllowedUrls: "https://assets.example.com/kaykit/");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        Write(project!.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="PackedScene" path="res://Game.Godot/Assets/old-crate.glb" id="1"]
            [node name="Crate" instance=ExtResource("1")]
            [node name="CrateBody" type="StaticBody3D"]
            [node name="CollisionShape3D" type="CollisionShape3D" parent="CrateBody"]
            """);
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, new FakeHostedProcessRunner("unused")),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new FakeAssetHttpHandler(Encoding.UTF8.GetBytes("glTF placeholder"), "model/gltf-binary")));
        var unit = new ProjectAssetUnitRequest(
            "crate-model",
            "Crate",
            "Node3D",
            "res://Game.Godot/Scenes/Main.tscn",
            "res://Game.Godot/Assets/old-crate.glb",
            "blocking_prop",
            "solid dungeon prop",
            "replace KayKit model and preserve collision");

        var imported = await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit/crate.glb", unit));
        var selected = await service.SelectAsync(accountId, projectId, new ProjectAssetSelectionRequest("crate-model", imported!.Entry.EntryId));

        imported.Status.Should().Be("imported");
        imported.Entry.PreviewResourcePath.Should().EndWith("/crate.glb");
        var sceneText = File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "Main.tscn"));
        sceneText.Should().Contain(imported.Entry.PreviewResourcePath);
        var selectedEntry = selected!.Units.Single().Entries.Single(entry => entry.Selected);
        selectedEntry.SelectionValidation!.ReplacementResourceExists.Should().BeTrue();
        selectedEntry.SelectionValidation.ScenePatch!.Applied.Should().BeTrue();
    }

    [Fact]
    public async Task ProjectAssetLibrary_RejectsWhitelistedUrlRedirects()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, assetAllowedUrls: "https://assets.example.com/kaykit/");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, new FakeHostedProcessRunner("unused")),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new RedirectAssetHttpHandler("https://evil.example.com/crate.png")));
        var unit = new ProjectAssetUnitRequest(
            "crate-unit",
            "Crate",
            "Sprite2D",
            "res://Game.Godot/Scenes/Main.tscn",
            "res://Game.Godot/Assets/old-crate.png",
            "blocking_prop",
            "solid dungeon prop",
            "replace visual and preserve collision");

        var act = async () => await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit/crate.png", unit));

        await act.Should().ThrowAsync<ArgumentException>().WithMessage("*redirects are not allowed*");
    }

    [Fact]
    public async Task ProjectAssetLibrary_RejectsFinalUriChangedByRedirectingClient()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, assetAllowedUrls: "https://assets.example.com/kaykit/");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, new FakeHostedProcessRunner("unused")),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new FinalUriChangedAssetHttpHandler(MinimalPng(16, 16), "https://evil.example.com/crate.png")));
        var unit = new ProjectAssetUnitRequest(
            "crate-unit",
            "Crate",
            "Sprite2D",
            "res://Game.Godot/Scenes/Main.tscn",
            "res://Game.Godot/Assets/old-crate.png",
            "blocking_prop",
            "solid dungeon prop",
            "replace visual and preserve collision");

        var act = async () => await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit/crate.png", unit));

        await act.Should().ThrowAsync<ArgumentException>().WithMessage("*redirects are not allowed*");
    }


    [Fact]
    public async Task ProjectAssetLibrary_WhitelistedZipImport_ExtractsOnlyRuntimeAssetsFromQuarantine()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, assetAllowedUrls: "https://assets.example.com/kaykit/");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        Write(project!.RepoPath, "Game.Godot/Scenes/Main.tscn", "[gd_scene format=3]\n[node name=\"Crate\" type=\"Sprite2D\"]\n");
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, new FakeHostedProcessRunner("unused")),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new FakeAssetHttpHandler(ZipBytes(("props/crate.png", MinimalPng(16, 16))), "application/zip")));
        var unit = new ProjectAssetUnitRequest(
            "crate-unit",
            "Crate",
            "Sprite2D",
            "res://Game.Godot/Scenes/Main.tscn",
            "",
            "blocking_prop",
            "solid dungeon prop",
            "replace visual and preserve collision");

        var imported = await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit/crate-pack.zip", unit));

        imported!.Status.Should().Be("imported");
        imported.Entry.ArtifactPaths.Should().ContainSingle(path => path.EndsWith("crate.png", StringComparison.OrdinalIgnoreCase));
        imported.Entry.PreviewResourcePath.Should().EndWith("/crate.png");
        File.Exists(Path.Combine(project.RepoPath, imported.Entry.ArtifactPaths.Single().Replace('/', Path.DirectorySeparatorChar))).Should().BeTrue();
        Directory.EnumerateFiles(Path.Combine(project.RepoPath, "logs", "prototype-evidence", project.ProjectId), "crate-pack.zip", SearchOption.AllDirectories)
            .Should().ContainSingle("downloaded zip should stay in the evidence quarantine area");
    }

    [Theory]
    [InlineData("../escape.png", "path is not allowed")]
    [InlineData("scripts/payload.cs", "dynamic code")]
    [InlineData("props/vector.svg", "supported runtime assets")]
    public async Task ProjectAssetLibrary_WhitelistedZipImport_RejectsUnsafeArchiveEntries(string entryName, string expectedMessage)
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, assetAllowedUrls: "https://assets.example.com/kaykit/");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, new FakeHostedProcessRunner("unused")),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new FakeAssetHttpHandler(ZipBytes((entryName, MinimalPng(16, 16))), "application/zip")));
        var unit = new ProjectAssetUnitRequest(
            "crate-unit",
            "Crate",
            "Sprite2D",
            "res://Game.Godot/Scenes/Main.tscn",
            "",
            "blocking_prop",
            "solid dungeon prop",
            "replace visual and preserve collision");

        var act = async () => await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit/crate-pack.zip", unit));

        await act.Should().ThrowAsync<ArgumentException>().WithMessage($"*{expectedMessage}*");
        Directory.Exists(Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "ProjectAssetLibrary", "crate-unit"))
            .Should().BeTrue("the run may create its output directory, but unsafe archive entries must not be staged as runtime files");
        Directory.EnumerateFiles(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "ProjectAssetLibrary", "crate-unit"), "*", SearchOption.AllDirectories)
            .Should().BeEmpty();
    }

    [Fact]
    public async Task ProjectAssetLibrary_SelectAsync_RollsBackScenePatch_WhenSmokeFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, godotBin: @"C:\Godot\Godot.exe");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteBytes(project!.RepoPath, "Game.Godot/Assets/player-old.png", MinimalPng(16, 16));
        WriteBytes(project.RepoPath, "Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png", MinimalPng(16, 16));
        Write(project.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Assets/player-old.png" id="1"]
            [node name="PlayerSprite" type="Sprite2D"]
            texture = ExtResource("1")
            [node name="PlayerBody" type="CharacterBody2D"]
            [node name="CollisionShape2D" type="CollisionShape2D" parent="PlayerBody"]
            """);
        Write(project.RepoPath, "meta/assets/library.json", AssetLibraryJson(projectId));
        var runner = new FakeHostedProcessRunner("SMOKE FAIL\n", exitCode: 23);
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, runner),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            processRunner: runner);

        var selected = await service.SelectAsync(accountId, projectId, new ProjectAssetSelectionRequest("player-unit", "entry-1", ValidateWithSmoke: true));

        var sceneText = File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "Main.tscn"));
        sceneText.Should().Contain("res://Game.Godot/Assets/player-old.png");
        sceneText.Should().NotContain("res://Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png");
        selected!.Units.Single().SelectedEntryId.Should().BeNull();
        selected.Units.Single().Entries.Should().NotContain(entry => entry.Selected);
        var attemptedEntry = selected.Units.Single().Entries.Single(entry => entry.EntryId == "entry-1");
        attemptedEntry.SelectionValidation!.Status.Should().Be("smoke_failed");
        attemptedEntry.SelectionValidation.ScenePatch!.Reason.Should().Contain("rolled_back_after_smoke_failed");
        var assetsManifest = Path.Combine(project.RepoPath, "docs", "prototype", "ASSETS.md");
        File.ReadAllText(assetsManifest).Should().Contain("status: failed");
    }

    [Fact]
    public async Task ProjectAssetLibrary_SelectAsync_PatchesSceneImmediately_AndCanRunSmoke()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, godotBin: @"C:\Godot\Godot.exe");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteBytes(project!.RepoPath, "Game.Godot/Assets/player-old.png", MinimalPng(16, 16));
        WriteBytes(project.RepoPath, "Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png", MinimalPng(16, 16));
        Write(project.RepoPath, "Game.Godot/Scenes/Main.tscn", """
            [gd_scene load_steps=2 format=3]
            [ext_resource type="Texture2D" path="res://Game.Godot/Assets/player-old.png" id="1"]
            [node name="PlayerSprite" type="Sprite2D"]
            texture = ExtResource("1")
            [node name="PlayerBody" type="CharacterBody2D"]
            [node name="CollisionShape2D" type="CollisionShape2D" parent="PlayerBody"]
            """);
        Write(project.RepoPath, "meta/assets/library.json", AssetLibraryJson(projectId));
        var runner = new FakeHostedProcessRunner("SMOKE PASS\n");
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, runner),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            processRunner: runner);

        var selected = await service.SelectAsync(accountId, projectId, new ProjectAssetSelectionRequest("player-unit", "entry-1", ValidateWithSmoke: true));

        var sceneText = File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "Main.tscn"));
        sceneText.Should().Contain("res://Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png");
        sceneText.Should().NotContain("res://Game.Godot/Assets/player-old.png");
        var selectedEntry = selected!.Units.Single().Entries.Single(entry => entry.Selected);
        selectedEntry.SelectionValidation!.Status.Should().Be("smoke_passed");
        selectedEntry.SelectionValidation.ScenePatch!.Applied.Should().BeTrue();
        selectedEntry.SelectionValidation.SelectionSmoke!.Ran.Should().BeTrue();
        runner.Commands.Should().ContainSingle(command => command.Arguments.Any(argument => Path.GetFileName(argument).Equals("smoke_headless.py", StringComparison.OrdinalIgnoreCase)));
    }

    [Fact]
    public async Task ProjectAssetLibrary_WriteRoutes_BlockWhenProjectRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, assetAllowedUrls: "https://assets.example.com/kaykit/");
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Demo Game");
        var project = await store.GetProjectSnapshotAsync(projectId);
        Write(project!.RepoPath, "meta/assets/library.json", AssetLibraryJson(projectId));
        var heldRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "held-run");
        (await store.TryAcquireRunnerLockAsync(projectId, heldRunId)).Should().BeTrue();
        var runner = new FakeHostedProcessRunner("asset generation output");
        var service = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, runner),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new FakeAssetHttpHandler(MinimalPng(16, 16))),
            processRunner: runner);
        var unit = new ProjectAssetUnitRequest(
            "player-unit",
            "PlayerSprite",
            "Sprite2D",
            "res://Game.Godot/Scenes/Main.tscn",
            "res://Game.Godot/Assets/player-old.png",
            "player_sprite",
            "player",
            "selected replacement");

        var generate = async () => await service.GenerateAsync(accountId, projectId, new ProjectAssetGenerationRunRequest("make player", unit));
        var import = async () => await service.ImportAsync(accountId, projectId, new ProjectAssetImportRequest("https://assets.example.com/kaykit/player.png", unit));
        var select = async () => await service.SelectAsync(accountId, projectId, new ProjectAssetSelectionRequest("player-unit", "entry-1"));

        await generate.Should().ThrowAsync<InvalidOperationException>().WithMessage("Project runner is busy.");
        await import.Should().ThrowAsync<InvalidOperationException>().WithMessage("Project runner is busy.");
        await select.Should().ThrowAsync<InvalidOperationException>().WithMessage("Project runner is busy.");
        runner.Commands.Should().BeEmpty();
    }

    private static async Task<PhaseAMetadataStore> CreateStoreAsync(string connectionString, PhaseAPlatformOptions options)
    {
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var store = new PhaseAMetadataStore(connectionString, options);
        await store.EnsureSingleAdminAsync();
        return store;
    }

    private static async Task CompleteRunWithTimingAsync(
        string connectionString,
        PhaseAMetadataStore store,
        string runId,
        string createdUtc,
        string startedUtc,
        string finishedUtc,
        int? queuePositionAtStart)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            UPDATE runs
            SET created_utc = $created_utc,
                started_utc = $started_utc,
                finished_utc = NULL,
                queue_position_at_start = $queue_position_at_start
            WHERE id = $id;
            """;
        command.Parameters.AddWithValue("$id", runId);
        command.Parameters.AddWithValue("$created_utc", createdUtc);
        command.Parameters.AddWithValue("$started_utc", startedUtc);
        command.Parameters.AddWithValue("$queue_position_at_start", (object?)queuePositionAtStart ?? DBNull.Value);
        await command.ExecuteNonQueryAsync();

        await store.CompleteRunAsync(runId, "succeeded", 0, "", "", "{}");

        await using var fixConnection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await fixConnection.OpenAsync();
        await using var fixCommand = fixConnection.CreateCommand();
        fixCommand.CommandText =
            """
            UPDATE runs
            SET finished_utc = $finished_utc
            WHERE id = $id;
            UPDATE run_duration_metrics
            SET finished_utc = $finished_utc,
                queue_seconds = ROUND(CASE
                    WHEN started_utc IS NULL THEN NULL
                    ELSE MAX(0.0, (julianday(started_utc) - julianday(created_utc)) * 86400.0)
                END, 3),
                runtime_seconds = ROUND(CASE
                    WHEN started_utc IS NULL THEN NULL
                    ELSE MAX(0.0, (julianday($finished_utc) - julianday(started_utc)) * 86400.0)
                END, 3)
            WHERE run_id = $id;
            """;
        fixCommand.Parameters.AddWithValue("$id", runId);
        fixCommand.Parameters.AddWithValue("$finished_utc", finishedUtc);
        await fixCommand.ExecuteNonQueryAsync();
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

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot, string? assetAllowedUrls = null, string? godotBin = null)
    {
        var values = new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot
        };
        if (!string.IsNullOrWhiteSpace(assetAllowedUrls))
        {
            values["PHASEA_ASSET_ALLOWED_URLS"] = assetAllowedUrls;
        }
        if (!string.IsNullOrWhiteSpace(godotBin))
        {
            values["GODOT_BIN"] = godotBin;
        }

        return PhaseAPlatformOptionsLoader.FromDictionary(values);
    }

    private static string AssetLibraryJson(string projectId)
    {
        return """
            {
              "projectId": "PROJECT_ID",
              "units": [
                {
                  "key": "player-unit",
                  "instanceName": "PlayerSprite",
                  "nodeType": "Sprite2D",
                  "scenePath": "res://Game.Godot/Scenes/Main.tscn",
                  "resourcePath": "res://Game.Godot/Assets/player-old.png",
                  "kind": "player_sprite",
                  "intendedUse": "player",
                  "reason": "selected replacement",
                  "selectedEntryId": "entry-1",
                  "entries": [
                    {
                      "entryId": "entry-1",
                      "createdUtc": "2026-06-06T00:00:00Z",
                      "runId": "run-1",
                      "actionId": "character-making-master",
                      "skillName": "generate2dsprite",
                      "prompt": "new player",
                      "status": "succeeded",
                      "assistantMessage": "",
                      "artifactPaths": [
                        "Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png"
                      ],
                      "previewResourcePath": "res://Game.Godot/Prototypes/ProjectAssetLibrary/player-unit/entry-1/player-new.png",
                      "selected": true
                    }
                  ]
                }
              ]
            }
            """.Replace("PROJECT_ID", projectId, StringComparison.Ordinal);
    }

    private static void Write(string root, string relativePath, string content)
    {
        var path = Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    private static void WriteBytes(string root, string relativePath, byte[] content)
    {
        var path = Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllBytes(path, content);
    }


    private static byte[] ZipBytes(params (string Name, byte[] Content)[] entries)
    {
        using var memory = new MemoryStream();
        using (var archive = new ZipArchive(memory, ZipArchiveMode.Create, leaveOpen: true))
        {
            foreach (var (name, content) in entries)
            {
                var entry = archive.CreateEntry(name);
                using var stream = entry.Open();
                stream.Write(content, 0, content.Length);
            }
        }

        return memory.ToArray();
    }

    private static byte[] MinimalPng(int width, int height)
    {
        var bytes = new byte[24];
        bytes[0] = 0x89;
        bytes[1] = 0x50;
        bytes[2] = 0x4E;
        bytes[3] = 0x47;
        bytes[4] = 0x0D;
        bytes[5] = 0x0A;
        bytes[6] = 0x1A;
        bytes[7] = 0x0A;
        bytes[12] = 0x49;
        bytes[13] = 0x48;
        bytes[14] = 0x44;
        bytes[15] = 0x52;
        WriteBigEndian(bytes, 16, width);
        WriteBigEndian(bytes, 20, height);
        return bytes;
    }

    private static void WriteBigEndian(byte[] bytes, int offset, int value)
    {
        bytes[offset] = (byte)((value >> 24) & 0xFF);
        bytes[offset + 1] = (byte)((value >> 16) & 0xFF);
        bytes[offset + 2] = (byte)((value >> 8) & 0xFF);
        bytes[offset + 3] = (byte)(value & 0xFF);
    }

    private static async Task CreateSucceededIterationPlanAsync(
        PhaseAMetadataStore store,
        string accountId,
        string projectId)
    {
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "test",
            "test",
            "test",
            [
                new ProjectIterationGoalCreateCommand(1, "step1", "step1", null),
                new ProjectIterationGoalCreateCommand(2, "final", "final", null)
            ]);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in details!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", "done", DateTimeOffset.UtcNow.ToString("O"));
        }

        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "completed", 2, "done", null, DateTimeOffset.UtcNow.ToString("O"));
    }

    private static async Task SeedPackagePrerequisitesAsync(
        PhaseAMetadataStore store,
        string accountId,
        string projectId)
    {
        await SeedPrototypeCreationRunAsync(store, projectId);
        await CreateSucceededIterationPlanAsync(store, accountId, projectId);
        await Task.Delay(20);
        await SeedPrototypeAcceptanceRunAsync(store, projectId);
    }

    private static async Task SeedPrototypeCreationRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var runId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "succeeded",
            0,
            "prototype complete",
            "",
            """{"prototype_completion":{"succeeded":true},"godot_smoke":{"exit_code":0}}""",
            CancellationToken.None);
    }

    private static async Task SeedPrototypeAcceptanceRunAsync(PhaseAMetadataStore store, string projectId)
    {
        var project = (await store.GetProjectSnapshotAsync(projectId))!;
        var runId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "succeeded",
            0,
            "prototype validation",
            "",
            """{"validation_only":true,"prototype_completion":{"succeeded":true},"godot_smoke":{"exit_code":0}}""",
            CancellationToken.None);
    }

    private static IReadOnlyList<string> ZipEntryNames(byte[] content)
    {
        using var memory = new MemoryStream(content);
        using var archive = new ZipArchive(memory, ZipArchiveMode.Read);
        return archive.Entries.Select(entry => entry.FullName).ToArray();
    }

    private static string ZipEntryText(byte[] content, string entryName)
    {
        using var memory = new MemoryStream(content);
        using var archive = new ZipArchive(memory, ZipArchiveMode.Read);
        var entry = archive.GetEntry(entryName);
        entry.Should().NotBeNull();
        using var reader = new StreamReader(entry!.Open(), Encoding.UTF8);
        return reader.ReadToEnd();
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

    private sealed class FakeCodexChatClient : ICodexChatClient
    {
        private readonly string _reply;

        public FakeCodexChatClient(string reply = """{"items":[]}""")
        {
            _reply = reply;
        }

        public string LastPrompt { get; private set; } = "";
        public int CallCount { get; private set; }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            CallCount++;
            LastPrompt = prompt;
            return Task.FromResult(new CodexChatClientResult(true, _reply, null, 0, "", ""));
        }
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly string _output;
        private readonly int _exitCode;
        private readonly bool _writeGeneratedAsset;
        private readonly string _generatedAssetFileName;

        public FakeHostedProcessRunner(string output, int exitCode = 0, bool writeGeneratedAsset = true, string generatedAssetFileName = "generated.png")
        {
            _output = output;
            _exitCode = exitCode;
            _writeGeneratedAsset = writeGeneratedAsset;
            _generatedAssetFileName = generatedAssetFileName;
        }

        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.Arguments.Any(argument => Path.GetFileName(argument).Equals("smoke_headless.py", StringComparison.OrdinalIgnoreCase)))
            {
                return Task.FromResult(new HostedProcessResult(_exitCode, _output, _exitCode == 0 ? "" : "smoke failed"));
            }

            if (command.Arguments.Contains("--out", StringComparer.Ordinal))
            {
                var outputPath = ReadArgument(command.Arguments, "--out")!;
                var manifestPath = ReadArgument(command.Arguments, "--manifest-out");
                if (manifestPath is not null)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(manifestPath)!);
                    File.WriteAllText(manifestPath, """{"result_count":1}""");
                }

                if (_writeGeneratedAsset)
                {
                    var count = int.TryParse(ReadArgument(command.Arguments, "--n"), out var parsedCount) ? Math.Clamp(parsedCount, 1, 4) : 1;
                    for (var index = 0; index < count; index++)
                    {
                        var assetPath = Path.GetExtension(_generatedAssetFileName).Equals(".png", StringComparison.OrdinalIgnoreCase)
                            ? (count == 1 ? outputPath : Path.Combine(Path.GetDirectoryName(outputPath)!, $"{Path.GetFileNameWithoutExtension(outputPath)}-{index + 1:00}.png"))
                            : Path.Combine(Path.GetDirectoryName(outputPath)!, _generatedAssetFileName);
                        Directory.CreateDirectory(Path.GetDirectoryName(assetPath)!);
                        if (Path.GetExtension(assetPath).Equals(".png", StringComparison.OrdinalIgnoreCase))
                        {
                            File.WriteAllBytes(assetPath, MinimalPng(16, 16));
                        }
                        else
                        {
                            File.WriteAllText(assetPath, "spec only");
                        }
                    }
                }
                else
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
                }

                return Task.FromResult(new HostedProcessResult(_exitCode, _output, _exitCode == 0 ? "" : "image generation failed"));
            }

            var codexOutputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(codexOutputPath)!);
            File.WriteAllText(codexOutputPath, _output);
            var outputDirectory = ReadRequiredOutputDirectory(command.StandardInput ?? "");
            if (_writeGeneratedAsset && !string.IsNullOrWhiteSpace(outputDirectory))
            {
                var assetPath = Path.Combine(command.WorkingDirectory, outputDirectory.Replace('/', Path.DirectorySeparatorChar), _generatedAssetFileName);
                Directory.CreateDirectory(Path.GetDirectoryName(assetPath)!);
                if (Path.GetExtension(assetPath).Equals(".png", StringComparison.OrdinalIgnoreCase))
                {
                    File.WriteAllBytes(assetPath, MinimalPng(16, 16));
                }
                else
                {
                    File.WriteAllText(assetPath, "spec only");
                }
            }

            return Task.FromResult(new HostedProcessResult(_exitCode, "codex stdout", _exitCode == 0 ? "" : "codex failed"));
        }

        private static string? ReadArgument(IReadOnlyList<string> arguments, string name)
        {
            for (var index = 0; index < arguments.Count - 1; index++)
            {
                if (string.Equals(arguments[index], name, StringComparison.Ordinal))
                {
                    return arguments[index + 1];
                }
            }

            return null;
        }

        private static string? ReadRequiredOutputDirectory(string prompt)
        {
            var lines = prompt.Split(["\r\n", "\n"], StringSplitOptions.None);
            for (var i = 0; i < lines.Length - 1; i++)
            {
                if (lines[i].Trim().Equals("Required output directory:", StringComparison.Ordinal))
                {
                    return lines[i + 1].Trim();
                }
            }

            return null;
        }
    }

    private sealed class FakeAssetHttpHandler : HttpMessageHandler
    {
        private readonly byte[] _content;
        private readonly string _mediaType;

        public FakeAssetHttpHandler(byte[] content, string mediaType = "image/png")
        {
            _content = content;
            _mediaType = mediaType;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var response = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new ByteArrayContent(_content)
            };
            response.Content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(_mediaType);
            return Task.FromResult(response);
        }
    }

    private sealed class RedirectAssetHttpHandler : HttpMessageHandler
    {
        private readonly string _location;

        public RedirectAssetHttpHandler(string location)
        {
            _location = location;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var response = new HttpResponseMessage(HttpStatusCode.Redirect);
            response.Headers.Location = new Uri(_location);
            return Task.FromResult(response);
        }
    }

    private sealed class FinalUriChangedAssetHttpHandler : HttpMessageHandler
    {
        private readonly byte[] _content;
        private readonly string _finalUri;

        public FinalUriChangedAssetHttpHandler(byte[] content, string finalUri)
        {
            _content = content;
            _finalUri = finalUri;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            request.RequestUri = new Uri(_finalUri);
            var response = new HttpResponseMessage(HttpStatusCode.OK)
            {
                RequestMessage = request,
                Content = new ByteArrayContent(_content)
            };
            response.Content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("image/png");
            return Task.FromResult(response);
        }
    }

    private sealed class FakeLlmRouteEngine : ILlmRouteEngine
    {
        private readonly string _json;

        public FakeLlmRouteEngine(string json)
        {
            _json = json;
        }

        public string LastPrompt { get; private set; } = "";

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            LastPrompt = request.Prompt;
            return Task.FromResult(new LlmRouteResult(
                true,
                _json,
                _json,
                request.Model,
                null,
                null,
                0,
                "",
                "",
                null,
                1,
                request.Prompt.Length,
                System.Text.Encoding.UTF8.GetByteCount(request.Prompt),
                1));
        }
    }

    private sealed class NoopWorkspaceSeeder : IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string projectRepoPath)
        {
        }
    }
}
