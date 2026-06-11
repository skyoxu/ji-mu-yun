using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using Microsoft.Extensions.DependencyInjection;

namespace PhaseA.Platform.Readback;

public sealed class ProjectAssetLibraryService
{
    private const string RunType = "project-asset-generation";
    private const int MaxInstructionLength = 2000;
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly ProjectAssetImageGenerator _imageGenerator;
    private readonly ILlmRouteEngine? _llmRouteEngine;
    private readonly HeavyRunnerQueueService _assetRunnerQueue;

    public ProjectAssetLibraryService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ProjectAssetImageGenerator imageGenerator,
        ILlmRouteEngine? llmRouteEngine = null,
        [FromKeyedServices("asset-generation")] HeavyRunnerQueueService? assetRunnerQueue = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _imageGenerator = imageGenerator;
        _llmRouteEngine = llmRouteEngine;
        _assetRunnerQueue = assetRunnerQueue ?? new HeavyRunnerQueueService(TimeSpan.FromMinutes(4), options.MaxConcurrentAssetGenerations);
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
        var count = Math.Clamp(request.Count ?? 1, 1, 4);
        var actionId = await ResolveActionIdAsync(project, unit, request.FloatingPrompt, cancellationToken);
        var entryId = Guid.NewGuid().ToString("N");
        var outputRelativeDirectory = ToSlash(Path.Combine("Game.Godot", "Prototypes", "ProjectAssetLibrary", unit.Key, entryId));
        var outputAbsoluteDirectory = Path.Combine(project.RepoPath, outputRelativeDirectory.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(outputAbsoluteDirectory);
        var prompt = BuildImagePrompt(project, unit, request.FloatingPrompt, actionId);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await using var assetQueueLease = await _assetRunnerQueue.EnterAsync(
            runId,
            project.AccountId,
            project.ProjectId,
            RunType,
            cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, assetQueueLease.QueuePositionAtStart, cancellationToken);

        ProjectAssetImageGenerationResult imageResult;
        string? referenceImagePath = null;
        try
        {
            referenceImagePath = WriteTemporaryReferenceImage(outputAbsoluteDirectory, request);
            imageResult = await _imageGenerator.GenerateAsync(
                project,
                runId,
                prompt,
                outputAbsoluteDirectory,
                outputRelativeDirectory,
                SanitizeFileStem(unit.InstanceName, actionId),
                count,
                referenceImagePath,
                cancellationToken);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            var failureEvidence = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                action_id = actionId,
                skill_name = actionId == "map-making-master" ? "generate2dmap" : "generate2dsprite",
                output_directory = outputRelativeDirectory,
                failure = ex.Message
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), failureEvidence, CancellationToken.None);
            imageResult = new ProjectAssetImageGenerationResult(
                runId,
                "failed",
                500,
                "",
                ex.ToString(),
                $"轻量图片生成失败：{ex.Message}",
                [],
                TimeSpan.Zero);
        }
        finally
        {
            if (!string.IsNullOrWhiteSpace(referenceImagePath) && File.Exists(referenceImagePath))
            {
                File.Delete(referenceImagePath);
                var referenceDirectory = Path.GetDirectoryName(referenceImagePath);
                if (!string.IsNullOrWhiteSpace(referenceDirectory) && Directory.Exists(referenceDirectory))
                {
                    Directory.Delete(referenceDirectory, recursive: true);
                }
            }
        }

        foreach (var artifactPath in imageResult.ArtifactPaths)
        {
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "project-asset-generation-output",
                artifactPath,
                "Project asset generation output"), cancellationToken);
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            action_id = actionId,
            skill_name = actionId == "map-making-master" ? "generate2dmap" : "generate2dsprite",
            generation_mode = string.Equals(request.GenerationMode, "image-to-image", StringComparison.OrdinalIgnoreCase) ? "image-to-image" : "text-to-image",
            requested_count = count,
            output_directory = outputRelativeDirectory,
            elapsed_seconds = Math.Round(imageResult.Elapsed.TotalSeconds, 3),
            artifacts = imageResult.ArtifactPaths
        });
        await _metadataStore.CompleteRunAsync(
            runId,
            imageResult.Status,
            imageResult.ExitCode,
            imageResult.Stdout,
            imageResult.Stderr,
            evidenceJson,
            cancellationToken);

        var library = ReadLibrary(project);
        var generatedFiles = EnumerateGeneratedFiles(project.RepoPath, outputAbsoluteDirectory).ToArray();
        var generatedImageFiles = generatedFiles
            .Where(path => IsPreviewResource(ToResPath(project.RepoPath, path)))
            .ToArray();
        var skillSucceeded = string.Equals(imageResult.Status, "succeeded", StringComparison.OrdinalIgnoreCase);
        var entryStatus = skillSucceeded && generatedImageFiles.Length == 0
            ? "no_image_generated"
            : imageResult.Status;
        if (generatedImageFiles.Length == 0)
        {
            var entry = CreateLibraryEntry(project, entryId, runId, actionId, prompt, entryStatus, imageResult, null, generatedImageFiles);
            return new ProjectAssetGenerationRunResult(
                entryStatus,
                actionId,
                entry,
                library);
        }

        var existingUnit = UpsertUnit(library, unit);
        var entries = generatedImageFiles
            .Select((path, index) => CreateLibraryEntry(project, index == 0 ? entryId : $"{entryId}-{index + 1:00}", runId, actionId, prompt, entryStatus, imageResult, path, generatedImageFiles))
            .ToArray();
        var updatedUnit = existingUnit with
        {
            Entries = [.. entries, .. existingUnit.Entries]
        };
        library = WriteUnit(library, updatedUnit);
        await WriteLibraryAsync(project, library, cancellationToken);

        return new ProjectAssetGenerationRunResult(
            imageResult.Status,
            actionId,
            entries[0],
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

    private static ProjectAssetLibraryEntry CreateLibraryEntry(
        ProjectSnapshot project,
        string entryId,
        string runId,
        string actionId,
        string prompt,
        string entryStatus,
        ProjectAssetImageGenerationResult imageResult,
        string? generatedImageFile,
        IReadOnlyList<string> generatedImageFiles)
    {
        var previewResourcePath = string.IsNullOrWhiteSpace(generatedImageFile)
            ? null
            : ToResPath(project.RepoPath, generatedImageFile);
        return new ProjectAssetLibraryEntry(
            entryId,
            DateTimeOffset.UtcNow.ToString("O"),
            runId,
            actionId,
            actionId == "map-making-master" ? "generate2dmap" : "generate2dsprite",
            prompt,
            entryStatus,
            imageResult.AssistantMessage,
            imageResult.ArtifactPaths.Concat(generatedImageFiles.Select(path => ToSlash(Path.GetRelativePath(project.RepoPath, path)))).Distinct(StringComparer.Ordinal).ToArray(),
            previewResourcePath,
            false);
    }

    private static string? WriteTemporaryReferenceImage(string outputAbsoluteDirectory, ProjectAssetGenerationRunRequest request)
    {
        if (!string.Equals(request.GenerationMode, "image-to-image", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var fileName = Trim(request.ReferenceImageFileName);
        var payload = Trim(request.ReferenceImageBase64);
        if (string.IsNullOrWhiteSpace(fileName) || string.IsNullOrWhiteSpace(payload))
        {
            throw new ArgumentException("Reference image is required for image-to-image generation.");
        }

        var extension = Path.GetExtension(fileName).ToLowerInvariant();
        if (extension is not ".png" and not ".jpg" and not ".jpeg" and not ".webp")
        {
            throw new ArgumentException("Reference image must be png, jpg, jpeg, or webp.");
        }

        var contentType = Trim(request.ReferenceImageContentType).ToLowerInvariant();
        if (!string.IsNullOrWhiteSpace(contentType) &&
            contentType is not "image/png" and not "image/jpeg" and not "image/webp")
        {
            throw new ArgumentException("Reference image content type must be image/png, image/jpeg, or image/webp.");
        }

        var commaIndex = payload.IndexOf(',', StringComparison.Ordinal);
        if (commaIndex >= 0)
        {
            payload = payload[(commaIndex + 1)..];
        }

        var bytes = Convert.FromBase64String(payload);
        if (bytes.Length > 10 * 1024 * 1024)
        {
            throw new ArgumentException("Reference image must be 10MB or smaller.");
        }

        var tempDirectory = Path.Combine(Path.GetTempPath(), "phasea-asset-reference", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDirectory);
        var path = Path.Combine(tempDirectory, $"reference-input{extension}");
        File.WriteAllBytes(path, bytes);
        return path;
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

    private static string BuildImagePrompt(ProjectSnapshot project, ProjectAssetLibraryUnit unit, string? floatingPrompt, string actionId)
    {
        var userInstruction = Trim(floatingPrompt);
        if (userInstruction.Length > MaxInstructionLength)
        {
            userInstruction = userInstruction[..MaxInstructionLength];
        }

        var assetMode = actionId == "map-making-master" ? "2D map/background asset" : "2D sprite/game asset";
        var currentResourceNote = string.IsNullOrWhiteSpace(unit.ResourcePath)
            ? "(none)"
            : unit.ResourcePath;
        var directionText = string.IsNullOrWhiteSpace(userInstruction)
            ? "(no explicit user style direction; infer only the minimum asset subject from the asset unit)"
            : userInstruction;
        return $"""
            Create one production-oriented {assetMode} for this hosted Godot project asset unit.

            Project:
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource} (classification only; do not treat this as a mandatory visual style when user direction says otherwise)

            Asset unit:
            - InstanceName: {unit.InstanceName}
            - NodeType: {unit.NodeType}
            - ScenePath: {unit.ScenePath}
            - CurrentResource: {currentResourceNote}
            - SuggestedKind: {unit.Kind}
            - IntendedUse: {unit.IntendedUse}
            - Reason: {unit.Reason}

            User generation direction:
            {directionText}

            Prompt isolation rules:
            - Treat User generation direction as the highest-priority style source.
            - Treat CurrentResource only as the asset slot being replaced. Do not copy its visual style, palette, composition, filename, or previous generated output unless the user explicitly asks to reference it.
            - Do not infer style from previous entries in Game.Godot/Prototypes/ProjectAssetLibrary.
            - Do not reuse earlier generation-prompt files, asset-manifest files, or previous fallback SVG/PNG decisions as style anchors.
            - IntendedUse and Reason describe gameplay placement only; do not let template wording such as JRPG, DQ, Dragon Quest, Final Fantasy, pixel art, or 16-bit override the current user direction.
            - If the user direction is empty, produce a neutral asset matching only the asset subject, gameplay role, and transparent-background requirement.

            Image requirements:
            - Generate exactly one clean game asset image.
            - No text, no watermark, no UI chrome, no border.
            - Use transparent background by default. Use an opaque or scene background only when the user generation direction explicitly asks for one.
            - Keep the subject centered with safe padding so it can be used as a Godot Texture2D.
            """;
    }

    private static string SanitizeFileStem(string value, string actionId)
    {
        var fallback = actionId == "map-making-master" ? "generated-map-asset" : "generated-sprite-asset";
        var source = string.IsNullOrWhiteSpace(value) ? fallback : value.Trim();
        var builder = new StringBuilder(source.Length);
        foreach (var ch in source)
        {
            if (char.IsAsciiLetterOrDigit(ch))
            {
                builder.Append(char.ToLowerInvariant(ch));
            }
            else if (ch is '-' or '_' || char.IsWhiteSpace(ch))
            {
                builder.Append('-');
            }
        }

        var stem = builder.ToString().Trim('-');
        while (stem.Contains("--", StringComparison.Ordinal))
        {
            stem = stem.Replace("--", "-", StringComparison.Ordinal);
        }

        return string.IsNullOrWhiteSpace(stem) ? fallback : stem[..Math.Min(stem.Length, 64)];
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
    ProjectAssetUnitRequest? Unit,
    string? GenerationMode = null,
    int? Count = null,
    string? ReferenceImageFileName = null,
    string? ReferenceImageBase64 = null,
    string? ReferenceImageContentType = null);

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
