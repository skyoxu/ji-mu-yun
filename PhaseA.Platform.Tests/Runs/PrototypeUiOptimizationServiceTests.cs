using FluentAssertions;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeUiOptimizationServiceTests
{
    [Fact]
    public async Task RunAsync_ShouldReject_WhenIterationPlanIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("iteration_plan_not_ready");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_ShouldReject_WhenIterationPlanHasPendingGoals()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: false);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("iteration_plan_not_complete");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_ShouldUseCodexRuntimeAndReleaseRunnerLock_WhenIterationPlanIsComplete()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var runner = new FakeHostedProcessRunner();
        var issuer = new HostedContextManifestIssuer(
            store,
            new HostedContextManifestSignatureService("test-key", new Dictionary<string, string>
            {
                ["test-key"] = "test-hosted-context-signing-secret"
            }));
        var validator = new CapturingManifestValidator();
        var policy = new HostedContextGatePolicy(new Dictionary<string, HostedContextGateMode>
        {
            ["codex:prototype-ui-optimization"] = HostedContextGateMode.Enforce
        });
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            runner,
            new ProjectWorkspaceSeeder(options),
            contextManifestIssuer: issuer,
            contextGatePolicy: policy,
            contextManifestValidator: validator);

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        validator.Envelope.Should().NotBeNull();
        validator.Envelope!.AccountId.Should().Be(accountId);
        validator.Envelope.ProjectId.Should().Be(projectId);
        validator.Envelope.OperationKey.Should().Be("codex:prototype-ui-optimization");
        validator.Envelope.SignatureKeyId.Should().Be("test-key");
        validator.OperationKey.Should().Be("codex:prototype-ui-optimization");
        runner.Commands.Should().HaveCount(3);
        runner.Commands[0].Arguments.Should().Contain("--sandbox");
        runner.Commands[0].Arguments.Should().Contain("workspace-write");
        runner.Commands[0].Environment.Should().ContainKey("PHASEA_CODEX_DEFAULT_MODEL").WhoseValue.Should().Be("gpt-5.4");
        runner.Commands[0].StandardInput.Should().Contain("$prototype-rpg-ui-optimizer-zh");
        runner.Commands[0].StandardInput.Should().Contain("meta/routes/prototype-contract/latest.json");
        runner.Commands[0].StandardInput.Should().Contain("legacy fallback");
        runner.Commands[0].StandardInput.Should().Contain("the platform runs a short Godot smoke after generation exits");
        runner.Commands[0].StandardInput.Should().Contain("project.godot -> main scene -> Start Adventure");
        runner.Commands[0].StandardInput.Should().Contain("Do not leave UI optimization in an unreferenced side scene");
        runner.Commands[0].StandardInput.Should().Contain("A thin wrapper scene or a standalone visual mock");
        runner.Commands[0].StandardInput.Should().Contain("Player-visible text rule");
        runner.Commands[0].StandardInput.Should().Contain("must default to Chinese");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ProgressStep.Should().Be("succeeded");
        run.ProgressSubstep.Should().Be("completed");
        run.EvidenceJson.Should().Contain("\"timeout_seconds\":1200");
        run.EvidenceJson.Should().Contain("codex_ui_edit_only_platform_short_godot_smoke");
        run.EvidenceJson.Should().Contain("strict_headless_main_menu_navigation");
        run.LlmGateway.Should().Be("codex-cli");
        run.LlmModel.Should().Be("gpt-5.4");
        run.LlmCostJson.Should().Contain("prototype-ui-optimization");
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);
        artifacts.Should().Contain(item => item.ArtifactType == "prototype-ui-optimization-prompt");
        artifacts.Should().Contain(item => item.ArtifactType == "prototype-ui-optimization-output");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var promptArtifact = artifacts.Single(item => item.ArtifactType == "prototype-ui-optimization-prompt");
        var promptPath = Path.Combine(project!.RepoPath, promptArtifact.RelativePath.Replace('/', Path.DirectorySeparatorChar));
        File.ReadAllText(promptPath).Should().Contain("$prototype-rpg-ui-optimizer-zh");
        File.ReadAllText(promptPath).Should().Contain("meta/routes/prototype-contract/latest.json");
        File.ReadAllText(promptPath).Should().Contain("project.godot must use it as run/main_scene");
    }

    [Fact]
    public async Task RunAsync_ShouldStripBomFromGodotTextResourcesBeforeValidation()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var scenePath = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(scenePath)!);
        var sceneBytes = "\uFEFF[gd_scene format=3]\n"u8.ToArray();
        await File.WriteAllBytesAsync(scenePath, sceneBytes);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        File.ReadAllBytes(scenePath).Take(3).Should().NotEqual([0xEF, 0xBB, 0xBF]);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain("godot_text_bom_cleaned");
        run.EvidenceJson.Should().Contain("Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldFailAsValidationFailed_WhenCodexSucceedsButShortSmokeFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var runner = new FakeHostedProcessRunner(smokeExitCode: 12);
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        result.Summary.Should().Be("UI optimization changed files, but short validation failed.");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ExitCode.Should().Be(12);
        run.ProgressSubstep.Should().Be("validation_failed");
        run.EvidenceJson.Should().Contain("\"codex_exit_code\":0");
        run.EvidenceJson.Should().Contain("\"exit_code\":12");
    }

    [Fact]
    public async Task RunAsync_ShouldFailStrictValidation_WhenDirectSceneSmokeFailsButNavigationWouldPass()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var runner = new DirectSceneFailsNavigationPassesRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        result.Summary.Should().Be("UI optimization changed files, but short validation failed.");
        runner.Commands.Should().Contain(command => HasScriptArgument(command, "smoke_headless.py"));
        runner.Commands.Should().NotContain(command => HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ExitCode.Should().Be(9);
        run.EvidenceJson.Should().Contain("strict_headless_prototype_scene");
    }

    [Fact]
    public async Task RunAsync_ShouldFallbackToProjectGodotMainScene_WhenSmokeSceneIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: false);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        runner.Commands.Should().HaveCount(3);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ProgressSubstep.Should().Be("completed");
        run.EvidenceJson.Should().Contain("\"validation_required\":true");
        run.EvidenceJson.Should().Contain("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldValidateProjectGodotMainScene_BeforePrototypeEvidenceSmokeScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(
            store,
            options,
            accountId,
            seedProjectGodot: true,
            mainScene: "res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain("res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        run.EvidenceJson.Should().NotContain("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldSkipHostMainScene_AndUsePrototypeEvidenceSmokeScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(
            store,
            options,
            accountId,
            seedProjectGodot: true,
            mainScene: "res://Game.Godot/Scenes/Main.tscn");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var prototypeScenePath = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(prototypeScenePath)!);
        await File.WriteAllTextAsync(prototypeScenePath, "[gd_scene format=3]\n[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n");
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
        run.EvidenceJson.Should().NotContain("res://Game.Godot/Scenes/Main.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldParseProjectGodotMainScene_WithWhitespaceAndCase()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(
            store,
            options,
            accountId,
            seedProjectGodot: true,
            mainScene: "res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await File.WriteAllTextAsync(
            Path.Combine(project!.RepoPath, "project.godot"),
            "[application]\nRUN/MAIN_SCENE = \"res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn\"\n");
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain("res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        run.EvidenceJson.Should().NotContain("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldSkipInvalidProjectGodotMainScene_AndUseLaterValidEntry()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(
            store,
            options,
            accountId,
            seedProjectGodot: true,
            mainScene: "res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        var project = await store.GetProjectSnapshotAsync(projectId);
        await File.WriteAllTextAsync(
            Path.Combine(project!.RepoPath, "project.godot"),
            "[application]\nrun/main_scene=\"res://C:/outside/InvalidPrototype.tscn\"\nrun/main_scene=\"res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn\"\n");
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain("res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        run.EvidenceJson.Should().NotContain("InvalidPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldIgnoreEscapingPrototypeEvidenceSmokeScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        using var outsideRoot = TempDirectory.Create("phase-a-outside");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(
            store,
            options,
            accountId,
            seedProjectGodot: true,
            mainScene: "res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var mainScenePath = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgUiOptimized.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(mainScenePath)!);
        File.WriteAllText(mainScenePath, "[gd_scene format=3]\n[node name=\"DqRpgUiOptimized\" type=\"Node2D\"]\n");
        var externalScenePath = Path.Combine(outsideRoot.Path, "ExternalPrototype.tscn");
        File.WriteAllText(externalScenePath, "[gd_scene format=3]\n[node name=\"External\" type=\"Node2D\"]\n");
        var escapedScene = Path.GetRelativePath(project.RepoPath, externalScenePath).Replace('\\', '/');
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: false);
        var runId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "succeeded",
            0,
            "",
            "",
            JsonSerializer.Serialize(new
            {
                prototype_completion = new
                {
                    succeeded = true,
                    smoke_scene = externalScenePath
                },
                godot_smoke = new
                {
                    scene = $"res://{escapedScene}"
                }
            }));
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain("res://Game.Godot/Prototypes/dq-rpg/DqRpgUiOptimized.tscn");
        run.EvidenceJson.Should().NotContain("ExternalPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldPreferSucceededPrototypeRunScene_OverLaterRouteStateScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, seedProjectGodot: false);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var succeededScene = "res://Game.Godot/Prototypes/dq-rpg/SucceededPrototype.tscn";
        var laterRouteStateScene = "res://Game.Godot/Prototypes/dq-rpg/NeedsFixPrototype.tscn";
        foreach (var scene in new[] { succeededScene, laterRouteStateScene })
        {
            var scenePath = Path.Combine(project!.RepoPath, scene["res://".Length..].Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(scenePath)!);
            File.WriteAllText(scenePath, "[gd_scene format=3]\n[node name=\"Prototype\" type=\"Node2D\"]\n");
        }

        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true, smokeScene: succeededScene);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            status = "needs_fix",
            prototype_completion = new
            {
                succeeded = false,
                smoke_scene = laterRouteStateScene
            }
        });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain(succeededScene);
        run.EvidenceJson.Should().NotContain(laterRouteStateScene);
    }

    [Fact]
    public async Task RunAsync_ShouldFallbackToSucceededRun_WhenProjectGodotMainSceneIsInvalid()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(
            store,
            options,
            accountId,
            seedProjectGodot: true,
            mainScene: "res://C:/outside/InvalidPrototype.tscn");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var succeededScene = "res://Game.Godot/Prototypes/dq-rpg/SucceededPrototype.tscn";
        var scenePath = Path.Combine(project!.RepoPath, succeededScene["res://".Length..].Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(scenePath)!);
        File.WriteAllText(scenePath, "[gd_scene format=3]\n[node name=\"Prototype\" type=\"Node2D\"]\n");
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true, smokeScene: succeededScene);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain(succeededScene);
        run.EvidenceJson.Should().NotContain("InvalidPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldSkipInvalidSucceededEvidence_AndUseNextSucceededScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        using var outsideRoot = TempDirectory.Create("phase-a-outside");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, seedProjectGodot: false);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var validScene = "res://Game.Godot/Prototypes/dq-rpg/ValidPrototype.tscn";
        var validScenePath = Path.Combine(project!.RepoPath, validScene["res://".Length..].Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(validScenePath)!);
        File.WriteAllText(validScenePath, "[gd_scene format=3]\n[node name=\"Prototype\" type=\"Node2D\"]\n");
        var externalScenePath = Path.Combine(outsideRoot.Path, "ExternalPrototype.tscn");
        File.WriteAllText(externalScenePath, "[gd_scene format=3]\n[node name=\"External\" type=\"Node2D\"]\n");
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true, smokeScene: validScene);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true, smokeScene: externalScenePath);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain(validScene);
        run.EvidenceJson.Should().NotContain("ExternalPrototype.tscn");
    }

    [Fact]
    public async Task RunAsync_ShouldFailValidation_WhenSmokeSceneAndProjectGodotAreMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, seedProjectGodot: false);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: false);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        runner.Commands.Should().ContainSingle();
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ProgressSubstep.Should().Be("validation_failed");
        run.EvidenceJson.Should().Contain("\"validation_required\":true");
        run.EvidenceJson.Should().Contain("prototype_smoke_scene_missing");
    }

    [Fact]
    public async Task RunAsync_ShouldReject_WhenPrototypeSkeletonIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("prototype_skeleton_not_ready");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_ShouldMarkFailedAndReleaseRunnerLock_WhenCodexTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        AgePrototypeFiles(project!.RepoPath);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new CancelingHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromMilliseconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        result.Summary.Should().Be("UI optimization timed out.");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
        run.ProgressStep.Should().Be("failed");
        run.ProgressSubstep.Should().Be("timeout");
        run.EvidenceJson.Should().Contain("ui_optimization_codex_timeout");
        run.EvidenceJson.Should().Contain("\"timeout_seconds\":0");
    }

    [Fact]
    public async Task RunAsync_WhenUserCancelsRun_ShouldReturnCancelInsteadOfTimeout()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new UserCancelHostedProcessRunner(store, accountId),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromMinutes(20));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("cancel");
        result.Summary.Should().Be("UI optimization cancelled.");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("cancel");
        run.ExitCode.Should().Be(499);
        run.ProgressStep.Should().NotBe("failed");
        run.ProgressSubstep.Should().NotBe("timeout");
    }

    [Fact]
    public async Task RunAsync_ShouldMarkSucceeded_WhenCodexTimesOutAfterPrototypeUiEditsAndSmokePasses()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new EditingThenCancelingHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        result.Summary.Should().Be("UI optimization timed out after edits, but short validation passed.");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("succeeded");
        run.ExitCode.Should().Be(0);
        run.ProgressStep.Should().Be("succeeded");
        run.ProgressSubstep.Should().Be("completed_after_timeout");
        run.EvidenceJson.Should().Contain("ui_optimization_timeout_validated_after_cancel");
        run.EvidenceJson.Should().Contain("\"changed_files_detected\":true");
        run.LlmGateway.Should().Be("codex-cli");
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);
        artifacts.Should().Contain(item => item.ArtifactType == "prototype-ui-optimization-prompt");
        artifacts.Should().Contain(item => item.ArtifactType == "prototype-ui-optimization-output");
    }

    [Fact]
    public async Task RunAsync_ShouldMarkSucceeded_WhenCodexTimesOutAfterReferencedPrototypeScriptEditAndSmokePasses()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var scenePath = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
        var scriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "Hud.cs");
        Directory.CreateDirectory(Path.GetDirectoryName(scriptPath)!);
        await File.WriteAllTextAsync(scriptPath, "public sealed class Hud {}\n");
        await File.WriteAllTextAsync(scenePath, """
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://Game.Godot/Prototypes/dq-rpg/Scripts/Hud.cs" id="1_hud"]

[node name="DqRpgPrototype" type="Node2D"]
script = ExtResource("1_hud")
""");
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new ReferencedScriptEditingThenCancelingHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ProgressSubstep.Should().Be("completed_after_timeout");
        run.EvidenceJson.Should().Contain("Scripts/Hud.cs");
        run.EvidenceJson.Should().Contain("ui_optimization_timeout_validated_after_cancel");
    }

    [Fact]
    public async Task RunAsync_ShouldMarkSucceeded_WhenCodexTimesOutAfterProjectGodotOnlyEditAndSmokePasses()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var alternateScenePath = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "AlternatePrototype.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(alternateScenePath)!);
        await File.WriteAllTextAsync(alternateScenePath, "[gd_scene format=3]\n[node name=\"AlternatePrototype\" type=\"Node2D\"]\n");
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new ProjectGodotEditingThenCancelingHostedProcessRunner("res://Game.Godot/Prototypes/dq-rpg/AlternatePrototype.tscn"),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ProgressSubstep.Should().Be("completed_after_timeout");
        run.EvidenceJson.Should().Contain("AlternatePrototype.tscn");
        run.EvidenceJson.Should().Contain("\"changed_files_detected\":true");
        run.EvidenceJson.Should().Contain("project.godot");
    }

    [Fact]
    public async Task RunAsync_ShouldIgnoreHostProjectGodotMainSceneEdit_WhenCodexTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new ProjectGodotEditingThenCancelingHostedProcessRunner("res://Game.Godot/Scenes/Main.tscn"),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        result.Summary.Should().Be("UI optimization timed out.");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
        run.ProgressSubstep.Should().Be("timeout");
        run.EvidenceJson.Should().Contain("\"changed_files_detected\":true");
        run.EvidenceJson.Should().Contain("project.godot");
        run.EvidenceJson.Should().NotContain("ui_optimization_timeout_validated_after_cancel");
    }

    [Fact]
    public async Task RunAsync_ShouldIgnoreProjectGodotCommentOnlyEdit_WhenCodexTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new ProjectGodotCommentEditingThenCancelingHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ProgressSubstep.Should().Be("timeout");
        run.EvidenceJson.Should().Contain("project.godot");
        run.EvidenceJson.Should().NotContain("ui_optimization_timeout_validated_after_cancel");
    }

    [Fact]
    public async Task RunAsync_ShouldIgnoreUnreferencedPrototypeFileEdit_WhenCodexTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new UnreferencedPrototypeFileEditingThenCancelingHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        result.Summary.Should().Be("UI optimization timed out.");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ProgressSubstep.Should().Be("timeout");
        run.EvidenceJson.Should().Contain("UnusedUiHelper.gd");
        run.EvidenceJson.Should().NotContain("ui_optimization_timeout_validated_after_cancel");
    }

    [Fact]
    public async Task RunAsync_ShouldIgnoreHostMainSceneEdit_WhenCodexTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new HostMainSceneEditingThenCancelingHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        result.Summary.Should().Be("UI optimization timed out.");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
        run.ProgressSubstep.Should().Be("timeout");
        run.EvidenceJson.Should().Contain("ui_optimization_codex_timeout");
        run.EvidenceJson.Should().NotContain("ui_optimization_timeout_validated_after_cancel");
    }

    [Fact]
    public async Task RunAsync_ShouldUseLastValidProjectGodotMainScene_WhenDuplicateEntriesExist()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var firstScene = "res://Game.Godot/Prototypes/dq-rpg/OldPrototype.tscn";
        var lastScene = "res://Game.Godot/Prototypes/dq-rpg/NewPrototype.tscn";
        var projectId = await CreateProjectAsync(store, options, accountId, mainScene: firstScene);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var lastScenePath = Path.Combine(project!.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "NewPrototype.tscn");
        Directory.CreateDirectory(Path.GetDirectoryName(lastScenePath)!);
        await File.WriteAllTextAsync(lastScenePath, "[gd_scene format=3]\n[node name=\"NewPrototype\" type=\"Node2D\"]\n");
        await File.AppendAllTextAsync(Path.Combine(project.RepoPath, "project.godot"), $"run/main_scene=\"{lastScene}\"\n");
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: true, smokeScene: firstScene);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeUiOptimizationService(store, options, runner, new ProjectWorkspaceSeeder(options));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("succeeded");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.EvidenceJson.Should().Contain(lastScene);
    }

    [Fact]
    public async Task RunAsync_ShouldFail_WhenCodexTimesOutAfterEditsButSmokeSceneIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, seedProjectGodot: false);
        await CreateIterationPlanAsync(store, accountId, projectId, complete: true);
        await CreateSucceededPrototypeSkeletonRunAsync(store, projectId, includeSmokeScene: false);
        var service = new PrototypeUiOptimizationService(
            store,
            options,
            new EditingWithoutSceneThenCancelingHostedProcessRunner(),
            new ProjectWorkspaceSeeder(options),
            executionTimeout: TimeSpan.FromSeconds(1));

        var result = await service.RunAsync(accountId, projectId, new PrototypeUiOptimizationRequest("gpt-5.4"));

        result.Status.Should().Be("failed");
        result.Summary.Should().Be("UI optimization timed out after edits, and short validation failed.");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ProgressSubstep.Should().Be("timeout_validation_failed");
        run.EvidenceJson.Should().Contain("prototype_smoke_scene_missing");
        run.EvidenceJson.Should().Contain("\"changed_files_detected\":true");
    }

    private static async Task<string> CreateProjectAsync(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        string accountId,
        bool seedProjectGodot = true,
        string mainScene = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn")
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo RPG", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        if (seedProjectGodot)
        {
            var project = await store.GetProjectSnapshotAsync(result.ProjectId!);
            Directory.CreateDirectory(project!.RepoPath);
            await File.WriteAllTextAsync(
                Path.Combine(project.RepoPath, "project.godot"),
                $"[application]\nrun/main_scene=\"{mainScene}\"\n");
            if (mainScene.StartsWith("res://", StringComparison.OrdinalIgnoreCase) &&
                mainScene.EndsWith(".tscn", StringComparison.OrdinalIgnoreCase))
            {
                var relativeScenePath = mainScene["res://".Length..];
                if (!relativeScenePath.Contains(':', StringComparison.Ordinal) &&
                    !Path.IsPathRooted(relativeScenePath))
                {
                    var scenePath = Path.Combine(project.RepoPath, relativeScenePath.Replace('/', Path.DirectorySeparatorChar));
                    Directory.CreateDirectory(Path.GetDirectoryName(scenePath)!);
                    if (!File.Exists(scenePath))
                    {
                        await File.WriteAllTextAsync(scenePath, "[gd_scene format=3]\n[node name=\"Prototype\" type=\"Node2D\"]\n");
                    }
                }
            }
        }

        return result.ProjectId!;
    }

    private static async Task CreateIterationPlanAsync(PhaseAMetadataStore store, string accountId, string projectId, bool complete)
    {
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "manual_feedback",
            "Improve the RPG prototype.",
            "Improve the RPG prototype.",
            [
                new ProjectIterationGoalCreateCommand(1, "Improve RPG HUD", "Align HUD with RPG template.", "HUD is visible."),
                new ProjectIterationGoalCreateCommand(2, "Improve battle panel", "Align battle panel with RPG template.", "Battle panel is visible.")
            ]);

        if (!complete)
        {
            return;
        }

        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in details!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} completed.", DateTimeOffset.UtcNow.ToString("O"));
        }
    }

    private static async Task CreateSucceededPrototypeSkeletonRunAsync(
        PhaseAMetadataStore store,
        string projectId,
        bool includeSmokeScene = true,
        string smokeScene = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn")
    {
        var project = await store.GetProjectSnapshotAsync(projectId);
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        var evidence = includeSmokeScene
            ? JsonSerializer.Serialize(new
            {
                prototype_completion = new
                {
                    succeeded = true,
                    smoke_scene = smokeScene
                }
            })
            : "{\"prototype_completion\":{\"succeeded\":true}}";
        await store.CompleteRunAsync(runId, "succeeded", 0, "", "", evidence);
    }

    private static void AgePrototypeFiles(string repoPath)
    {
        var prototypesRoot = Path.Combine(repoPath, "Game.Godot", "Prototypes");
        if (!Directory.Exists(prototypesRoot))
        {
            return;
        }

        var oldTimestamp = DateTime.UtcNow.AddMinutes(-5);
        foreach (var file in Directory.EnumerateFiles(prototypesRoot, "*", SearchOption.AllDirectories))
        {
            File.SetLastWriteTimeUtc(file, oldTimestamp);
        }
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["GODOT_BIN"] = @"C:\Godot\fake-godot.exe"
        });
    }

    private static bool HasScriptArgument(HostedProcessCommand command, string scriptName)
    {
        return command.Arguments.Any(argument =>
            string.Equals(argument, scriptName, StringComparison.OrdinalIgnoreCase) ||
            argument.Replace('\\', '/').EndsWith($"/{scriptName}", StringComparison.OrdinalIgnoreCase));
    }

    private sealed class DirectSceneFailsNavigationPassesRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.Arguments.Contains("exec"))
            {
                var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
                Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
                File.WriteAllText(outputPath, "UI optimization completed.");
                return Task.FromResult(new HostedProcessResult(0, "codex stdout", ""));
            }

            if (HasScriptArgument(command, "prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "navigation passed", ""));
            }

            return Task.FromResult(new HostedProcessResult(9, "direct scene smoke failed", ""));
        }
    }

    private sealed class CapturingManifestValidator : IHostedContextManifestValidator
    {
        public HostedContextEnvelope? Envelope { get; private set; }
        public string? OperationKey { get; private set; }

        public Task<bool> ValidateAndConsumeAsync(
            HostedContextEnvelope envelope,
            string operationKey,
            CancellationToken cancellationToken = default)
        {
            Envelope = envelope;
            OperationKey = operationKey;
            return Task.FromResult(true);
        }
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly int _smokeExitCode;

        public FakeHostedProcessRunner(int smokeExitCode = 0)
        {
            _smokeExitCode = smokeExitCode;
        }

        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(_smokeExitCode, "smoke stdout", _smokeExitCode == 0 ? "" : "smoke failed"));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "UI optimization completed.");
            return Task.FromResult(new HostedProcessResult(0, "codex stdout", ""));
        }
    }

    private sealed class CancelingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            throw new OperationCanceledException(cancellationToken);
        }
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

    private sealed class EditingThenCancelingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "smoke stdout", ""));
            }

            var scenePath = Path.Combine(command.WorkingDirectory, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
            Directory.CreateDirectory(Path.GetDirectoryName(scenePath)!);
            File.WriteAllText(scenePath, "[gd_scene format=3]\n[node name=\"DqRpgPrototype\" type=\"Node2D\"]\n");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class EditingWithoutSceneThenCancelingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "smoke stdout", ""));
            }

            var scriptPath = Path.Combine(command.WorkingDirectory, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "Hud.cs");
            Directory.CreateDirectory(Path.GetDirectoryName(scriptPath)!);
            File.WriteAllText(scriptPath, "public sealed class Hud {}\n");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class ReferencedScriptEditingThenCancelingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "smoke stdout", ""));
            }

            var scriptPath = Path.Combine(command.WorkingDirectory, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "Hud.cs");
            File.AppendAllText(scriptPath, "public void RefreshUi() {}\n");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class ProjectGodotEditingThenCancelingHostedProcessRunner : IHostedProcessRunner
    {
        private readonly string _mainScene;

        public ProjectGodotEditingThenCancelingHostedProcessRunner(string mainScene)
        {
            _mainScene = mainScene;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "smoke stdout", ""));
            }

            File.WriteAllText(Path.Combine(command.WorkingDirectory, "project.godot"), $"[application]\nrun/main_scene=\"{_mainScene}\"\n");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class ProjectGodotCommentEditingThenCancelingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "smoke stdout", ""));
            }

            File.AppendAllText(Path.Combine(command.WorkingDirectory, "project.godot"), "\n; timeout comment only\n");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class UnreferencedPrototypeFileEditingThenCancelingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "smoke stdout", ""));
            }

            var helperPath = Path.Combine(command.WorkingDirectory, "Game.Godot", "Prototypes", "dq-rpg", "UnusedUiHelper.gd");
            Directory.CreateDirectory(Path.GetDirectoryName(helperPath)!);
            File.WriteAllText(helperPath, "extends Node\n");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class HostMainSceneEditingThenCancelingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!command.Arguments.Contains("exec"))
            {
                return Task.FromResult(new HostedProcessResult(0, "smoke stdout", ""));
            }

            var mainScenePath = Path.Combine(command.WorkingDirectory, "Game.Godot", "Scenes", "Main.tscn");
            Directory.CreateDirectory(Path.GetDirectoryName(mainScenePath)!);
            File.AppendAllText(mainScenePath, "\n[node name=\"TimeoutUiEdit\" type=\"Label\" parent=\".\"]\ntext = \"timeout edit\"\n");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            return new TempDirectory(System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}"));
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
