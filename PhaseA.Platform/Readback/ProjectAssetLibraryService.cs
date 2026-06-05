using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Readback;

public sealed class ProjectAssetLibraryService
{
    private const int MaxInstructionLength = 2000;
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly SkillActionService _skillActionService;
    private readonly ILlmRouteEngine? _llmRouteEngine;

    public ProjectAssetLibraryService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        SkillActionService skillActionService,
        ILlmRouteEngine? llmRouteEngine = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _skillActionService = skillActionService;
        _llmRouteEngine = llmRouteEngine;
    }

    public async Task<ProjectAssetLibraryResult?> ReadAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        return ReadLibrary(project);
    }

    public async Task<ProjectAssetGenerationRunResult?> GenerateAsync(
        string accountId,
        string projectId,
        ProjectAssetGenerationRunRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }
        if (request.Unit is null)
        {
            throw new ArgumentException("Asset unit is required.", nameof(request));
        }

        var unit = NormalizeUnit(request.Unit);
        var actionId = await ResolveActionIdAsync(project, unit, request.FloatingPrompt, cancellationToken);
        var entryId = Guid.NewGuid().ToString("N");
        var outputRelativeDirectory = ToSlash(Path.Combine("Game.Godot", "Prototypes", "ProjectAssetLibrary", unit.Key, entryId));
        var outputAbsoluteDirectory = Path.Combine(project.RepoPath, outputRelativeDirectory.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(outputAbsoluteDirectory);
        var prompt = BuildSkillPrompt(project, unit, request.FloatingPrompt, actionId, outputRelativeDirectory);
        var skillResult = await _skillActionService.RunAsync(
            accountId,
            projectId,
            actionId,
            new SkillActionRunRequest(prompt),
            cancellationToken);

        var library = ReadLibrary(project);
        var generatedFiles = EnumerateGeneratedFiles(project.RepoPath, outputAbsoluteDirectory).ToArray();
        var previewResourcePath = generatedFiles
            .Select(path => ToResPath(project.RepoPath, path))
            .FirstOrDefault(IsPreviewResource);
        var entry = new ProjectAssetLibraryEntry(
            entryId,
            DateTimeOffset.UtcNow.ToString("O"),
            skillResult.RunId,
            actionId,
            actionId == "map-making-master" ? "generate2dmap" : "generate2dsprite",
            prompt,
            skillResult.Status,
            skillResult.AssistantMessage,
            skillResult.Artifacts.Select(artifact => artifact.RelativePath).Concat(generatedFiles.Select(path => ToSlash(Path.GetRelativePath(project.RepoPath, path)))).ToArray(),
            previewResourcePath,
            false);
        if (!string.Equals(skillResult.Status, "succeeded", StringComparison.OrdinalIgnoreCase) && generatedFiles.Length == 0)
        {
            return new ProjectAssetGenerationRunResult(
                skillResult.Status,
                actionId,
                entry,
                library);
        }

        var existingUnit = UpsertUnit(library, unit);
        var updatedUnit = existingUnit with
        {
            Entries = [entry, .. existingUnit.Entries]
        };
        library = WriteUnit(library, updatedUnit);
        await WriteLibraryAsync(project, library, cancellationToken);

        return new ProjectAssetGenerationRunResult(
            skillResult.Status,
            actionId,
            entry,
            ReadLibrary(project));
    }

    public async Task<ProjectAssetLibraryResult?> SelectAsync(
        string accountId,
        string projectId,
        ProjectAssetSelectionRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var library = ReadLibrary(project);
        var units = library.Units.Select(unit =>
        {
            if (!string.Equals(unit.Key, request.UnitKey, StringComparison.Ordinal))
            {
                return unit;
            }

            return unit with
            {
                SelectedEntryId = request.EntryId,
                Entries = unit.Entries
                    .Select(entry => entry with { Selected = string.Equals(entry.EntryId, request.EntryId, StringComparison.Ordinal) })
                    .ToArray()
            };
        }).ToArray();
        library = library with { Units = units };
        await WriteLibraryAsync(project, library, cancellationToken);
        return library;
    }

    private async Task<ProjectSnapshot?> GetProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        return project;
    }

    private static ProjectAssetLibraryResult ReadLibrary(ProjectSnapshot project)
    {
        var path = LibraryPath(project);
        if (!File.Exists(path))
        {
            return new ProjectAssetLibraryResult(project.ProjectId, []);
        }

        try
        {
            return JsonSerializer.Deserialize<ProjectAssetLibraryResult>(
                       File.ReadAllText(path, Encoding.UTF8),
                       new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
                   ?? new ProjectAssetLibraryResult(project.ProjectId, []);
        }
        catch (JsonException)
        {
            return new ProjectAssetLibraryResult(project.ProjectId, []);
        }
    }

    private static async Task WriteLibraryAsync(ProjectSnapshot project, ProjectAssetLibraryResult library, CancellationToken cancellationToken)
    {
        var path = LibraryPath(project);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        await File.WriteAllTextAsync(
            path,
            JsonSerializer.Serialize(library, new JsonSerializerOptions { WriteIndented = true }),
            Encoding.UTF8,
            cancellationToken);
    }

    private static string LibraryPath(ProjectSnapshot project)
    {
        return Path.Combine(project.RepoPath, "meta", "assets", "library.json");
    }

    private static ProjectAssetLibraryUnit NormalizeUnit(ProjectAssetUnitRequest unit)
    {
        var scenePath = Trim(unit.ScenePath);
        var instanceName = Trim(unit.InstanceName);
        var resourcePath = Trim(unit.ResourcePath);
        var key = string.IsNullOrWhiteSpace(unit.UnitKey)
            ? ComputeUnitKey(scenePath, instanceName, resourcePath, Trim(unit.Kind))
            : Trim(unit.UnitKey);
        return new ProjectAssetLibraryUnit(
            key,
            instanceName,
            Trim(unit.NodeType),
            scenePath,
            resourcePath,
            Trim(unit.Kind),
            Trim(unit.IntendedUse),
            Trim(unit.Reason),
            null,
            []);
    }

    private static ProjectAssetLibraryUnit UpsertUnit(ProjectAssetLibraryResult library, ProjectAssetLibraryUnit unit)
    {
        return library.Units.FirstOrDefault(existing => string.Equals(existing.Key, unit.Key, StringComparison.Ordinal))
               ?? unit;
    }

    private static ProjectAssetLibraryResult WriteUnit(ProjectAssetLibraryResult library, ProjectAssetLibraryUnit unit)
    {
        var units = library.Units
            .Where(existing => !string.Equals(existing.Key, unit.Key, StringComparison.Ordinal))
            .Append(unit)
            .OrderBy(existing => existing.ScenePath, StringComparer.OrdinalIgnoreCase)
            .ThenBy(existing => existing.InstanceName, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        return library with { Units = units };
    }

    private async Task<string> ResolveActionIdAsync(
        ProjectSnapshot project,
        ProjectAssetLibraryUnit unit,
        string? floatingPrompt,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return ResolveActionIdHeuristic(unit, floatingPrompt);
        }

        var prompt = $$"""
            Decide the correct asset generation skill for one hosted Godot project asset unit.
            Return JSON only:
            {
              "actionId": "map-making-master|character-making-master",
              "reason": "short reason"
            }

            Choose map-making-master only for map, tilemap, terrain, level, room, field, overworld, background map, or spatial layout assets.
            Choose character-making-master for player, enemy, NPC, item, icon, projectile, effect, UI sprite, prop, or any sprite-like asset.

            Project:
            - GameName: {{project.GameName}}
            - GameType: {{project.GameTypeSource}}

            Asset unit:
            - InstanceName: {{unit.InstanceName}}
            - NodeType: {{unit.NodeType}}
            - ScenePath: {{unit.ScenePath}}
            - CurrentResource: {{unit.ResourcePath}}
            - SuggestedKind: {{unit.Kind}}
            - IntendedUse: {{unit.IntendedUse}}
            - Reason: {{unit.Reason}}

            User direction:
            {{Trim(floatingPrompt)}}
            """;
        try
        {
            var decision = await _llmRouteEngine.CompleteAsync(
                new LlmRouteRequest(
                    EnsureAssetLibraryDecisionWorkspace(project),
                    "project-asset-library-skill-selection",
                    "gpt-5.4",
                    prompt,
                    null,
                    project.AccountId,
                    RequireJsonObject: true),
                cancellationToken);
            if (!decision.Succeeded)
            {
                return ResolveActionIdHeuristic(unit, floatingPrompt);
            }

            using var document = JsonDocument.Parse(LlmRouteEngine.ExtractFirstJsonObject(decision.JsonObjectText ?? decision.AssistantMessage) ?? decision.AssistantMessage ?? "{}");
            var actionId = document.RootElement.TryGetProperty("actionId", out var actionElement) && actionElement.ValueKind == JsonValueKind.String
                ? actionElement.GetString()
                : null;
            return actionId is "map-making-master" or "character-making-master"
                ? actionId
                : ResolveActionIdHeuristic(unit, floatingPrompt);
        }
        catch (JsonException)
        {
            return ResolveActionIdHeuristic(unit, floatingPrompt);
        }
    }

    private static string ResolveActionIdHeuristic(ProjectAssetLibraryUnit unit, string? floatingPrompt)
    {
        var text = $"{unit.Kind} {unit.InstanceName} {unit.NodeType} {unit.IntendedUse} {unit.Reason} {floatingPrompt}".ToLowerInvariant();
        return text.Contains("map", StringComparison.Ordinal) ||
               text.Contains("tile", StringComparison.Ordinal) ||
               text.Contains("background", StringComparison.Ordinal) ||
               text.Contains("terrain", StringComparison.Ordinal)
            ? "map-making-master"
            : "character-making-master";
    }

    private static string EnsureAssetLibraryDecisionWorkspace(ProjectSnapshot project)
    {
        var repoParent = Path.GetDirectoryName(project.RepoPath);
        var workspaceRoot = string.IsNullOrWhiteSpace(repoParent) ? project.RepoPath : repoParent;
        var root = Path.Combine(workspaceRoot, "_phasea_llm", "asset-library");
        Directory.CreateDirectory(root);
        return root;
    }

    private static string BuildSkillPrompt(ProjectSnapshot project, ProjectAssetLibraryUnit unit, string? floatingPrompt, string actionId, string outputRelativeDirectory)
    {
        var userInstruction = Trim(floatingPrompt);
        if (userInstruction.Length > MaxInstructionLength)
        {
            userInstruction = userInstruction[..MaxInstructionLength];
        }

        var target = actionId == "map-making-master" ? "$generate2dmap" : "$generate2dsprite";
        return $"""
            Use {target} for this project asset unit.

            Project:
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            Asset unit:
            - InstanceName: {unit.InstanceName}
            - NodeType: {unit.NodeType}
            - ScenePath: {unit.ScenePath}
            - CurrentResource: {unit.ResourcePath}
            - SuggestedKind: {unit.Kind}
            - IntendedUse: {unit.IntendedUse}
            - Reason: {unit.Reason}

            User generation direction:
            {userInstruction}

            Required output directory:
            {outputRelativeDirectory}

            Generate or prepare this asset unit under the required output directory. If the selected skill can create image files, put the image files there. If real image generation is unavailable, write an asset-spec.md or generation-prompt.md there with the exact prompt, style constraints, dimensions, and intended usage.
            """;
    }

    private static IEnumerable<string> EnumerateGeneratedFiles(string projectRoot, string outputAbsoluteDirectory)
    {
        if (!Directory.Exists(outputAbsoluteDirectory))
        {
            yield break;
        }

        foreach (var path in Directory.EnumerateFiles(outputAbsoluteDirectory, "*", SearchOption.AllDirectories))
        {
            var fullPath = Path.GetFullPath(path);
            if (WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath))
            {
                yield return fullPath;
            }
        }
    }

    private static bool IsPreviewResource(string resourcePath)
    {
        var extension = Path.GetExtension(resourcePath);
        return resourcePath.StartsWith("res://", StringComparison.Ordinal) &&
               (extension.Equals(".png", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".webp", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".svg", StringComparison.OrdinalIgnoreCase));
    }

    private static string ToResPath(string projectRoot, string absolutePath)
    {
        return $"res://{ToSlash(Path.GetRelativePath(projectRoot, absolutePath))}";
    }

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }

    private static string ComputeUnitKey(string scenePath, string instanceName, string resourcePath, string kind)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes($"{scenePath}|{instanceName}|{resourcePath}|{kind}"));
        return Convert.ToHexString(bytes)[..24].ToLowerInvariant();
    }

    private static string Trim(string? value)
    {
        return value?.Trim() ?? "";
    }
}

public sealed record ProjectAssetLibraryResult(
    string ProjectId,
    IReadOnlyList<ProjectAssetLibraryUnit> Units);

public sealed record ProjectAssetLibraryUnit(
    string Key,
    string InstanceName,
    string NodeType,
    string ScenePath,
    string ResourcePath,
    string Kind,
    string IntendedUse,
    string Reason,
    string? SelectedEntryId,
    IReadOnlyList<ProjectAssetLibraryEntry> Entries);

public sealed record ProjectAssetLibraryEntry(
    string EntryId,
    string CreatedUtc,
    string RunId,
    string ActionId,
    string SkillName,
    string Prompt,
    string Status,
    string AssistantMessage,
    IReadOnlyList<string> ArtifactPaths,
    string? PreviewResourcePath,
    bool Selected);

public sealed record ProjectAssetGenerationRunRequest(
    string? FloatingPrompt,
    ProjectAssetUnitRequest? Unit);

public sealed record ProjectAssetUnitRequest(
    string? UnitKey,
    string? InstanceName,
    string? NodeType,
    string? ScenePath,
    string? ResourcePath,
    string? Kind,
    string? IntendedUse,
    string? Reason);

public sealed record ProjectAssetGenerationRunResult(
    string Status,
    string ActionId,
    ProjectAssetLibraryEntry Entry,
    ProjectAssetLibraryResult Library);

public sealed record ProjectAssetSelectionRequest(
    string UnitKey,
    string EntryId);
