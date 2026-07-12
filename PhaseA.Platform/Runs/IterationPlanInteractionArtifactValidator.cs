using System.Text.Json;
using System.Text.Json.Nodes;

namespace PhaseA.Platform.Runs;

internal sealed record IterationPlanInteractionArtifactValidationResult(
    bool Allowed,
    string Summary,
    JsonObject? ValidatedPayload);

internal static class IterationPlanInteractionArtifactValidator
{
    public const string ValidationMethod = "deterministic-interaction-contract-validator";

    public static IterationPlanInteractionArtifactValidationResult ValidateCandidate(
        string projectRoot,
        string artifactRef,
        int goalIndex,
        IReadOnlyList<string> requirementIds,
        string sourceHashRef,
        IReadOnlyList<string> expectedOwners,
        IReadOnlyList<PrototypeIterationInteractionGeometryResult> expectedGeometry,
        string expectedCoordinateSemantics)
    {
        try
        {
            var root = Path.GetFullPath(projectRoot);
            var relative = artifactRef.Replace('/', Path.DirectorySeparatorChar);
            var path = Path.GetFullPath(Path.Combine(root, relative));
            if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) || !File.Exists(path))
            {
                return Blocked("Interaction-region candidate is missing or outside the project root.");
            }

            var payload = JsonNode.Parse(File.ReadAllText(path))?.AsObject();
            if (payload is null ||
                !string.Equals(ReadString(payload, "schema_version"), "godot-interaction-region.v1", StringComparison.Ordinal) ||
                !string.Equals(ReadString(payload, "validation_status"), "pending", StringComparison.Ordinal) ||
                !string.Equals(ReadString(payload, "artifact_form"), "planned-godot-node-map", StringComparison.Ordinal) ||
                !string.Equals(ReadString(payload, "evidence_kind"), "pre-execution-design-contract", StringComparison.Ordinal) ||
                payload["runtime_validation_required"]?.GetValue<bool>() != true ||
                !string.Equals(ReadString(payload, "coordinate_semantics"), expectedCoordinateSemantics, StringComparison.Ordinal) ||
                ReadInt(payload, "goal_index") != goalIndex ||
                !string.Equals(ReadString(payload, "source_hash_ref"), sourceHashRef, StringComparison.Ordinal) ||
                !SameValues(ReadStrings(payload, "requirement_ids"), requirementIds) ||
                !SameValues(ReadStrings(payload, "scene_node_owners"), expectedOwners) ||
                !HasValidOwnerContract(expectedOwners) ||
                !HasValidGeometry(payload, expectedGeometry, expectedOwners, expectedCoordinateSemantics) ||
                !HasValues(payload, "valid_regions") ||
                !HasValues(payload, "invalid_regions") ||
                !HasValues(payload, "state_transitions") ||
                !HasValues(payload, "validation_refs") ||
                !string.Equals(
                    ReadString(payload, "region_map"),
                    BuildRegionMap(
                        expectedOwners,
                        ReadStrings(payload, "valid_regions"),
                        ReadStrings(payload, "invalid_regions"),
                        ReadStrings(payload, "state_transitions")),
                    StringComparison.Ordinal))
            {
                return Blocked("Interaction-region candidate failed deterministic contract validation.");
            }

            payload["validation_status"] = "contract_validated";
            payload["validation_method"] = ValidationMethod;
            payload["validated_utc"] = DateTimeOffset.UtcNow.ToString("O");
            return new IterationPlanInteractionArtifactValidationResult(true, "Interaction-region candidate passed deterministic validation.", payload);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or InvalidOperationException or ArgumentException)
        {
            return Blocked("Interaction-region candidate could not be validated.");
        }
    }

    public static bool IsValidatedArtifact(
        JsonElement artifact,
        int goalIndex,
        IReadOnlyList<string> requirementIds,
        string sourceHashRef,
        IReadOnlyList<string> expectedOwners,
        IReadOnlyList<string> expectedDevices,
        IReadOnlyList<string> expectedValidRegions,
        IReadOnlyList<string> expectedInvalidRegions,
        IReadOnlyList<string> expectedStateTransitions,
        IReadOnlyList<string> expectedValidationRefs,
        IReadOnlyList<PrototypeIterationInteractionGeometryResult> expectedGeometry,
        string expectedCoordinateSemantics)
    {
        var owners = ReadStrings(artifact, "scene_node_owners");
        return string.Equals(ReadString(artifact, "schema_version"), "godot-interaction-region.v1", StringComparison.Ordinal) &&
               string.Equals(ReadString(artifact, "artifact_form"), "planned-godot-node-map", StringComparison.Ordinal) &&
               string.Equals(ReadString(artifact, "evidence_kind"), "pre-execution-design-contract", StringComparison.Ordinal) &&
               ReadBool(artifact, "runtime_validation_required") &&
               string.Equals(ReadString(artifact, "coordinate_semantics"), expectedCoordinateSemantics, StringComparison.Ordinal) &&
               ReadInt(artifact, "goal_index") == goalIndex &&
               string.Equals(ReadString(artifact, "source_hash_ref"), sourceHashRef, StringComparison.Ordinal) &&
               SameValues(ReadStrings(artifact, "requirement_ids"), requirementIds) &&
               SameValues(owners, expectedOwners) &&
               HasValidOwnerContract(owners) &&
               HasValidGeometry(artifact, expectedGeometry, expectedOwners, expectedCoordinateSemantics) &&
               SameValues(ReadStrings(artifact, "devices"), expectedDevices) &&
               SameValues(ReadStrings(artifact, "valid_regions"), expectedValidRegions) &&
               SameValues(ReadStrings(artifact, "invalid_regions"), expectedInvalidRegions) &&
               SameValues(ReadStrings(artifact, "state_transitions"), expectedStateTransitions) &&
               SameValues(ReadStrings(artifact, "validation_refs"), expectedValidationRefs) &&
               string.Equals(
                   ReadString(artifact, "region_map"),
                   BuildRegionMap(expectedOwners, expectedValidRegions, expectedInvalidRegions, expectedStateTransitions),
                   StringComparison.Ordinal) &&
               string.Equals(ReadString(artifact, "validation_status"), "contract_validated", StringComparison.Ordinal) &&
               string.Equals(ReadString(artifact, "validation_method"), ValidationMethod, StringComparison.Ordinal) &&
               !string.IsNullOrWhiteSpace(ReadString(artifact, "validated_utc"));
    }

    private static bool HasValidOwnerContract(IReadOnlyList<string> owners)
    {
        var hasUiOwners = owners.Any(value => value.StartsWith("scene:", StringComparison.Ordinal) && value.Length > 6) &&
                          owners.Any(value => value.StartsWith("node:", StringComparison.Ordinal) && value.Length > 5);
        var hasCameraOwners = owners.Any(value => value.StartsWith("rig:", StringComparison.Ordinal) && value.Length > 4) &&
                              owners.Any(value => value.StartsWith("target:", StringComparison.Ordinal) && value.Length > 7);
        var hasModuleOwner = owners.Any(value =>
            value.StartsWith("module:", StringComparison.Ordinal) &&
            value.EndsWith(":interaction-owner", StringComparison.Ordinal) &&
            value.Length > "module::interaction-owner".Length);
        return hasUiOwners || hasCameraOwners || hasModuleOwner;
    }

    private static bool HasValidGeometry(
        JsonObject payload,
        IReadOnlyList<PrototypeIterationInteractionGeometryResult> expectedGeometry,
        IReadOnlyList<string> expectedOwners,
        string expectedCoordinateSemantics)
    {
        return payload["planned_geometry"] is JsonArray geometry &&
               HasValidGeometry(geometry.Select(item => item?.AsObject()).Where(item => item is not null).Cast<JsonObject>().ToArray(), expectedGeometry, expectedOwners, expectedCoordinateSemantics);
    }

    private static bool HasValidGeometry(
        JsonElement payload,
        IReadOnlyList<PrototypeIterationInteractionGeometryResult> expectedGeometry,
        IReadOnlyList<string> expectedOwners,
        string expectedCoordinateSemantics)
    {
        if (!payload.TryGetProperty("planned_geometry", out var geometry) || geometry.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        return HasValidGeometry(geometry.EnumerateArray().ToArray(), expectedGeometry, expectedOwners, expectedCoordinateSemantics);
    }

    private static bool HasValidGeometry(
        IReadOnlyList<JsonObject> actual,
        IReadOnlyList<PrototypeIterationInteractionGeometryResult> expected,
        IReadOnlyList<string> expectedOwners,
        string expectedCoordinateSemantics)
    {
        if (actual.Count == 0 || actual.Count != expected.Count)
        {
            return false;
        }

        return expected.All(item => actual.Any(candidate => GeometryMatches(candidate, item, expectedOwners, expectedCoordinateSemantics)));
    }

    private static bool HasValidGeometry(
        IReadOnlyList<JsonElement> actual,
        IReadOnlyList<PrototypeIterationInteractionGeometryResult> expected,
        IReadOnlyList<string> expectedOwners,
        string expectedCoordinateSemantics)
    {
        if (actual.Count == 0 || actual.Count != expected.Count)
        {
            return false;
        }

        return expected.All(item => actual.Any(candidate => GeometryMatches(candidate, item, expectedOwners, expectedCoordinateSemantics)));
    }

    private static bool GeometryMatches(
        JsonObject actual,
        PrototypeIterationInteractionGeometryResult expected,
        IReadOnlyList<string> expectedOwners,
        string expectedCoordinateSemantics)
    {
        var bounds = actual["bounds"] as JsonObject;
        return string.Equals(ReadString(actual, "geometry_id"), expected.GeometryId, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "owner_ref"), expected.OwnerRef, StringComparison.Ordinal) &&
               expectedOwners.Contains(expected.OwnerRef, StringComparer.Ordinal) &&
               string.Equals(ReadString(actual, "geometry_kind"), expected.GeometryKind, StringComparison.Ordinal) &&
               expected.GeometryKind is "control_rect" or "collision_shape" &&
               string.Equals(ReadString(actual, "coordinate_space"), expectedCoordinateSemantics, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "coordinate_space"), expected.CoordinateSpace, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "shape"), expected.Shape, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "interaction_role"), expected.InteractionRole, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "locator_ref"), expected.LocatorRef, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "resolution_source"), expected.ResolutionSource, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "bounds_policy"), expected.BoundsPolicy, StringComparison.Ordinal) &&
               GeometryBoundsMatch(bounds, actual["bounds"] is null, expected);
    }

    private static bool GeometryMatches(
        JsonElement actual,
        PrototypeIterationInteractionGeometryResult expected,
        IReadOnlyList<string> expectedOwners,
        string expectedCoordinateSemantics)
    {
        var bounds = default(JsonElement);
        var hasBounds = actual.ValueKind == JsonValueKind.Object && actual.TryGetProperty("bounds", out bounds);
        return actual.ValueKind == JsonValueKind.Object &&
               string.Equals(ReadString(actual, "geometry_id"), expected.GeometryId, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "owner_ref"), expected.OwnerRef, StringComparison.Ordinal) &&
               expectedOwners.Contains(expected.OwnerRef, StringComparer.Ordinal) &&
               string.Equals(ReadString(actual, "geometry_kind"), expected.GeometryKind, StringComparison.Ordinal) &&
               expected.GeometryKind is "control_rect" or "collision_shape" &&
               string.Equals(ReadString(actual, "coordinate_space"), expectedCoordinateSemantics, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "coordinate_space"), expected.CoordinateSpace, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "shape"), expected.Shape, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "interaction_role"), expected.InteractionRole, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "locator_ref"), expected.LocatorRef, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "resolution_source"), expected.ResolutionSource, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "bounds_policy"), expected.BoundsPolicy, StringComparison.Ordinal) &&
               GeometryBoundsMatch(hasBounds ? bounds : default, !hasBounds || bounds.ValueKind == JsonValueKind.Null, expected);
    }

    private static bool GeometryBoundsMatch(
        JsonObject? actualBounds,
        bool boundsAreNull,
        PrototypeIterationInteractionGeometryResult expected)
    {
        return expected.Bounds is null
            ? boundsAreNull && expected.BoundsPolicy == "runtime_resolved" && !string.IsNullOrWhiteSpace(expected.LocatorRef) && !string.IsNullOrWhiteSpace(expected.ResolutionSource)
            : actualBounds is not null && BoundsMatch(actualBounds, expected.Bounds);
    }

    private static bool GeometryBoundsMatch(
        JsonElement actualBounds,
        bool boundsAreNull,
        PrototypeIterationInteractionGeometryResult expected)
    {
        return expected.Bounds is null
            ? boundsAreNull && expected.BoundsPolicy == "runtime_resolved" && !string.IsNullOrWhiteSpace(expected.LocatorRef) && !string.IsNullOrWhiteSpace(expected.ResolutionSource)
            : actualBounds.ValueKind == JsonValueKind.Object && BoundsMatch(actualBounds, expected.Bounds);
    }

    private static bool BoundsMatch(JsonObject actual, PrototypeIterationInteractionBounds expected)
    {
        return NearlyEqual(ReadDouble(actual, "x"), expected.X) &&
               NearlyEqual(ReadDouble(actual, "y"), expected.Y) &&
               NearlyEqual(ReadDouble(actual, "width"), expected.Width) &&
               NearlyEqual(ReadDouble(actual, "height"), expected.Height) &&
               expected.Width > 0 && expected.Height > 0;
    }

    private static bool BoundsMatch(JsonElement actual, PrototypeIterationInteractionBounds expected)
    {
        return NearlyEqual(ReadDouble(actual, "x"), expected.X) &&
               NearlyEqual(ReadDouble(actual, "y"), expected.Y) &&
               NearlyEqual(ReadDouble(actual, "width"), expected.Width) &&
               NearlyEqual(ReadDouble(actual, "height"), expected.Height) &&
               expected.Width > 0 && expected.Height > 0;
    }

    private static bool NearlyEqual(double left, double right) => Math.Abs(left - right) < 0.000001;

    public static string BuildRegionMap(
        IReadOnlyList<string> owners,
        IReadOnlyList<string> validRegions,
        IReadOnlyList<string> invalidRegions,
        IReadOnlyList<string> stateTransitions)
    {
        return string.Join("\n", new[]
        {
            $"OWNERS: {string.Join(" | ", owners.OrderBy(value => value, StringComparer.Ordinal))}",
            $"VALID: {string.Join(" | ", validRegions.OrderBy(value => value, StringComparer.Ordinal))}",
            $"INVALID: {string.Join(" | ", invalidRegions.OrderBy(value => value, StringComparer.Ordinal))}",
            $"TRANSITIONS: {string.Join(" | ", stateTransitions.OrderBy(value => value, StringComparer.Ordinal))}"
        });
    }

    private static bool SameValues(IReadOnlyList<string> left, IReadOnlyList<string> right)
    {
        return left.OrderBy(value => value, StringComparer.Ordinal)
            .SequenceEqual(right.OrderBy(value => value, StringComparer.Ordinal), StringComparer.Ordinal);
    }

    private static bool HasValues(JsonObject payload, string propertyName) => ReadStrings(payload, propertyName).Count > 0;

    private static bool HasValues(JsonElement payload, string propertyName) => ReadStrings(payload, propertyName).Count > 0;

    private static IReadOnlyList<string> ReadStrings(JsonObject payload, string propertyName)
    {
        return payload[propertyName] is JsonArray array
            ? array.Select(node => node?.GetValue<string>() ?? "").Where(value => value.Length > 0).ToArray()
            : [];
    }

    private static IReadOnlyList<string> ReadStrings(JsonElement payload, string propertyName)
    {
        return payload.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Array
            ? value.EnumerateArray().Where(item => item.ValueKind == JsonValueKind.String).Select(item => item.GetString() ?? "").Where(item => item.Length > 0).ToArray()
            : [];
    }

    private static string ReadString(JsonObject payload, string propertyName) => payload[propertyName]?.GetValue<string>() ?? "";

    private static string ReadString(JsonElement payload, string propertyName) =>
        payload.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() ?? "" : "";

    private static int ReadInt(JsonObject payload, string propertyName) => payload[propertyName]?.GetValue<int>() ?? 0;

    private static double ReadDouble(JsonObject payload, string propertyName) => payload[propertyName]?.GetValue<double>() ?? double.NaN;

    private static int ReadInt(JsonElement payload, string propertyName) =>
        payload.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var result) ? result : 0;

    private static double ReadDouble(JsonElement payload, string propertyName) =>
        payload.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Number && value.TryGetDouble(out var result) ? result : double.NaN;

    private static bool ReadBool(JsonElement payload, string propertyName) =>
        payload.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.True;

    private static IterationPlanInteractionArtifactValidationResult Blocked(string summary) => new(false, summary, null);
}
