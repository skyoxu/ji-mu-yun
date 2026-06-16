using System.Text.Json;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeGodotSmokeService
{
    private static readonly Regex GodotNamespaceAliasPattern = new(
        @"(?<!global::)(?<![A-Za-z0-9_\.])Godot\.",
        RegexOptions.Compiled);

    public static async Task<PrototypeGodotSmokeResult> RunAsync(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        string projectRepoPath,
        string scenePath,
        CancellationToken cancellationToken = default)
    {
        return await RunAsync(
            options,
            processRunner,
            projectRepoPath,
            scenePath,
            requireDirectSceneSmoke: true,
            cancellationToken);
    }

    public static async Task<PrototypeGodotSmokeResult> RunPostPrototypeAcceptanceAsync(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        string projectRepoPath,
        string scenePath,
        CancellationToken cancellationToken = default)
    {
        return await RunAsync(
            options,
            processRunner,
            projectRepoPath,
            scenePath,
            requireDirectSceneSmoke: false,
            cancellationToken);
    }

    private static async Task<PrototypeGodotSmokeResult> RunAsync(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        string projectRepoPath,
        string scenePath,
        bool requireDirectSceneSmoke,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(options);
        ArgumentNullException.ThrowIfNull(processRunner);

        if (string.IsNullOrWhiteSpace(options.GodotBin))
        {
            return PrototypeGodotSmokeResult.NotRun("godot_bin_not_configured", scenePath);
        }

        NormalizeGodotCSharpNamespaceAliases(projectRepoPath);

        var command = new HostedProcessCommand(
            options.PythonCommand,
            [
                "-3",
                ResolveRepositoryScriptPath(options, "scripts/python/smoke_headless.py"),
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
            PrototypeValidationProcessEnvironment.Create(projectRepoPath, new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = options.GodotBin
            }));

        var result = await processRunner.RunAsync(command, cancellationToken);
        var sceneSmokeHasGodotFailure = ContainsGodotFailureMarker($"{result.Stdout}\n{result.Stderr}");
        var sceneSmokeExitCode = ResolvePrototypeSmokeExitCode(result);
        if (sceneSmokeHasGodotFailure || (sceneSmokeExitCode != 0 && requireDirectSceneSmoke))
        {
            return new PrototypeGodotSmokeResult(true, sceneSmokeExitCode, result.Stdout, result.Stderr, "strict_headless_prototype_scene", scenePath, projectRepoPath);
        }

        var navigationCommand = new HostedProcessCommand(
            options.PythonCommand,
            [
                "-3",
                ResolveRepositoryScriptPath(options, "scripts/python/prototype_main_menu_navigation_smoke.py"),
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
            PrototypeValidationProcessEnvironment.Create(projectRepoPath, new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = options.GodotBin
            }));
        var navigationResult = await processRunner.RunAsync(navigationCommand, cancellationToken);
        var navigationExitCode = navigationResult.ExitCode;
        var stdout = CombineProcessText(result.Stdout, navigationResult.Stdout);
        var stderr = CombineProcessText(result.Stderr, navigationResult.Stderr);
        var reason = navigationExitCode != 0
            ? "prototype_main_menu_navigation_failed"
            : sceneSmokeExitCode == 0
                ? "strict_headless_main_menu_navigation"
                : "strict_headless_prototype_scene_warning_main_menu_navigation_passed";
        return new PrototypeGodotSmokeResult(
            true,
            navigationExitCode,
            stdout,
            stderr,
            reason,
            scenePath,
            projectRepoPath);
    }

    internal static IReadOnlyList<string> NormalizeGodotCSharpNamespaceAliases(string projectRepoPath)
    {
        if (string.IsNullOrWhiteSpace(projectRepoPath))
        {
            return [];
        }

        var prototypesRoot = Path.Combine(projectRepoPath, "Game.Godot", "Prototypes");
        if (!Directory.Exists(prototypesRoot))
        {
            return [];
        }

        var changed = new List<string>();
        foreach (var scriptPath in Directory.EnumerateFiles(prototypesRoot, "*.cs", SearchOption.AllDirectories))
        {
            string text;
            try
            {
                text = File.ReadAllText(scriptPath);
            }
            catch (IOException)
            {
                continue;
            }
            catch (UnauthorizedAccessException)
            {
                continue;
            }

            if (!text.Contains("namespace Game.Godot", StringComparison.Ordinal) ||
                !text.Contains("Godot.", StringComparison.Ordinal))
            {
                continue;
            }

            var normalized = GodotNamespaceAliasPattern.Replace(text, "global::Godot.");
            if (string.Equals(normalized, text, StringComparison.Ordinal))
            {
                continue;
            }

            File.WriteAllText(scriptPath, normalized);
            changed.Add(Path.GetRelativePath(projectRepoPath, scriptPath).Replace('\\', '/'));
        }

        return changed;
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

        if (goal.GoalIndex is >= 1 and <= 4 && string.IsNullOrWhiteSpace(options.GodotBin))
        {
            return PrototypeGoalGodotSmokeValidationResult.NotRequired();
        }

        var scenePath = ResolveSmokeScene(prototypeStateJson);
        if (string.IsNullOrWhiteSpace(scenePath))
        {
            return RequiresSmokeScene(project, goal)
                ? PrototypeGoalGodotSmokeValidationResult.RequiredResult(PrototypeGodotSmokeResult.NotRun("prototype_smoke_scene_missing"))
                : PrototypeGoalGodotSmokeValidationResult.NotRequired();
        }

        var smoke = await RunAsync(options, processRunner, project.RepoPath, scenePath, cancellationToken);
        return PrototypeGoalGodotSmokeValidationResult.RequiredResult(smoke);
    }

    public static async Task<PrototypeRpgGdUnitValidationResult> RunRpgGdUnitValidationAsync(
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        ProjectSnapshot project,
        string slug,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(options);
        ArgumentNullException.ThrowIfNull(processRunner);
        ArgumentNullException.ThrowIfNull(project);

        if (!PrototypeRouteSkillPolicy.IsRpgProject(project))
        {
            return PrototypeRpgGdUnitValidationResult.NotRequired("not_rpg_project");
        }

        var gdUnitRelativePath = ResolveRpgGdUnitRelativePath(project.RepoPath, slug);
        if (string.IsNullOrWhiteSpace(gdUnitRelativePath))
        {
            return PrototypeRpgGdUnitValidationResult.NotRequired("rpg_gdunit_tests_missing");
        }

        if (string.IsNullOrWhiteSpace(options.GodotBin))
        {
            return PrototypeRpgGdUnitValidationResult.RequiredResult(
                false,
                0,
                "",
                "",
                "godot_bin_not_configured",
                gdUnitRelativePath,
                null);
        }

        var reportDir = Path.Combine(
            "logs",
            "e2e",
            DateTimeOffset.Now.ToString("yyyy-MM-dd", System.Globalization.CultureInfo.InvariantCulture),
            $"gdunit-{NormalizeReportSlug(slug)}-prototype");
        var command = new HostedProcessCommand(
            options.PythonCommand,
            [
                "-3",
                ResolveRepositoryScriptPath(options, "scripts/python/run_gdunit.py"),
                "--godot-bin",
                options.GodotBin,
                "--add",
                gdUnitRelativePath,
                "--timeout-sec",
                "120",
                "--prewarm",
                "--rd",
                reportDir.Replace('\\', '/')
            ],
            project.RepoPath,
            PrototypeValidationProcessEnvironment.Create(project.RepoPath, new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = options.GodotBin
            }));

        var result = await processRunner.RunAsync(command, cancellationToken);
        var combined = CombineProcessText(result.Stdout, result.Stderr);
        var effectiveExitCode = ResolveGdUnitEffectiveExitCode(result.ExitCode, combined);
        var noTestCasesFound = combined.Contains("No test cases found", StringComparison.OrdinalIgnoreCase);
        var passed = effectiveExitCode == 0 && !noTestCasesFound;
        var reason = passed
            ? "rpg_project_specific_gdunit_passed"
            : noTestCasesFound
                ? "rpg_project_specific_gdunit_no_tests_found"
                : "rpg_project_specific_gdunit_failed";
        return PrototypeRpgGdUnitValidationResult.RequiredResult(
            passed,
            effectiveExitCode,
            result.Stdout,
            result.Stderr,
            reason,
            gdUnitRelativePath,
            reportDir.Replace('\\', '/'));
    }

    public static bool ShouldValidateGoal(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);

        if (PrototypeRouteSkillPolicy.IsRpgProject(project))
        {
            return goal.GoalIndex is >= 1 and <= 7;
        }

        if (PrototypeRouteSkillPolicy.IsSurvivorsLikeProject(project))
        {
            return goal.GoalIndex is >= 1 and <= 10;
        }

        return false;
    }

    private static bool RequiresSmokeScene(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        if (PrototypeRouteSkillPolicy.IsRpgProject(project))
        {
            return goal.GoalIndex is 5 or 6 or 7;
        }

        if (PrototypeRouteSkillPolicy.IsSurvivorsLikeProject(project))
        {
            return goal.GoalIndex is >= 5 and <= 10;
        }

        return false;
    }

    private static string? ResolveRpgGdUnitRelativePath(string projectRepoPath, string slug)
    {
        var candidates = new[]
        {
            $"tests/Prototype/{ToPascalCase(slug)}",
            "tests/Prototype/DqRpgPrototype",
            "tests/Prototype/DefaultRpgPrototype"
        };

        foreach (var candidate in candidates)
        {
            var absolute = Path.Combine(projectRepoPath, "Tests.Godot", candidate.Replace('/', Path.DirectorySeparatorChar));
            if (Directory.Exists(absolute))
            {
                return candidate;
            }
        }

        return null;
    }

    private static string ToPascalCase(string value)
    {
        var parts = value.Split(['-', '_', ' '], StringSplitOptions.RemoveEmptyEntries);
        return string.Concat(parts.Select(part => char.ToUpperInvariant(part[0]) + part[1..]));
    }

    private static string NormalizeReportSlug(string slug)
    {
        var chars = slug.Select(ch => char.IsLetterOrDigit(ch) ? char.ToLowerInvariant(ch) : '-').ToArray();
        var normalized = new string(chars).Trim('-');
        return string.IsNullOrWhiteSpace(normalized) ? "rpg" : normalized;
    }

    private static string ResolveRepositoryScriptPath(PhaseAPlatformOptions options, string relativePath)
    {
        if (string.IsNullOrWhiteSpace(options.RepositoryRoot))
        {
            return relativePath;
        }

        var absolutePath = Path.Combine(options.RepositoryRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
        return File.Exists(absolutePath) ? absolutePath : relativePath;
    }

    private static int ResolveGdUnitEffectiveExitCode(int processExitCode, string output)
    {
        const string marker = "GDUNIT_DONE rc=";
        var markerIndex = output.LastIndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (markerIndex < 0)
        {
            return processExitCode;
        }

        var start = markerIndex + marker.Length;
        var end = start;
        while (end < output.Length && (char.IsDigit(output[end]) || output[end] == '-'))
        {
            end++;
        }

        return end > start && int.TryParse(output[start..end], System.Globalization.NumberStyles.Integer, System.Globalization.CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : processExitCode;
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
        var combined = $"{result.Stdout}\n{result.Stderr}";
        if (ContainsGodotFailureMarker(combined))
        {
            return result.ExitCode == 0 ? 1 : result.ExitCode;
        }

        if (result.ExitCode == 0)
        {
            return 0;
        }

        return combined.Contains("SMOKE PASS", StringComparison.OrdinalIgnoreCase) ? 0 : result.ExitCode;
    }

    private static bool ContainsGodotFailureMarker(string output)
    {
        return output.Contains("ERROR:", StringComparison.OrdinalIgnoreCase)
               || output.Contains("Parse Error:", StringComparison.OrdinalIgnoreCase)
               || output.Contains("C# backtrace", StringComparison.OrdinalIgnoreCase)
               || output.Contains("Nodes with non-equal opposite anchors", StringComparison.OrdinalIgnoreCase);
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
    string? ScenePath,
    string? ProjectRepoPath = null)
{
    private static readonly Regex GodotResourcePathPattern = new(
        @"res://[^\s`'""\)\]]+\.(?:png|jpg|jpeg|webp|svg|ogg|wav|mp3|ttf|otf|tscn|tres|res)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

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
            scene = ScenePath,
            diagnostic_excerpt = BuildDiagnosticExcerpt(Stdout, Stderr),
            resource_diagnostics = BuildResourceDiagnostics(ProjectRepoPath, Stdout, Stderr).Select(d => d.ToEvidence()).ToArray()
        };
    }

    private static string BuildDiagnosticExcerpt(string stdout, string stderr)
    {
        var lines = string.Join(
                Environment.NewLine,
                new[] { stdout, stderr }.Where(static value => !string.IsNullOrWhiteSpace(value)))
            .Replace("\r", "", StringComparison.Ordinal)
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(static line =>
                line.Contains("ERROR:", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("SCRIPT ERROR", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("Parse Error", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("No loader found for resource", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("referenced non-existent resource", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("Node not found", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("MAIN_MENU_PROTOTYPE_NAV FAIL", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("C# backtrace", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("Nodes with non-equal opposite anchors", StringComparison.OrdinalIgnoreCase))
            .Distinct(StringComparer.Ordinal)
            .Take(12)
            .ToArray();

        var excerpt = string.Join(Environment.NewLine, lines);
        if (excerpt.Length <= 1800)
        {
            return excerpt;
        }

        return excerpt[..1800].TrimEnd();
    }

    private static IReadOnlyList<PrototypeGodotResourceDiagnostic> BuildResourceDiagnostics(string? projectRepoPath, string stdout, string stderr)
    {
        if (string.IsNullOrWhiteSpace(projectRepoPath))
        {
            return [];
        }

        var combined = string.Join(
            Environment.NewLine,
            new[] { stdout, stderr }.Where(static value => !string.IsNullOrWhiteSpace(value)));

        var results = new List<PrototypeGodotResourceDiagnostic>();
        foreach (Match match in GodotResourcePathPattern.Matches(combined))
        {
            var resourcePath = NormalizeResourceDiagnosticPath(match.Value);
            if (!ShouldInspectResourcePath(combined, resourcePath))
            {
                continue;
            }

            var relative = resourcePath["res://".Length..].Replace('/', Path.DirectorySeparatorChar);
            var filePath = Path.Combine(projectRepoPath, relative);
            var importPath = filePath + ".import";
            var fileExists = File.Exists(filePath);
            var requiresImport = RequiresGodotImportMetadata(resourcePath);
            var importExists = !requiresImport || File.Exists(importPath);
            var pngValid = !fileExists || !string.Equals(Path.GetExtension(filePath), ".png", StringComparison.OrdinalIgnoreCase) || HasPngSignature(filePath);

            if (!results.Any(item => string.Equals(item.ResourcePath, resourcePath, StringComparison.OrdinalIgnoreCase)))
            {
                results.Add(new PrototypeGodotResourceDiagnostic(
                    resourcePath,
                    fileExists,
                    importExists,
                    pngValid,
                    BuildResourceDiagnosticFix(resourcePath, fileExists, importExists, pngValid)));
            }
        }

        return results;
    }

    private static string NormalizeResourceDiagnosticPath(string value)
    {
        return value.TrimEnd('.', ',', ';', ':');
    }

    private static bool ShouldInspectResourcePath(string combinedOutput, string resourcePath)
    {
        var extension = Path.GetExtension(resourcePath);
        if (string.Equals(extension, ".gd", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (RequiresGodotImportMetadata(resourcePath))
        {
            return combinedOutput.Contains($"No loader found for resource: {resourcePath}", StringComparison.OrdinalIgnoreCase) ||
                   combinedOutput.Contains($"referenced non-existent resource at: {resourcePath}", StringComparison.OrdinalIgnoreCase) ||
                   combinedOutput.Contains(resourcePath, StringComparison.OrdinalIgnoreCase);
        }

        return combinedOutput.Contains($"Parse Error: [ext_resource] referenced non-existent resource at: {resourcePath}", StringComparison.OrdinalIgnoreCase);
    }

    private static bool RequiresGodotImportMetadata(string resourcePath)
    {
        var extension = Path.GetExtension(resourcePath);
        return extension.Equals(".png", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".webp", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".svg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".ogg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".wav", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".mp3", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".ttf", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".otf", StringComparison.OrdinalIgnoreCase);
    }

    private static bool HasPngSignature(string filePath)
    {
        try
        {
            var bytes = File.ReadAllBytes(filePath);
            return bytes.Length >= 8 &&
                   bytes[0] == 0x89 &&
                   bytes[1] == 0x50 &&
                   bytes[2] == 0x4E &&
                   bytes[3] == 0x47 &&
                   bytes[4] == 0x0D &&
                   bytes[5] == 0x0A &&
                   bytes[6] == 0x1A &&
                   bytes[7] == 0x0A;
        }
        catch (IOException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static string BuildResourceDiagnosticFix(string resourcePath, bool fileExists, bool importExists, bool pngValid)
    {
        if (!fileExists)
        {
            return $"Restore or copy the missing resource file at {resourcePath} and regenerate its Godot import metadata.";
        }

        if (!pngValid)
        {
            return $"Replace the invalid PNG at {resourcePath} with a valid PNG file before retrying Godot smoke.";
        }

        if (!importExists)
        {
            return $"Regenerate Godot import metadata for {resourcePath} so the loader can open the resource again.";
        }

        return $"Recheck the Godot import cache and scene ext_resource entry for {resourcePath}.";
    }
}

internal sealed record PrototypeGodotResourceDiagnostic(
    string ResourcePath,
    bool FileExists,
    bool ImportExists,
    bool PngValid,
    string SuggestedFix)
{
    public object ToEvidence()
    {
        return new
        {
            resource_path = ResourcePath,
            file_exists = FileExists,
            import_exists = ImportExists,
            png_valid = PngValid,
            suggested_fix = SuggestedFix
        };
    }
}

internal sealed record PrototypeRpgGdUnitValidationResult(
    bool Required,
    bool Ran,
    bool Passed,
    int ExitCode,
    string Stdout,
    string Stderr,
    string Reason,
    string? GdUnitPath,
    string? ReportDir)
{
    public static PrototypeRpgGdUnitValidationResult NotRequired(string reason)
    {
        return new PrototypeRpgGdUnitValidationResult(false, false, true, 0, "", "", reason, null, null);
    }

    public static PrototypeRpgGdUnitValidationResult RequiredResult(
        bool passed,
        int exitCode,
        string stdout,
        string stderr,
        string reason,
        string? gdUnitPath,
        string? reportDir)
    {
        return new PrototypeRpgGdUnitValidationResult(true, true, passed, exitCode, stdout, stderr, reason, gdUnitPath, reportDir);
    }

    public object ToEvidence()
    {
        return new
        {
            required = Required,
            ran = Ran,
            passed = Passed,
            exit_code = ExitCode,
            reason = Reason,
            gdunit_path = GdUnitPath,
            report_dir = ReportDir
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
