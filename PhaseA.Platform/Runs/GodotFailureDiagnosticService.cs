using System.Text.Json;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

internal static class GodotFailureDiagnosticService
{
    private const int MaxExcerptLength = 1600;

    public static async Task<GodotFailureDiagnostic> AnalyzeLatestAsync(
        PhaseAMetadataStore metadataStore,
        ProjectSnapshot project,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(metadataStore);
        ArgumentNullException.ThrowIfNull(project);

        var runs = await metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var run = runs.FirstOrDefault(candidate =>
            candidate.Status is "failed" or "needs_fix" ||
            HasGodotSmokeFailure(candidate.EvidenceJson) ||
            ContainsGodotFailure(candidate.StdoutText, candidate.StderrText, candidate.EvidenceJson));
        return Analyze(project, run);
    }

    public static GodotFailureDiagnostic Analyze(ProjectSnapshot project, RunSnapshot? run)
    {
        ArgumentNullException.ThrowIfNull(project);

        if (run is null)
        {
            return GodotFailureDiagnostic.None();
        }

        var latestSmokeLog = ReadLatestSmokeLog(project.RepoPath);
        var combined = string.Join(
            "\n",
            run.StdoutText ?? "",
            run.StderrText ?? "",
            run.EvidenceJson ?? "",
            latestSmokeLog);
        var hasGodotFailure = HasGodotSmokeFailure(run.EvidenceJson) || ContainsGodotFailure(combined);
        if (!hasGodotFailure)
        {
            return GodotFailureDiagnostic.None(run.RunId);
        }

        var cleanupRecommended = ContainsAny(
            combined,
            "associated class could not be found",
            "class definition with a name that matches",
            "global_script_class_cache",
            "could not resolve class",
            "failed loading resource",
            "resource uid",
            "imported",
            "build-solutions prewarm timed out",
            "dotnet build-server",
            "file is locked",
            "access is denied",
            "sharing violation",
            ".godot",
            "mono temp",
            "cannot open assembly");

        var summary = cleanupRecommended
            ? "Recent Godot validation failed with signs of generated metadata, import, build, or file-lock contamination. Safe generated-cache cleanup should run before the next repair attempt."
            : "Recent Godot validation failed with engine/runtime errors. The next repair should consume the engine error summary and fix project code or scene wiring directly.";

        return new GodotFailureDiagnostic(
            true,
            cleanupRecommended,
            summary,
            BuildPublicExcerpt(combined),
            run.RunId);
    }

    public static async Task<GodotCacheCleanupResult> CleanupIfRecommendedAsync(
        ProjectSnapshot project,
        GodotFailureDiagnostic diagnostic,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(diagnostic);

        if (!diagnostic.CleanupRecommended)
        {
            return new GodotCacheCleanupResult(false, []);
        }

        await Task.Yield();
        cancellationToken.ThrowIfCancellationRequested();
        var cleaned = new List<string>();
        TryDeleteDirectory(project.RepoPath, Path.Combine(project.RepoPath, ".godot", "mono", "temp"), "godot_mono_temp", cleaned);
        TryDeleteDirectory(project.RepoPath, Path.Combine(project.RepoPath, ".godot", "imported"), "godot_import_cache", cleaned);
        TryDeleteDirectory(project.RepoPath, Path.Combine(project.RepoPath, ".godot", "editor"), "godot_editor_cache", cleaned);
        TryDeleteFile(project.RepoPath, Path.Combine(project.RepoPath, ".godot", "global_script_class_cache.cfg"), "godot_script_class_cache", cleaned);
        TryDeleteFile(project.RepoPath, Path.Combine(project.RepoPath, ".godot", "uid_cache.bin"), "godot_uid_cache", cleaned);
        TryDeleteDirectory(project.RepoPath, Path.Combine(project.RepoPath, "Game.Godot", ".godot", "mono", "temp"), "nested_godot_mono_temp", cleaned);
        TryDeleteDirectory(project.RepoPath, Path.Combine(project.RepoPath, "Game.Godot", ".godot", "imported"), "nested_godot_import_cache", cleaned);

        return new GodotCacheCleanupResult(cleaned.Count > 0, cleaned);
    }

    public static string BuildPromptBlock(GodotFailureDiagnostic diagnostic, GodotCacheCleanupResult? cleanup = null)
    {
        ArgumentNullException.ThrowIfNull(diagnostic);
        if (!diagnostic.HasGodotFailure)
        {
            return "Godot diagnostic: no recent Godot engine failure was detected.";
        }

        var cleanupLine = cleanup is { Performed: true }
            ? $"Safe generated-cache cleanup already ran before this repair. Cleaned scopes: {string.Join(", ", cleanup.CleanedScopes)}."
            : diagnostic.CleanupRecommended
                ? "Safe generated-cache cleanup is recommended before relying on the previous engine result."
                : "Do not assume this is a generated-cache issue; prefer fixing scene, script, resource, or runtime wiring.";

        return $"""
            Godot diagnostic:
            - {diagnostic.Summary}
            - {cleanupLine}
            - Recent engine error excerpt:
            {diagnostic.PublicExcerpt}
            """;
    }

    public static object ToEvidence(GodotFailureDiagnostic diagnostic, GodotCacheCleanupResult? cleanup = null)
    {
        ArgumentNullException.ThrowIfNull(diagnostic);
        return new
        {
            has_godot_failure = diagnostic.HasGodotFailure,
            cleanup_recommended = diagnostic.CleanupRecommended,
            cleanup_performed = cleanup?.Performed ?? false,
            cleaned_scopes = cleanup?.CleanedScopes ?? [],
            source_run_id = diagnostic.SourceRunId,
            summary = diagnostic.Summary
        };
    }

    private static bool HasGodotSmokeFailure(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            if (!document.RootElement.TryGetProperty("godot_smoke", out var smoke) ||
                smoke.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            return smoke.TryGetProperty("exit_code", out var exitCode) &&
                   exitCode.ValueKind == JsonValueKind.Number &&
                   exitCode.TryGetInt32(out var value) &&
                   value != 0;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool ContainsGodotFailure(params string?[] values)
    {
        return ContainsAny(
            string.Join("\n", values.Where(value => !string.IsNullOrWhiteSpace(value))),
            "ERROR:",
            "SCRIPT ERROR",
            "Godot",
            "autoload",
            "associated class could not be found",
            "failed loading resource",
            "failed to instantiate",
            "cannot instantiate",
            "unhandled exception",
            "build-solutions prewarm timed out");
    }

    private static bool ContainsAny(string text, params string[] markers)
    {
        return markers.Any(marker => text.Contains(marker, StringComparison.OrdinalIgnoreCase));
    }

    private static string ReadLatestSmokeLog(string repoPath)
    {
        var smokeRoot = Path.Combine(repoPath, "logs", "ci");
        if (!Directory.Exists(smokeRoot))
        {
            return "";
        }

        try
        {
            var latestLog = Directory
                .EnumerateFiles(smokeRoot, "headless.log", SearchOption.AllDirectories)
                .Where(path => path.Replace('\\', '/').Contains("/smoke/", StringComparison.OrdinalIgnoreCase))
                .Select(path => new FileInfo(path))
                .OrderByDescending(file => file.LastWriteTimeUtc)
                .FirstOrDefault();
            return latestLog is null ? "" : File.ReadAllText(latestLog.FullName, System.Text.Encoding.UTF8);
        }
        catch (IOException)
        {
            return "";
        }
        catch (UnauthorizedAccessException)
        {
            return "";
        }
    }

    private static string BuildPublicExcerpt(string text)
    {
        var lines = text
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(line => ContainsAny(line, "ERROR:", "SCRIPT ERROR", "Exception", "failed", "cannot", "autoload", "class"))
            .Select(SanitizeLine)
            .Where(line => !string.IsNullOrWhiteSpace(line))
            .Distinct(StringComparer.Ordinal)
            .Take(8)
            .ToArray();
        var excerpt = lines.Length == 0 ? "No compact engine error excerpt was available." : string.Join("\n", lines);
        return excerpt.Length <= MaxExcerptLength ? excerpt : excerpt[..MaxExcerptLength];
    }

    private static string SanitizeLine(string line)
    {
        var sanitized = line.Replace('\\', '/');
        foreach (var token in sanitized.Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            if (token.Contains(":/", StringComparison.Ordinal) || token.StartsWith("res://", StringComparison.OrdinalIgnoreCase))
            {
                sanitized = sanitized.Replace(token, "[path]", StringComparison.Ordinal);
            }
        }

        return sanitized;
    }

    private static void TryDeleteDirectory(string root, string candidate, string scope, List<string> cleaned)
    {
        var fullPath = Path.GetFullPath(candidate);
        if (!WorkspacePathPolicy.IsUnderRoot(root, fullPath) || !Directory.Exists(fullPath))
        {
            return;
        }

        try
        {
            Directory.Delete(fullPath, recursive: true);
            cleaned.Add(scope);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static void TryDeleteFile(string root, string candidate, string scope, List<string> cleaned)
    {
        var fullPath = Path.GetFullPath(candidate);
        if (!WorkspacePathPolicy.IsUnderRoot(root, fullPath) || !File.Exists(fullPath))
        {
            return;
        }

        try
        {
            File.Delete(fullPath);
            cleaned.Add(scope);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }
}

internal sealed record GodotFailureDiagnostic(
    bool HasGodotFailure,
    bool CleanupRecommended,
    string Summary,
    string PublicExcerpt,
    string? SourceRunId)
{
    public static GodotFailureDiagnostic None(string? sourceRunId = null)
    {
        return new GodotFailureDiagnostic(false, false, "No recent Godot engine failure was detected.", "", sourceRunId);
    }
}

internal sealed record GodotCacheCleanupResult(bool Performed, IReadOnlyList<string> CleanedScopes);
