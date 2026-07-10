using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeContractFreezeService
{
    private const string GddRelativePath = "docs/gdd/GDD.md";
    private const string SceneRouteRelativePath = "meta/routes/scene-route/latest.json";
    private const string GddDocumentRelativePath = "meta/routes/gdd-document/latest.json";
    private const string RequirementMapRelativePath = "meta/routes/gdd-requirements/latest.json";
    private const string ContractRelativePath = "routes/prototype-contract/latest.json";
    private const string ContractMirrorRelativePath = "meta/routes/prototype-contract/latest.json";
    private readonly PhaseAMetadataStore _metadataStore;

    public PrototypeContractFreezeService(PhaseAMetadataStore metadataStore)
    {
        _metadataStore = metadataStore;
    }

    public async Task<PrototypeContractStatusResult?> GetStatusAsync(string accountId, string projectId, CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        return project is null ? null : ReadStatus(project);
    }

    public async Task<PrototypeContractStatusResult> FreezeAsync(
        string accountId,
        string projectId,
        PrototypeContractFreezeRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return PrototypeContractStatusResult.NotFound(projectId);
        }

        var source = ReadSourceHashes(project);
        if (source.BlockingIssues.Count > 0)
        {
            return ToStatus(project.ProjectId, "blocked", "", source, "rejected");
        }

        var existing = ReadStatus(project);
        if (existing.Status == "fresh" &&
            !request.Refresh &&
            string.Equals(existing.SourceGddHash, source.SourceGddHash, StringComparison.Ordinal) &&
            string.Equals(existing.SourceSceneRouteHash, source.SourceSceneRouteHash, StringComparison.Ordinal) &&
            string.Equals(existing.SourceRequirementMapHash, source.SourceRequirementMapHash, StringComparison.Ordinal))
        {
            return existing with { OperationStatus = "returned_existing" };
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        var canonicalPayload = new SortedDictionary<string, object?>
        {
            ["schema_version"] = "prototype-contract.v2",
            ["route"] = "prototype-contract",
            ["project_id"] = project.ProjectId,
            ["source_gdd_hash"] = source.SourceGddHash,
            ["source_scene_route_hash"] = source.SourceSceneRouteHash,
            ["source_requirement_map_hash"] = source.SourceRequirementMapHash,
            ["source_contract_snapshot_hash"] = source.SourceContractSnapshotHash,
            ["godot_ui_contract_version"] = source.GodotUiContractVersion,
            ["source_godot_ui_contract_hash"] = source.SourceGodotUiContractHash,
            ["ui_style_id"] = source.UiStyleId,
            ["ui_style_version"] = source.UiStyleVersion,
            ["source_ui_style_contract_hash"] = source.SourceUiStyleContractHash,
            ["ui_style_snapshot_hash"] = source.UiStyleSnapshotHash,
            ["requirement_traceability"] = source.RequirementIds.Select(id => new { requirement_id = id }).ToArray()
        };
        var contractHash = Sha256(JsonSerializer.Serialize(canonicalPayload, JsonOptions()));
        var payload = new SortedDictionary<string, object?>(canonicalPayload)
        {
            ["contract_hash"] = contractHash,
            ["freshness"] = new { status = "fresh", stale_reasons = Array.Empty<string>() },
            ["source_boundary_enforced"] = true,
            ["source_boundary"] = new
            {
                recovery_source_order_ref = "hosted-route-recovery-order.v1",
                authority_sources = new[] { "docs/gdd/GDD.md", "confirmed scene route", "meta/routes/gdd-requirements/latest.json", "project contract snapshot" },
                source_hashes = new Dictionary<string, string>
                {
                    [GddRelativePath] = source.SourceGddHash,
                    [SceneRouteRelativePath] = source.SourceSceneRouteHash,
                    [RequirementMapRelativePath] = source.SourceRequirementMapHash,
                    ["project-contract-snapshot"] = source.SourceContractSnapshotHash
                },
                forbidden_source_patterns = new[] { "docs/game-type-guides/** raw excerpts" },
                prompt_evidence_refs = Array.Empty<object>(),
                checked_utc = now
            },
            ["updated_utc"] = now,
            ["evidence_refs"] = new[] { new { kind = "sidecar", path = ContractRelativePath } }
        };
        await WriteJsonAsync(project, ContractRelativePath, payload, cancellationToken);
        await WriteJsonAsync(project, ContractMirrorRelativePath, payload, cancellationToken);
        return ToStatus(project.ProjectId, "fresh", contractHash, source, request.Refresh ? "created_run" : "returned_existing");
    }

    public NewChainGuardResult EvaluateNewChainGuard(ProjectSnapshot project)
    {
        var active = HasExplicitNewChainArtifact(project);
        if (!active)
        {
            return new NewChainGuardResult(false, true, "legacy_compatibility", "Legacy project has no new-chain route-state sidecars.", ReadStatus(project));
        }

        var status = ReadStatus(project);
        if (status.Status == "fresh")
        {
            return new NewChainGuardResult(true, true, "fresh", "", status);
        }

        return new NewChainGuardResult(true, false, string.IsNullOrWhiteSpace(status.ContractHash) ? "contract_missing" : "contract_stale", "New-chain prototype skeleton and module execution require a fresh frozen prototype contract.", status);
    }

    private static bool HasExplicitNewChainArtifact(ProjectSnapshot project)
    {
        return JsonStringEquals(project, RequirementMapRelativePath, "schema_version", "gdd-requirements.v1") ||
               JsonStringEquals(project, SceneRouteRelativePath, "schema_version", "scene-route.v1") ||
               IsExplicitFrozenContract(project);
    }

    private static bool IsExplicitFrozenContract(ProjectSnapshot project)
    {
        var path = Resolve(project.RepoPath, ContractRelativePath);
        if (!File.Exists(path))
        {
            return false;
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            var root = doc.RootElement;
            if (string.Equals(ReadString(root, "schema_version"), "prototype-contract.v2", StringComparison.Ordinal))
            {
                return true;
            }

            return !string.IsNullOrWhiteSpace(ReadString(root, "contract_hash")) &&
                   !string.IsNullOrWhiteSpace(ReadString(root, "source_gdd_hash")) &&
                   !string.IsNullOrWhiteSpace(ReadString(root, "source_scene_route_hash")) &&
                   !string.IsNullOrWhiteSpace(ReadString(root, "source_requirement_map_hash"));
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private PrototypeContractStatusResult ReadStatus(ProjectSnapshot project)
    {
        var source = ReadSourceHashes(project);
        var contractPath = Resolve(project.RepoPath, ContractRelativePath);
        if (!File.Exists(contractPath))
        {
            return ToStatus(project.ProjectId, source.BlockingIssues.Count > 0 ? "blocked" : "missing", "", source, "returned_existing");
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(contractPath, Encoding.UTF8));
            var root = doc.RootElement;
            var staleReasons = new List<string>();
            Compare(staleReasons, "source_gdd_hash", ReadString(root, "source_gdd_hash"), source.SourceGddHash);
            Compare(staleReasons, "source_scene_route_hash", ReadString(root, "source_scene_route_hash"), source.SourceSceneRouteHash);
            Compare(staleReasons, "source_requirement_map_hash", ReadString(root, "source_requirement_map_hash"), source.SourceRequirementMapHash);
            Compare(staleReasons, "source_godot_ui_contract_hash", ReadString(root, "source_godot_ui_contract_hash"), source.SourceGodotUiContractHash);
            Compare(staleReasons, "source_ui_style_contract_hash", ReadString(root, "source_ui_style_contract_hash"), source.SourceUiStyleContractHash);
            Compare(staleReasons, "ui_style_snapshot_hash", ReadString(root, "ui_style_snapshot_hash"), source.UiStyleSnapshotHash);
            var mirrorPath = Resolve(project.RepoPath, ContractMirrorRelativePath);
            if (File.Exists(mirrorPath) && Sha256(NormalizeText(File.ReadAllText(mirrorPath, Encoding.UTF8))) != Sha256(NormalizeText(File.ReadAllText(contractPath, Encoding.UTF8))))
            {
                staleReasons.Add("mirror_hash_mismatch");
            }

            var status = staleReasons.Count == 0 && source.BlockingIssues.Count == 0 ? "fresh" : "stale";
            return ToStatus(project.ProjectId, status, ReadString(root, "contract_hash"), source, "returned_existing", staleReasons);
        }
        catch (JsonException)
        {
            var invalid = source.BlockingIssues.Concat([
                new ProjectWorkflowBlockingIssue("contract_invalid", "contract_missing", "P0", "Prototype contract JSON is invalid.", [new ProjectRouteStateEvidenceRef("sidecar", ContractRelativePath)])
            ]).ToArray();
            source = source with { BlockingIssues = invalid };
            return ToStatus(project.ProjectId, "unknown", "", source, "returned_existing");
        }
    }

    private PrototypeContractSourceHashes ReadSourceHashes(ProjectSnapshot project)
    {
        var issues = new List<ProjectWorkflowBlockingIssue>();
        var gddHash = ReadFileHash(project, GddRelativePath, issues, "gdd_not_found", "P1");
        var requirementMapHash = ReadFileHash(project, RequirementMapRelativePath, issues, "requirement_map_missing", "P1");
        var sceneStatus = ReadSceneRouteSource(project, gddHash, issues);
        var requirementMapSourceSceneHash = ReadJsonString(project, RequirementMapRelativePath, "source_scene_route_hash", [], "", "P2");
        if (!string.IsNullOrWhiteSpace(sceneStatus.ConfirmedSceneRouteHash) &&
            !string.IsNullOrWhiteSpace(requirementMapSourceSceneHash) &&
            !string.Equals(sceneStatus.ConfirmedSceneRouteHash, requirementMapSourceSceneHash, StringComparison.Ordinal))
        {
            issues.Add(new ProjectWorkflowBlockingIssue(
                "requirement_map_scene_hash_mismatch",
                "requirement_map_invalid",
                "P1",
                "Requirement map source_scene_route_hash does not match the confirmed scene route hash.",
                [new ProjectRouteStateEvidenceRef("sidecar", RequirementMapRelativePath)]));
        }

        var requirementIds = ReadRequirementIds(project);
        return new PrototypeContractSourceHashes(
            gddHash,
            sceneStatus.ConfirmedSceneRouteHash,
            requirementMapHash,
            string.IsNullOrWhiteSpace(sceneStatus.SourceContractSnapshotHash) ? "unknown" : sceneStatus.SourceContractSnapshotHash,
            "godot-ui-capability.v1",
            ReadJsonString(project, RequirementMapRelativePath, "source_godot_ui_contract_hash", [], "", "P2", "unknown"),
            "godot_cosmic",
            "1",
            "unknown",
            "unknown",
            requirementIds,
            issues);
    }

    private static PrototypeContractSceneSource ReadSceneRouteSource(ProjectSnapshot project, string currentGddHash, List<ProjectWorkflowBlockingIssue> issues)
    {
        var path = Resolve(project.RepoPath, SceneRouteRelativePath);
        if (!File.Exists(path))
        {
            issues.Add(new ProjectWorkflowBlockingIssue("scene_route_missing", "scene_route_missing", "P1", $"{SceneRouteRelativePath} is missing.", [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)]));
            return new PrototypeContractSceneSource("", "");
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            var root = doc.RootElement;
            if (!string.Equals(ReadString(root, "schema_version"), "scene-route.v1", StringComparison.Ordinal))
            {
                issues.Add(new ProjectWorkflowBlockingIssue("scene_route_invalid", "route_state_invalid", "P1", "Scene route schema_version is invalid.", [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)]));
            }

            var status = ReadString(root, "status");
            if (!string.Equals(status, "confirmed", StringComparison.Ordinal))
            {
                issues.Add(new ProjectWorkflowBlockingIssue(
                    status == "stale" ? "scene_route_stale" : "scene_route_unconfirmed",
                    status == "stale" ? "scene_route_stale" : "scene_route_unconfirmed",
                    "P1",
                    "Scene route must be confirmed before prototype contract freeze.",
                    [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)]));
            }

            var sceneHash = ReadString(root, "confirmed_scene_route_hash");
            if (string.IsNullOrWhiteSpace(sceneHash))
            {
                issues.Add(new ProjectWorkflowBlockingIssue("scene_route_unconfirmed", "scene_route_unconfirmed", "P1", "Confirmed scene route hash is missing.", [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)]));
            }

            var currentStructuredHash = Sha256(NormalizeText(project.GameTypeMatchJson));
            var structuredHash = ReadString(root, "source_game_type_structured_hash");
            if (!string.IsNullOrWhiteSpace(structuredHash) &&
                !string.Equals(structuredHash, currentStructuredHash, StringComparison.Ordinal))
            {
                issues.Add(new ProjectWorkflowBlockingIssue("game_type_structured_stale", "game_type_structured_stale", "P1", "Structured game-type metadata changed after scene route confirmation.", [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)]));
            }

            var gddDocumentPath = Resolve(project.RepoPath, GddDocumentRelativePath);
            if (!File.Exists(gddDocumentPath))
            {
                issues.Add(new ProjectWorkflowBlockingIssue("gdd_document_state_missing", "gdd_document_state_missing", "P1", $"{GddDocumentRelativePath} is missing.", [new ProjectRouteStateEvidenceRef("sidecar", GddDocumentRelativePath)]));
            }
            else
            {
                using var gddDoc = JsonDocument.Parse(File.ReadAllText(gddDocumentPath, Encoding.UTF8));
                if (!string.Equals(ReadString(gddDoc.RootElement, "generated_gdd_hash"), currentGddHash, StringComparison.Ordinal) ||
                    !string.Equals(ReadString(root, "source_generated_gdd_hash"), currentGddHash, StringComparison.Ordinal))
                {
                    issues.Add(new ProjectWorkflowBlockingIssue("generated_gdd_hash_mismatch", "generated_gdd_hash_mismatch", "P1", "Generated GDD hash does not match scene route and document state.", [new ProjectRouteStateEvidenceRef("sidecar", GddDocumentRelativePath)]));
                }
            }

            return new PrototypeContractSceneSource(sceneHash, ReadString(root, "source_contract_snapshot_hash"));
        }
        catch (JsonException)
        {
            issues.Add(new ProjectWorkflowBlockingIssue("scene_route_invalid", "route_state_invalid", "P1", "Scene route JSON is invalid.", [new ProjectRouteStateEvidenceRef("sidecar", SceneRouteRelativePath)]));
            return new PrototypeContractSceneSource("", "");
        }
    }

    private async Task<ProjectSnapshot?> GetProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        return project is not null && string.Equals(project.AccountId, accountId, StringComparison.Ordinal)
            ? project
            : null;
    }

    private static PrototypeContractStatusResult ToStatus(
        string projectId,
        string status,
        string contractHash,
        PrototypeContractSourceHashes source,
        string operationStatus,
        IReadOnlyList<string>? staleReasons = null)
    {
        return new PrototypeContractStatusResult(
            projectId,
            status,
            contractHash,
            source.SourceGddHash,
            source.SourceSceneRouteHash,
            source.SourceRequirementMapHash,
            source.SourceContractSnapshotHash,
            source.SourceGodotUiContractHash,
            source.SourceUiStyleContractHash,
            source.UiStyleSnapshotHash,
            new PrototypeContractFreshness(status == "fresh" ? "fresh" : status == "missing" ? "unknown" : status, staleReasons ?? []),
            source.BlockingIssues,
            [new ProjectRouteStateEvidenceRef("sidecar", ContractRelativePath)],
            operationStatus);
    }

    private static string ReadFileHash(ProjectSnapshot project, string relativePath, List<ProjectWorkflowBlockingIssue> issues, string domainCode, string severity)
    {
        var path = Resolve(project.RepoPath, relativePath);
        if (!File.Exists(path))
        {
            issues.Add(new ProjectWorkflowBlockingIssue(domainCode, domainCode, severity, $"{relativePath} is missing.", [new ProjectRouteStateEvidenceRef("sidecar", relativePath)]));
            return "";
        }

        return Sha256(NormalizeText(File.ReadAllText(path, Encoding.UTF8)));
    }

    private static string ReadJsonString(ProjectSnapshot project, string relativePath, string propertyName, List<ProjectWorkflowBlockingIssue> issues, string domainCode, string severity, string fallback = "")
    {
        var path = Resolve(project.RepoPath, relativePath);
        if (!File.Exists(path))
        {
            if (!string.IsNullOrWhiteSpace(domainCode))
            {
                issues.Add(new ProjectWorkflowBlockingIssue(domainCode, domainCode, severity, $"{relativePath} is missing.", [new ProjectRouteStateEvidenceRef("sidecar", relativePath)]));
            }

            return fallback;
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            return ReadString(doc.RootElement, propertyName, fallback);
        }
        catch (JsonException)
        {
            issues.Add(new ProjectWorkflowBlockingIssue("route_state_invalid", "route_state_invalid", severity, $"{relativePath} is invalid.", [new ProjectRouteStateEvidenceRef("sidecar", relativePath)]));
            return fallback;
        }
    }

    private static bool JsonStringEquals(ProjectSnapshot project, string relativePath, string propertyName, string expected)
    {
        var path = Resolve(project.RepoPath, relativePath);
        if (!File.Exists(path))
        {
            return false;
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            return string.Equals(ReadString(doc.RootElement, propertyName), expected, StringComparison.Ordinal);
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static IReadOnlyList<string> ReadRequirementIds(ProjectSnapshot project)
    {
        var path = Resolve(project.RepoPath, RequirementMapRelativePath);
        if (!File.Exists(path))
        {
            return [];
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            return doc.RootElement.TryGetProperty("requirements", out var requirements) && requirements.ValueKind == JsonValueKind.Array
                ? requirements.EnumerateArray().Select(item => ReadString(item, "requirement_id")).Where(item => !string.IsNullOrWhiteSpace(item)).ToArray()
                : [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static void Compare(List<string> staleReasons, string field, string recorded, string current)
    {
        if (!string.IsNullOrWhiteSpace(recorded) &&
            !string.IsNullOrWhiteSpace(current) &&
            !string.Equals(recorded, current, StringComparison.Ordinal))
        {
            staleReasons.Add(field);
        }
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
            throw new InvalidOperationException("Prototype contract path escaped project root.");
        }

        return path;
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

public sealed record PrototypeContractFreezeRequest(bool Refresh = false);

public sealed record PrototypeContractStatusResult(
    string ProjectId,
    string Status,
    string ContractHash,
    string SourceGddHash,
    string SourceSceneRouteHash,
    string SourceRequirementMapHash,
    string SourceContractSnapshotHash,
    string SourceGodotUiContractHash,
    string SourceUiStyleContractHash,
    string UiStyleSnapshotHash,
    PrototypeContractFreshness Freshness,
    IReadOnlyList<ProjectWorkflowBlockingIssue> BlockingIssues,
    IReadOnlyList<ProjectRouteStateEvidenceRef> EvidenceRefs,
    string OperationStatus)
{
    public static PrototypeContractStatusResult NotFound(string projectId) =>
        new(projectId, "project_not_found", "", "", "", "", "", "", "", "", new PrototypeContractFreshness("unknown", []), [], [], "rejected");
}

public sealed record PrototypeContractFreshness(string Status, IReadOnlyList<string> StaleReasons);

public sealed record NewChainGuardResult(
    bool NewChainActive,
    bool Allowed,
    string Status,
    string Summary,
    PrototypeContractStatusResult ContractStatus);

internal sealed record PrototypeContractSourceHashes(
    string SourceGddHash,
    string SourceSceneRouteHash,
    string SourceRequirementMapHash,
    string SourceContractSnapshotHash,
    string GodotUiContractVersion,
    string SourceGodotUiContractHash,
    string UiStyleId,
    string UiStyleVersion,
    string SourceUiStyleContractHash,
    string UiStyleSnapshotHash,
    IReadOnlyList<string> RequirementIds,
    IReadOnlyList<ProjectWorkflowBlockingIssue> BlockingIssues);

internal sealed record PrototypeContractSceneSource(string ConfirmedSceneRouteHash, string SourceContractSnapshotHash);
