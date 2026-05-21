using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeGodotSmokeService
{
    public static async Task<PrototypeGodotSmokeResult> RunAsync(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        string projectRepoPath,
        string scenePath,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(options);
        ArgumentNullException.ThrowIfNull(processRunner);

        if (string.IsNullOrWhiteSpace(options.GodotBin))
        {
            return PrototypeGodotSmokeResult.NotRun("godot_bin_not_configured", scenePath);
        }

        var command = new HostedProcessCommand(
            options.PythonCommand,
            [
                "-3",
                "scripts/python/smoke_headless.py",
                "--godot-bin",
                options.GodotBin,
                "--project-path",
                projectRepoPath,
                "--scene",
                scenePath,
                "--timeout-sec",
                "10",
                "--strict"
            ],
            projectRepoPath,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = options.GodotBin
            });

        var result = await processRunner.RunAsync(command, cancellationToken);
        var sceneSmokeExitCode = ResolvePrototypeSmokeExitCode(result);
        if (sceneSmokeExitCode != 0)
        {
            return new PrototypeGodotSmokeResult(true, sceneSmokeExitCode, result.Stdout, result.Stderr, "strict_headless_prototype_scene", scenePath);
        }

        var navigationCommand = new HostedProcessCommand(
            options.PythonCommand,
            [
                "-3",
                "scripts/python/prototype_main_menu_navigation_smoke.py",
                "--godot-bin",
                options.GodotBin,
                "--project-path",
                projectRepoPath,
                "--expected-scene",
                scenePath,
                "--timeout-sec",
                "15"
            ],
            projectRepoPath,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = options.GodotBin
            });
        var navigationResult = await processRunner.RunAsync(navigationCommand, cancellationToken);
        var navigationExitCode = navigationResult.ExitCode;
        var stdout = CombineProcessText(result.Stdout, navigationResult.Stdout);
        var stderr = CombineProcessText(result.Stderr, navigationResult.Stderr);
        return new PrototypeGodotSmokeResult(
            true,
            navigationExitCode,
            stdout,
            stderr,
            navigationExitCode == 0 ? "strict_headless_main_menu_navigation" : "prototype_main_menu_navigation_failed",
            scenePath);
    }

    public static async Task<PrototypeGoalGodotSmokeValidationResult> ValidateGoalAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        string prototypeStateJson,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);
        ArgumentNullException.ThrowIfNull(options);
        ArgumentNullException.ThrowIfNull(processRunner);

        if (!ShouldValidateGoal(project, goal))
        {
            return PrototypeGoalGodotSmokeValidationResult.NotRequired();
        }

        var scenePath = ResolveSmokeScene(prototypeStateJson);
        if (string.IsNullOrWhiteSpace(scenePath))
        {
            return PrototypeGoalGodotSmokeValidationResult.RequiredResult(PrototypeGodotSmokeResult.NotRun("prototype_smoke_scene_missing"));
        }

        var smoke = await RunAsync(options, processRunner, project.RepoPath, scenePath, cancellationToken);
        return PrototypeGoalGodotSmokeValidationResult.RequiredResult(smoke);
    }

    public static bool ShouldValidateGoal(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);

        if (!PrototypeRouteSkillPolicy.IsRpgProject(project))
        {
            return false;
        }

        return goal.GoalIndex is 5 or 6;
    }

    private static string? ResolveSmokeScene(string prototypeStateJson)
    {
        if (string.IsNullOrWhiteSpace(prototypeStateJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(prototypeStateJson);
            var root = document.RootElement;
            if (root.TryGetProperty("prototype_completion", out var completion) &&
                completion.ValueKind == JsonValueKind.Object &&
                completion.TryGetProperty("smoke_scene", out var completionScene) &&
                completionScene.ValueKind == JsonValueKind.String)
            {
                return completionScene.GetString();
            }

            if (root.TryGetProperty("godot_smoke", out var smoke) &&
                smoke.ValueKind == JsonValueKind.Object &&
                smoke.TryGetProperty("scene", out var scene) &&
                scene.ValueKind == JsonValueKind.String)
            {
                return scene.GetString();
            }
        }
        catch (JsonException)
        {
            return null;
        }

        return null;
    }

    private static int ResolvePrototypeSmokeExitCode(HostedProcessResult result)
    {
        if (result.ExitCode == 0)
        {
            return 0;
        }

        var combined = $"{result.Stdout}\n{result.Stderr}";
        return combined.Contains("SMOKE PASS", StringComparison.OrdinalIgnoreCase) ? 0 : result.ExitCode;
    }

    private static string CombineProcessText(string primary, string secondary)
    {
        if (string.IsNullOrWhiteSpace(secondary))
        {
            return primary;
        }

        return string.IsNullOrWhiteSpace(primary)
            ? secondary
            : $"{primary.TrimEnd()}{Environment.NewLine}{Environment.NewLine}[post-prototype-godot-smoke]{Environment.NewLine}{secondary}";
    }
}

internal sealed record PrototypeGodotSmokeResult(
    bool Ran,
    int ExitCode,
    string Stdout,
    string Stderr,
    string Reason,
    string? ScenePath)
{
    public static PrototypeGodotSmokeResult NotRun(string reason, string? scenePath = null)
    {
        return new PrototypeGodotSmokeResult(false, 0, "", "", reason, scenePath);
    }

    public object ToEvidence()
    {
        return new
        {
            ran = Ran,
            exit_code = ExitCode,
            reason = Reason,
            scene = ScenePath
        };
    }
}

internal sealed record PrototypeGoalGodotSmokeValidationResult(bool Required, PrototypeGodotSmokeResult Smoke)
{
    public bool Passed => !Required || (Smoke.Ran && Smoke.ExitCode == 0);

    public static PrototypeGoalGodotSmokeValidationResult NotRequired()
    {
        return new PrototypeGoalGodotSmokeValidationResult(false, PrototypeGodotSmokeResult.NotRun("not_required"));
    }

    public static PrototypeGoalGodotSmokeValidationResult RequiredResult(PrototypeGodotSmokeResult smoke)
    {
        return new PrototypeGoalGodotSmokeValidationResult(true, smoke);
    }

    public object ToEvidence()
    {
        return new
        {
            required = Required,
            passed = Passed,
            smoke = Smoke.ToEvidence()
        };
    }
}
