using System.Diagnostics;
using System.IO.Compression;
using System.Net;
using System.Text;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class DiablolikeGddWorkflowIntegrationTests
{
    [Fact]
    public async Task DiablolikeStyleGddFlow_ShouldCreateSkeletonStepsAssetsAndPackage()
    {
        await using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        Write(project!.RepoPath, "docs/gdd/GDD.md", DiablolikeGdd);

        var runner = new DiablolikePrototypeRunner();
        var completionQueue = new HeavyRunnerQueueService();
        var routeStateWriter = new PrototypeRouteStateWriter();
        var workflow = new PrototypeWorkflowService(
            store,
            options,
            runner,
            new PrototypeRecordWriter(options),
            new PrototypeWorkflowCommandBuilder(options),
            new PrototypeArtifactIndexer(),
            new LlmBindingService(store, options),
            new LlmStopLossService(store, options),
            new ProjectWorkspaceSeeder(options),
            new GameTypeTemplateCatalog(options),
            routeStateWriter,
            heavyRunnerQueue: completionQueue);

        var skeleton = await workflow.QueueFromGddAsync(accountId, projectId, new PrototypeFromGddRequest(Model: "gpt-5.5"));
        await WaitForRunStatusAsync(store, skeleton.RunId, "succeeded", completionQueue);

        skeleton.Status.Should().Be("queued");
        runner.Commands.Should().Contain(command => command.Arguments.Contains("run-prototype-workflow"));
        var record = File.ReadAllText(Path.Combine(project.RepoPath, skeleton.PrototypeRecordPath.Replace('/', Path.DirectorySeparatorChar)));
        record.Should().Contain("docs/gdd/GDD.md");
        record.Should().Contain("Phantom Tower");
        record.Should().Contain("WASD movement");
        record.Should().Contain("M1: Core combat loop");

        var reviewJson = """
        {
          "shouldAdjust": true,
          "title": "M2：Active skills after first-room tuning",
          "description": "Tune right click, Q, and E after M1 feedback while preserving the dungeon combat loop.",
          "acceptance": "Player can package, download, and validate the three active skills in the first room.",
          "summary": "已根据 M1 验证结果微调 M2 技能节奏。"
        }
        """;
        var steps = new GddMilestoneStepService(
            store,
            new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), routeStateWriter),
            new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), routeStateWriter),
            new FakeLlmRouteEngine(reviewJson));
        var plan = await steps.GetOrCreateLatestAsync(accountId, projectId);
        plan!.Steps.Select(step => step.StepId).Should().ContainInOrder("M1", "M2", "M10-1", "M10-2", "M10-3");
        plan.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();

        var firstStepPlan = await steps.ExecuteCurrentStepAsync(accountId, projectId);
        firstStepPlan!.Plan!.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        var confirmed = await steps.ConfirmAsync(accountId, projectId, "M1", new GddMilestoneStepConfirmRequest("M1 first room validated; skill pacing should be gentler.", "gpt-5.5"));
        var next = confirmed!.Plan!.Steps.Single(step => step.StepId == "M2");
        next.Locked.Should().BeFalse();
        next.CanConfirm.Should().BeFalse();
        next.Title.Should().Contain("after first-room tuning");
        next.ReviewSummary.Should().Contain("微调 M2");

        var assetLibrary = new ProjectAssetLibraryService(
            store,
            options,
            new ProjectAssetImageGenerator(options, runner),
            new FakeLlmRouteEngine("""{"actionId":"character-making-master"}"""),
            httpClient: new HttpClient(new FakeAssetHttpHandler(MinimalPng())),
            processRunner: runner);
        var imported = await assetLibrary.ImportAsync(
            accountId,
            projectId,
            new ProjectAssetImportRequest(
                "https://assets.example.com/kaykit/Knight.png",
                new ProjectAssetUnitRequest(
                    "player-knight",
                    "PlayerSprite",
                    "Sprite2D",
                    "res://Game.Godot/Scenes/Main.tscn",
                    "res://Game.Godot/Assets/player-old.png",
                    "player_sprite",
                    "KayKit player replacement",
                    "Preserve player collision and controls.")));
        imported!.Status.Should().Be("imported");
        imported.SourceUrlAllowed.Should().BeTrue();

        var selected = await assetLibrary.SelectAsync(accountId, projectId, new ProjectAssetSelectionRequest("player-knight", imported.Entry.EntryId, true));
        var selectedEntry = selected!.Units.Single().Entries.Single(entry => entry.Selected);
        selectedEntry.SelectionValidation!.Status.Should().Be("smoke_passed");
        File.ReadAllText(Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "Main.tscn"))
            .Should().Contain("res://Game.Godot/Prototypes/ProjectAssetLibrary/player-knight/");

        var packageService = new ProjectPackageService(store, options, processRunner: runner);
        var package = await packageService.CreatePackageAsync(accountId, projectId);
        var download = await packageService.ReadPackageAsync(accountId, projectId, package.FileName);

        package.Status.Should().Be("succeeded");
        package.FailureCode.Should().BeNull();
        var packageScene = ZipEntryText(download!.Content, "Game.Godot/Scenes/Main.tscn");
        packageScene.Should().Contain("res://Game.Godot/Prototypes/ProjectAssetLibrary/player-knight/");
        packageScene.Should().NotContain("res://Game.Godot/Assets/player-old.png");
        ZipEntryNames(download.Content).Should().Contain(name => name.Contains("ProjectAssetLibrary/player-knight", StringComparison.Ordinal));
        runner.Commands.Should().Contain(command => command.Arguments.Any(argument => Path.GetFileName(argument).Equals("smoke_headless.py", StringComparison.OrdinalIgnoreCase)));
    }

    private const string DiablolikeGdd = """
        # Phantom Tower Like Action Roguelike GDD

        ## Reference Game
        Reference game: Phantom Tower. Borrow third-person action roguelike pacing, readable rooms, and compact combat escalation.

        ## Scene Creation
        The first playable scene is a dungeon room with doors, blocking props, enemy wave spawners, upgrade reward, HUD, and retry flow.

        ## Keyboard Mouse Basics
        WASD movement, mouse facing, left click combo, space dodge, right click skill, Q skill, and E skill.

        ## Core Gameplay Loop
        Enter a random dungeon room, fight waves, choose upgrades, preserve souls after death, then retry stronger.

        ## Milestones
        M1: Core combat loop with movement, mouse facing, left-click combo, dodge, first enemy, damage, death, and first-room package validation.
        M2: Active skills with right click, Q, and E cooldown feedback.
        M3: Waves and upgrades after enemy kills.
        M10-1: KayKit art blocking props with collision and smoke checks.
        M10-2: KayKit Adventurers player model replacement while preserving collision.
        M10-3: KayKit runtime animation hooks without changing combat timing.
        """;

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest("diablolike-e2e", "Phantom Tower Like", "Action Roguelike", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        return result.ProjectId!;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe",
            ["PHASEA_ASSET_ALLOWED_URLS"] = "https://assets.example.com/kaykit/"
        });
    }

    private static async Task<RunSnapshot> WaitForRunStatusAsync(
        PhaseAMetadataStore store, string runId, string status, HeavyRunnerQueueService completionQueue)
    {
        // ADR-0036: await machine-confirmed completion, including route closure.
        // A bounded readiness wait is independent of production execution timeouts.
        var elapsed = Stopwatch.StartNew();
        RunSnapshot? run = null;
        while (elapsed.Elapsed < TimeSpan.FromSeconds(30))
        {
            run = await store.GetRunSnapshotAsync(runId);
            if (run is not null &&
                string.Equals(run.Status, status, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(run.ProgressStep, status, StringComparison.OrdinalIgnoreCase))
            {
                var project = await store.GetProjectSnapshotAsync(run.ProjectId)
                    ?? throw new InvalidOperationException("Fixture project was not found.");
                var remaining = TimeSpan.FromSeconds(30) - elapsed.Elapsed;
                using var readiness = new CancellationTokenSource(
                    remaining > TimeSpan.Zero ? remaining : TimeSpan.FromMilliseconds(1));
                // ADR-0036/0061: observe queue completion after metadata publication.
                await using var completed = await completionQueue.EnterAsync(
                    $"fixture-readback-{Guid.NewGuid():N}", project.AccountId, run.ProjectId,
                    "fixture-readback", readiness.Token);
                return run;
            }

            if (run?.Status is "failed" or "blocked" or "cancelled" or "cancel")
            {
                throw new InvalidOperationException($"Run {runId} failed: stderr={run.StderrText}; evidence={run.EvidenceJson}");
            }

            await Task.Delay(50);
        }

        throw new TimeoutException(
            $"Run {runId} did not reach {status} within 30 seconds: " +
            $"status={run?.Status ?? "missing"}; progress={run?.ProgressStep ?? "missing"}; " +
            $"stderr={run?.StderrText}; evidence={run?.EvidenceJson}");
    }

    private static void Write(string root, string relativePath, string content)
    {
        var path = Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content, Encoding.UTF8);
    }

    private static void WriteBytes(string root, string relativePath, byte[] content)
    {
        var path = Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllBytes(path, content);
    }

    private static byte[] MinimalPng()
    {
        return Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=");
    }

    private static IReadOnlyList<string> ZipEntryNames(byte[] content)
    {
        using var stream = new MemoryStream(content);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
        return archive.Entries.Select(entry => entry.FullName).ToArray();
    }

    private static string ZipEntryText(byte[] content, string entryName)
    {
        using var stream = new MemoryStream(content);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
        var entry = archive.GetEntry(entryName);
        entry.Should().NotBeNull();
        using var reader = new StreamReader(entry!.Open(), Encoding.UTF8);
        return reader.ReadToEnd();
    }

    private sealed class DiablolikePrototypeRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.Arguments.Any(argument => Path.GetFileName(argument).Equals("smoke_headless.py", StringComparison.OrdinalIgnoreCase)))
            {
                return new HostedProcessResult(0, "SMOKE PASS\n", "");
            }

            if (command.Arguments.Any(argument => Path.GetFileName(argument).Equals("prototype_main_menu_navigation_smoke.py", StringComparison.OrdinalIgnoreCase)))
            {
                return new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/phantom-tower-like/PhantomTowerLikePrototype.tscn\n", "");
            }

            if (command.Arguments.Contains("run-prototype-workflow"))
            {
                // Regression: background completion may exceed the old two-second polling window.
                await Task.Delay(TimeSpan.FromSeconds(3), cancellationToken);
            }

            WritePrototypeCompletion(command);
            return new HostedProcessResult(0, "prototype workflow ok\n", "");
        }

        private static void WritePrototypeCompletion(HostedProcessCommand command)
        {
            var root = command.WorkingDirectory;
            var recordPath = command.Arguments.LastOrDefault(argument =>
                argument.StartsWith("docs/prototypes/", StringComparison.OrdinalIgnoreCase) &&
                argument.EndsWith(".md", StringComparison.OrdinalIgnoreCase)) ?? "docs/prototypes/2026-06-21-phantom-tower-like.md";
            var recordName = Path.GetFileNameWithoutExtension(recordPath);
            var slug = recordName.Length > "2026-06-21-".Length && recordName.StartsWith("2026-", StringComparison.Ordinal)
                ? recordName["2026-06-21-".Length..]
                : recordName;
            var prototypeScene = $"res://Game.Godot/Prototypes/{slug}/{ToPascalSlug(slug)}Prototype.tscn";
            Write(root, "Game.Godot/Assets/player-old.png", "old-player");
            Write(root, "Game.Godot/Scenes/Main.tscn", """
                [gd_scene load_steps=2 format=3]
                [ext_resource type="Texture2D" path="res://Game.Godot/Assets/player-old.png" id="1"]
                [node name="Main" type="Node2D"]
                [node name="PlayerSprite" type="Sprite2D" parent="."]
                texture = ExtResource("1")
                [node name="PlayerBody" type="CharacterBody2D" parent="."]
                [node name="CollisionShape2D" type="CollisionShape2D" parent="PlayerBody"]
                """);
            Write(root, $"Game.Godot/Prototypes/{slug}/{ToPascalSlug(slug)}Prototype.tscn", """
                [gd_scene format=3]
                [node name="PrototypeRoot" type="Node2D"]
                [node name="PlayerSprite" type="Sprite2D" parent="."]
                """);
            Write(root, "Game.Core/Prototypes/DiablolikePrototypeLoop.cs", """
public sealed class DiablolikePrototypeLoop
{
    public DiablolikePrototypeState ContinueFirstLoop(DiablolikePrototypeState state)
    {
        return state with
        {
            Objective = "Loop objective updated.",
            Feedback = "Combat loop feedback is visible.",
            Result = "State result changed."
        };
    }
}

public sealed record DiablolikePrototypeState(string Objective, string Feedback, string Result);
""");
            Write(root, "Game.Core.Tests/Prototypes/DiablolikePrototypeLoopTests.cs", """
public sealed class DiablolikePrototypeLoopTests
{
    public void ShouldContinueFirstLoop_WithStateFeedbackAndResult() { }
}
""");
            Write(root, $"docs/prototypes/{slug}.prototype.json", $$"""
                {
                  "prototype_type_kit": {
                    "manifest": {
                      "paths": {
                        "default_scene": "{{prototypeScene}}"
                      }
                    }
                  }
                }
                """);
            Write(root, $"logs/ci/active-prototypes/{slug}.packaging.json", $$"""
                {
                  "kind": "prototype-packaging-summary",
                  "default_scene": "{{prototypeScene}}",
                  "tdd_stage_counts": { "red": 1, "green": 1, "refactor": 1 },
                  "playtest_focus_points": ["Verify WASD movement", "Verify blocking props", "Verify active skills"]
                }
                """);
            Write(root, $"logs/ci/active-prototypes/{slug}.completion.md", "# Completion\nPrototype completed.\n");
            Write(root, $"logs/ci/active-prototypes/{slug}.active.json", $$"""
                {
                  "status": "completed-through-day",
                  "completed_through_day": 7,
                  "missing_required_fields": [],
                  "prototype_spec": "docs/prototypes/{{slug}}.prototype.json",
                  "completion_summary": "Diablolike GDD skeleton completed from source GDD.",
                  "next_step_source": "codex",
                  "next_step_evaluation": "recommended",
                  "next_step_evaluation_reason": "Continue with milestone steps.",
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
        }

        private static string ToPascalSlug(string slug)
        {
            return string.Concat(slug.Split(['-', '_', ' '], StringSplitOptions.RemoveEmptyEntries)
                .Select(part => char.ToUpperInvariant(part[0]) + part[1..]));
        }
    }

    private sealed class FakeLlmRouteEngine : ILlmRouteEngine
    {
        private readonly string _json;

        public FakeLlmRouteEngine(string json)
        {
            _json = json;
        }

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new LlmRouteResult(true, _json, _json, request.Model, null, null, 0, "", "", null, 1, request.Prompt.Length, Encoding.UTF8.GetByteCount(request.Prompt), 1));
        }
    }

    private sealed class FakeAssetHttpHandler : HttpMessageHandler
    {
        private readonly byte[] _content;

        public FakeAssetHttpHandler(byte[] content)
        {
            _content = content;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var response = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new ByteArrayContent(_content)
            };
            response.Content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("image/png");
            return Task.FromResult(response);
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
