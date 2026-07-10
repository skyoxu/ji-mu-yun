namespace PhaseA.Platform.Workflow;

public static class RouteFreshnessPolicy
{
    public static readonly IReadOnlyList<RouteFreshnessEdge> Edges =
    [
        new("docs/gdd/GDD.md", "meta/routes/gdd-document/latest.json", "generated_gdd_hash"),
        new("docs/gdd/GDD.md", "meta/routes/gdd-requirements/latest.json", "source_gdd_hash"),
        new("meta/routes/gdd-document/latest.json", "meta/routes/gdd-requirements/latest.json", "source_generated_gdd_hash"),
        new("metadata:projects.game_type_match_json", "meta/routes/gdd-requirements/latest.json", "source_game_type_structured_hash"),
        new("metadata:projects.game_type_match_json", "meta/routes/scene-route/latest.json", "source_game_type_structured_hash"),
        new("meta/routes/scene-route/latest.json", "meta/routes/gdd-requirements/latest.json", "source_scene_route_hash"),
        new("docs/gdd/GDD.md", "routes/prototype-contract/latest.json", "source_gdd_hash"),
        new("meta/routes/scene-route/latest.json", "routes/prototype-contract/latest.json", "source_scene_route_hash"),
        new("meta/routes/gdd-requirements/latest.json", "routes/prototype-contract/latest.json", "source_requirement_map_hash"),
        new("routes/prototype-contract/latest.json", "meta/routes/prototype-skeleton/latest.json", "source_contract_hash"),
        new("meta/routes/scene-route/latest.json", "meta/routes/prototype-skeleton/latest.json", "source_scene_route_hash"),
        new("meta/routes/gdd-requirements/latest.json", "meta/routes/prototype-skeleton/latest.json", "source_requirement_map_hash"),
        new("routes/prototype-contract/latest.json", "meta/routes/iteration-plan/latest.json", "source_contract_hash"),
        new("meta/routes/gdd-requirements/latest.json", "meta/routes/iteration-plan/latest.json", "source_requirement_map_hash"),
        new("meta/routes/scene-route/latest.json", "meta/routes/iteration-plan/latest.json", "source_scene_route_hash"),
        new("meta/routes/iteration-plan/latest.json", "meta/routes/execute-next-goal/latest.json", "source_iteration_session_hash"),
        new("routes/prototype-contract/latest.json", "meta/routes/execute-next-goal/latest.json", "source_contract_hash"),
        new("meta/routes/gdd-requirements/latest.json", "meta/routes/execute-next-goal/latest.json", "source_requirement_map_hash"),
        new("routes/prototype-contract/latest.json", "meta/routes/ui-wiring/latest.json", "source_contract_hash"),
        new("meta/routes/gdd-requirements/latest.json", "meta/routes/ui-wiring/latest.json", "source_requirement_map_hash"),
        new("meta/routes/iteration-plan/latest.json", "meta/routes/ui-wiring/latest.json", "source_iteration_session_hash"),
        new("meta/routes/validation/latest.json", "meta/routes/ui-wiring/latest.json", "source_validation_input_hash"),
        new("meta/routes/godot-ui-contract/latest.json", "meta/routes/ui-wiring/latest.json", "source_godot_ui_contract_hash"),
        new("meta/routes/ui-style-contract/latest.json", "meta/routes/ui-wiring/latest.json", "source_ui_style_contract_hash"),
        new("meta/routes/ui-style-snapshot/latest.json", "meta/routes/ui-wiring/latest.json", "ui_style_snapshot_hash"),
        new("metadata:project_admin_review_queue", "meta/routes/workflow-recommendation/latest.json", "admin_review_queue_updated_utc"),
        new("metadata:project_diagnostic_spool", "meta/routes/workflow-recommendation/latest.json", "diagnostic_spool_updated_utc")
    ];

    public static IReadOnlyList<RouteFreshnessEdge> ForTarget(string targetArtifact)
    {
        return Edges.Where(edge => string.Equals(edge.TargetArtifact, targetArtifact, StringComparison.Ordinal)).ToArray();
    }

    public static bool IsKnownEdge(string sourceArtifact, string targetArtifact, string hashField)
    {
        return Edges.Any(edge =>
            string.Equals(edge.SourceArtifact, sourceArtifact, StringComparison.Ordinal) &&
            string.Equals(edge.TargetArtifact, targetArtifact, StringComparison.Ordinal) &&
            string.Equals(edge.HashField, hashField, StringComparison.Ordinal));
    }
}

public sealed record RouteFreshnessEdge(
    string SourceArtifact,
    string TargetArtifact,
    string HashField);
