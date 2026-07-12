using System.Text.Json;

namespace PhaseA.Platform.Runs;

internal static class IterationPlanExecutionPreflight
{
    public static IterationPlanExecutionPreflightResult EvaluateForConfirmation(
        string stateJson,
        string expectedSessionId,
        PrototypeIterationPlanSourceHashes currentHashes,
        PrototypeIterationStyleApplicability? currentStyleApplicability = null)
    {
        if (string.IsNullOrWhiteSpace(stateJson))
        {
            return Blocked("iteration_plan_state_missing", "The current iteration plan route state is missing.");
        }

        try
        {
            using var document = JsonDocument.Parse(stateJson);
            return ValidateEnvelope(document.RootElement, expectedSessionId, currentHashes, currentStyleApplicability);
        }
        catch (Exception ex) when (ex is JsonException or InvalidOperationException)
        {
            return Blocked("iteration_plan_state_invalid", "The current iteration plan route state is invalid JSON.");
        }
    }

    public static IterationPlanExecutionPreflightResult Evaluate(
        string stateJson,
        string expectedSessionId,
        int goalIndex,
        PrototypeIterationPlanSourceHashes currentHashes,
        string projectRoot = "",
        string trustedAnchorJson = "",
        bool requireTrustedAnchor = false,
        PrototypeIterationStyleApplicability? currentStyleApplicability = null)
    {
        if (string.IsNullOrWhiteSpace(stateJson))
        {
            return Blocked("iteration_plan_state_missing", "The current iteration plan route state is missing.");
        }

        try
        {
            using var document = JsonDocument.Parse(stateJson);
            var root = document.RootElement;
            var envelope = ValidateEnvelope(root, expectedSessionId, currentHashes, currentStyleApplicability);
            if (!envelope.Allowed)
            {
                return envelope;
            }

            if (requireTrustedAnchor && string.IsNullOrWhiteSpace(trustedAnchorJson))
            {
                return Blocked("plan_confirmation_anchor_mismatch", "The server-side confirmation anchor is missing.");
            }
            if (!string.IsNullOrWhiteSpace(trustedAnchorJson))
            {
                var anchor = ValidateTrustedAnchor(root, trustedAnchorJson);
                if (!anchor.Allowed)
                {
                    return anchor;
                }
            }

            if (!HasCurrentConfirmation(root, expectedSessionId))
            {
                return Blocked("plan_confirmation_required", "The current hash-bound iteration plan has not been confirmed.");
            }

            if (!root.TryGetProperty("goals", out var goals) || goals.ValueKind != JsonValueKind.Array)
            {
                return Blocked("iteration_plan_goal_missing", "The iteration plan does not contain goal traceability state.");
            }

            var goal = goals.EnumerateArray().FirstOrDefault(item => ReadInt(item, "goal_index") == goalIndex);
            if (goal.ValueKind != JsonValueKind.Object)
            {
                return Blocked("iteration_plan_goal_missing", "The pending goal is missing from the iteration plan route state.");
            }

            if (!string.Equals(ReadString(goal, "source_hash_ref"), ReadString(root, "source_hash_ref"), StringComparison.Ordinal))
            {
                return Blocked("source_stale", "The pending goal is not bound to the current plan source hash.");
            }

            var hasRequirementIds = goal.TryGetProperty("requirement_ids", out var requirementIds) &&
                                    requirementIds.ValueKind == JsonValueKind.Array &&
                                    requirementIds.EnumerateArray().Any(item => item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString()));
            var hasInfrastructureReason = goal.TryGetProperty("infrastructure_reason", out var infrastructureReason) &&
                                          infrastructureReason.ValueKind == JsonValueKind.Object &&
                                          !string.IsNullOrWhiteSpace(ReadString(infrastructureReason, "code"));
            if (!hasRequirementIds && !hasInfrastructureReason)
            {
                return Blocked("coverage_gap", "The pending goal has neither requirement traceability nor a structured infrastructure reason.");
            }

            var requirements = goal.TryGetProperty("capability_requirements", out var capabilityElement) && capabilityElement.ValueKind == JsonValueKind.Object
                ? capabilityElement
                : default;
            if (ReadBool(requirements, "dynamic_ui_required") && !HasStrings(goal, "godot_ui_update_ownership", [
                    "construction_owner",
                    "update_mode",
                    "state_owner",
                    "cleanup_policy",
                    "signal_ownership",
                    "stable_item_identity"
                ]))
            {
                return Blocked("ui_update_ownership_missing", "Dynamic UI ownership evidence is incomplete for the pending goal.");
            }

            if (ReadBool(requirements, "third_person_camera_required") && !HasStrings(goal, "godot_third_person_camera_profile", [
                    "rig_ref",
                    "target_owner",
                    "input_owner",
                    "collision_owner",
                    "yaw_pitch_ownership",
                    "camera_relative_movement_boundary",
                    "camera_state_validation"
                ]))
            {
                return Blocked("third_person_camera_profile_missing", "Third-person camera profile evidence is incomplete for the pending goal.");
            }

            if (ReadBool(requirements, "feature_family_reading_required") && !HasNonEmptyArray(goal, "engine_semantics", "reading_evidence_refs"))
            {
                return Blocked("feature_family_reading_missing", "Feature-family reading evidence is missing for the pending goal.");
            }

            if (ReadBool(requirements, "feature_family_reading_required") && !HasNonEmptyArray(goal, "engine_semantics", "profile_refs"))
            {
                return Blocked("feature_family_reading_missing", "Feature-family profile evidence is missing for the pending goal.");
            }

            if (goal.TryGetProperty("ui_surface", out var uiSurface) && uiSurface.ValueKind == JsonValueKind.Object &&
                !HasCurrentStyleEvidence(root, goal, currentHashes.UiStyleSnapshotHash, currentStyleApplicability))
            {
                return Blocked("ui_style_snapshot_missing", "The UI goal is not bound to the current frozen style snapshot.");
            }

            if (ReadBool(requirements, "interaction_region_required") && !HasInteractionRegion(goal, ReadString(root, "source_hash_ref"), projectRoot))
            {
                return Blocked("interaction_region_missing", "Interaction-region evidence is missing for the pending goal.");
            }

            return new IterationPlanExecutionPreflightResult(true, "", "");
        }
        catch (Exception ex) when (ex is JsonException or InvalidOperationException)
        {
            return Blocked("iteration_plan_state_invalid", "The current iteration plan route state is invalid JSON.");
        }
    }

    private static IterationPlanExecutionPreflightResult ValidateEnvelope(
        JsonElement root,
        string expectedSessionId,
        PrototypeIterationPlanSourceHashes currentHashes,
        PrototypeIterationStyleApplicability? currentStyleApplicability)
    {
        if (root.ValueKind != JsonValueKind.Object)
        {
            return Blocked("iteration_plan_state_invalid", "The current iteration plan route state must be an object.");
        }
        if (!string.Equals(ReadString(root, "session_id"), expectedSessionId, StringComparison.Ordinal))
        {
            return Blocked("iteration_plan_session_stale", "The iteration plan route state does not match the current session.");
        }
        if (!string.Equals(ReadString(root, "status"), "ready", StringComparison.Ordinal))
        {
            return Blocked("plan_blocked", "Only a ready iteration plan can be executed.");
        }
        if (!HashesMatch(root, currentHashes))
        {
            return Blocked("source_stale", "The iteration plan source hashes no longer match the frozen authority sources.");
        }
        if (currentStyleApplicability is not null && !StyleApplicabilityMatches(root, currentStyleApplicability))
        {
            return Blocked("source_stale", "The iteration plan style applicability evidence no longer matches the frozen authority source.");
        }
        var expectedSourceHashRef = currentStyleApplicability is null
            ? ""
            : IterationPlanTraceabilityBuilder.ComputeSourceHashRef(currentHashes, currentStyleApplicability);
        if (!string.IsNullOrWhiteSpace(expectedSourceHashRef) &&
            !string.Equals(ReadString(root, "source_hash_ref"), expectedSourceHashRef, StringComparison.Ordinal))
        {
            return Blocked("source_stale", "The iteration plan source identity no longer matches the frozen authority chain.");
        }
        var storedPlanHash = ReadString(root, "plan_hash");
        var computedPlanHash = IterationPlanIntegrity.Compute(root);
        if (string.IsNullOrWhiteSpace(storedPlanHash) || !string.Equals(storedPlanHash, computedPlanHash, StringComparison.Ordinal))
        {
            return Blocked("plan_hash_mismatch", "The iteration plan payload no longer matches its canonical plan hash.");
        }
        if (!root.TryGetProperty("blockers", out var blockers) || blockers.ValueKind != JsonValueKind.Array || blockers.GetArrayLength() > 0)
        {
            return Blocked("plan_blocked", "The iteration plan has unresolved blockers or invalid blocker state.");
        }
        if (!root.TryGetProperty("coverage", out var coverage) || coverage.ValueKind != JsonValueKind.Object ||
            !coverage.TryGetProperty("uncovered_requirement_ids", out var uncovered) || uncovered.ValueKind != JsonValueKind.Array || uncovered.GetArrayLength() > 0)
        {
            return Blocked("coverage_gap", "The iteration plan does not prove complete P0/P1 requirement coverage.");
        }
        return new IterationPlanExecutionPreflightResult(true, "", "");
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

    private static IterationPlanExecutionPreflightResult ValidateTrustedAnchor(JsonElement root, string trustedAnchorJson)
    {
        try
        {
            using var document = JsonDocument.Parse(trustedAnchorJson);
            var anchor = document.RootElement;
            return anchor.ValueKind == JsonValueKind.Object &&
                   string.Equals(ReadString(anchor, "status"), "confirmed", StringComparison.Ordinal) &&
                   string.Equals(ReadString(anchor, "session_id"), ReadString(root, "session_id"), StringComparison.Ordinal) &&
                   string.Equals(ReadString(anchor, "plan_hash"), ReadString(root, "plan_hash"), StringComparison.Ordinal) &&
                   string.Equals(ReadString(anchor, "source_hash_ref"), ReadString(root, "source_hash_ref"), StringComparison.Ordinal)
                ? new IterationPlanExecutionPreflightResult(true, "", "")
                : Blocked("plan_confirmation_anchor_mismatch", "The workspace plan no longer matches the server-side confirmation anchor.");
        }
        catch (JsonException)
        {
            return Blocked("plan_confirmation_anchor_mismatch", "The server-side confirmation anchor is invalid.");
        }
    }

    private static bool HasStrings(JsonElement parent, string objectName, IReadOnlyList<string> propertyNames)
    {
        if (!parent.TryGetProperty(objectName, out var value) || value.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        return propertyNames.All(name => !string.IsNullOrWhiteSpace(ReadString(value, name)));
    }

    private static bool HasNonEmptyArray(JsonElement parent, string objectName, string propertyName)
    {
        return parent.TryGetProperty(objectName, out var value) &&
               value.ValueKind == JsonValueKind.Object &&
               value.TryGetProperty(propertyName, out var array) &&
               array.ValueKind == JsonValueKind.Array &&
               array.EnumerateArray().Any(item => item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString()));
    }

    private static bool HasInteractionRegion(JsonElement goal, string sourceHashRef, string projectRoot)
    {
        if (goal.TryGetProperty("interaction_region", out var region) &&
            region.ValueKind == JsonValueKind.Object &&
            !string.IsNullOrWhiteSpace(ReadString(region, "artifact_ref")) &&
            region.TryGetProperty("validation_refs", out var validation) &&
            validation.ValueKind == JsonValueKind.Array &&
            validation.EnumerateArray().Any(item => item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString())))
        {
            return string.IsNullOrWhiteSpace(projectRoot) || ValidateInteractionArtifact(goal, region, sourceHashRef, projectRoot);
        }

        return goal.TryGetProperty("no_interaction_region_needed", out var exemption) &&
               exemption.ValueKind == JsonValueKind.Object &&
               !string.IsNullOrWhiteSpace(ReadString(exemption, "reviewed_by")) &&
               !string.IsNullOrWhiteSpace(ReadString(exemption, "reviewed_utc")) &&
               !string.IsNullOrWhiteSpace(ReadString(exemption, "rationale"));
    }

    private static bool HasCurrentStyleEvidence(
        JsonElement root,
        JsonElement goal,
        string snapshotHash,
        PrototypeIterationStyleApplicability? currentStyleApplicability)
    {
        if (string.Equals(currentStyleApplicability?.Status, "reviewed_not_applicable", StringComparison.Ordinal))
        {
            return StyleApplicabilityMatches(root, currentStyleApplicability!);
        }
        if (!goal.TryGetProperty("style", out var style) || style.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        return HasNonEmptyStringArray(style, "style_token_refs") &&
               style.GetProperty("style_token_refs").EnumerateArray().Any(item =>
                   item.ValueKind == JsonValueKind.String &&
                   string.Equals(item.GetString(), $"snapshot:{snapshotHash}", StringComparison.Ordinal)) &&
               HasNonEmptyStringArray(style, "component_families") &&
               HasNonEmptyStringArray(style, "design_dna") &&
               HasNonEmptyStringArray(style, "visual_evidence_expectations");
    }

    private static bool StyleApplicabilityMatches(JsonElement root, PrototypeIterationStyleApplicability expected)
    {
        return root.TryGetProperty("style_applicability", out var actual) &&
               actual.ValueKind == JsonValueKind.Object &&
               string.Equals(ReadString(actual, "status"), expected.Status, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "reason"), expected.Reason, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "reviewed_by"), expected.ReviewedBy, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "recheck_trigger"), expected.RecheckTrigger, StringComparison.Ordinal) &&
               string.Equals(ReadString(actual, "evidence_hash"), expected.EvidenceHash, StringComparison.Ordinal);
    }

    private static bool ValidateInteractionArtifact(JsonElement goal, JsonElement region, string sourceHashRef, string projectRoot)
    {
        try
        {
            var root = Path.GetFullPath(projectRoot);
            var relative = ReadString(region, "artifact_ref").Replace('/', Path.DirectorySeparatorChar);
            var path = Path.GetFullPath(Path.Combine(root, relative));
            if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) || !File.Exists(path))
            {
                return false;
            }

            using var document = JsonDocument.Parse(File.ReadAllText(path));
            var artifact = document.RootElement;
            var goalRequirementIds = ReadStringArray(goal, "requirement_ids");
            return IterationPlanInteractionArtifactValidator.IsValidatedArtifact(
                artifact,
                ReadInt(goal, "goal_index"),
                goalRequirementIds,
                sourceHashRef,
                ReadStringArray(region, "owner_refs"),
                ReadStringArray(region, "devices"),
                ReadStringArray(region, "valid_regions"),
                ReadStringArray(region, "invalid_regions"),
                ReadStringArray(region, "state_transitions"),
                ReadStringArray(region, "validation_refs"),
                ReadInteractionGeometry(region),
                goal.TryGetProperty("engine_semantics", out var semantics) && semantics.ValueKind == JsonValueKind.Object
                    ? ReadString(semantics, "coordinate_semantics")
                    : "project-profile-coordinate-semantics");
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or ArgumentException)
        {
            return false;
        }
    }

    private static bool HasNonEmptyStringArray(JsonElement parent, string propertyName)
    {
        return parent.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.Array &&
               value.EnumerateArray().Any(item => item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString()));
    }

    private static IReadOnlyList<PrototypeIterationInteractionGeometryResult> ReadInteractionGeometry(JsonElement region)
    {
        if (!region.TryGetProperty("planned_geometry", out var geometry) || geometry.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        return geometry.EnumerateArray()
            .Where(item => item.ValueKind == JsonValueKind.Object)
            .Select(item =>
            {
                var hasBounds = item.TryGetProperty("bounds", out var bounds) && bounds.ValueKind == JsonValueKind.Object;
                return new PrototypeIterationInteractionGeometryResult(
                    ReadString(item, "geometry_id"),
                    ReadString(item, "owner_ref"),
                    ReadString(item, "geometry_kind"),
                    ReadString(item, "coordinate_space"),
                    hasBounds
                        ? new PrototypeIterationInteractionBounds(
                            ReadDouble(bounds, "x"),
                            ReadDouble(bounds, "y"),
                            ReadDouble(bounds, "width"),
                            ReadDouble(bounds, "height"))
                        : null,
                    ReadString(item, "shape"),
                    ReadString(item, "interaction_role"),
                    ReadString(item, "locator_ref"),
                    ReadString(item, "resolution_source"),
                    ReadString(item, "bounds_policy"));
            })
            .ToArray();
    }

    private static IReadOnlyList<string> ReadStringArray(JsonElement parent, string propertyName)
    {
        return parent.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Array
            ? value.EnumerateArray().Where(item => item.ValueKind == JsonValueKind.String).Select(item => item.GetString() ?? "").Where(item => item.Length > 0).ToArray()
            : [];
    }

    private static bool HasCurrentConfirmation(JsonElement root, string expectedSessionId)
    {
        return root.TryGetProperty("confirmation", out var confirmation) &&
               confirmation.ValueKind == JsonValueKind.Object &&
               string.Equals(ReadString(confirmation, "status"), "confirmed", StringComparison.Ordinal) &&
               string.Equals(ReadString(confirmation, "session_id"), expectedSessionId, StringComparison.Ordinal) &&
               string.Equals(ReadString(confirmation, "plan_hash"), ReadString(root, "plan_hash"), StringComparison.Ordinal) &&
               !string.IsNullOrWhiteSpace(ReadString(root, "plan_hash")) &&
               string.Equals(ReadString(confirmation, "source_hash_ref"), ReadString(root, "source_hash_ref"), StringComparison.Ordinal) &&
               !string.IsNullOrWhiteSpace(ReadString(root, "source_hash_ref"));
    }

    private static bool ReadBool(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.True;
    }

    private static int ReadInt(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.TryGetInt32(out var parsed) ? parsed : 0;
    }

    private static double ReadDouble(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.TryGetDouble(out var parsed) ? parsed : double.NaN;
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? ""
            : "";
    }

    private static IterationPlanExecutionPreflightResult Blocked(string domainCode, string summary)
    {
        return new IterationPlanExecutionPreflightResult(false, domainCode, summary);
    }
}

internal sealed record IterationPlanExecutionPreflightResult(bool Allowed, string DomainCode, string Summary);
