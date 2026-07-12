using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

public sealed class GameDesignRequirementMapService
{
    private static readonly Encoding Utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
    private const string GddRelativePath = "docs/gdd/GDD.md";
    private const string SceneRouteRelativePath = "meta/routes/scene-route/latest.json";
    private const string GddDocumentRelativePath = "meta/routes/gdd-document/latest.json";
    private const string RequirementMapRelativePath = "meta/routes/gdd-requirements/latest.json";
    private const string RequirementPromptEvidenceRelativePath = "meta/routes/gdd-requirements/prompt-evidence.json";
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
        await using var lease = await ProjectMutationLockRegistry.Shared.AcquireAsync(accountId, projectId, cancellationToken);
        return await CreateCoreAsync(accountId, projectId, request, cancellationToken);
    }

    private async Task<GameDesignRequirementMapResult> CreateCoreAsync(
        string accountId,
        string projectId,
        GameDesignRequirementMapRequest request,
        CancellationToken cancellationToken)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return GameDesignRequirementMapResult.NotFound(projectId);
        }

        var validation = ValidateSources(project);
        if (validation is not null)
        {
            await RecordDiagnosticsAsync(project, validation.BlockingIssues, cancellationToken);
            return validation;
        }

        var existing = ReadLatest(project);
        if (!request.Refresh && existing is not null && IsCurrent(project, existing))
        {
            return existing with { OperationStatus = "returned_existing" };
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
        var deterministicRequirements = BuildDeterministicRequirements(gddText, sceneDoc.RootElement);
        var generation = await BuildRequirementsAsync(
            project,
            request,
            gddText,
            sceneDoc.RootElement,
            deterministicRequirements,
            cancellationToken);
        var requirements = generation.Requirements;
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
        var status = requirements.Any(item => item.Priority is "P0" or "P1" && item.Status is "missing_scene" or "missing_module" or "needs_review" or "conflict" or "explicitly_deferred")
            ? "needs_review"
            : "ready";
        var now = DateTimeOffset.UtcNow.ToString("O");
        var sourceHashes = new Dictionary<string, string>
        {
            [GddRelativePath] = sourceGddHash,
            [SceneRouteRelativePath] = sceneHash,
            ["project-contract-snapshot"] = contractSnapshotHash
        };
        await WriteJsonAsync(project, RequirementPromptEvidenceRelativePath, new
        {
            schema_version = "gdd-requirements-prompt-evidence.v1",
            route = "gdd-requirements",
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            source_hashes = sourceHashes,
            prompt_purpose = "gdd-requirement-map",
            prompt_transport = "shared-llm-route-engine",
            raw_prompt_persisted = false,
            checked_utc = now
        }, cancellationToken);
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
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "docs/gdd/GDD.md", "confirmed scene route", "project contract snapshot" },
                source_hashes = sourceHashes,
                forbidden_source_patterns = new[] { "docs/game-type-guides/** raw excerpts" },
                prompt_evidence_refs = new[] { RequirementPromptEvidenceRelativePath },
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
        var persistedHash = Sha256(NormalizeText(File.ReadAllText(Resolve(project.RepoPath, RequirementMapRelativePath), Encoding.UTF8)));
        await RecordAdminReviewQueueAsync(
            project,
            requirements,
            persistedHash,
            result.SourceGddHash,
            result.SourceSceneRouteHash,
            result.SourceContractSnapshotHash,
            result.SourceGodotUiContractHash,
            cancellationToken);
        await RecordDiagnosticsAsync(project, result.BlockingIssues, cancellationToken);
        return result with
        {
            SourceRequirementMapHash = persistedHash,
            OperationStatus = "created_run"
        };
    }

    private static bool IsCurrent(ProjectSnapshot project, GameDesignRequirementMapResult existing)
    {
        var gddPath = Resolve(project.RepoPath, GddRelativePath);
        var scenePath = Resolve(project.RepoPath, SceneRouteRelativePath);
        if (!File.Exists(gddPath) || !File.Exists(scenePath))
        {
            return false;
        }

        try
        {
            using var scene = JsonDocument.Parse(File.ReadAllText(scenePath, Encoding.UTF8));
            return string.Equals(existing.SourceGddHash, Sha256(NormalizeText(File.ReadAllText(gddPath, Encoding.UTF8))), StringComparison.Ordinal) &&
                   string.Equals(existing.SourceSceneRouteHash, ReadString(scene.RootElement, "confirmed_scene_route_hash"), StringComparison.Ordinal) &&
                   existing.Status is "ready" or "needs_review";
        }
        catch (JsonException)
        {
            return false;
        }
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

    private async Task RecordDiagnosticsAsync(
        ProjectSnapshot project,
        IReadOnlyList<ProjectWorkflowBlockingIssue> issues,
        CancellationToken cancellationToken)
    {
        foreach (var issue in issues.Where(item => item.Severity is "P0" or "P1" or "P2"))
        {
            var existing = await _metadataStore.ListProjectDiagnosticSpoolForAdminAsync(
                new ProjectDiagnosticSpoolQuery(
                    "unresolved",
                    project.AccountId,
                    project.ProjectId,
                    "gdd-requirements",
                    issue.DomainCode,
                    issue.Severity,
                    1),
                cancellationToken);
            if (existing.Count > 0)
            {
                continue;
            }

            var evidenceJson = JsonSerializer.Serialize(issue.EvidenceRefs, JsonOptions());
            await _metadataStore.RecordProjectDiagnosticSpoolEntryAsync(
                new ProjectDiagnosticSpoolCommand(
                    project.AccountId,
                    project.ProjectId,
                    "gdd-requirements",
                    issue.DomainCode,
                    issue.Severity,
                    issue.Summary,
                    evidenceJson,
                    issue.EvidenceRefs.FirstOrDefault()?.Path ?? RequirementMapRelativePath,
                    ProjectNameSnapshot: project.Name,
                    SourceRefsJson: evidenceJson,
                    RetentionClass: "unresolved_blocker",
                    RemediationHintId: issue.DomainCode),
                cancellationToken);
        }
    }

    private async Task RecordAdminReviewQueueAsync(
        ProjectSnapshot project,
        IReadOnlyList<GameDesignRequirementRow> requirements,
        string sourceRequirementMapHash,
        string sourceGddHash,
        string sourceSceneRouteHash,
        string sourceContractSnapshotHash,
        string sourceGodotUiContractHash,
        CancellationToken cancellationToken)
    {
        var activeRequirements = requirements.Where(item =>
                item.Priority is "P0" or "P1" &&
                item.Status is "conflict" or "explicitly_deferred")
            .ToArray();
        foreach (var requirement in activeRequirements)
        {
            var evidenceJson = JsonSerializer.Serialize(
                new[]
                {
                    new
                    {
                        kind = "sidecar",
                        path = RequirementMapRelativePath,
                        source_requirement_map_hash = sourceRequirementMapHash,
                        source_gdd_hash = sourceGddHash,
                        source_scene_route_hash = sourceSceneRouteHash,
                        source_contract_snapshot_hash = sourceContractSnapshotHash,
                        source_godot_ui_contract_hash = sourceGodotUiContractHash
                    }
                },
                JsonOptions());
            await _metadataStore.UpsertProjectAdminReviewQueueEntryAsync(
                new ProjectAdminReviewQueueCommand(
                    project.AccountId,
                    project.ProjectId,
                    "gdd-requirements",
                    requirement.RequirementId,
                    requirement.Priority,
                    $"Requirement {requirement.RequirementId} requires review for status {requirement.Status}.",
                    RequirementMapRelativePath,
                    evidenceJson),
                cancellationToken);
        }

        var reconciliationEvidence = JsonSerializer.Serialize(
            new[]
            {
                new
                {
                    kind = "sidecar",
                    path = RequirementMapRelativePath,
                    source_requirement_map_hash = sourceRequirementMapHash,
                    source_gdd_hash = sourceGddHash,
                    source_scene_route_hash = sourceSceneRouteHash,
                    source_contract_snapshot_hash = sourceContractSnapshotHash,
                    source_godot_ui_contract_hash = sourceGodotUiContractHash,
                    summary = "Current requirement map no longer contains the prior blocker."
                }
            },
            JsonOptions());
        await _metadataStore.ReconcileProjectAdminReviewQueueAsync(
            project.AccountId,
            project.ProjectId,
            "gdd-requirements",
            activeRequirements.Select(requirement => requirement.RequirementId).ToHashSet(StringComparer.Ordinal),
            RequirementMapRelativePath,
            reconciliationEvidence,
            cancellationToken);
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

    private async Task<RequirementGenerationResult> BuildRequirementsAsync(
        ProjectSnapshot project,
        GameDesignRequirementMapRequest request,
        string gddText,
        JsonElement sceneRoot,
        IReadOnlyList<GameDesignRequirementRow> deterministicRequirements,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return FallbackRequirements(deterministicRequirements, "llm_unavailable", []);
        }

        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                project.RepoPath,
                "gdd-requirement-map",
                PrototypeModelPolicy.Normalize(request.Model),
                BuildStructuredRequirementPrompt(gddText, sceneRoot, deterministicRequirements),
                new CodexChatClientOptions(ReasoningEffort: "low"),
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        var promptEvidence = new object[] { new { kind = "log", path = "logs/phase-a-chat/", purpose = "gdd-requirement-map" } };
        if (!completion.Succeeded || string.IsNullOrWhiteSpace(completion.JsonObjectText))
        {
            return FallbackRequirements(deterministicRequirements, completion.FailureCode ?? "llm_failed", promptEvidence);
        }

        try
        {
            using var document = JsonDocument.Parse(completion.JsonObjectText);
            if (!document.RootElement.TryGetProperty("requirements", out var requirementsElement) ||
                requirementsElement.ValueKind != JsonValueKind.Array)
            {
                return FallbackRequirements(deterministicRequirements, "llm_requirements_missing", promptEvidence);
            }

            var requirementElements = requirementsElement.EnumerateArray().ToArray();
            var declaredIds = requirementElements
                .Where(item => item.ValueKind == JsonValueKind.Object)
                .Select(item => ReadString(item, "requirement_id"))
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .ToArray();
            if (declaredIds.Distinct(StringComparer.Ordinal).Count() != declaredIds.Length)
            {
                return FallbackRequirements(deterministicRequirements, "duplicate_requirement_id", promptEvidence);
            }

            var parsed = requirementElements.Select(ReadStructuredRequirement).ToArray();
            if (parsed.Any(item => item is null || !IsStructuredRequirementSemanticallyComplete(item)))
            {
                return FallbackRequirements(deterministicRequirements, "llm_requirement_invalid", promptEvidence);
            }

            var rows = parsed.Select(item => item!).ToArray();
            var requiredFloorIds = deterministicRequirements
                .Where(item => item.Priority is "P0" or "P1")
                .Select(item => item.RequirementId)
                .ToHashSet(StringComparer.Ordinal);
            var returnedIds = rows.Select(item => item.RequirementId).ToHashSet(StringComparer.Ordinal);
            if (rows.Length < deterministicRequirements.Count || !requiredFloorIds.IsSubsetOf(returnedIds))
            {
                return FallbackRequirements(deterministicRequirements, "llm_requirement_coverage_incomplete", promptEvidence);
            }

            var floorById = deterministicRequirements.ToDictionary(item => item.RequirementId, StringComparer.Ordinal);
            var mergedRows = rows.Select(item => floorById.TryGetValue(item.RequirementId, out var floor)
                ? item with
                {
                    SourceSection = floor.SourceSection,
                    NormalizedSourceSummary = floor.NormalizedSourceSummary,
                    SourceLanguage = floor.SourceLanguage,
                    SourceExcerptPolicy = floor.SourceExcerptPolicy,
                    NormalizedRequirement = floor.NormalizedRequirement,
                    Priority = floor.Priority,
                    AcceptanceMarkers = floor.AcceptanceMarkers.Concat(item.AcceptanceMarkers).Distinct(StringComparer.Ordinal).ToArray()
                }
                : item).ToList();
            return new RequirementGenerationResult(mergedRows, promptEvidence);
        }
        catch (JsonException)
        {
            return FallbackRequirements(deterministicRequirements, "llm_json_parse_failed", promptEvidence);
        }
    }

    private static string BuildStructuredRequirementPrompt(
        string gddText,
        JsonElement sceneRoot,
        IReadOnlyList<GameDesignRequirementRow> deterministicRequirements)
    {
        var floorRows = deterministicRequirements.Select(item => new
        {
            item.RequirementId,
            item.NormalizedRequirement,
            item.Priority,
            item.Kind,
            item.MappedSceneIds,
            item.MappedRequiredModuleIds
        });
        return $$"""
        Produce one JSON object for the Phase A GDD requirement map.
        Use only the frozen GDD text, confirmed scene-route JSON, and deterministic floor rows below.
        Do not use mutable game-type guide excerpts or invent runtime technology.

        GDD:
        {{gddText}}

        Confirmed scene route:
        {{sceneRoot.GetRawText()}}

        Deterministic floor rows:
        {{JsonSerializer.Serialize(floorRows, JsonOptions())}}

        Return:
        {
          "requirements": [
            {
              "requirement_id": "REQ-001",
              "normalized_requirement": "English requirement",
              "priority": "P0|P1|P2",
              "kind": "mechanic|scene|ui|input|camera|animation|rendering|procedural|geometry|typed_state",
              "mapped_scene_ids": ["scene_id"],
              "mapped_required_module_ids": ["module_id"],
              "status": "mapped|missing_scene|missing_module|needs_review|conflict|explicitly_deferred",
              "capability_domain_ids": ["stable_capability_id"],
              "godot_ui_update_ownership": {
                "construction_owner": "owner",
                 "update_mode": "signal_driven|polling|immutable",
                 "state_owner": "owner",
                 "cleanup_policy": "policy",
                 "signal_ownership": "signal owner",
                 "stable_item_identity": "identity"
              },
              "godot_third_person_camera_profile": {
                "rig_ref": "repo-owned rig/profile",
                "target_owner": "owner",
                 "input_owner": "owner",
                 "collision_owner": "owner",
                 "validation_method": "method",
                 "yaw_pitch_ownership": "repo-owned rig/profile",
                 "camera_relative_movement_boundary": "movement owner",
                 "camera_state_validation": "validation reference"
              },
              "acceptance_markers": ["observable acceptance"]
            }
          ]
        }
        Keep every deterministic P0/P1 floor row. Preserve its requirement_id, normalized_requirement, and priority; enrich only mapping and capability evidence. Requirement IDs must be unique and stable.
        """;
    }

    private static GameDesignRequirementRow? ReadStructuredRequirement(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        var id = ReadString(root, "requirement_id");
        var requirement = ReadString(root, "normalized_requirement");
        var priority = ReadString(root, "priority");
        var kind = ReadString(root, "kind");
        var status = ReadString(root, "status");
        if (!Regex.IsMatch(id, "^REQ-[0-9]{3}$", RegexOptions.CultureInvariant) ||
            string.IsNullOrWhiteSpace(requirement) ||
            priority is not ("P0" or "P1" or "P2") ||
            kind is not ("mechanic" or "scene" or "ui" or "input" or "camera" or "animation" or "rendering" or "procedural" or "geometry" or "typed_state") ||
            status is not ("mapped" or "missing_scene" or "missing_module" or "needs_review" or "conflict" or "explicitly_deferred"))
        {
            return null;
        }

        var ownership = root.TryGetProperty("godot_ui_update_ownership", out var ownershipElement) && ownershipElement.ValueKind == JsonValueKind.Object
            ? new GodotUiUpdateOwnership(
                ReadString(ownershipElement, "construction_owner"),
                ReadString(ownershipElement, "update_mode"),
                ReadString(ownershipElement, "state_owner"),
                ReadString(ownershipElement, "cleanup_policy"),
                ReadString(ownershipElement, "stable_item_identity"),
                ReadString(ownershipElement, "signal_ownership"))
            : null;
        var camera = root.TryGetProperty("godot_third_person_camera_profile", out var cameraElement) && cameraElement.ValueKind == JsonValueKind.Object
            ? new GodotThirdPersonCameraProfile(
                ReadString(cameraElement, "rig_ref"),
                ReadString(cameraElement, "target_owner"),
                ReadString(cameraElement, "input_owner"),
                ReadString(cameraElement, "collision_owner"),
                ReadString(cameraElement, "validation_method"),
                ReadString(cameraElement, "yaw_pitch_ownership"),
                ReadString(cameraElement, "camera_relative_movement_boundary"),
                ReadString(cameraElement, "camera_state_validation"))
            : null;
        return new GameDesignRequirementRow(
            id,
            "GDD",
            requirement,
            "en",
            "normalized_english_summary",
            requirement,
            priority,
            kind,
            ReadStringArray(root, "mapped_scene_ids"),
            ReadStringArray(root, "mapped_required_module_ids"),
            [],
            status,
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            ReadStringArray(root, "acceptance_markers"),
            ReadStringArray(root, "capability_domain_ids"),
            ownership,
            camera);
    }

    private static bool IsStructuredRequirementSemanticallyComplete(GameDesignRequirementRow? item)
    {
        if (item is null)
        {
            return false;
        }

        if (item.CapabilityDomainIds.Any(id =>
                !GodotUiCapabilityContract.IsKnownCapabilityDomain(id) &&
                !GodotUiStyleCatalog.Capabilities.Any(capability => string.Equals(capability.CapabilityId, id, StringComparison.Ordinal))))
        {
            return false;
        }

        if (item.Kind == "ui" && item.CapabilityDomainIds.Count == 0)
        {
            return false;
        }

        if (item.GodotUiUpdateOwnership is not null && item.GodotUiUpdateOwnership is not
            {
                ConstructionOwner.Length: > 0,
                UpdateMode.Length: > 0,
                StateOwner.Length: > 0,
                CleanupPolicy.Length: > 0,
                StableItemIdentity.Length: > 0,
                SignalOwnership.Length: > 0
            })
        {
            return false;
        }

        var thirdPerson = item.NormalizedRequirement.Contains("third-person", StringComparison.OrdinalIgnoreCase) ||
                          item.NormalizedRequirement.Contains("third person", StringComparison.OrdinalIgnoreCase);
        return !thirdPerson || item.GodotThirdPersonCameraProfile is
        {
            RigRef.Length: > 0,
            TargetOwner.Length: > 0,
            InputOwner.Length: > 0,
            CollisionOwner.Length: > 0,
            ValidationMethod.Length: > 0,
            YawPitchOwnership.Length: > 0,
            CameraRelativeMovementBoundary.Length: > 0,
            CameraStateValidation.Length: > 0
        };
    }

    private static RequirementGenerationResult FallbackRequirements(
        IReadOnlyList<GameDesignRequirementRow> deterministicRequirements,
        string reason,
        IReadOnlyList<object> promptEvidenceRefs)
    {
        var marker = $"structured_llm_fallback:{reason}";
        var rows = deterministicRequirements.Select(item => item with
        {
            Status = item.Priority is "P0" or "P1" ? "needs_review" : item.Status,
            AcceptanceMarkers = item.AcceptanceMarkers.Concat([marker]).Distinct(StringComparer.Ordinal).ToArray()
        }).ToList();
        return new RequirementGenerationResult(rows, promptEvidenceRefs);
    }

    private static string InferKind(string text)
    {
        var lower = text.ToLowerInvariant();
        if (ContainsAsciiToken(lower, "ui") || lower.Contains("hud") || lower.Contains("menu") || lower.Contains("button") || lower.Contains("feedback") || lower.Contains("camera"))
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
               ContainsAsciiToken(lower, "ui") ||
               lower.Contains("feedback");
    }

    private static bool ContainsAsciiToken(string text, string token)
    {
        return Regex.IsMatch(text, $@"(?<![a-z0-9]){Regex.Escape(token)}(?![a-z0-9])", RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);
    }

    private static string NormalizeSummary(string text)
    {
        text = Regex.Replace(text, @"\s+", " ").Trim();
        return text.Length <= 240 ? text : text[..240];
    }

    private static IReadOnlyList<ProjectWorkflowBlockingIssue> BuildBlockingIssues(IReadOnlyList<GameDesignRequirementRow> requirements)
    {
        return requirements
            .Where(item => item.Priority is "P0" or "P1" && item.Status is "missing_scene" or "missing_module" or "needs_review" or "conflict" or "explicitly_deferred")
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
            acceptance_markers = item.AcceptanceMarkers,
            capability_domain_ids = item.CapabilityDomainIds,
            godot_ui_update_ownership = item.GodotUiUpdateOwnership is null ? null : new
            {
                construction_owner = item.GodotUiUpdateOwnership.ConstructionOwner,
                update_mode = item.GodotUiUpdateOwnership.UpdateMode,
                state_owner = item.GodotUiUpdateOwnership.StateOwner,
                cleanup_policy = item.GodotUiUpdateOwnership.CleanupPolicy,
                signal_ownership = item.GodotUiUpdateOwnership.SignalOwnership,
                stable_item_identity = item.GodotUiUpdateOwnership.StableItemIdentity
            },
            godot_third_person_camera_profile = item.GodotThirdPersonCameraProfile is null ? null : new
            {
                rig_ref = item.GodotThirdPersonCameraProfile.RigRef,
                target_owner = item.GodotThirdPersonCameraProfile.TargetOwner,
                input_owner = item.GodotThirdPersonCameraProfile.InputOwner,
                collision_owner = item.GodotThirdPersonCameraProfile.CollisionOwner,
                validation_method = item.GodotThirdPersonCameraProfile.ValidationMethod,
                yaw_pitch_ownership = item.GodotThirdPersonCameraProfile.YawPitchOwnership,
                camera_relative_movement_boundary = item.GodotThirdPersonCameraProfile.CameraRelativeMovementBoundary,
                camera_state_validation = item.GodotThirdPersonCameraProfile.CameraStateValidation
            }
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
            ReadStringArray(root, "acceptance_markers"),
            ReadStringArray(root, "capability_domain_ids"),
            ReadGodotUiUpdateOwnership(root),
            ReadGodotThirdPersonCameraProfile(root));
    }

    private static GodotUiUpdateOwnership? ReadGodotUiUpdateOwnership(JsonElement root)
    {
        return root.TryGetProperty("godot_ui_update_ownership", out var value) && value.ValueKind == JsonValueKind.Object
            ? new GodotUiUpdateOwnership(
                ReadString(value, "construction_owner"),
                ReadString(value, "update_mode"),
                ReadString(value, "state_owner"),
                ReadString(value, "cleanup_policy"),
                ReadString(value, "stable_item_identity"),
                ReadString(value, "signal_ownership"))
            : null;
    }

    private static GodotThirdPersonCameraProfile? ReadGodotThirdPersonCameraProfile(JsonElement root)
    {
        return root.TryGetProperty("godot_third_person_camera_profile", out var value) && value.ValueKind == JsonValueKind.Object
            ? new GodotThirdPersonCameraProfile(
                ReadString(value, "rig_ref"),
                ReadString(value, "target_owner"),
                ReadString(value, "input_owner"),
                ReadString(value, "collision_owner"),
                ReadString(value, "validation_method"),
                ReadString(value, "yaw_pitch_ownership"),
                ReadString(value, "camera_relative_movement_boundary"),
                ReadString(value, "camera_state_validation"))
            : null;
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
        await File.WriteAllTextAsync(path, JsonSerializer.Serialize(payload, JsonOptions()), Utf8NoBom, cancellationToken);
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
    IReadOnlyList<string> AcceptanceMarkers,
    IReadOnlyList<string>? CapabilityDomainIds = null,
    GodotUiUpdateOwnership? GodotUiUpdateOwnership = null,
    GodotThirdPersonCameraProfile? GodotThirdPersonCameraProfile = null)
{
    public IReadOnlyList<string> CapabilityDomainIds { get; init; } = CapabilityDomainIds ?? [];
}

public sealed record GodotUiUpdateOwnership(
    string ConstructionOwner,
    string UpdateMode,
    string StateOwner,
    string CleanupPolicy,
    string StableItemIdentity,
    string SignalOwnership = "");

public sealed record GodotThirdPersonCameraProfile(
    string RigRef,
    string TargetOwner,
    string InputOwner,
    string CollisionOwner,
    string ValidationMethod,
    string YawPitchOwnership = "",
    string CameraRelativeMovementBoundary = "",
    string CameraStateValidation = "");

internal sealed record RequirementGenerationResult(
    List<GameDesignRequirementRow> Requirements,
    IReadOnlyList<object> PromptEvidenceRefs);
