namespace PhaseA.Platform.Workflow;

public static class RouteStatusVocabulary
{
    public const string StageTimeline = "stage_timeline";
    public const string RouteReadback = "route_readback";
    public const string RequirementCoverage = "requirement_coverage";
    public const string SceneRouteConfirmation = "scene_route_confirmation";
    public const string AdminReviewQueue = "admin_review_queue";
    public const string UiSurfaceMatrix = "ui_surface_matrix";
    public const string ReadinessLabel = "readiness_label";
    public const string PrototypeSkeletonSource = "prototype_skeleton_source";
    public const string DiagnosticTriage = "diagnostic_triage";
    public const string StyleCapabilityCoverage = "style_capability_coverage";
    public const string FullTargetClosure = "full_target_closure";
    public const string OperationStatus = "operation_status";

    private static readonly Dictionary<string, IReadOnlySet<string>> Dimensions = new(StringComparer.Ordinal)
    {
        [StageTimeline] = Set("not_started", "ready", "running", "needs_review", "blocked", "completed", "stale"),
        [RouteReadback] = Set("queued", "running", "ready", "needs_review", "blocked", "needs_fix", "succeeded", "failed", "cancelled", "stale", "unknown"),
        [RequirementCoverage] = Set("mapped", "missing_scene", "missing_module", "needs_review", "explicitly_deferred", "conflict"),
        [SceneRouteConfirmation] = Set("draft", "needs_review", "confirmed", "stale", "blocked"),
        [AdminReviewQueue] = Set("open", "approved", "deferred", "rejected", "backlog", "superseded", "resolved"),
        [UiSurfaceMatrix] = Set("covered", "missing_ui", "missing_feedback", "needs_fix", "no_ui_needed"),
        [ReadinessLabel] = Set("not_ready", "ready", "blocked", "stale", "unknown"),
        [PrototypeSkeletonSource] = Set("fresh", "stale", "missing", "unknown", "legacy_compatibility_only"),
        [DiagnosticTriage] = Set("unresolved", "resolved", "ignored", "backlog"),
        [StyleCapabilityCoverage] = Set("required", "style_optional", "conditional", "admin_tooling_or_security_gated", "not_applicable", "deferred", "not_consumed_by_first_slice"),
        [FullTargetClosure] = Set("covered", "reviewed_not_applicable", "explicitly_deferred"),
        [OperationStatus] = Set("returned_existing", "active_run_reused", "created_run", "rejected")
    };

    public static IReadOnlyDictionary<string, IReadOnlySet<string>> AllDimensions => Dimensions;

    public static IReadOnlySet<string> Values(string dimension)
    {
        return Dimensions.TryGetValue(dimension, out var values) ? values : new HashSet<string>(StringComparer.Ordinal);
    }

    public static bool IsKnownDimension(string dimension)
    {
        return Dimensions.ContainsKey(dimension);
    }

    public static bool Contains(string dimension, string status)
    {
        return Dimensions.TryGetValue(dimension, out var values) && values.Contains(status);
    }

    public static bool IsSubset(string dimension, IEnumerable<string> statuses)
    {
        return Dimensions.TryGetValue(dimension, out var values) &&
               statuses.All(status => values.Contains(status));
    }

    public static string MapRouteReadbackToStageTimeline(string routeStatus, bool validatedArtifact)
    {
        return routeStatus switch
        {
            "queued" => "ready",
            "running" => "running",
            "ready" => validatedArtifact ? "completed" : "ready",
            "succeeded" => validatedArtifact ? "completed" : "ready",
            "needs_fix" => "needs_review",
            "failed" => "blocked",
            "blocked" => "blocked",
            "cancelled" => "blocked",
            "stale" => "stale",
            "unknown" => "not_started",
            _ => "blocked"
        };
    }

    private static IReadOnlySet<string> Set(params string[] values)
    {
        return new HashSet<string>(values, StringComparer.Ordinal);
    }
}
