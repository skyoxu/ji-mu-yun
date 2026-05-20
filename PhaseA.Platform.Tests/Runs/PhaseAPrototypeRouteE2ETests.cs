using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PhaseAPrototypeRouteE2ETests
{
    [Fact]
    public async Task PrototypePlanAndNeedsFixRoutes_ShouldFlowThroughRecoverableArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var routeStateWriter = new PrototypeRouteStateWriter();
        var projectCreation = new ProjectCreationService(store, options, new ProjectRuleCatalog(), new ProjectWorkspaceSeeder(options), routeStateWriter);

        var created = await projectCreation.CreateProjectAsync(
            accountId,
            new ProjectCreationRequest("route-e2e", "Route E2E RPG", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);

        File.Exists(Path.Combine(project!.RepoPath, "README.md")).Should().BeTrue();
        File.ReadAllText(Path.Combine(project.RepoPath, "README.md")).Should().Contain(project.ProjectId);

        var prototypeRunner = new PrototypeWorkflowRunner();
        var prototypeWorkflow = new PrototypeWorkflowService(
            store,
            options,
            prototypeRunner,
            new PrototypeRecordWriter(options),
            new PrototypeWorkflowCommandBuilder(options),
            new PrototypeArtifactIndexer(),
            new LlmBindingService(store, options),
            new LlmStopLossService(store, options),
            new ProjectWorkspaceSeeder(options),
            new GameTypeTemplateCatalog(options),
            routeStateWriter);
        var prototype = await prototypeWorkflow.RunAsync(project.ProjectId, PrototypeRequest());
        prototype.Status.Should().Be("succeeded");
        routeStateWriter.ReadLatestPrototypeState(project).Should().Contain(prototype.RunId);

        var planService = new PrototypeIterationPlanService(store, routeStateWriter);
        var plan = await planService.CreateAsync(
            accountId,
            project.ProjectId,
            new PrototypeIterationPlanRequest("First stabilize map movement. Then complete the first encounter. Finally clarify the victory condition."));
        plan.Status.Should().Be("ready");
        routeStateWriter.ReadLatestPrototypeState(project).Should().Contain(prototype.RunId);
        File.ReadAllText(Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json")).Should().Contain(plan.SessionId);

        var iterationRunner = new IterationNeedsFixRunner();
        var iterationGoalService = new PrototypeIterationGoalService(store, options, iterationRunner);
        var executed = await iterationGoalService.ExecuteNextAsync(accountId, project.ProjectId);
        executed.Status.Should().Be("needs_fix");
        executed.SessionStatus.Should().Be("needs_fix");

        var details = await store.GetLatestProjectIterationSessionAsync(project.ProjectId);
        var blockedGoal = details!.Goals.Single(goal => goal.Status == "needs_fix");
        var needsFixRunner = new NeedsFixCompletedRunner();
        var needsFixRoute = new PrototypeNeedsFixRouteService(
            store,
            new PrototypeQuickFixService(store, options, needsFixRunner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog()),
            routeStateWriter);

        var fixedResult = await needsFixRoute.RunAsync(
            accountId,
            project.ProjectId,
            new PrototypeNeedsFixRouteRequest("Repair this step.", "gpt-5.4", "normal", blockedGoal.GoalId, blockedGoal.GoalIndex));

        fixedResult.Status.Should().Be("completed");
        fixedResult.IterationGoalStatus.Should().Be("succeeded");
        routeStateWriter.ReadLatestNeedsFixState(project, blockedGoal.GoalIndex).Should().Contain(fixedResult.RunId);
        needsFixRunner.Prompt.Should().Contain("Project README:");
        needsFixRunner.Prompt.Should().Contain("Prototype route state");
        needsFixRunner.Prompt.Should().Contain(project.ProjectId);

        var refreshed = await store.GetLatestProjectIterationSessionAsync(project.ProjectId);
        refreshed!.Goals.Single(goal => goal.GoalId == blockedGoal.GoalId).Status.Should().Be("succeeded");
        refreshed.Session.Status.Should().Be("paused_for_review");
    }

    private static PrototypeWorkflowRequest PrototypeRequest()
    {
        return new PrototypeWorkflowRequest(
            Slug: "route-e2e-rpg",
            GameName: "Route E2E RPG",
            GameType: "rpg",
            GameTypeSource: "RPG",
            Hypothesis: "A tiny RPG loop can prove the fantasy.",
            CorePlayerFantasy: "The player can move, trigger an encounter, and understand the goal.",
            MinimumPlayableLoop: "Move on map, enter encounter, win or lose.",
            SuccessCriteria: ["Player reaches the encounter.", "Outcome is clear."],
            GameFeature: "RPG first encounter.",
            CoreGameplayLoop: "Move, encounter, resolve, return.",
            WinFailConditions: "Win after one successful encounter; fail when defeated.",
            Confirm: true);
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

    private sealed class PrototypeWorkflowRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (marker)\n", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn\n", ""));
            }

            Write(command.WorkingDirectory, "docs/prototypes/route-e2e-rpg.prototype.json", """
{
  "prototype_type_kit": {
    "manifest": {
      "paths": {
        "default_scene": "res://Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn"
      }
    }
  }
}
""");
            Write(command.WorkingDirectory, "Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn", "[gd_scene format=3]\n");
            Write(command.WorkingDirectory, "logs/ci/project-health/latest.html", "<html></html>");
            Write(command.WorkingDirectory, "logs/ci/project-health/latest.json", "{}");
            Write(command.WorkingDirectory, "logs/ci/active-prototypes/route-e2e-rpg.completion.md", "# Prototype Completion Report\n");
            Write(command.WorkingDirectory, "logs/ci/active-prototypes/route-e2e-rpg.packaging.json", """
{
  "kind": "prototype-packaging-summary",
  "default_scene": "res://Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn",
  "tdd_stage_counts": { "red": 1, "green": 1, "refactor": 1 }
}
""");
            Write(command.WorkingDirectory, "logs/ci/active-prototypes/route-e2e-rpg.active.json", """
{
  "status": "completed-through-day",
  "completed_through_day": 7,
  "missing_required_fields": [],
  "prototype_spec": "docs/prototypes/route-e2e-rpg.prototype.json",
  "completion_summary": "Prototype route finished. Next step: stabilize the first encounter.",
  "steps_run": [
    { "day": 1, "status": "ok" },
    { "day": 2, "status": "ok" },
    { "day": 3, "status": "ok" },
    { "day": 4, "status": "ok" },
    { "day": 5, "status": "ok" },
    { "day": 6, "status": "ok" },
    { "day": 7, "status": "ok" }
  ]
}
""");
            return Task.FromResult(new HostedProcessResult(0, "prototype workflow ok\n", ""));
        }
    }

    private sealed class IterationNeedsFixRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: The first goal still needs route repair.
CHANGED: Found the blocker.
VERIFY: Needs-fix route should repair it.
REMAINING: Run needs-fix for this step.
""");
            return Task.FromResult(new HostedProcessResult(0, "iteration needs fix", ""));
        }
    }

    private sealed class NeedsFixCompletedRunner : IHostedProcessRunner
    {
        public string Prompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Prompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Current step is ready to continue.
CHANGED: Repaired the current step.
VERIFY: Current step verification passed.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "needs fix completed", ""));
        }
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
