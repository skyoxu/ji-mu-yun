using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeEngineeringClosureService
{
    public const string StructureRelativePath = "docs/prototype/STRUCTURE.md";
    public const string MemoryRelativePath = "docs/prototype/MEMORY.md";
    public const string AssetsRelativePath = "docs/prototype/ASSETS.md";

    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true
    };

    public PrototypeEngineeringClosureSnapshot EnsureProjectFiles(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);

        Directory.CreateDirectory(Path.Combine(project.RepoPath, "docs", "prototype"));
        var structure = RefreshText(project, StructureRelativePath, BuildStructure(project));
        var memory = RefreshMemory(project);
        var assets = EnsureText(project, AssetsRelativePath, BuildDefaultAssets(project));
        return new PrototypeEngineeringClosureSnapshot(structure, memory, assets);
    }

    public async Task<PrototypeEngineeringEvidenceWriteResult> WriteEvidenceAsync(
        ProjectSnapshot project,
        PrototypeEngineeringEvidence evidence,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(evidence);

        var safeProjectId = SafeSegment(project.ProjectId);
        var safeRunId = SafeSegment(evidence.RunId);
        var relativeDirectory = Path.Combine("logs", "prototype-evidence", safeProjectId, safeRunId);
        var absoluteDirectory = Path.Combine(project.RepoPath, relativeDirectory);
        Directory.CreateDirectory(absoluteDirectory);

        var relativePath = Path.Combine(relativeDirectory, "evidence.json").Replace('\\', '/');
        var absolutePath = Path.Combine(absoluteDirectory, "evidence.json");
        var payload = BuildEvidencePayload(project, evidence, relativePath);
        await File.WriteAllTextAsync(
            absolutePath,
            JsonSerializer.Serialize(payload, JsonOptions),
            Encoding.UTF8,
            cancellationToken);

        return new PrototypeEngineeringEvidenceWriteResult(relativePath);
    }

    public async Task TouchMemoryAsync(
        ProjectSnapshot project,
        string route,
        string runId,
        string status,
        string? moduleId,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);
        EnsureProjectFiles(project);

        var memoryPath = Resolve(project, MemoryRelativePath);
        var line = $"- {DateTimeOffset.UtcNow:O} route={route}; run={runId}; module={moduleId ?? "n/a"}; status={status}";
        await File.AppendAllTextAsync(memoryPath, Environment.NewLine + line + Environment.NewLine, Encoding.UTF8, cancellationToken);
    }

    private static object BuildEvidencePayload(ProjectSnapshot project, PrototypeEngineeringEvidence evidence, string relativePath)
    {
        return new
        {
            schemaVersion = 1,
            projectId = project.ProjectId,
            runId = evidence.RunId,
            route = evidence.Route,
            moduleId = evidence.ModuleId,
            status = evidence.Status,
            startedAt = evidence.StartedAtUtc ?? DateTimeOffset.UtcNow.ToString("O"),
            finishedAt = evidence.FinishedAtUtc ?? DateTimeOffset.UtcNow.ToString("O"),
            repairAttempts = evidence.RepairAttempts,
            evidencePath = relativePath,
            checks = new
            {
                dotnetBuild = evidence.DotnetBuild,
                godotImport = evidence.GodotImport,
                headlessLoad = evidence.HeadlessLoad,
                milestoneSmoke = evidence.MilestoneSmoke,
                localEntryContract = evidence.LocalEntryContract,
                assetValidation = evidence.AssetValidation,
                frameCheck = evidence.FrameCheck
            },
            riskItems = evidence.RiskItems,
            changedFiles = evidence.ChangedFiles,
            failureSummary = evidence.FailureSummary
        };
    }

    private static string EnsureText(ProjectSnapshot project, string relativePath, string defaultText)
    {
        var path = Resolve(project, relativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        if (!File.Exists(path))
        {
            File.WriteAllText(path, defaultText, Encoding.UTF8);
        }

        return relativePath;
    }

    private static string RefreshText(ProjectSnapshot project, string relativePath, string text)
    {
        var path = Resolve(project, relativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text, Encoding.UTF8);
        return relativePath;
    }

    private static string Resolve(ProjectSnapshot project, string relativePath)
    {
        return Path.Combine(project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
    }

    private static string RefreshMemory(ProjectSnapshot project)
    {
        var path = Resolve(project, MemoryRelativePath);
        var previous = File.Exists(path) ? File.ReadAllText(path, Encoding.UTF8) : "";
        var events = ExtractMemoryEvents(previous);
        var text = BuildMemory(project, events);
        return RefreshText(project, MemoryRelativePath, text);
    }

    private static string BuildStructure(ProjectSnapshot project)
    {
        var facts = ScanProjectFacts(project);
        return $"""
            # STRUCTURE

            - engine: Godot 4.5.1 mono
            - dotnet: net8.0
            - project_id: {project.ProjectId}
            - main_scene: {facts.MainScene}
            - prototype_scene: {facts.PrototypeScene}
            - modules: {FormatList(facts.Modules)}
            - scenes: {FormatList(facts.Scenes)}
            - scripts: {FormatList(facts.Scripts)}
            - inputs: {FormatList(facts.Inputs)}
            - collision_layers: {FormatList(facts.CollisionLayers)}
            - autoloads: {FormatList(facts.Autoloads)}
            - runtime_resources: {FormatList(facts.RuntimeResources)}
            """;
    }

    private static string BuildMemory(ProjectSnapshot project, IReadOnlyList<string> events)
    {
        var facts = ScanProjectFacts(project);
        return $"""
            # MEMORY

            - project_id: {project.ProjectId}
            - dimension: {facts.Dimension}
            - physics: {facts.Physics}
            - stable_scenes: {FormatList(facts.Scenes)}
            - stable_scripts: {FormatList(facts.Scripts)}
            - confirmed_inputs: {FormatList(facts.Inputs)}
            - known_errors: []
            - module_facts: []

            ## Events
            {FormatEventLines(events)}
            """;
    }

    private static string BuildDefaultAssets(ProjectSnapshot project)
    {
        return $"""
            # ASSETS

            - project_id: {project.ProjectId}
            - assets: []
            - rule: Assets are marked verified only after download/import/bind/collision-or-smoke validation passes.
            """;
    }

    private static string SafeSegment(string value)
    {
        var chars = value.Select(ch => char.IsLetterOrDigit(ch) || ch is '-' or '_' ? ch : '-').ToArray();
        var safe = new string(chars).Trim('-');
        return string.IsNullOrWhiteSpace(safe) ? "unknown" : safe;
    }

    private static PrototypeProjectFacts ScanProjectFacts(ProjectSnapshot project)
    {
        var projectGodot = Path.Combine(project.RepoPath, "project.godot");
        var projectText = File.Exists(projectGodot) ? File.ReadAllText(projectGodot, Encoding.UTF8) : "";
        var mainScene = ExtractProjectGodotValue(projectText, "run/main_scene");
        var scenes = EnumerateRelativeFiles(project.RepoPath, ["Game.Godot/Prototypes", "Game.Godot/Scenes"], "*.tscn");
        var scripts = EnumerateRelativeFiles(project.RepoPath, ["Game.Godot/Prototypes", "Game.Godot/Scripts", "Game.Core/Prototypes"], "*.cs");
        var resources = EnumerateRelativeFiles(project.RepoPath, ["Game.Godot/Prototypes", "Game.Godot/Assets"], "*.*")
            .Where(path => IsRuntimeResource(path))
            .Take(80)
            .ToArray();
        var prototypeScene = scenes.FirstOrDefault(path => path.Contains("/Prototypes/", StringComparison.OrdinalIgnoreCase)) ?? "<pending>";
        var modules = Directory.Exists(Path.Combine(project.RepoPath, "docs"))
            ? Directory.EnumerateFiles(Path.Combine(project.RepoPath, "docs"), "m*-*.md", SearchOption.TopDirectoryOnly)
                .Select(path => Path.GetFileNameWithoutExtension(path))
                .OrderBy(value => value, StringComparer.OrdinalIgnoreCase)
                .Take(40)
                .ToArray()
            : [];

        var runtimeText = ReadSmallRuntimeFiles(project.RepoPath, scenes.Concat(scripts));

        return new PrototypeProjectFacts(
            string.IsNullOrWhiteSpace(mainScene) ? "<pending>" : mainScene,
            prototypeScene,
            modules,
            scenes,
            scripts,
            ExtractProjectGodotSectionKeys(projectText, "input"),
            ExtractProjectGodotSectionKeys(projectText, "layer_names"),
            ExtractProjectGodotSectionKeys(projectText, "autoload"),
            resources,
            DetectDimension(scenes, scripts, runtimeText),
            DetectPhysics(scenes, scripts, projectText, runtimeText));
    }

    private static string[] EnumerateRelativeFiles(string repoPath, IReadOnlyList<string> roots, string pattern)
    {
        return roots
            .Select(root => Path.Combine(repoPath, root.Replace('/', Path.DirectorySeparatorChar)))
            .Where(Directory.Exists)
            .SelectMany(root => Directory.EnumerateFiles(root, pattern, SearchOption.AllDirectories))
            .Select(path => Path.GetRelativePath(repoPath, path).Replace('\\', '/'))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .Take(120)
            .ToArray();
    }

    private static string ExtractProjectGodotValue(string text, string key)
    {
        foreach (var line in text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries))
        {
            var trimmed = line.Trim();
            if (!trimmed.StartsWith(key + "=", StringComparison.Ordinal))
            {
                continue;
            }

            return trimmed[(key.Length + 1)..].Trim().Trim('"');
        }

        return "";
    }

    private static string[] ExtractProjectGodotSectionKeys(string text, string section)
    {
        var inSection = false;
        var values = new List<string>();
        foreach (var line in text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries))
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("[", StringComparison.Ordinal) && trimmed.EndsWith("]", StringComparison.Ordinal))
            {
                inSection = string.Equals(trimmed.Trim('[', ']'), section, StringComparison.OrdinalIgnoreCase);
                continue;
            }

            if (!inSection || !trimmed.Contains('=', StringComparison.Ordinal) || trimmed.StartsWith(';'))
            {
                continue;
            }

            values.Add(trimmed.Split('=', 2)[0].Trim().Trim('"'));
        }

        return values.Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(value => value, StringComparer.OrdinalIgnoreCase).Take(80).ToArray();
    }

    private static bool IsRuntimeResource(string relativePath)
    {
        var extension = Path.GetExtension(relativePath);
        return extension.Equals(".png", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".webp", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".glb", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".gltf", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".obj", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".tres", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".res", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".wav", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".ogg", StringComparison.OrdinalIgnoreCase);
    }

    private static string ReadSmallRuntimeFiles(string repoPath, IEnumerable<string> relativePaths)
    {
        var builder = new StringBuilder();
        foreach (var relativePath in relativePaths.Take(80))
        {
            var path = Path.Combine(repoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path))
            {
                continue;
            }

            var info = new FileInfo(path);
            if (info.Length > 256_000)
            {
                continue;
            }

            builder.AppendLine(File.ReadAllText(path, Encoding.UTF8));
        }

        return builder.ToString();
    }

    private static string DetectDimension(IReadOnlyList<string> scenes, IReadOnlyList<string> scripts, string runtimeText)
    {
        var combined = string.Join('\n', scenes.Concat(scripts)) + "\n" + runtimeText;
        if (combined.Contains("3D", StringComparison.OrdinalIgnoreCase) ||
            combined.Contains("CharacterBody3D", StringComparison.OrdinalIgnoreCase))
        {
            return "3d";
        }

        if (combined.Contains("2D", StringComparison.OrdinalIgnoreCase) ||
            combined.Contains("CharacterBody2D", StringComparison.OrdinalIgnoreCase))
        {
            return "2d";
        }

        return "<pending>";
    }

    private static string DetectPhysics(IReadOnlyList<string> scenes, IReadOnlyList<string> scripts, string projectText, string runtimeText)
    {
        var combined = string.Join('\n', scenes.Concat(scripts)) + "\n" + projectText + "\n" + runtimeText;
        if (combined.Contains("CharacterBody3D", StringComparison.OrdinalIgnoreCase) ||
            combined.Contains("RigidBody3D", StringComparison.OrdinalIgnoreCase) ||
            combined.Contains("CollisionShape3D", StringComparison.OrdinalIgnoreCase))
        {
            return "godot-3d-physics";
        }

        if (combined.Contains("CharacterBody2D", StringComparison.OrdinalIgnoreCase) ||
            combined.Contains("RigidBody2D", StringComparison.OrdinalIgnoreCase) ||
            combined.Contains("CollisionShape2D", StringComparison.OrdinalIgnoreCase))
        {
            return "godot-2d-physics";
        }

        return "<pending>";
    }

    private static IReadOnlyList<string> ExtractMemoryEvents(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return [];
        }

        var start = text.IndexOf("## Events", StringComparison.OrdinalIgnoreCase);
        var source = start >= 0 ? text[start..] : text;
        return source
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.Trim())
            .Where(line => line.StartsWith("- ", StringComparison.Ordinal) && line.Contains("route=", StringComparison.Ordinal))
            .Distinct(StringComparer.Ordinal)
            .TakeLast(80)
            .ToArray();
    }

    private static string FormatList(IReadOnlyList<string> values)
    {
        return values.Count == 0 ? "[]" : JsonSerializer.Serialize(values, JsonOptions);
    }

    private static string FormatEventLines(IReadOnlyList<string> events)
    {
        return events.Count == 0 ? "- none" : string.Join(Environment.NewLine, events);
    }

    private sealed record PrototypeProjectFacts(
        string MainScene,
        string PrototypeScene,
        IReadOnlyList<string> Modules,
        IReadOnlyList<string> Scenes,
        IReadOnlyList<string> Scripts,
        IReadOnlyList<string> Inputs,
        IReadOnlyList<string> CollisionLayers,
        IReadOnlyList<string> Autoloads,
        IReadOnlyList<string> RuntimeResources,
        string Dimension,
        string Physics);
}

public sealed record PrototypeEngineeringClosureSnapshot(
    string StructureRelativePath,
    string MemoryRelativePath,
    string AssetsRelativePath);

public sealed record PrototypeEngineeringEvidenceWriteResult(string RelativePath);

public sealed record PrototypeEngineeringEvidence(
    string RunId,
    string Route,
    string Status,
    string? ModuleId = null,
    string? StartedAtUtc = null,
    string? FinishedAtUtc = null,
    int RepairAttempts = 0,
    PrototypeEngineeringCheckResult? DotnetBuild = null,
    PrototypeEngineeringCheckResult? GodotImport = null,
    PrototypeEngineeringCheckResult? HeadlessLoad = null,
    PrototypeEngineeringCheckResult? MilestoneSmoke = null,
    PrototypeEngineeringCheckResult? LocalEntryContract = null,
    PrototypeEngineeringCheckResult? AssetValidation = null,
    PrototypeEngineeringCheckResult? FrameCheck = null,
    IReadOnlyList<string>? RiskItems = null,
    IReadOnlyList<string>? ChangedFiles = null,
    IReadOnlyList<string>? FailureSummary = null);

public sealed record PrototypeEngineeringCheckResult(
    string Status,
    string? Log = null,
    string? Reason = null)
{
    public static PrototypeEngineeringCheckResult Passed(string? log = null)
        => new("passed", log);

    public static PrototypeEngineeringCheckResult Failed(string? log = null, string? reason = null)
        => new("failed", log, reason);

    public static PrototypeEngineeringCheckResult Skipped(string reason)
        => new("skipped", null, reason);
}
