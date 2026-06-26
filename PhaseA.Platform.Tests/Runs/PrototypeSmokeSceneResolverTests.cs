using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeSmokeSceneResolverTests
{
    [Fact]
    public async Task ResolveLatestAsync_ShouldUseCurrentGoalSafeSceneBeforeProjectGodot_WhenGoalSceneFileIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        project = await StoreProjectAsync(store, project);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "OldMain"));
        File.WriteAllText(
            Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "OldMain", "OldMainPrototype.tscn"),
            "[gd_scene format=3]\n[node name=\"OldMain\" type=\"Node\"]\n");
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "Towerdemo"));
        File.WriteAllText(
            Path.Combine(project.RepoPath, "project.godot"),
            "[application]\nrun/main_scene=\"res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn\"\n");
        var goal = Goal();
        var writer = new PrototypeRouteStateWriter();
        writer.WriteExecuteNextGoalState(project, goal.GoalIndex, new
        {
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/MissingPrototype.tscn"
            }
        });

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo/MissingPrototype.tscn");
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldUseRecordedPrototypeSceneBeforeProjectGodot_WhenBaselineFallbackIsAllowed()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        project = await StoreProjectAsync(store, project);
        EnsureScene(project.RepoPath, "OldMain", "OldMainPrototype.tscn");
        EnsureScene(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        File.WriteAllText(
            Path.Combine(project.RepoPath, "project.godot"),
            "[application]\nrun/main_scene=\"res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn\"\n");
        var goal = Goal();
        var writer = new PrototypeRouteStateWriter();
        writer.WriteNeedsFixState(project, goal.GoalIndex, new
        {
            route = "needs-fix",
            summary = "legacy needs-fix state without current identity"
        });
        writer.WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            updated_utc = DateTimeOffset.UtcNow.ToString("O"),
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true,
            allowBaselineFallbackForGoalContext: true);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn");
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldRejectTimeOnlyPrototypeState_WhenCurrentGoalContextIsStrict()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        project = await StoreProjectAsync(store, project);
        EnsureScene(project.RepoPath, "OldMain", "OldMainPrototype.tscn");
        EnsureScene(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        File.WriteAllText(
            Path.Combine(project.RepoPath, "project.godot"),
            "[application]\nrun/main_scene=\"res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn\"\n");
        var goal = Goal(DateTimeOffset.UtcNow.AddMinutes(-5));
        var writer = new PrototypeRouteStateWriter();
        writer.WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            updated_utc = DateTimeOffset.UtcNow.ToString("O"),
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().BeNull();
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldRejectTimeOnlyRecordedRun_WhenCurrentGoalContextIsStrict()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        project = await StoreProjectAsync(store, project);
        EnsureScene(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        var goal = Goal(DateTimeOffset.UtcNow.AddMinutes(-5));
        var writer = new PrototypeRouteStateWriter();
        var runId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(runId, "succeeded", 0, "", "", """
        {
          "route": "prototype-7day-playable",
          "completed_utc": "2099-01-01T00:00:00Z",
          "prototype_completion": {
            "smoke_scene": "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
          }
        }
        """);
        await SetRunTimingAsync(database.ConnectionString, runId, DateTimeOffset.UtcNow.ToString("O"));

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().BeNull();
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldUseRecordedRun_WhenCurrentGoalIdentityMatches()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        project = await StoreProjectAsync(store, project);
        EnsureScene(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        var goal = Goal();
        var writer = new PrototypeRouteStateWriter();
        var runId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(runId, "succeeded", 0, "", "", $$"""
        {
          "route": "prototype-7day-playable",
          "session_id": "{{goal.SessionId}}",
          "prototype_completion": {
            "smoke_scene": "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
          }
        }
        """);

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn");
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldIgnoreStaleRecordedPrototypeScene_WhenCurrentGoalStateIsRejected()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        project = await StoreProjectAsync(store, project);
        EnsureScene(project.RepoPath, "OldMain", "OldMainPrototype.tscn");
        EnsureScene(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        File.WriteAllText(
            Path.Combine(project.RepoPath, "project.godot"),
            "[application]\nrun/main_scene=\"res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn\"\n");
        var staleUtc = DateTimeOffset.UtcNow.AddDays(-2);
        var goal = Goal(DateTimeOffset.UtcNow);
        var writer = new PrototypeRouteStateWriter();
        writer.WriteNeedsFixState(project, goal.GoalIndex, new
        {
            route = "needs-fix",
            summary = "legacy needs-fix state without current identity"
        });
        writer.WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            updated_utc = staleUtc.ToString("O"),
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });
        var staleRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(staleRunId, "succeeded", 0, "", "", """
        {
          "route": "prototype-7day-playable",
          "prototype_completion": {
            "smoke_scene": "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
          }
        }
        """);
        var lateFinishedUtc = DateTimeOffset.UtcNow.AddMinutes(1);
        await SetRunTimingAsync(database.ConnectionString, staleRunId, staleUtc.ToString("O"), lateFinishedUtc.ToString("O"));

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().BeNull();
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldIgnorePrototypeStateWithOnlyMatchingGoalIndex_WhenCurrentGoalStateIsRejected()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        EnsureScene(project.RepoPath, "OldMain", "OldMainPrototype.tscn");
        EnsureScene(project.RepoPath, "Towerdemo", "TowerdemoPrototype.tscn");
        File.WriteAllText(
            Path.Combine(project.RepoPath, "project.godot"),
            "[application]\nrun/main_scene=\"res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn\"\n");
        var goal = Goal(DateTimeOffset.UtcNow);
        var writer = new PrototypeRouteStateWriter();
        writer.WriteNeedsFixState(project, goal.GoalIndex, new
        {
            route = "needs-fix",
            summary = "legacy needs-fix state without current identity"
        });
        writer.WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            goal_index = goal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/TowerdemoPrototype.tscn"
            }
        });

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().BeNull();
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldIgnoreRouteStateWithOnlyMatchingGoalIndex_WhenCurrentGoalContextIsStrict()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        var goal = Goal();
        var writer = new PrototypeRouteStateWriter();
        writer.WriteExecuteNextGoalState(project, goal.GoalIndex, new
        {
            route = "execute-next-goal",
            goal_index = goal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/MissingPrototype.tscn"
            }
        });

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().BeNull();
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldTryExecuteNextScene_WhenCurrentNeedsFixStateHasNoScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        var goal = Goal();
        var writer = new PrototypeRouteStateWriter();
        writer.WriteNeedsFixState(project, goal.GoalIndex, new
        {
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            summary = "current needs-fix state without scene"
        });
        writer.WriteExecuteNextGoalState(project, goal.GoalIndex, new
        {
            session_id = goal.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            prototype_completion = new
            {
                smoke_scene = "res://Game.Godot/Prototypes/Towerdemo/MissingPrototype.tscn"
            }
        });

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            writer,
            goal.GoalIndex,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true);

        scene.Should().Be("res://Game.Godot/Prototypes/Towerdemo/MissingPrototype.tscn");
    }

    [Fact]
    public void SelectCurrentNeedsFixState_ShouldIgnoreLegacyNeedsFix_WhenExecuteNextStateIsStale()
    {
        var goal = Goal();
        var needsFixState = "{\"route\":\"needs-fix\",\"summary\":\"legacy-current-needs-fix\"}";
        var staleExecuteNextState = """
        {
          "route": "execute-next-goal",
          "session_id": "old-session",
          "goal_id": "old-goal",
          "goal_index": 5,
          "summary": "stale-execute-state"
        }
        """;

        var selected = PrototypeRouteStateSelection.SelectCurrentNeedsFixState(
            needsFixState,
            staleExecuteNextState,
            goal.SessionId,
            goal);

        selected.Should().BeEmpty();
    }

    [Fact]
    public void SelectCurrentExecuteNextGoalState_ShouldIgnoreInvalidJsonState()
    {
        var goal = Goal();

        var selected = PrototypeRouteStateSelection.SelectCurrentExecuteNextGoalState(
            "{not-json",
            goal.SessionId,
            goal);

        selected.Should().BeEmpty();
    }

    [Fact]
    public void SelectCurrentExecuteNextGoalState_ShouldIgnoreLegacyStateWithoutCurrentIdentity()
    {
        var goal = Goal();

        var selected = PrototypeRouteStateSelection.SelectCurrentExecuteNextGoalState(
            "{\"route\":\"execute-next-goal\",\"summary\":\"legacy-execute-state\"}",
            goal.SessionId,
            goal);

        selected.Should().BeEmpty();
    }

    [Fact]
    public void SelectCurrentExecuteNextGoalState_ShouldIgnoreStateWithOnlyMatchingGoalIndex()
    {
        var goal = Goal();

        var selected = PrototypeRouteStateSelection.SelectCurrentExecuteNextGoalState(
            "{\"route\":\"execute-next-goal\",\"goal_index\":5,\"summary\":\"index-only-state\"}",
            goal.SessionId,
            goal);

        selected.Should().BeEmpty();
    }

    [Fact]
    public void SelectCurrentNeedsFixState_ShouldIgnoreStateWithOnlyMatchingGoalIndex()
    {
        var goal = Goal();

        var selected = PrototypeRouteStateSelection.SelectCurrentNeedsFixState(
            "{\"route\":\"needs-fix\",\"goal_index\":5,\"summary\":\"index-only-state\"}",
            "",
            goal.SessionId,
            goal);

        selected.Should().BeEmpty();
    }

    [Fact]
    public void SelectCurrentRouteStates_ShouldIgnoreLegacyNeedsFix_WhenExecuteNextStateIsLegacy()
    {
        var goal = Goal();
        var needsFixState = "{\"route\":\"needs-fix\",\"summary\":\"legacy-current-needs-fix\"}";
        var executeNextState = "{\"route\":\"execute-next-goal\",\"summary\":\"legacy-execute-state\"}";

        var selected = PrototypeRouteStateSelection.SelectCurrentRouteStates(
            needsFixState,
            executeNextState,
            goal.SessionId,
            goal);

        selected.Should().BeEmpty();
    }

    [Fact]
    public async Task ResolveLatestAsync_ShouldTreatLastProjectGodotMainSceneAsEffective()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var project = Project(repo.Path);
        EnsureScene(project.RepoPath, "OldMain", "OldMainPrototype.tscn");
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Game.Godot", "Scenes"));
        File.WriteAllText(
            Path.Combine(project.RepoPath, "Game.Godot", "Scenes", "Main.tscn"),
            "[gd_scene format=3]\n[node name=\"Main\" type=\"Node\"]\n");
        File.WriteAllText(
            Path.Combine(project.RepoPath, "project.godot"),
            """
            [application]
            run/main_scene="res://Game.Godot/Prototypes/OldMain/OldMainPrototype.tscn"
            run/main_scene="res://Game.Godot/Scenes/Main.tscn"
            """);

        var scene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            store,
            project,
            new PrototypeRouteStateWriter());

        scene.Should().BeNull();
    }

    [Fact]
    public void SelectCurrentNeedsFixState_ShouldIgnoreInvalidJsonState()
    {
        var goal = Goal();

        var selected = PrototypeRouteStateSelection.SelectCurrentNeedsFixState(
            "{not-json",
            "",
            goal.SessionId,
            goal);

        selected.Should().BeEmpty();
    }

    private static ProjectSnapshot Project(string repoPath)
    {
        return new ProjectSnapshot(
            "project-1",
            "account-1",
            "Project",
            "Game",
            "rpg",
            "godot-prototype-default",
            false,
            "[]",
            "ready",
            null,
            "workspace-1",
            repoPath,
            repoPath,
            repoPath,
            Path.Combine(repoPath, "meta"));
    }

    private static async Task<ProjectSnapshot> StoreProjectAsync(PhaseAMetadataStore store, ProjectSnapshot project)
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var created = await store.CreateProjectAsync(new ProjectCreationCommand(
            project.ProjectId,
            accountId,
            project.Name,
            project.GameName,
            project.GameTypeSource,
            project.TemplateRuleId,
            project.LlmBindingRequired,
            ["chapter2-bootstrap", "prototype-7day-playable", "prototype-tdd", "prototype-scene"],
            project.WorkspaceRootPath,
            project.RepoPath,
            project.RuntimePath,
            project.MetaPath));
        return project with { AccountId = accountId, WorkspaceId = created.WorkspaceId! };
    }

    private static ProjectIterationGoalSnapshot Goal()
    {
        return Goal(DateTimeOffset.UtcNow);
    }

    private static ProjectIterationGoalSnapshot Goal(DateTimeOffset now)
    {
        return new ProjectIterationGoalSnapshot(
            "goal-current",
            "session-current",
            5,
            "Current goal",
            "Repair current goal",
            null,
            "needs_fix",
            null,
            now.ToString("O"),
            now.ToString("O"),
            null);
    }

    private static void EnsureScene(string repoPath, string slug, string fileName)
    {
        var directory = Path.Combine(repoPath, "Game.Godot", "Prototypes", slug);
        Directory.CreateDirectory(directory);
        File.WriteAllText(
            Path.Combine(directory, fileName),
            $"[gd_scene format=3]\n[node name=\"{slug}\" type=\"Node\"]\n");
    }

    private static async Task SetRunTimingAsync(string connectionString, string runId, string createdUtc, string? finishedUtc = null)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        var completedUtc = finishedUtc ?? createdUtc;
        command.CommandText = """
            UPDATE runs
            SET created_utc = $created_utc,
                started_utc = $created_utc,
                finished_utc = $finished_utc,
                progress_updated_utc = $finished_utc
            WHERE id = $run_id;
            """;
        command.Parameters.AddWithValue("$run_id", runId);
        command.Parameters.AddWithValue("$created_utc", createdUtc);
        command.Parameters.AddWithValue("$finished_utc", completedUtc);
        await command.ExecuteNonQueryAsync();
    }

    private sealed class TempDirectory : IDisposable
    {
        public TempDirectory(string prefix)
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            return new TempDirectory(prefix);
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
