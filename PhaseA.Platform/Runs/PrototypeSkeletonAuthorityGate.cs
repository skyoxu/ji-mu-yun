using System.Text.Json;
using System.Text.Json.Nodes;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

internal sealed record PrototypeSkeletonAuthorityGateResult(
    bool Allowed,
    string DomainCode,
    string Summary,
    IReadOnlyList<string> EvidenceRefs,
    IReadOnlySet<string> VerifiedRequirementIds);

internal static class PrototypeSkeletonAuthorityGate
{
    public const string CanonicalPath = "meta/routes/prototype-skeleton/latest.json";
    private const string RecoverySourceOrderRef = HostedRouteRecoveryContract.ContractId;
    private static readonly string[] RequiredAuthoritySources =
    [
        "game-type-route-profile",
        PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath,
        "routes/prototype-contract/latest.json",
        "meta/routes/gdd-requirements/latest.json",
        "meta/routes/prototype/latest.json"
    ];

    public static PrototypeSkeletonAuthorityGateResult Evaluate(
        ProjectSnapshot project,
        PrototypeRouteStateWriter routeStateWriter,
        PrototypeIterationPlanSourceHashes expectedHashes)
    {
        var copies = routeStateWriter.ReadPrototypeSkeletonStateCopies(project);
        if (string.IsNullOrWhiteSpace(copies.MetadataState) || string.IsNullOrWhiteSpace(copies.ProjectMirrorState))
        {
            return Blocked("prototype_skeleton_missing", "The current prototype skeleton authority readback is missing.");
        }

        try
        {
            var metadataNode = JsonNode.Parse(copies.MetadataState);
            var mirrorNode = JsonNode.Parse(copies.ProjectMirrorState);
            if (metadataNode is null || mirrorNode is null || !JsonNode.DeepEquals(metadataNode, mirrorNode))
            {
                return Blocked("prototype_skeleton_stale", "The prototype skeleton metadata state and project mirror do not match.");
            }
            using var document = JsonDocument.Parse(copies.MetadataState);
            var root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object ||
                !string.Equals(ReadString(root, "route"), "prototype-skeleton", StringComparison.Ordinal) ||
                !root.TryGetProperty("source_boundary_enforced", out var sourceBoundary) ||
                sourceBoundary.ValueKind != JsonValueKind.True ||
                ReadString(root, "status") is not ("ready" or "succeeded") ||
                !string.Equals(ReadString(root, "freshness"), "fresh", StringComparison.Ordinal) ||
                !HasEvidenceRefs(root) ||
                !DateTimeOffset.TryParse(ReadString(root, "updated_utc"), out _))
            {
                return Blocked("prototype_skeleton_stale", "The prototype skeleton readback is incomplete or not fresh.");
            }

            return HashesMatch(root, expectedHashes) && SourceBoundaryMatches(root, expectedHashes)
                ? new PrototypeSkeletonAuthorityGateResult(
                    true,
                    "",
                    "",
                    [CanonicalPath],
                    ReadStringSet(root, "verified_requirement_ids"))
                : Blocked("prototype_skeleton_stale", "The prototype skeleton source hashes do not match the current frozen authority chain.");
        }
        catch (JsonException)
        {
            return Blocked("prototype_skeleton_stale", "The prototype skeleton readback is invalid JSON.");
        }
    }

    private static bool HashesMatch(JsonElement root, PrototypeIterationPlanSourceHashes hashes)
    {
        return string.Equals(ReadString(root, "source_gdd_hash"), hashes.SourceGddHash, StringComparison.Ordinal) &&
               string.Equals(ReadString(root, "source_scene_route_hash"), hashes.SourceSceneRouteHash, StringComparison.Ordinal) &&
               string.Equals(ReadString(root, "source_requirement_map_hash"), hashes.SourceRequirementMapHash, StringComparison.Ordinal) &&
               string.Equals(ReadString(root, "source_contract_hash"), hashes.SourceContractHash, StringComparison.Ordinal) &&
               string.Equals(ReadString(root, "source_contract_snapshot_hash"), hashes.SourceContractSnapshotHash, StringComparison.Ordinal) &&
               string.Equals(ReadString(root, "source_godot_ui_contract_hash"), hashes.SourceGodotUiContractHash, StringComparison.Ordinal) &&
               string.Equals(ReadString(root, "source_ui_style_contract_hash"), hashes.SourceUiStyleContractHash, StringComparison.Ordinal) &&
               string.Equals(ReadString(root, "ui_style_snapshot_hash"), hashes.UiStyleSnapshotHash, StringComparison.Ordinal);
    }

    private static bool SourceBoundaryMatches(JsonElement root, PrototypeIterationPlanSourceHashes hashes)
    {
        if (!string.Equals(ReadString(root, "recovery_source_order_ref"), RecoverySourceOrderRef, StringComparison.Ordinal) ||
            !root.TryGetProperty("source_boundary", out var boundary) ||
            boundary.ValueKind != JsonValueKind.Object ||
            !string.Equals(ReadString(boundary, "recovery_source_order_ref"), RecoverySourceOrderRef, StringComparison.Ordinal) ||
            !HasCanonicalRecoverySourceOrder(boundary) ||
            !HasRequiredAuthoritySources(boundary) ||
            !boundary.TryGetProperty("source_hashes", out var sourceHashes) ||
            sourceHashes.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        return HashesMatch(sourceHashes, hashes);
    }

    private static bool HasRequiredAuthoritySources(JsonElement boundary)
    {
        if (!boundary.TryGetProperty("authority_sources", out var sources) ||
            sources.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        var actualSources = sources.EnumerateArray()
            .Select(static item => item.ValueKind == JsonValueKind.String ? item.GetString()?.Trim() ?? "" : "")
            .ToArray();
        return actualSources.SequenceEqual(RequiredAuthoritySources, StringComparer.Ordinal);
    }

    private static bool HasCanonicalRecoverySourceOrder(JsonElement boundary)
    {
        return boundary.TryGetProperty("recovery_source_order", out var order) &&
               order.ValueKind == JsonValueKind.Array &&
               order.EnumerateArray()
                   .Select(static item => item.ValueKind == JsonValueKind.String ? item.GetString()?.Trim() ?? "" : "")
                   .SequenceEqual(HostedRouteRecoveryContract.SourceOrder, StringComparer.Ordinal);
    }

    private static bool HasEvidenceRefs(JsonElement root)
    {
        return root.TryGetProperty("evidence_refs", out var refs) &&
               refs.ValueKind == JsonValueKind.Array &&
               refs.EnumerateArray().Any(item => item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString()));
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? ""
            : "";
    }

    private static IReadOnlySet<string> ReadStringSet(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out var value) || value.ValueKind != JsonValueKind.Array)
        {
            return new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        }

        return value.EnumerateArray()
            .Where(static item => item.ValueKind == JsonValueKind.String)
            .Select(static item => item.GetString()?.Trim() ?? "")
            .Where(static item => item.Length > 0)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static PrototypeSkeletonAuthorityGateResult Blocked(string domainCode, string summary)
    {
        return new PrototypeSkeletonAuthorityGateResult(
            false,
            domainCode,
            summary,
            [CanonicalPath],
            new HashSet<string>(StringComparer.OrdinalIgnoreCase));
    }
}
