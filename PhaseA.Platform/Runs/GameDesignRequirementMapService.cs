using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

public sealed class GameDesignRequirementMapService
{
    private const string GddRelativePath = "docs/gdd/GDD.md";
    private const string SceneRouteRelativePath = "meta/routes/scene-route/latest.json";
    private const string GddDocumentRelativePath = "meta/routes/gdd-document/latest.json";
    private const string RequirementMapRelativePath = "meta/routes/gdd-requirements/latest.json";
    private const string ContractRelativePath = "routes/prototype-contract/latest.json";
    private static readonly Regex RequirementLineRegex = new(@"^\s*(?:[-*]|\d+[\.\)、:：])\s*(?<text>.+)$", RegexOptions.Compiled);
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly ILlmRouteEngine? _llmRouteEngine;

    public GameDesignRequirementMapService(PhaseAMetadataStore metadataStore, ILlmRouteEngine? llmRouteEngine = null)
    {
        _metadataStore = metadataStore;
        _llmRouteEngine = llmRouteEngine;
    }

    public async Task<GameDesignRequirementMapResult?> GetLatestAsync(string accountId, string projectId, CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        return ReadLatest(project);
    }

    public async Task<GameDesignRequirementMapResult> CreateAsync(
        string accountId,
        string projectId,
        GameDesignRequirementMapRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return GameDesignRequirementMapResult.NotFound(projectId);
        }

        var validation = ValidateSources(project);
        if (validation is not null)
        {
            return validation;
        }

        var gddPath = Resolve(project.RepoPath, GddRelativePath);
        var scenePath = Resolve(project.RepoPath, SceneRouteRelativePath);
        var gddDocumentPath = Resolve(project.RepoPath, GddDocumentRelativePath);
        var gddText = await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken);
        using var sceneDoc = JsonDocument.Parse(await File.ReadAllTextAsync(scenePath, Encoding.UTF8, cancellationToken));
        using var gddDoc = JsonDocument.Parse(await File.ReadAllTextAsync(gddDocumentPath, Encoding.UTF8, cancellationToken));
        var sourceGddHash = Sha256(NormalizeText(gddText));
        var sceneHash = ReadString(sceneDoc.RootElement, "confirmed_scene_route_hash");
        var contractSnapshotHash = ReadString(sceneDoc.RootElement, "source_contract_snapshot_hash");
        var requirements = BuildDeterministicRequirements(gddText, sceneDoc.RootElement);
        if (requirements.Count == 0)
        {
            requirements.Add(new GameDesignRequirementRow(
                "REQ-001",
                "GDD",
                "No concrete requirement could be extracted from the current GDD.",
                "en",
                "normalized_english_summary",
                "Review the current GDD and add concrete gameplay, scene, or UI requirements.",
                "P1",
                "meta",
                [],
                [],
                [],
                "needs_review",
                "",
                "",
                "",
                "system",
                "",
                "",
                [],
                ["Requirement map must not be empty."]));
        }

        var coverage = new GameDesignRequirementCoverageSummary(
            requirements.Count,
            requirements.Count(item => item.Status == "mapped"),
            requirements.Count(item => item.Status == "missing_scene"),
            requirements.Count(item => item.Status == "missing_module"),
            requirements.Count(item => item.Status == "explicitly_deferred"),
            requirements.Count(item => item.Status == "conflict"));
        var status = requirements.Any(item => item.Priority is "P0" or "P1" && item.Status is "missing_scene" or "missing_module" or "needs_review" or "conflict")
            ? "needs_review"
            : "ready";
        var now = DateTimeOffset.UtcNow.ToString("O");
        var result = new GameDesignRequirementMapResult(
            project.ProjectId,
            status,
            sourceGddHash,
            sceneHash,
            Sha256(NormalizeText(JsonSerializer.Serialize(requirements, JsonOptions()))),
            contractSnapshotHash,
            $"{GodotUiCapabilityContract.ContractId}.v{GodotUiCapabilityContract.ContractVersion}",
            GodotUiCapabilityContract.ContractHash,
            coverage,
            requirements,
            BuildBlockingIssues(requirements),
            [new ProjectRouteStateEvidenceRef("sidecar", RequirementMapRelativePath)],
            now,
            "returned_existing");

        var output = new
        {
            schema_version = "gdd-requirements.v1",
            route = "gdd-requirements",
            project_id = project.ProjectId,
            source_gdd_path = GddRelativePath,
            source_gdd_hash = result.SourceGddHash,
            source_scene_route_hash = result.SourceSceneRouteHash,
            source_contract_snapshot_hash = result.SourceContractSnapshotHash,
            godot_ui_contract_version = result.GodotUiContractVersion,
            source_godot_ui_contract_hash = result.SourceGodotUiContractHash,
            status_dimension = "route_readback",
            status_allowed_values = new[] { "ready", "needs_review", "blocked", "stale", "unknown" },
            status,
            readiness_scope = "requirement_map",
            status_reason = status == "ready" ? "" : "P0/P1 requirements need review before contract freeze.",
            updated_utc = now,
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = "hosted-route-recovery-order.v1",
                authority_sources = new[] { "docs/gdd/GDD.md", "confirmed scene route", "project contract snapshot" },
                source_hashes = new Dictionary<string, string>
                {
                    [GddRelativePath] = result.SourceGddHash,
                    [SceneRouteRelativePath] = result.SourceSceneRouteHash,
                    ["project-contract-snapshot"] = result.SourceContractSnapshotHash
                },
                forbidden_source_patterns = new[] { "docs/game-type-guides/** raw excerpts" },
                prompt_evidence_refs = Array.Empty<object>(),
                checked_utc = now
            },
            evidence_refs = new[] { new { kind = "sidecar", path = RequirementMapRelativePath } },
            coverage_summary = new
            {
                requirement_count = coverage.RequirementCount,
                covered_count = coverage.CoveredCount,
                missing_scene_count = coverage.MissingSceneCount,
                missing_module_count = coverage.MissingModuleCount,
                explicitly_deferred_count = coverage.ExplicitlyDeferredCount,
                conflict_count = coverage.ConflictCount
            },
            requirements = requirements.Select(ToSidecarRequirement).ToArray()
        };
        await WriteJsonAsync(project, RequirementMapRelativePath, output, cancellationToken);
        return result with { OperationStatus = request.Refresh ? "created_run" : "returned_existing" };
    }

    private GameDesignRequirementMapResult? ReadLatest(ProjectSnapshot project)
    {
        var path = Resolve(project.RepoPath, RequirementMapRelativePath);
        if (!File.Exists(path))
        {
            return null;
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            var root = doc.RootElement;
            var requirements = ReadArray(root, "requirements")
                .Select(ReadRequirement)
                .ToArray();
            var coverage = root.TryGetProperty("coverage_summary", out var coverageElement)
                ? new GameDesignRequirementCoverageSummary(
                    ReadInt(coverageElement, "requirement_count"),
                    ReadInt(coverageElement, "covered_count"),
                    ReadInt(coverageElement, "missing_scene_count"),
                    ReadInt(coverageElement, "missing_module_count"),
                    ReadInt(coverageElement, "explicitly_deferred_count"),
                    ReadInt(coverageElement, "conflict_count"))
                : new GameDesignRequirementCoverageSummary(requirements.Length, requirements.Count(item => item.Status == "mapped"), 0, 0, 0, 0);
            return new GameDesignRequirementMapResult(
                project.ProjectId,
                ReadString(root, "status", "unknown"),
                ReadString(root, "source_gdd_hash"),
                ReadString(root, "source_scene_route_hash"),
                Sha256(NormalizeText(File.ReadAllText(path, Encoding.UTF8))),
                ReadString(root, "source_contract_snapshot_hash"),
                ReadString(root, "godot_ui_contract_version", "unknown"),
                ReadString(root, "source_godot_ui_contract_hash", "unknown"),
                coverage,
                requirements,
                BuildBlockingIssues(requirements),
                [new ProjectRouteStateEvidenceRef("sidecar", RequirementMapRelativePath)],
                ReadString(root, "updated_utc"),
                "returned_existing");
        }
        catch (JsonException)
        {
            return new GameDesignRequirementMapResult(
                project.ProjectId,
                "blocked",
                "",
                "",
                "",
                "",
                "unknown",
                "unknown",
                new GameDesignRequirementCoverageSummary(0, 0, 0, 0, 0, 0),
                [],
                [new ProjectWorkflowBlockingIssue("requirement_map_invalid", "requirement_map_invalid", "P1", "Requirement map JSON is invalid.", [new ProjectRouteStateEvidenceRef("sidecar", RequirementMapRelativePath)])],
                [new ProjectRouteStateEvidenceRef("sidecar", RequirementMapRelativePath)],
                "",
                "rejected");
        }
    }

    private GameDesignRequirementMapResult? ValidateSources(ProjectSnapshot project)
    {
        var gddPath = Resolve(project.RepoPath, GddRelativePath);
        if (!File.Exists(gddPath))
        {
            return Blocked(project.ProjectId, "gdd_not_found", "GDD document is missing.", GddRelativePath);
        }

        var scenePath = Resolve(project.RepoPath, SceneRouteRelativePath);
        if (!File.Exists(scenePath))
        {
            return Blocked(project.ProjectId, "scene_route_missing", "Scene route sidecar is missing.", SceneRouteRelativePath);
        }

        var gddDocumentPath = Resolve(project.RepoPath, GddDocumentRelativePath);
        if (!File.Exists(gddDocumentPath))
        {
            return Blocked(project.ProjectId, "gdd_document_state_missing", "GDD document route state is missing.", GddDocumentRelativePath);
        }

        try
        {
            using var sceneDoc = JsonDocument.Parse(File.ReadAllText(scenePath, Encoding.UTF8));
            using var gddDoc = JsonDocument.Parse(File.ReadAllText(gddDocumentPath, Encoding.UTF8));
            var sceneRoot = sceneDoc.RootElement;
            var gddRoot = gddDoc.RootElement;
            if (ReadString(sceneRoot, "schema_version") != "scene-route.v1")
            {
                return Blocked(project.ProjectId, "scene_route_invalid", "Scene route sidecar schema is invalid.", SceneRouteRelativePath);
            }

            if (ReadString(sceneRoot, "status") != "confirmed")
            {
                var status = ReadString(sceneRoot, "status");
                return Blocked(
                    project.ProjectId,
                    status == "stale" ? "scene_route_stale" : "scene_route_unconfirmed",
                    "Scene route is not confirmed.",
                    SceneRouteRelativePath);
            }

            var sceneHash = ReadString(sceneRoot, "confirmed_scene_route_hash");
            if (string.IsNullOrWhiteSpace(sceneHash))
            {
                return Blocked(project.ProjectId, "scene_route_unconfirmed", "Confirmed scene route hash is missing.", SceneRouteRelativePath);
            }

            var currentStructuredHash = Sha256(NormalizeText(project.GameTypeMatchJson));
            var recordedStructuredHash = ReadString(sceneRoot, "source_game_type_structured_hash");
            if (!string.IsNullOrWhiteSpace(recordedStructuredHash) &&
                !string.Equals(recordedStructuredHash, currentStructuredHash, StringComparison.Ordinal))
            {
                return Blocked(project.ProjectId, "game_type_structured_stale", "Structured game-type metadata changed after scene route confirmation.", SceneRouteRelativePath);
            }

            var generatedHash = Sha256(NormalizeText(File.ReadAllText(gddPath, Encoding.UTF8)));
            if (ReadString(gddRoot, "generated_gdd_hash") != generatedHash ||
                ReadString(sceneRoot, "source_generated_gdd_hash") != generatedHash)
            {
                return Blocked(project.ProjectId, "generated_gdd_hash_mismatch", "Generated GDD hash does not match scene route and document state.", GddDocumentRelativePath);
            }
        }
        catch (JsonException)
        {
            return Blocked(project.ProjectId, "route_state_invalid", "Scene route or GDD document state JSON is invalid.", SceneRouteRelativePath);
        }

        return null;
    }

    private async Task<ProjectSnapshot?> GetProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        return project is not null && string.Equals(project.AccountId, accountId, StringComparison.Ordinal)
            ? project
            : null;
    }

    private static List<GameDesignRequirementRow> BuildDeterministicRequirements(string gddText, JsonElement sceneRoot)
    {
        var scenes = ReadArray(sceneRoot, "scenes")
            .Select(scene => ReadString(scene, "scene_id"))
            .Where(id => !string.IsNullOrWhiteSpace(id))
            .ToArray();
        var rows = new List<GameDesignRequirementRow>();
        foreach (var rawLine in gddText.Replace("\r\n", "\n").Split('\n'))
        {
            var line = rawLine.Trim();
            if (line.Length < 12)
            {
                continue;
            }

            var match = RequirementLineRegex.Match(line);
            if (!match.Success && !ContainsRequirementKeyword(line))
            {
                continue;
            }

            var text = match.Success ? match.Groups["text"].Value.Trim() : line;
            var id = $"REQ-{rows.Count + 1:000}";
            var kind = InferKind(text);
            var mappedScenes = scenes.Length == 0 ? Array.Empty<string>() : new[] { scenes[0] };
            rows.Add(new GameDesignRequirementRow(
                id,
                "GDD",
                NormalizeSummary(text),
                "en",
                "normalized_english_summary",
                NormalizeSummary(text),
                rows.Count == 0 ? "P0" : "P1",
                kind,
                mappedScenes,
                mappedScenes.Length == 0 ? [] : [$"{kind}_{rows.Count + 1:000}"],
                [],
                mappedScenes.Length == 0 ? "missing_scene" : "mapped",
                "",
                "",
                "",
                "",
                "",
                "",
                [],
                [NormalizeSummary(text)]));
        }

        return rows;
    }

    private static string InferKind(string text)
    {
        var lower = text.ToLowerInvariant();
        if (lower.Contains("ui") || lower.Contains("hud") || lower.Contains("menu") || lower.Contains("button") || lower.Contains("feedback") || lower.Contains("camera"))
        {
            return "ui";
        }

        if (lower.Contains("scene") || lower.Contains("map") || lower.Contains("level"))
        {
            return "scene";
        }

        return "mechanic";
    }

    private static bool ContainsRequirementKeyword(string line)
    {
        var lower = line.ToLowerInvariant();
        return lower.Contains("must") ||
               lower.Contains("should") ||
               lower.Contains("require") ||
               lower.Contains("player") ||
               lower.Contains("scene") ||
               lower.Contains("ui") ||
               lower.Contains("feedback");
    }

    private static string NormalizeSummary(string text)
    {
        text = Regex.Replace(text, @"\s+", " ").Trim();
        return text.Length <= 240 ? text : text[..240];
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> BuildBlockingIssues(IReadOnlyList<GameDesignRequirementRow> requirements)
    {
        return requirements
            .Where(item => item.Priority is "P0" or "P1" && item.Status is "missing_scene" or "missing_module" or "needs_review" or "conflict")
            .Select(item => new ProjectWorkflowBlockingIssue(
                $"gdd-requirements:{item.RequirementId}:requirement_gap",
                "requirement_map_invalid",
                item.Priority,
                $"Requirement {item.RequirementId} is {item.Status}.",
                [new ProjectRouteStateEvidenceRef("sidecar", RequirementMapRelativePath)]))
            .ToArray();
    }

    private static object ToSidecarRequirement(GameDesignRequirementRow item)
    {
        return new
        {
            requirement_id = item.RequirementId,
            source_section = item.SourceSection,
            normalized_source_summary = item.NormalizedSourceSummary,
            source_language = item.SourceLanguage,
            source_excerpt_policy = item.SourceExcerptPolicy,
            normalized_requirement = item.NormalizedRequirement,
            priority = item.Priority,
            kind = item.Kind,
            mapped_scene_ids = item.MappedSceneIds,
            mapped_required_module_ids = item.MappedRequiredModuleIds,
            mapped_iteration_goal_ids = item.MappedIterationGoalIds,
            status = item.Status,
            defer_reason = item.DeferReason,
            conflict_reason = item.ConflictReason,
            decision_by = item.DecisionBy,
            decision_role = item.DecisionRole,
            decision_utc = item.DecisionUtc,
            decision_reason = item.DecisionReason,
            affected_requirement_ids = item.AffectedRequirementIds,
            acceptance_markers = item.AcceptanceMarkers
        };
    }

    private static GameDesignRequirementRow ReadRequirement(JsonElement root)
    {
        return new GameDesignRequirementRow(
            ReadString(root, "requirement_id"),
            ReadString(root, "source_section"),
            ReadString(root, "normalized_source_summary"),
            ReadString(root, "source_language"),
            ReadString(root, "source_excerpt_policy"),
            ReadString(root, "normalized_requirement"),
            ReadString(root, "priority"),
            ReadString(root, "kind"),
            ReadStringArray(root, "mapped_scene_ids"),
            ReadStringArray(root, "mapped_required_module_ids"),
            ReadStringArray(root, "mapped_iteration_goal_ids"),
            ReadString(root, "status"),
            ReadString(root, "defer_reason"),
            ReadString(root, "conflict_reason"),
            ReadString(root, "decision_by"),
            ReadString(root, "decision_role"),
            ReadString(root, "decision_utc"),
            ReadString(root, "decision_reason"),
            ReadStringArray(root, "affected_requirement_ids"),
            ReadStringArray(root, "acceptance_markers"));
    }

    private static GameDesignRequirementMapResult Blocked(string projectId, string domainCode, string summary, string path)
    {
        return new GameDesignRequirementMapResult(
            projectId,
            "blocked",
            "",
            "",
            "",
            "",
            "unknown",
            "unknown",
            new GameDesignRequirementCoverageSummary(0, 0, 0, 0, 0, 0),
            [],
            [new ProjectWorkflowBlockingIssue(domainCode, domainCode, "P1", summary, [new ProjectRouteStateEvidenceRef("sidecar", path)])],
            [new ProjectRouteStateEvidenceRef("sidecar", path)],
            DateTimeOffset.UtcNow.ToString("O"),
            "rejected");
    }

    private static async Task WriteJsonAsync(ProjectSnapshot project, string relativePath, object payload, CancellationToken cancellationToken)
    {
        var path = Resolve(project.RepoPath, relativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        await File.WriteAllTextAsync(path, JsonSerializer.Serialize(payload, JsonOptions()), Encoding.UTF8, cancellationToken);
    }

    private static string Resolve(string root, string relativePath)
    {
        var rootFullPath = Path.GetFullPath(root);
        var path = Path.GetFullPath(Path.Combine(rootFullPath, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (!path.StartsWith(rootFullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar, comparison))
        {
            throw new InvalidOperationException("Project route-state path escaped the project root.");
        }

        return path;
    }

    private static IEnumerable<JsonElement> ReadArray(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Array
            ? value.EnumerateArray()
            : [];
    }

    private static IReadOnlyList<string> ReadStringArray(JsonElement root, string propertyName)
    {
        return ReadArray(root, propertyName)
            .Where(item => item.ValueKind == JsonValueKind.String)
            .Select(item => item.GetString() ?? "")
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToArray();
    }

    private static int ReadInt(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.TryGetInt32(out var number) ? number : 0;
    }

    private static string ReadString(JsonElement root, string propertyName, string fallback = "")
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? fallback
            : fallback;
    }

    private static string Sha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    }

    private static string NormalizeText(string text)
    {
        return text.Replace("\r\n", "\n").Trim();
    }

    private static JsonSerializerOptions JsonOptions()
    {
        return new JsonSerializerOptions(JsonSerializerDefaults.Web)
        {
            WriteIndented = true
        };
    }
}

public sealed record GameDesignRequirementMapRequest(bool Refresh = false, string? Model = null);

public sealed record GameDesignRequirementMapResult(
    string ProjectId,
    string Status,
    string SourceGddHash,
    string SourceSceneRouteHash,
    string SourceRequirementMapHash,
    string SourceContractSnapshotHash,
    string GodotUiContractVersion,
    string SourceGodotUiContractHash,
    GameDesignRequirementCoverageSummary CoverageSummary,
    IReadOnlyList<GameDesignRequirementRow> Requirements,
    IReadOnlyList<ProjectWorkflowBlockingIssue> BlockingIssues,
    IReadOnlyList<ProjectRouteStateEvidenceRef> EvidenceRefs,
    string UpdatedUtc,
    string OperationStatus)
{
    public static GameDesignRequirementMapResult NotFound(string projectId) =>
        new(projectId, "project_not_found", "", "", "", "", "unknown", "unknown", new GameDesignRequirementCoverageSummary(0, 0, 0, 0, 0, 0), [], [], [], "", "rejected");
}

public sealed record GameDesignRequirementCoverageSummary(
    int RequirementCount,
    int CoveredCount,
    int MissingSceneCount,
    int MissingModuleCount,
    int ExplicitlyDeferredCount,
    int ConflictCount);

public sealed record GameDesignRequirementRow(
    string RequirementId,
    string SourceSection,
    string NormalizedSourceSummary,
    string SourceLanguage,
    string SourceExcerptPolicy,
    string NormalizedRequirement,
    string Priority,
    string Kind,
    IReadOnlyList<string> MappedSceneIds,
    IReadOnlyList<string> MappedRequiredModuleIds,
    IReadOnlyList<string> MappedIterationGoalIds,
    string Status,
    string DeferReason,
    string ConflictReason,
    string DecisionBy,
    string DecisionRole,
    string DecisionUtc,
    string DecisionReason,
    IReadOnlyList<string> AffectedRequirementIds,
    IReadOnlyList<string> AcceptanceMarkers);
