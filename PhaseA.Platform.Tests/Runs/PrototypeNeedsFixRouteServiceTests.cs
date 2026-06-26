using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeNeedsFixRouteServiceTests
{
    [Fact]
    public async Task RunAsync_ShouldUseProjectLevelNeedsFix_WhenNoCurrentRepairGoalExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var fakeGodotBin = Path.Combine(workspaceRoot.Path, "fake-godot.exe");
        await File.WriteAllTextAsync(fakeGodotBin, "");
        var options = Options(workspaceRoot.Path, repoRoot.Path, fakeGodotBin);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectService = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await projectService.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        var readmePath = Path.Combine(project!.RepoPath, "README.md");
        await File.WriteAllTextAsync(readmePath, "PROJECT_README_NATURAL_LANGUAGE_CONTEXT keep this sentence.\n" + await File.ReadAllTextAsync(readmePath));
        var smokeScenePath = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(smokeScenePath)!);
        await File.WriteAllTextAsync(smokeScenePath, "[gd_scene format=3]\n[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n");
        writer.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            status = "needs_fix",
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var plan = TestRpgIterationPlanServiceFactory.Create(store);
        await plan.CreateAsync(accountId, created.ProjectId!, new PrototypeIterationPlanRequest("1. Stabilize map movement\n2. Finish battle"));
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, created.ProjectId!, new PrototypeNeedsFixRouteRequest(Feedback: "Godot error"));

        result.Status.Should().Be("completed");
        result.RunId.Should().NotBeEmpty();
        result.GoalIndex.Should().Be(0);
        var details = await store.GetLatestProjectIterationSessionAsync(created.ProjectId!);
        details!.Goals[0].Status.Should().Be("pending");
        runner.Prompt.Should().Contain("project-level runtime issue");
        runner.Prompt.Should().Contain("Do not generate or rewrite the iteration plan.");
        runner.Prompt.Should().Contain("Full contract block is supplied by the outer quick-fix prompt");
        runner.Prompt.Should().Contain("PROJECT_README_NATURAL_LANGUAGE_CONTEXT");
        runner.Prompt.Should().NotContain("Mandatory: the JSON below is the per-project hard contract");
    }

    [Fact]
    public async Task RunAsync_ShouldRequirePrototypeState_WhenNoNeedsFixStateExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, new SuccessRunner()), new PrototypeRouteStateWriter());

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1));

        result.Status.Should().Be("prototype_required");
        result.RunId.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_ShouldConsumeCurrentStepState_AndPersistNeedsFixRouteState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        var contract = new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        writer.WriteProjectExecutionGuide(project!, contract, "docs/prototypes/2026-05-20-contract.md", "contract", "prototype-7day-playable", "prototype-run", "succeeded");
        File.Exists(Path.Combine(project!.RepoPath, "meta", "routes", "prototype-contract", "latest.json"))
            .Should().BeTrue();
        writer.WriteNeedsFixState(project!, 1, new
        {
            route = "needs-fix",
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            marker = "current-step-only",
            summary = string.Concat(Enumerable.Repeat("nested-old-prompt ", 800))
        });
        writer.WriteNeedsFixState(project!, 2, new { route = "needs-fix", goal_index = 2, marker = "wrong-step" });
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        result.Status.Should().Be("needs_fix");
        result.Summary.Should().Contain("完成报告");
        result.Summary.Should().Contain("STATUS: completed");
        result.Summary.Should().NotContain("Project README:");
        result.Summary.Should().NotContain("Recovery source consumed:");
        result.Summary.Should().NotContain("Direction lock:");
        result.Summary.Should().NotContain("Current goal:");
        runner.Prompt.Should().Contain("current needs fix step state");
        runner.Prompt.Should().NotContain("wrong-step");
        runner.Prompt.Length.Should().BeLessThan(24000);
        runner.Prompt.Should().Contain("Project README、Project Execution Guide 和恢复来源只作为只读恢复上下文，不是修复目标。");
        runner.Prompt.Should().Contain("Project Execution Guide");
        runner.Prompt.Should().Contain("Route Recovery Protocol");
        runner.Prompt.Should().Contain("使用 Prototype Chapter 6 Lite 语义");
        runner.Prompt.Should().Contain("正式验收文件");
        runner.Prompt.Should().Contain("如果最新平台验收阻塞是 core_tests_failed");
        runner.Prompt.Should().Contain("缺少 Xunit/FluentAssertions/package references");
        runner.Prompt.Should().Contain("先修托管测试项目/包/引用文件");
        runner.Prompt.Should().Contain("平台路由或恢复测试通过，不代表玩法任务已经完成。");
        runner.Prompt.Should().Contain("Project prototype contract");
        runner.Prompt.Should().Contain("Every movement increases encounter probability by 10% and encounter must happen within 10 steps.");
        runner.Prompt.Should().Contain("First enemy has 30 HP and 5 ATK.");
        writer.ReadLatestNeedsFixState(project!, 1).Should().Contain(result.RunId);
        writer.ReadLatestNeedsFixState(project!, 1).Should().Contain("prototype_contract");
        writer.ReadLatestNeedsFixState(project!, 1).Should().Contain("project_execution_guide");
        File.ReadAllText(Path.Combine(project!.RepoPath, "meta", "routes", "needs-fix", "step-01", "latest.json"))
            .Should().Contain(result.RunId);
    }

    [Fact]
    public async Task RunAsync_ShouldCompactOversizedRecoverySourcesBeforeQuickFixPrompt()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        var contract = new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        writer.WriteProjectExecutionGuide(project!, contract, "docs/prototypes/2026-05-20-contract.md", "contract", "prototype-7day-playable", "prototype-run", "succeeded");
        File.AppendAllText(
            Path.Combine(project!.RepoPath, PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath.Replace('/', Path.DirectorySeparatorChar)),
            "\nGUIDE_BULK_MARKER " + string.Concat(Enumerable.Repeat("GUIDE_BULK_CONTEXT ", 1600)));
        writer.WriteNeedsFixState(project!, 1, new
        {
            route = "needs-fix",
            status = "needs_fix",
            run_id = "previous-run",
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            summary = string.Concat(Enumerable.Repeat("STATE_BULK_CONTEXT ", 1600)),
            godot_smoke_validation = new
            {
                required = true,
                passed = false,
                smoke = new
                {
                    reason = "prototype_smoke_scene_missing",
                    scene = "res://Game.Godot/Prototypes/prototype/PrototypePrototype.tscn"
                }
            },
            prototype_completion = new
            {
                succeeded = false,
                error = "prototype_completion_state_missing",
                smoke_scene = "res://Game.Godot/Prototypes/prototype/PrototypePrototype.tscn"
            }
        });
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "keep current smoke blocker"));

        runner.Prompt.Should().Contain("prototype_smoke_scene_missing");
        runner.Prompt.Should().Contain("prototype_completion_state_missing");
        runner.Prompt.Should().Contain("res://Game.Godot/Prototypes/prototype/PrototypePrototype.tscn");
        runner.Prompt.Should().Contain("Every movement increases encounter probability by 10% and encounter must happen within 10 steps.");
        runner.Prompt.Should().NotContain("GUIDE_BULK_MARKER");
        runner.Prompt.Should().NotContain(string.Concat(Enumerable.Repeat("STATE_BULK_CONTEXT ", 40)));
        runner.Prompt.Length.Should().BeLessThan(32000);
    }

    [Fact]
    public async Task RunAsync_ShouldOmitInvalidSmokeSceneFromCompactRouteState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        using var outsideRoot = TempDirectory.Create("phase-a-outside");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        var contract = new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        writer.WriteProjectExecutionGuide(project!, contract, "docs/prototypes/2026-05-20-contract.md", "contract", "prototype-7day-playable", "prototype-run", "succeeded");
        var externalScenePath = Path.Combine(outsideRoot.Path, "ExternalPrototype.tscn");
        File.WriteAllText(externalScenePath, "[gd_scene format=3]\n[node name=\"External\" type=\"Node\"]\n");
        var escapedScene = Path.GetRelativePath(project!.RepoPath, externalScenePath).Replace('\\', '/');
        writer.WriteNeedsFixState(project!, 1, new
        {
            route = "needs-fix",
            status = "needs_fix",
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            prototype_completion = new
            {
                succeeded = false,
                smoke_scene = $"res://{escapedScene}"
            }
        });
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "keep current blocker"));

        runner.Prompt.Should().Contain("invalid_scene_omitted");
        runner.Prompt.Should().NotContain("ExternalPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldConsumeExecuteNextGoalState_WhenNeedsFixStateIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, new
        {
            route = "execute-next-goal",
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            marker = "execute-next-current-step"
        });
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        result.Status.Should().Be("needs_fix");
        runner.Prompt.Should().Contain("current execute next goal step state");
        runner.Prompt.Should().Contain("\"route\":\"execute-next-goal\"");
        runner.Prompt.Should().NotContain("prototype-fallback");
    }

    [Fact]
    public async Task RunAsync_ShouldIgnoreLegacyNeedsFixState_WhenCurrentExecuteNextGoalStateExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteNeedsFixState(project!, 1, new
        {
            route = "needs-fix",
            step = 1,
            status = "completed",
            goal_title = "legacy skeleton repair",
            summary = "old completed skeleton repair"
        });
        writer.WriteNeedsFixRepairLedger(project!, 1, new
        {
            route = "needs-fix-repair-ledger",
            step = 1,
            status = "completed",
            source_failure = "old skeleton failure"
        });
        writer.WriteExecuteNextGoalState(project!, 1, new
        {
            route = "execute-next-goal",
            session_id = details!.Session.SessionId,
            goal_id = details.Goals[0].GoalId,
            goal_index = 1,
            summary = "current-execute-state"
        });
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().Contain("current execute next goal step state");
        runner.Prompt.Should().Contain("current-execute-state");
        runner.Prompt.Should().NotContain("legacy skeleton repair");
        runner.Prompt.Should().NotContain("old skeleton failure");
    }

    [Fact]
    public async Task RunAsync_ShouldIgnoreLegacyNeedsFixState_WhenExecuteNextGoalStateIsStale()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteNeedsFixState(project!, 1, new
        {
            route = "needs-fix",
            step = 1,
            status = "needs_fix",
            summary = "legacy-current-needs-fix"
        });
        writer.WriteExecuteNextGoalState(project!, 1, new
        {
            route = "execute-next-goal",
            session_id = "old-session",
            goal_id = "old-goal",
            goal_index = 1,
            summary = "stale-execute-state"
        });
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().NotContain("current needs fix step state");
        runner.Prompt.Should().NotContain("legacy-current-needs-fix");
        runner.Prompt.Should().NotContain("stale-execute-state");
        runner.Prompt.Should().Contain("prototype route state");
        runner.Prompt.Should().Contain("\"route\":\"prototype-7day-playable\"");
    }

    [Fact]
    public async Task RunAsync_ShouldAutoCreateProjectExecutionGuide_ForLegacyProject()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "legacy-rpg");
        writer.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            run_id = "legacy-prototype-run",
            status = "succeeded",
            prototype_record = "docs/prototypes/2026-05-20-contract.md",
            slug = "legacy-rpg"
        });
        writer.WriteExecuteNextGoalState(project!, 1, new { route = "execute-next-goal", goal_index = 1, marker = "legacy-execute-state" });
        var guidePath = Path.Combine(project!.RepoPath, PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (File.Exists(guidePath))
        {
            File.Delete(guidePath);
        }

        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        File.Exists(guidePath).Should().BeTrue();
        var guide = File.ReadAllText(guidePath);
        guide.Should().Contain("Slug: legacy-rpg");
        guide.Should().Contain("LatestRunId: legacy-prototype-run");
        runner.Prompt.Should().Contain("Project Execution Guide");
        runner.Prompt.Should().Contain("Route Recovery Protocol");
    }

    [Fact]
    public async Task RunAsync_ShouldKeepCurrentUserFeedbackInNeedsFixPrompt_WhenHistoryIsLarge()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        var contract = new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "legacy-rpg");
        writer.WriteProjectExecutionGuide(project!, contract, "docs/prototypes/2026-05-20-contract.md", "contract", "prototype-7day-playable", "prototype-run", "succeeded");
        writer.WriteNeedsFixState(project!, 1, new
        {
            route = "needs-fix",
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            marker = "step-state",
            summary = string.Concat(Enumerable.Repeat("step-state-bulk ", 1800))
        });
        writer.WriteNeedsFixRepairLedger(project!, 1, new
        {
            stepIndex = 1,
            currentStatus = "needs_fix",
            openBlockers = new[]
            {
                new
                {
                    id = "godot_smoke:prototype-main-menu-navigation-failed",
                    source = "godot_smoke",
                    reason = "prototype_main_menu_navigation_failed",
                    details = string.Concat(Enumerable.Repeat("ledger-bulk-context ", 1600)),
                    first_seen_run_id = "previous-run",
                    last_seen_run_id = "previous-run",
                    first_seen_utc = "2026-06-03T00:00:00+00:00",
                    last_seen_utc = "2026-06-03T00:00:00+00:00",
                    priority = 3,
                    suggested_fix = string.Concat(Enumerable.Repeat("ledger-fix-bulk ", 1200))
                }
            },
            resolvedBlockers = Array.Empty<object>(),
            newBlockersThisRun = Array.Empty<object>(),
            lastRun = new
            {
                runId = "previous-run",
                assistantClaimedStatus = "completed",
                platformStatus = "needs_fix",
                acceptedByPlatform = false
            },
            updatedUtc = "2026-06-03T00:00:00+00:00"
        });
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);
        var feedback = string.Concat(Enumerable.Repeat("leading-noise ", 900)) + "KEEP_CURRENT_BLOCKER prototype_main_menu_navigation_failed";

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: feedback));

        runner.Prompt.Should().Contain("KEEP_CURRENT_BLOCKER prototype_main_menu_navigation_failed");
        runner.Prompt.Should().Contain("step-state-bulk");
        runner.Prompt.Should().Contain("prototype_main_menu_navigation_failed");
        runner.Prompt.Should().Contain("[truncated ");
    }

    [Fact]
    public async Task ReadOrCreateProjectExecutionGuide_ShouldNotCreate_WhenNoRecoverySourceExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectService = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await projectService.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Empty Guide Guard", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var writer = new PrototypeRouteStateWriter();
        var guidePath = Path.Combine(project!.RepoPath, PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath.Replace('/', Path.DirectorySeparatorChar));

        var guide = writer.ReadOrCreateProjectExecutionGuide(project, new PrototypeContractSnapshot("routes/prototype-contract/latest.json", ""));

        guide.Should().BeEmpty();
        File.Exists(guidePath).Should().BeFalse();
    }

    [Fact]
    public async Task RunAsync_ShouldExposeNeedsFixStatus_WhenGoalRepairStillNeedsFix()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));
        var state = writer.ReadLatestNeedsFixState(project!, 1);

        result.Status.Should().Be("needs_fix");
        result.IterationGoalStatus.Should().Be("needs_fix");
        details!.Goals[0].Status.Should().Be("needs_fix");
        state.Should().Contain("\"status\": \"needs_fix\"");
        state.Should().Contain("\"iteration_goal_status\": \"needs_fix\"");
    }

    [Fact]
    public async Task RunAsync_ShouldInjectPreviousPlatformRejection_AsAuthoritativeBlocker()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var previousRunId = await store.CreateRunAsync(projectId, null, "prototype-quick-fix");
        await store.MarkRunStartedAsync(previousRunId);
        await store.CompleteRunAsync(previousRunId, "completed", 0, "assistant said completed", "", """
            {
              "goal_repair_status": "needs_fix",
              "acceptance_validation_status": "failed",
              "acceptance_validation_reason": "core_tests_failed",
              "acceptance_validation_details": "Game.Core.Tests/Domain/GameConfigTests.cs(1,7): error CS0246: The type or namespace name 'FluentAssertions' could not be found. Game.Core.Tests/Domain/PlayerTests.cs(2,7): error CS0246: The type or namespace name 'Xunit' could not be found.",
              "mutation_guard": { "status": "passed", "reason": null, "violations": [] },
              "godot_smoke_validation": { "required": false, "ran": false, "passed": true, "reason": "not_required" },
              "rpg_gdunit_validation": {
                "required": true,
                "ran": true,
                "passed": false,
                "reason": "reward_text_mismatch",
                "gdunit_path": "tests/Prototype/TowerdemoPrototype",
                "report_dir": "logs/e2e/2026-06-26/gdunit-towerdemo-prototype",
                "attempted_gdunit_paths": ["tests/Prototype/TowerdemoPrototype", "tests/Prototype/DqRpgPrototype"]
              }
            }
            """);
        await store.LinkProjectIterationGoalRunAsync(details.Session.SessionId, goal.GoalId, previousRunId, "prototype-iteration-goal-repair");
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().Contain("上一轮平台拒绝：");
        runner.Prompt.Should().Contain(previousRunId);
        runner.Prompt.Should().Contain("GoalRepairStatus: needs_fix");
        runner.Prompt.Should().Contain("PlatformAcceptanceReason: core_tests_failed");
        runner.Prompt.Should().Contain("FluentAssertions");
        runner.Prompt.Should().Contain("Xunit");
        runner.Prompt.Should().Contain("MutationGuard: passed");
        runner.Prompt.Should().Contain("RpgGdUnit: required=True; ran=True; passed=False; reason=reward_text_mismatch");
        runner.Prompt.Should().Contain("gdunit_path=tests/Prototype/TowerdemoPrototype");
        runner.Prompt.Should().Contain("attempted_gdunit_paths=[tests/Prototype/TowerdemoPrototype, tests/Prototype/DqRpgPrototype]");
        runner.Prompt.Should().Contain("report_dir=logs/e2e/2026-06-26/gdunit-towerdemo-prototype");
        runner.Prompt.Should().Contain("RepairFocus: Only repair the core test project dependency failure first");
        runner.Prompt.Should().Contain("Game.Core.Tests/Game.Core.Tests.csproj PackageReference");
        runner.Prompt.Should().Contain("Do not delete tests");
        runner.Prompt.Should().Contain("Treat this platform rejection as prior evidence");
        runner.Prompt.Should().Contain("当前平台验收结果优先于上一轮拒绝和修复台账");
        runner.Prompt.Should().Contain("任务修复台账：");
        runner.Prompt.Should().Contain("Forbidden detours");
    }

    [Fact]
    public async Task RunAsync_ShouldUseDerivedPlatformAcceptanceReason_WhenValidationDidNotRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var previousRunId = await store.CreateRunAsync(projectId, null, "prototype-quick-fix");
        await store.MarkRunStartedAsync(previousRunId);
        await store.CompleteRunAsync(previousRunId, "completed", 0, "assistant said completed", "", """
            {
              "goal_repair_status": "needs_fix",
              "acceptance_validation_status": "not_run",
              "acceptance_validation_reason": null,
              "acceptance_validation_details": null,
              "goal_repair_platform_acceptance_reason": "platform_acceptance_not_run_for_rpg_goal",
              "mutation_guard": { "status": "passed", "reason": null, "violations": [] },
              "godot_smoke_validation": { "required": false, "ran": false, "passed": true, "reason": "not_required" },
              "rpg_gdunit_validation": { "required": false, "ran": false, "passed": true, "reason": "not_required" }
            }
            """);
        await store.LinkProjectIterationGoalRunAsync(details.Session.SessionId, goal.GoalId, previousRunId, "prototype-iteration-goal-repair");
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().Contain("PlatformAcceptanceStatus: not_run");
        runner.Prompt.Should().Contain("PlatformAcceptanceReason: platform_acceptance_not_run_for_rpg_goal");
        runner.Prompt.Should().NotContain("PlatformAcceptanceReason: unknown");
        runner.Prompt.Should().Contain("RepairFocus: Repair the listed platform blocker first");
    }

    [Fact]
    public async Task RunAsync_ShouldKeepFlatAcceptanceValidationInCompactRouteState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, new
        {
            route = "execute-next-goal",
            status = "needs_fix",
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            acceptance_validation_status = "failed",
            acceptance_validation_reason = "missing_rpg_map_entry_contract",
            acceptance_validation_details = "missing_file=Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs"
        });
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().Contain("\"acceptance_validation_status\":\"failed\"");
        runner.Prompt.Should().Contain("\"acceptance_validation_reason\":\"missing_rpg_map_entry_contract\"");
        runner.Prompt.Should().Contain("missing_file=Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs");
    }

    [Fact]
    public async Task RunAsync_ShouldInjectCoreCompileFailureRepairFocus()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var previousRunId = await store.CreateRunAsync(projectId, null, "prototype-quick-fix");
        await store.MarkRunStartedAsync(previousRunId);
        await store.CompleteRunAsync(previousRunId, "completed", 0, "assistant said completed", "", """
            {
              "goal_repair_status": "needs_fix",
              "acceptance_validation_status": "failed",
              "acceptance_validation_reason": "core_tests_failed",
              "acceptance_validation_details": "Game.Core/Prototypes/DqRpgPrototypeLoop.cs(202,99): error CS1061: 'DqRpgPrototypeState' does not contain a definition for 'PlayerX'. Game.Core/Prototypes/DqRpgPrototypeLoop.cs(202,116): error CS1061: 'DqRpgPrototypeState' does not contain a definition for 'PlayerY'.",
              "mutation_guard": { "status": "passed", "reason": null, "violations": [] },
              "godot_smoke_validation": { "required": false, "ran": false, "passed": true, "reason": "not_required" },
              "rpg_gdunit_validation": { "required": false, "ran": false, "passed": true, "reason": "not_required" }
            }
            """);
        await store.LinkProjectIterationGoalRunAsync(details.Session.SessionId, goal.GoalId, previousRunId, "prototype-iteration-goal-repair");
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().Contain("RepairFocus: Only repair the C# compile errors named in PlatformAcceptanceDetails first");
        runner.Prompt.Should().Contain("Game.Core/Prototypes/DqRpgPrototypeLoop.cs");
        runner.Prompt.Should().Contain("PlayerX/PlayerY");
        runner.Prompt.Should().Contain("before any gameplay/UI/content polish");
    }

    [Fact]
    public async Task RunAsync_ShouldInjectMapEntryContractGroupRepairFocus()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var previousRunId = await store.CreateRunAsync(projectId, null, "prototype-quick-fix");
        await store.MarkRunStartedAsync(previousRunId);
        await store.CompleteRunAsync(previousRunId, "completed", 0, "assistant said completed", "", """
            {
              "goal_repair_status": "needs_fix",
              "acceptance_validation_status": "failed",
              "acceptance_validation_reason": "missing_rpg_map_entry_contract",
              "acceptance_validation_details": "missing_file=Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs",
              "mutation_guard": { "status": "passed", "reason": null, "violations": [] },
              "godot_smoke_validation": { "required": false, "ran": false, "passed": true, "reason": "not_required" },
              "rpg_gdunit_validation": { "required": false, "ran": false, "passed": true, "reason": "not_required" }
            }
            """);
        await store.LinkProjectIterationGoalRunAsync(details.Session.SessionId, goal.GoalId, previousRunId, "prototype-iteration-goal-repair");
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().Contain("PlatformAcceptanceReason: missing_rpg_map_entry_contract");
        runner.Prompt.Should().Contain("missing_file=Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs");
        runner.Prompt.Should().Contain("RepairFocus: Repair the full RPG/JRPG map-entry contract group");
        runner.Prompt.Should().Contain("MapScene.tscn and Scripts/MapScene.cs exist together");
        runner.Prompt.Should().Contain("stable movement handling");
        runner.Prompt.Should().Contain("Add RpgEnemyAsset or encounter trigger wiring only when");
        runner.Prompt.Should().NotContain("RpgPlayerAsset/RpgEnemyAsset, and MapScene.cs exposes");
    }

    [Fact]
    public async Task RunAsync_ShouldPersistAndReuseStepRepairLedger()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        var firstRunner = new GoalRepairPackageFailureRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, firstRunner), writer);

        var firstResult = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));
        var ledger = writer.ReadNeedsFixRepairLedger(project!, 1);

        firstResult.IterationGoalStatus.Should().Be("needs_fix");
        ledger.Should().Contain(firstResult.RunId);
        ledger.Should().Contain("platform_acceptance:missing-required-core-markers-missing-marker-objective-missing-marker-start-adventure");
        ledger.Should().Contain("missing_marker=Objective");
        ledger.Should().Contain("missing_marker=Start Adventure");
        ledger.Should().Contain("Add or restore the exact required markers");
        writer.ReadLatestNeedsFixState(project!, 1).Should().Contain("repair_ledger_path");

        var secondRunner = new NeedsFixRunner();
        route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, secondRunner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step again"));

        secondRunner.Prompt.Should().Contain("任务修复台账：");
        secondRunner.Prompt.Should().Contain("platform_acceptance:missing-required-core-markers-missing-marker-objective-missing-marker-start-adventure");
        secondRunner.Prompt.Should().Contain("missing_marker=Objective");
        secondRunner.Prompt.Should().Contain("missing_marker=Start Adventure");
        secondRunner.Prompt.Should().Contain("Add or restore the exact required markers");
        secondRunner.Prompt.Should().Contain("Current platform acceptance diagnosis overrides the ledger when they differ");
        secondRunner.Prompt.Should().Contain("continuity memory");
    }

    [Fact]
    public async Task RunAsync_ShouldNormalizeLegacyGodotSmokeLedgerReason()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        writer.WriteNeedsFixRepairLedger(project!, 1, new
        {
            stepIndex = 1,
            currentStatus = "needs_fix",
            openBlockers = new[]
            {
                new
                {
                    id = "godot_smoke:unknown",
                    source = "godot_smoke",
                    reason = "unknown",
                    details = "{\"required\":true,\"passed\":false,\"smoke\":{\"ran\":true,\"exit_code\":1,\"reason\":\"prototype_main_menu_navigation_failed\",\"scene\":\"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn\",\"diagnostic_excerpt\":\"ERROR: No loader found for resource: res://Game.Godot/Prototypes/dq-rpg/Assets/map_player.png\"}}",
                    first_seen_run_id = "previous-run",
                    last_seen_run_id = "previous-run",
                    first_seen_utc = "2026-06-03T00:00:00+00:00",
                    last_seen_utc = "2026-06-03T00:00:00+00:00",
                    priority = 3,
                    suggested_fix = "Fix the concrete Godot smoke/runtime validation error named by the validation evidence."
                }
            },
            resolvedBlockers = Array.Empty<object>(),
            newBlockersThisRun = Array.Empty<object>(),
            lastRun = new
            {
                runId = "previous-run",
                assistantClaimedStatus = "completed",
                platformStatus = "needs_fix",
                acceptedByPlatform = false
            },
            updatedUtc = "2026-06-03T00:00:00+00:00"
        });
        var runner = new NeedsFixRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        runner.Prompt.Should().Contain("godot_smoke:prototype-main-menu-navigation-failed");
        runner.Prompt.Should().Contain("prototype_main_menu_navigation_failed");
        runner.Prompt.Should().Contain("map_player.png");
        runner.Prompt.Should().Contain("Restore or copy the exact missing Godot resource files named in diagnostic_excerpt");
        runner.Prompt.Should().NotContain("godot_smoke:unknown");
    }

    [Fact]
    public async Task RunAsync_ShouldNotTreatNotRequiredMutationGuardAsRepairLedgerBlocker()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(
            store,
            options,
            accountId,
            prototypeSucceeded: true,
            gameTypeSource: "Action");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var goal = details!.Goals[0];
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, CurrentExecuteNextState(goal));
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "finish current step"));
        var ledger = writer.ReadNeedsFixRepairLedger(project!, 1);

        result.IterationGoalStatus.Should().Be("succeeded");
        ledger.Should().Contain("\"currentStatus\": \"succeeded\"");
        ledger.Should().NotContain("mutation_guard:not-specialized-prototype-project");
        ledger.Should().NotContain("not_specialized_prototype_project");
    }

    private static async Task<string> CreateProjectWithNeedsFixGoalAsync(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        string accountId,
        bool prototypeSucceeded,
        string gameTypeSource = "RPG")
    {
        var projectService = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await projectService.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameTypeSource, null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        if (prototypeSucceeded)
        {
            var runId = await store.CreateRunAsync(created.ProjectId!, null, "prototype-7day-playable");
            await store.MarkRunStartedAsync(runId);
            await store.CompleteRunAsync(runId, "succeeded", 0, "prototype ok", "", "{}");
        }

        var plan = TestRpgIterationPlanServiceFactory.Create(store);
        await plan.CreateAsync(accountId, created.ProjectId!, new PrototypeIterationPlanRequest("1. Stabilize map movement\n2. Finish battle"));
        var details = await store.GetLatestProjectIterationSessionAsync(created.ProjectId!);
        await store.UpdateProjectIterationGoalStatusAsync(
            details!.Goals[0].GoalId,
            "needs_fix",
            "still blocked\nProject README:\n" + string.Concat(Enumerable.Repeat("old nested prompt ", 800)),
            null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "goal 1 needs fix");
        return created.ProjectId!;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot, string? godotBin = null)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["GODOT_BIN"] = godotBin
        });
    }

    private static object CurrentExecuteNextState(ProjectIterationGoalSnapshot goal, string marker = "execute-next-current-step")
    {
        return new
        {
            route = "execute-next-goal",
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            marker
        };
    }

    private static PrototypeWorkflowRequest ContractRequest()
    {
        return new PrototypeWorkflowRequest(
            Slug: "contract",
            GameName: "Contract RPG",
            GameType: "rpg",
            GameTypeSource: "RPG",
            Hypothesis: "Project-specific form values must drive the RPG prototype.",
            CorePlayerFantasy: "Explore, encounter enemies, and grow through rewards.",
            MinimumPlayableLoop: "Move on map, trigger encounter, win battle, choose reward, return to map.",
            SuccessCriteria: ["Contract values are implemented."],
            GameFeature: "Every movement increases encounter probability by 10% and encounter must happen within 10 steps.",
            CoreGameplayLoop: "Player starts at 100 HP, 10 ATK, 2 DEF. First enemy has 30 HP and 5 ATK.",
            WinFailConditions: "Win after 15 battles. Any battle loss means game loss.",
            Confirm: true);
    }

    private sealed class SuccessRunner : IHostedProcessRunner
    {
        public string Prompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (HasScriptArgument(command, "smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS", ""));
            }

            Prompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "STATUS: completed\nSUMMARY: Current step completed.\nCHANGED: gameplay\nVERIFY: quick pass\nREMAINING: none\n");
            return Task.FromResult(new HostedProcessResult(0, "ok", ""));
        }
    }

    private static bool HasScriptArgument(HostedProcessCommand command, string scriptFileName)
    {
        return command.Arguments.Any(argument =>
            string.Equals(Path.GetFileName(argument), scriptFileName, StringComparison.OrdinalIgnoreCase) ||
            argument.Replace('\\', '/').EndsWith("/" + scriptFileName, StringComparison.OrdinalIgnoreCase));
    }

    private sealed class NeedsFixRunner : IHostedProcessRunner
    {
        public string Prompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Prompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "STATUS: needs_fix\nSUMMARY: Current step still needs repair.\nCHANGED: none\nVERIFY: blocked\nREMAINING: continue fixing this step\n");
            return Task.FromResult(new HostedProcessResult(0, "ok", ""));
        }
    }

    private sealed class GoalRepairPackageFailureRunner : IHostedProcessRunner
    {
        public string Prompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Prompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "STATUS: needs_fix\nSUMMARY: Core test packages are still missing.\nCHANGED: none\nVERIFY: core tests blocked\nREMAINING: fix test PackageReference entries\n");
            return Task.FromResult(new HostedProcessResult(
                0,
                "ok",
                "Game.Core.Tests/Domain/GameConfigTests.cs(1,7): error CS0246: The type or namespace name 'FluentAssertions' could not be found. Game.Core.Tests/Domain/PlayerTests.cs(2,7): error CS0246: The type or namespace name 'Xunit' could not be found."));
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
