using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using PhaseA.Platform.Data;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

public sealed class GddToModulePhase1StateService
{
    private static readonly string[] ForbiddenSourcePatterns =
    [
        "docs/game-type-guides/** raw excerpts",
        "unapproved raw game-type guide excerpt before contract freeze"
    ];
    private const string SceneRouteRelativePath = "meta/routes/scene-route/latest.json";
    private const string GddDocumentRelativePath = "meta/routes/gdd-document/latest.json";
    private const string GddDocumentPromptEvidenceRelativePath = "meta/routes/gdd-document/prompt-evidence.json";
    private const string GddRelativePath = "docs/gdd/GDD.md";
    private const string GddFormRelativePath = "meta/routes/gdd-question-form/latest.json";
    private readonly PhaseAMetadataStore _metadataStore;

    public GddToModulePhase1StateService(PhaseAMetadataStore metadataStore)
    {
        _metadataStore = metadataStore;
    }

    public async Task<SceneRouteStateResult?> ConfirmSceneRouteAsync(
        string accountId,
        string projectId,
        GameDesignSceneRouteDocument? sceneRoute,
        CancellationToken cancellationToken = default)
    {
        await using var lease = await ProjectMutationLockRegistry.Shared.AcquireAsync(accountId, projectId, cancellationToken);
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var normalized = GameDesignSceneRouteService.NormalizeSubmittedSceneRoute(sceneRoute);
        if (normalized is null)
        {
            return SceneRouteStateResult.Blocked(projectId, "scene_route_invalid", "Submitted scene route is invalid.");
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        var sceneRows = normalized.Scenes.Select(scene => new
        {
            scene_id = scene.Id,
            scene_name = scene.Name,
            role = scene.Role,
            m1_required = scene.M1Required,
            player_goal = scene.PlayerGoal
        }).ToArray();
        var transitionRows = normalized.Transitions.Select(transition => new
        {
            from = transition.From,
            to = transition.To,
            trigger = transition.Trigger,
            returns_to = transition.ReturnsTo,
            state_carried = transition.StateCarried
        }).ToArray();
        var hashPayload = new
        {
            scene_count_intent = normalized.SceneCountIntent,
            entry_scene = normalized.EntryScene,
            scenes = sceneRows,
            transitions = transitionRows,
            single_scene_confirmation = new
            {
                allowed = normalized.SingleSceneConfirmation.Allowed,
                reason = normalized.SingleSceneConfirmation.Reason
            },
            notes = normalized.Notes
        };
        var sceneHash = Sha256(JsonSerializer.Serialize(hashPayload, JsonOptions()));
        var structuredHash = GddToModuleAuthorityHashes.ComputeStructuredGameTypeHash(project.GameTypeMatchJson);
        var contractSnapshotHash = GddToModuleAuthorityHashes.ComputeContractSnapshotHash(project.GameTypeMatchJson);
        var gddFormHash = ReadOptionalFileHash(project, GddFormRelativePath);
        var existing = ReadSceneRoute(project);
        if (existing is not null &&
            existing.Status == "confirmed" &&
            string.Equals(existing.ConfirmedSceneRouteHash, sceneHash, StringComparison.Ordinal) &&
            string.Equals(existing.SourceGameTypeStructuredHash, structuredHash, StringComparison.Ordinal) &&
            string.Equals(existing.SourceContractSnapshotHash, contractSnapshotHash, StringComparison.Ordinal))
        {
            return existing with { OperationStatus = "returned_existing" };
        }

        var payload = new
        {
            schema_version = "scene-route.v1",
            route = "scene-route-confirmation",
            project_id = project.ProjectId,
            status_dimension = "scene_route_confirmation",
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.SceneRouteConfirmation),
            status = "confirmed",
            operation_status = "created_run",
            confirmed_utc = now,
            source_game_type_structured_hash = structuredHash,
            source_gdd_form_hash = gddFormHash,
            source_generated_gdd_hash = "",
            source_contract_snapshot_hash = contractSnapshotHash,
            confirmed_scene_route_hash = sceneHash,
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[] { "structured-game-type-metadata", GddFormRelativePath, "project-contract-snapshot" },
                source_hashes = new Dictionary<string, string>
                {
                    ["structured-game-type-metadata"] = structuredHash,
                    [GddFormRelativePath] = gddFormHash,
                    ["project-contract-snapshot"] = contractSnapshotHash
                },
                forbidden_source_patterns = ForbiddenSourcePatterns,
                prompt_evidence_refs = Array.Empty<object>(),
                checked_utc = now
            },
            evidence_refs = new[] { new { kind = "sidecar", path = SceneRouteRelativePath } },
            scene_count_intent = normalized.SceneCountIntent,
            entry_scene = normalized.EntryScene,
            scenes = sceneRows,
            transitions = transitionRows,
            single_scene_confirmation = new
            {
                allowed = normalized.SingleSceneConfirmation.Allowed,
                reason = normalized.SingleSceneConfirmation.Reason
            },
            notes = normalized.Notes
        };
        await WriteJsonAsync(project, SceneRouteRelativePath, payload, cancellationToken);
        return new SceneRouteStateResult(
            project.ProjectId,
            "confirmed",
            sceneHash,
            structuredHash,
            contractSnapshotHash,
            "",
            normalized,
            [],
            [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)],
            "created_run");
    }

    public async Task<SceneRouteStateResult?> GetSceneRouteAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        return project is null ? null : ReadSceneRoute(project);
    }

    public async Task<GddDocumentRouteStateResult?> RecordGeneratedGddAsync(
        string accountId,
        string projectId,
        string runId,
        CancellationToken cancellationToken = default)
    {
        await using var lease = await ProjectMutationLockRegistry.Shared.AcquireAsync(accountId, projectId, cancellationToken);
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var gddPath = Resolve(project.RepoPath, GddRelativePath);
        if (!File.Exists(gddPath))
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_not_found", "Generated GDD is missing.");
        }

        var scenePath = Resolve(project.RepoPath, SceneRouteRelativePath);
        JsonObject sceneRoot;
        try
        {
            sceneRoot = JsonNode.Parse(await File.ReadAllTextAsync(scenePath, Encoding.UTF8, cancellationToken))?.AsObject()
                ?? throw new JsonException("Scene route state root is missing.");
        }
        catch (Exception ex) when (ex is JsonException or FileNotFoundException or InvalidOperationException)
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_scene_hash_write_failed", "Confirmed scene route state is missing or invalid.");
        }

        if (!string.Equals(sceneRoot["schema_version"]?.GetValue<string>(), "scene-route.v1", StringComparison.Ordinal) ||
            !string.Equals(sceneRoot["status"]?.GetValue<string>(), "confirmed", StringComparison.Ordinal) ||
            string.IsNullOrWhiteSpace(sceneRoot["confirmed_scene_route_hash"]?.GetValue<string>()))
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_scene_hash_write_failed", "Confirmed scene route state is not current.");
        }

        var generatedHash = Sha256(await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken));
        var sceneHash = sceneRoot["confirmed_scene_route_hash"]!.GetValue<string>();
        var now = DateTimeOffset.UtcNow.ToString("O");
        var sourceHashes = new Dictionary<string, string>
        {
            [SceneRouteRelativePath] = sceneHash,
            [GddRelativePath] = generatedHash
        };
        var run = string.IsNullOrWhiteSpace(runId)
            ? null
            : await _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
        if (run is null ||
            !string.Equals(run.ProjectId, project.ProjectId, StringComparison.Ordinal) ||
            !string.Equals(run.RunType, "game-design-gdd", StringComparison.Ordinal) ||
            !string.Equals(run.Status, "succeeded", StringComparison.Ordinal) ||
            !TryReadRunPromptBinding(run, out var runPromptBinding))
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_prompt_run_invalid", "Generated GDD run is missing, incomplete, or belongs to another project.");
        }

        var approvedGuide = ReadApprovedGuide(project, run);
        if (approvedGuide is not null)
        {
            sourceHashes[$"game-type-guide:{approvedGuide.Id}"] = approvedGuide.ContentHash;
        }
        IReadOnlyList<ArtifactSnapshot> runArtifacts = runId.Length == 0
            ? Array.Empty<ArtifactSnapshot>()
            : await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
        var promptArtifactRefs = runArtifacts
            .Where(artifact => string.Equals(artifact.ArtifactType, GameDesignDocumentService.PromptArtifactType, StringComparison.Ordinal))
            .Select(artifact => artifact.RelativePath)
            .ToArray();
        var promptEvidenceRefs = runArtifacts
            .Where(artifact => string.Equals(artifact.ArtifactType, GameDesignDocumentService.PromptSourceEvidenceArtifactType, StringComparison.Ordinal))
            .Select(artifact => artifact.RelativePath)
            .ToArray();
        if (promptArtifactRefs.Length != 1 || promptEvidenceRefs.Length != 1)
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_prompt_evidence_missing", "Generated GDD run does not have one prompt artifact and one matching source-evidence artifact.");
        }

        var promptArtifactPath = Resolve(project.RepoPath, promptArtifactRefs[0]);
        var promptEvidencePath = Resolve(project.RepoPath, promptEvidenceRefs[0]);
        if (!File.Exists(promptArtifactPath) || !File.Exists(promptEvidencePath))
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_prompt_evidence_missing", "Generated GDD prompt evidence files are missing.");
        }

        JsonElement forbiddenSourceScan;
        string executionPromptHash;
        string persistedPromptHash;
        try
        {
            using var promptEvidenceDocument = JsonDocument.Parse(await File.ReadAllTextAsync(promptEvidencePath, Encoding.UTF8, cancellationToken));
            var promptEvidenceRoot = promptEvidenceDocument.RootElement;
            if (!string.Equals(ReadString(promptEvidenceRoot, "schema_version"), "gdd-prompt-source-evidence.v1", StringComparison.Ordinal) ||
                !string.Equals(ReadString(promptEvidenceRoot, "route"), "gdd-document-generation", StringComparison.Ordinal) ||
                !string.Equals(ReadString(promptEvidenceRoot, "run_id"), runId, StringComparison.Ordinal) ||
                !promptEvidenceRoot.TryGetProperty("prompt_manifest", out var promptManifest) ||
                promptManifest.ValueKind != JsonValueKind.Object ||
                !ReadStringArray(promptManifest, "prompt_artifact_refs").SequenceEqual(promptArtifactRefs, StringComparer.Ordinal) ||
                !ReadBoolean(promptManifest, "redacted"))
            {
                return GddDocumentRouteStateResult.Blocked(projectId, "gdd_prompt_evidence_invalid", "Generated GDD prompt evidence is not bound to the current run artifacts.");
            }

            executionPromptHash = ReadString(promptManifest, "execution_prompt_hash");
            persistedPromptHash = ReadString(promptManifest, "persisted_prompt_hash");
            if (!string.Equals(executionPromptHash, runPromptBinding.ExecutionPromptHash, StringComparison.Ordinal) ||
                !string.Equals(persistedPromptHash, runPromptBinding.PersistedPromptHash, StringComparison.Ordinal) ||
                !string.Equals(promptArtifactRefs[0], runPromptBinding.PromptArtifactRef, StringComparison.Ordinal) ||
                !string.Equals(promptEvidenceRefs[0], runPromptBinding.PromptSourceEvidenceRef, StringComparison.Ordinal))
            {
                return GddDocumentRouteStateResult.Blocked(projectId, "gdd_prompt_evidence_invalid", "Generated GDD prompt evidence does not match the database run binding.");
            }
            var allowedSourceReferences = approvedGuide is null ? Array.Empty<string>() : new[] { approvedGuide.RelativePath };
            var forbiddenGuideCatalog = BuildGuideFingerprints(project.RepoPath, approvedGuide?.ContentHash);
            if (!HostedRouteForbiddenSourceGuard.IsValidEvidence(
                    promptEvidenceRoot,
                    ForbiddenSourcePatterns,
                    forbiddenGuideCatalog.Fingerprints.Select(item => item.ContentHash).Distinct(StringComparer.Ordinal).OrderBy(item => item, StringComparer.Ordinal).ToArray(),
                    requireForbiddenContentFingerprints: true,
                    expectedAllowedSourceReferences: allowedSourceReferences,
                    forbiddenContentFingerprintSetComplete: forbiddenGuideCatalog.IsComplete) ||
                !promptEvidenceRoot.TryGetProperty("forbidden_source_scan", out var sourceScan) ||
                !string.Equals(ReadString(sourceScan, "prompt_hash"), executionPromptHash, StringComparison.Ordinal) ||
                !string.Equals(
                    HostedRouteForbiddenSourceGuard.PromptHash(await File.ReadAllTextAsync(promptArtifactPath, Encoding.UTF8, cancellationToken)),
                    persistedPromptHash,
                    StringComparison.Ordinal))
            {
                return GddDocumentRouteStateResult.Blocked(projectId, "gdd_forbidden_source_detected", "Generated GDD prompt source boundary could not be verified.");
            }

            forbiddenSourceScan = sourceScan.Clone();
        }
        catch (Exception ex) when (ex is JsonException or IOException or UnauthorizedAccessException)
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_prompt_evidence_invalid", "Generated GDD prompt evidence could not be read.");
        }
        await WriteJsonAsync(project, GddDocumentPromptEvidenceRelativePath, new
        {
            schema_version = "gdd-document-prompt-evidence.v1",
            route = "gdd-document-generation",
            run_id = runId,
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            source_hashes = sourceHashes,
            prompt_manifest = new
            {
                prompt_count = promptArtifactRefs.Length,
                prompt_artifact_refs = promptArtifactRefs,
                execution_prompt_hash = executionPromptHash,
                persisted_prompt_hash = persistedPromptHash,
                retention = "internal_recovery_only",
                browser_readable = false,
                redacted = true
            },
            forbidden_source_scan = forbiddenSourceScan,
            approved_guide_sources = approvedGuide is null
                ? Array.Empty<object>()
                : new object[]
                {
                    new
                    {
                        id = approvedGuide.Id,
                        path = approvedGuide.RelativePath,
                        content_hash = approvedGuide.ContentHash
                    }
                },
            raw_prompt_persisted = false,
            redacted_prompt_persisted = true,
            checked_utc = now
        }, cancellationToken);
        await _metadataStore.UpsertProjectRoutePromptEvidenceBindingAsync(
            new ProjectRoutePromptEvidenceBindingCommand(
                project.ProjectId,
                "gdd-document-generation",
                executionPromptHash,
                persistedPromptHash,
                promptArtifactRefs[0],
                GddDocumentPromptEvidenceRelativePath),
            cancellationToken);
        sceneRoot["source_generated_gdd_hash"] = generatedHash;
        sceneRoot["updated_utc"] = now;
        object BuildDocumentPayload(string status, string operationStatus) => new
        {
            schema_version = "gdd-document-generation.v1",
            route = "gdd-document-generation",
            project_id = project.ProjectId,
            run_id = runId,
            status_dimension = "route_readback",
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            status,
            operation_status = operationStatus,
            generated_gdd_path = GddRelativePath,
            generated_gdd_hash = generatedHash,
            source_scene_route_hash = sceneHash,
            scene_route_recorded_generated_gdd_hash = generatedHash,
            updated_utc = now,
            source_boundary_enforced = true,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = sourceHashes.Keys.ToArray(),
                source_hashes = sourceHashes,
                forbidden_source_patterns = ForbiddenSourcePatterns,
                allowed_source_references = approvedGuide is null ? Array.Empty<string>() : new[] { approvedGuide.RelativePath },
                prompt_evidence_refs = new[] { GddDocumentPromptEvidenceRelativePath },
                checked_utc = now
            },
            evidence_refs = new object[]
            {
                new { kind = "sidecar", path = GddDocumentRelativePath },
                new { kind = "sidecar", path = SceneRouteRelativePath },
                new { kind = "artifact", path = GddRelativePath }
            }
        };

        try
        {
            await WriteJsonAsync(project, GddDocumentRelativePath, BuildDocumentPayload("running", "in_progress"), cancellationToken);
            await WriteTextAtomicallyAsync(scenePath, sceneRoot.ToJsonString(JsonOptions()), cancellationToken);
            await WriteJsonAsync(project, GddDocumentRelativePath, BuildDocumentPayload("ready", "created_run"), cancellationToken);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            return GddDocumentRouteStateResult.Blocked(projectId, "gdd_scene_hash_write_failed", "Generated GDD state could not be written through to the scene route.");
        }

        return new GddDocumentRouteStateResult(
            project.ProjectId,
            "ready",
            generatedHash,
            generatedHash,
            sceneHash,
            [],
            [
                new ProjectRouteStateEvidenceRef("sidecar", GddDocumentRelativePath),
                new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath),
                new ProjectRouteStateEvidenceRef("artifact", GddRelativePath)
            ],
            "created_run");
    }

    public async Task<GddDocumentRouteStateResult?> GetGddDocumentStateAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var path = Resolve(project.RepoPath, GddDocumentRelativePath);
        if (!File.Exists(path))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(await File.ReadAllTextAsync(path, Encoding.UTF8, cancellationToken));
            var root = document.RootElement;
            var status = ReadString(root, "status", "unknown");
            var generatedHash = ReadString(root, "generated_gdd_hash");
            var sourceSceneHash = ReadString(root, "source_scene_route_hash");
            if (!string.Equals(status, "ready", StringComparison.Ordinal))
            {
                return GddDocumentRouteStateResult.Blocked(project.ProjectId, "gdd_document_write_incomplete", "GDD document route state is not ready.");
            }

            var gddPath = Resolve(project.RepoPath, GddRelativePath);
            var scenePath = Resolve(project.RepoPath, SceneRouteRelativePath);
            if (!File.Exists(gddPath) || !File.Exists(scenePath) ||
                !string.Equals(generatedHash, Sha256(await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken)), StringComparison.Ordinal))
            {
                return GddDocumentRouteStateResult.Blocked(project.ProjectId, "gdd_document_state_stale", "GDD document route state does not match the current GDD artifact.");
            }

            using var sceneDocument = JsonDocument.Parse(await File.ReadAllTextAsync(scenePath, Encoding.UTF8, cancellationToken));
            var sceneRoot = sceneDocument.RootElement;
            if (!string.Equals(ReadString(sceneRoot, "confirmed_scene_route_hash"), sourceSceneHash, StringComparison.Ordinal) ||
                !string.Equals(ReadString(sceneRoot, "source_generated_gdd_hash"), generatedHash, StringComparison.Ordinal))
            {
                return GddDocumentRouteStateResult.Blocked(project.ProjectId, "gdd_document_state_stale", "GDD document route state does not match the confirmed scene route.");
            }

            return new GddDocumentRouteStateResult(
                project.ProjectId,
                status,
                generatedHash,
                ReadString(root, "scene_route_recorded_generated_gdd_hash"),
                sourceSceneHash,
                [],
                [new ProjectRouteStateEvidenceRef("sidecar", GddDocumentRelativePath)],
                "returned_existing");
        }
        catch (Exception ex) when (ex is JsonException or IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            return GddDocumentRouteStateResult.Blocked(project.ProjectId, "gdd_document_state_invalid", "GDD document route state is invalid.");
        }
    }

    private SceneRouteStateResult? ReadSceneRoute(ProjectSnapshot project)
    {
        var path = Resolve(project.RepoPath, SceneRouteRelativePath);
        if (!File.Exists(path))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            var root = document.RootElement;
            var sceneRoute = new GameDesignSceneRouteDocument(
                "gdd-scene-route.v1",
                ReadString(root, "scene_count_intent", "unsure"),
                ReadString(root, "entry_scene"),
                ReadArray(root, "scenes").Select(scene => new GameDesignSceneRouteScene(
                    ReadString(scene, "scene_id"),
                    ReadString(scene, "scene_name"),
                    ReadString(scene, "role"),
                    ReadBoolean(scene, "m1_required"),
                    ReadString(scene, "player_goal"))).ToArray(),
                ReadArray(root, "transitions").Select(transition => new GameDesignSceneRouteTransition(
                    ReadString(transition, "from"),
                    ReadString(transition, "to"),
                    ReadString(transition, "trigger"),
                    ReadString(transition, "returns_to"),
                    ReadStringArray(transition, "state_carried"))).ToArray(),
                ReadSingleSceneConfirmation(root),
                ReadStringArray(root, "notes"));
            return new SceneRouteStateResult(
                project.ProjectId,
                ReadString(root, "status", "unknown"),
                ReadString(root, "confirmed_scene_route_hash"),
                ReadString(root, "source_game_type_structured_hash"),
                ReadString(root, "source_contract_snapshot_hash"),
                ReadString(root, "source_generated_gdd_hash"),
                sceneRoute,
                [],
                [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)],
                "returned_existing");
        }
        catch (JsonException)
        {
            return SceneRouteStateResult.Blocked(project.ProjectId, "scene_route_invalid", "Scene route sidecar is invalid.");
        }
    }

    private async Task<ProjectSnapshot?> GetProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        return project is not null && string.Equals(project.AccountId, accountId, StringComparison.Ordinal) ? project : null;
    }

    private static async Task WriteJsonAsync(ProjectSnapshot project, string relativePath, object payload, CancellationToken cancellationToken)
    {
        var path = Resolve(project.RepoPath, relativePath);
        await WriteTextAtomicallyAsync(path, JsonSerializer.Serialize(payload, JsonOptions()), cancellationToken);
    }

    private static async Task WriteTextAtomicallyAsync(string path, string content, CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporaryPath = $"{path}.{Guid.NewGuid():N}.tmp";
        try
        {
            await File.WriteAllTextAsync(temporaryPath, content, new UTF8Encoding(false), cancellationToken);
            File.Move(temporaryPath, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    private static string ReadOptionalFileHash(ProjectSnapshot project, string relativePath)
    {
        var path = Resolve(project.RepoPath, relativePath);
        return File.Exists(path) ? Sha256(File.ReadAllText(path, Encoding.UTF8)) : "";
    }

    private static string Resolve(string root, string relativePath)
    {
        var rootPath = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var path = Path.GetFullPath(Path.Combine(rootPath, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (!path.StartsWith(rootPath + Path.DirectorySeparatorChar, comparison))
        {
            throw new InvalidOperationException("Phase 1 route-state path escaped the project root.");
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

    private static GameDesignSingleSceneConfirmation ReadSingleSceneConfirmation(JsonElement root)
    {
        return root.TryGetProperty("single_scene_confirmation", out var value) && value.ValueKind == JsonValueKind.Object
            ? new GameDesignSingleSceneConfirmation(ReadBoolean(value, "allowed"), ReadString(value, "reason"))
            : new GameDesignSingleSceneConfirmation(false, "");
    }

    private static bool ReadBoolean(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind is JsonValueKind.True or JsonValueKind.False && value.GetBoolean();
    }

    private static string ReadString(JsonElement root, string propertyName, string fallback = "")
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? fallback
            : fallback;
    }

    private static string Sha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value.Replace("\r\n", "\n").Trim()))).ToLowerInvariant();
    }

    private static bool TryReadRunPromptBinding(RunSnapshot run, out RunPromptBinding binding)
    {
        binding = new RunPromptBinding("", "", "", "");
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (!document.RootElement.TryGetProperty("prompt_manifest", out var manifest) ||
                manifest.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            binding = new RunPromptBinding(
                ReadString(manifest, "execution_prompt_hash"),
                ReadString(manifest, "persisted_prompt_hash"),
                ReadString(manifest, "prompt_artifact_ref"),
                ReadString(manifest, "prompt_source_evidence_ref"));
            return binding.ExecutionPromptHash.Length == 64 &&
                   binding.PersistedPromptHash.Length == 64 &&
                   !string.IsNullOrWhiteSpace(binding.PromptArtifactRef) &&
                   !string.IsNullOrWhiteSpace(binding.PromptSourceEvidenceRef);
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static ApprovedGuideSource? ReadApprovedGuide(ProjectSnapshot project, RunSnapshot run)
    {
        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson!);
            if (!document.RootElement.TryGetProperty("game_type_design_template", out var template) ||
                template.ValueKind != JsonValueKind.Object)
            {
                return null;
            }

            var id = template.TryGetProperty("id", out var idValue) && idValue.ValueKind == JsonValueKind.String
                ? idValue.GetString()?.Trim() ?? ""
                : "";
            var recordedHash = template.TryGetProperty("guide_excerpt_hash", out var hashValue) && hashValue.ValueKind == JsonValueKind.String
                ? hashValue.GetString()?.Trim() ?? ""
                : "";
            var entry = new BmadGameTypeDesignCatalog(project.RepoPath).Find(id);
            if (entry is null)
            {
                return null;
            }

            var currentHash = HostedRouteForbiddenSourceGuard.ContentHash(entry.GuideExcerpt);
            return string.Equals(recordedHash, currentHash, StringComparison.Ordinal)
                ? new ApprovedGuideSource(entry.Id, entry.FragmentRelativePath, currentHash)
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static ForbiddenGuideCatalog BuildGuideFingerprints(
        string repositoryRoot,
        string? approvedContentHash)
    {
        try
        {
            var catalog = new BmadGameTypeDesignCatalog(repositoryRoot);
            var entries = catalog.SourceEntries;
            var approvedEntry = entries.FirstOrDefault(entry => string.Equals(
                HostedRouteForbiddenSourceGuard.ContentHash(entry.GuideExcerpt),
                approvedContentHash,
                StringComparison.Ordinal));
            var approvedChunkHashes = approvedEntry is null
                ? new HashSet<string>(StringComparer.Ordinal)
                : HostedRouteForbiddenSourceGuard.CreateContentFingerprints(
                        approvedEntry.FragmentRelativePath,
                        approvedEntry.GuideExcerpt)
                    .Select(item => item.ContentHash)
                    .ToHashSet(StringComparer.Ordinal);
            var fingerprints = entries
                .Where(entry => !string.IsNullOrWhiteSpace(entry.GuideExcerpt))
                .Where(entry => !string.Equals(
                    HostedRouteForbiddenSourceGuard.ContentHash(entry.GuideExcerpt),
                    approvedContentHash,
                    StringComparison.Ordinal))
                .SelectMany(entry => HostedRouteForbiddenSourceGuard.CreateContentFingerprints(
                    entry.FragmentRelativePath,
                    entry.GuideExcerpt))
                .Where(item => !approvedChunkHashes.Contains(item.ContentHash))
                .GroupBy(item => item.ContentHash, StringComparer.Ordinal)
                .Select(group => group.First())
                .OrderBy(item => item.ContentHash, StringComparer.Ordinal)
                .ToArray();
            return new ForbiddenGuideCatalog(fingerprints, catalog.IsComplete);
        }
        catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException or IOException or UnauthorizedAccessException)
        {
            return new ForbiddenGuideCatalog([], IsComplete: false);
        }
    }

    private sealed record ForbiddenGuideCatalog(
        IReadOnlyList<HostedRouteForbiddenContentFingerprint> Fingerprints,
        bool IsComplete);

    private sealed record ApprovedGuideSource(string Id, string RelativePath, string ContentHash);

    private sealed record RunPromptBinding(
        string ExecutionPromptHash,
        string PersistedPromptHash,
        string PromptArtifactRef,
        string PromptSourceEvidenceRef);

    private static JsonSerializerOptions JsonOptions()
    {
        return new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true };
    }
}

public sealed record SceneRouteStateResult(
    string ProjectId,
    string Status,
    string ConfirmedSceneRouteHash,
    string SourceGameTypeStructuredHash,
    string SourceContractSnapshotHash,
    string SourceGeneratedGddHash,
    GameDesignSceneRouteDocument? SceneRoute,
    IReadOnlyList<ProjectWorkflowBlockingIssue> BlockingIssues,
    IReadOnlyList<ProjectRouteStateEvidenceRef> EvidenceRefs,
    string OperationStatus)
{
    public static SceneRouteStateResult Blocked(string projectId, string domainCode, string summary) =>
        new(projectId, "blocked", "", "", "", "", null,
            [new ProjectWorkflowBlockingIssue(domainCode, domainCode, "P1", summary, [new ProjectRouteStateEvidenceRef("sidecar", "meta/routes/scene-route/latest.json")])],
            [new ProjectRouteStateEvidenceRef("sidecar", "meta/routes/scene-route/latest.json")], "rejected");
}

public sealed record GddDocumentRouteStateResult(
    string ProjectId,
    string Status,
    string GeneratedGddHash,
    string SceneRouteRecordedGeneratedGddHash,
    string SourceSceneRouteHash,
    IReadOnlyList<ProjectWorkflowBlockingIssue> BlockingIssues,
    IReadOnlyList<ProjectRouteStateEvidenceRef> EvidenceRefs,
    string OperationStatus)
{
    public static GddDocumentRouteStateResult Blocked(string projectId, string domainCode, string summary) =>
        new(projectId, "blocked", "", "", "",
            [new ProjectWorkflowBlockingIssue(domainCode, domainCode, "P1", summary, [new ProjectRouteStateEvidenceRef("sidecar", "meta/routes/gdd-document/latest.json")])],
            [new ProjectRouteStateEvidenceRef("sidecar", "meta/routes/gdd-document/latest.json")], "rejected");
}
