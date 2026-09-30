using System.Text.Json;
using PhaseA.Platform.Security;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Workspaces;

/// <summary>
/// Resolves restore authority from the current project sources. Persisted
/// evidence is only a readback of this resolution.
/// </summary>
public sealed class RouteRecoveryAuthorityResolver
{
    private readonly string _connectionString;

    public RouteRecoveryAuthorityResolver(string connectionString) => _connectionString = connectionString;

    public RouteRecoveryAuthoritySnapshot Resolve(string accountId, string projectId)
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = @"
            SELECT p.game_type_source, p.game_type_match_json, w.repo_path, w.meta_path, w.root_path, w.runtime_path, w.id,
                   p.name, p.game_name, p.template_rule_id, p.llm_binding_required,
                   p.allowed_workflows_json, p.bootstrap_status, p.bootstrap_error
            FROM projects p JOIN workspaces w ON w.project_id = p.id
            WHERE p.id=$project AND p.account_id=$account LIMIT 1";
        command.Parameters.AddWithValue("$project", projectId);
        command.Parameters.AddWithValue("$account", accountId);
        using var reader = command.ExecuteReader();
        if (!reader.Read()) return RouteRecoveryAuthoritySnapshot.Blocked("project_source_missing");

        var repoPath = reader.GetString(2);
        var metaPath = reader.GetString(3);
        var project = new ProjectSnapshot(projectId, accountId, reader.GetString(7), reader.GetString(8),
            reader.GetString(0), reader.GetString(9), reader.GetInt64(10) != 0, reader.GetString(11),
            reader.GetString(12), reader.IsDBNull(13) ? null : reader.GetString(13), reader.GetString(6),
            reader.GetString(4), repoPath, reader.GetString(5), metaPath, reader.IsDBNull(1) ? "{}" : reader.GetString(1));
        var sources = new List<string>();
        var blockers = new List<string>();

        var parsedProfile = !string.IsNullOrWhiteSpace(reader.GetString(0)) &&
                            IsJsonObjectWithContent(reader.IsDBNull(1) ? "{}" : reader.GetString(1));
        sources.Add($"{HostedRouteRecoveryContract.ParsedRouteProfileSource}:{parsedProfile}");
        if (!parsedProfile) blockers.Add("parsed_game_type_route_profile_missing");

        var promptBinding = HasPromptBinding(connection, projectId, repoPath);
        sources.Add($"{HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource}:{promptBinding}");
        if (!promptBinding) blockers.Add("selected_route_skill_prompt_block_missing");

        var executionGuide = ReadSource(repoPath, "meta/project-execution-guide.md") is { Length: > 0 };
        sources.Add($"meta/project-execution-guide.md:{executionGuide}");
        if (!executionGuide) blockers.Add("project_execution_guide_missing");

        var contract = ValidContract(project);
        sources.Add($"routes/prototype-contract/latest.json:{contract}");
        if (!contract) blockers.Add("prototype_contract_missing");

        var routeDirectory = Path.Combine(metaPath, "routes");
        var routeState = Directory.Exists(routeDirectory) &&
                         Directory.EnumerateFiles(routeDirectory, "latest.json", SearchOption.AllDirectories)
                             .Any(path => ValidRouteSource(metaPath, Path.GetRelativePath(metaPath, path), null));
        sources.Add($"current route latest state:{routeState}");
        if (!routeState) blockers.Add("current_route_state_missing");

        var goalState = HasCurrentGoalState(connection, accountId, projectId);
        sources.Add($"current goal/step/session state when applicable:{goalState}");
        if (!goalState) blockers.Add("current_goal_state_invalid");
        var repairEvidence = HasCurrentRepairEvidence(connection, accountId, projectId);
        sources.Add($"repair ledger and failing acceptance/Godot diagnostic evidence when applicable:{repairEvidence}");
        if (!repairEvidence) blockers.Add("current_repair_evidence_invalid");

        var liveBlocker = HasCurrentBlocker(connection, accountId, projectId);
        sources.Add($"latest live platform acceptance blocker:{!liveBlocker}");
        if (liveBlocker) blockers.Add("latest_live_platform_acceptance_blocker");

        return new RouteRecoveryAuthoritySnapshot(sources.Count, sources, blockers, blockers.Count == 0);
    }

    // ADR-0036/0061: readable current content, not the presence of a path, is authority.
    private static string? ReadSource(string root, string relative)
    {
        try
        {
            var path = RunnerIsolationPolicy.RequireContainedPath(root, relative);
            return File.ReadAllText(path).Trim();
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException)
        { return null; }
    }

    private static bool ValidRouteSource(string root, string relative, string? expectedRoute)
    {
        try
        {
            using var document = JsonDocument.Parse(ReadSource(root, relative) ?? "null");
            var value = document.RootElement;
            if (value.ValueKind != JsonValueKind.Object) return false;
            var route = Text(value, "route");
            var status = Text(value, "status");
            var dimension = Text(value, "status_dimension");
            if (string.IsNullOrWhiteSpace(route) || (expectedRoute is not null && route != expectedRoute) ||
                string.IsNullOrWhiteSpace(Text(value, "schema_version")) ||
                !RouteStatusVocabulary.IsKnownDimension(dimension) ||
                !RouteStatusVocabulary.Contains(dimension, status) ||
                status is "unknown" or "stale" or "queued" or "running" or "blocked" or "failed") return false;
            if (expectedRoute == "prototype-contract" && Text(value, "schema_version") != "prototype-contract.v2") return false;
            if (value.TryGetProperty("freshness", out var freshness) &&
                ((freshness.ValueKind == JsonValueKind.String && freshness.GetString() != "fresh") ||
                 (freshness.ValueKind == JsonValueKind.Object && Text(freshness, "status") != "fresh"))) return false;
            return value.TryGetProperty("status_allowed_values", out var allowed) &&
                   allowed.ValueKind == JsonValueKind.Array &&
                   allowed.EnumerateArray().Any(item => item.ValueKind == JsonValueKind.String && item.GetString() == status);
        }
        catch (JsonException) { return false; }
    }

    private static bool ValidContract(ProjectSnapshot project)
    {
        try
        {
            const string relative = "routes/prototype-contract/latest.json";
            if (!ValidRouteSource(project.RepoPath, relative, "prototype-contract")) return false;
            using var document = JsonDocument.Parse(ReadSource(project.RepoPath, relative) ?? "null");
            if (Text(document.RootElement, "project_id") != project.ProjectId) return false;
            // Reuse the canonical consumer, including recomputed GDD/scene/map hashes.
            return PrototypeContractFreezeService.IsFrozenContractCurrentForConsumption(project, document.RootElement);
        }
        catch (Exception error) when (error is JsonException or IOException or UnauthorizedAccessException or ArgumentException)
        { return false; }
    }

    private static string Text(JsonElement value, string key) =>
        value.TryGetProperty(key, out var item) && item.ValueKind == JsonValueKind.String ? item.GetString() ?? "" : "";

    private static bool IsJsonObjectWithContent(string json)
    {
        try
        {
            using var document = JsonDocument.Parse(json);
            return document.RootElement.ValueKind == JsonValueKind.Object &&
                   document.RootElement.EnumerateObject().Any();
        }
        catch (JsonException) { return false; }
    }

    private static bool HasPromptBinding(SqliteConnection connection, string projectId, string repoPath)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT execution_prompt_hash,persisted_prompt_hash,prompt_artifact_ref,prompt_evidence_ref FROM project_route_prompt_evidence_bindings WHERE project_id=$project ORDER BY updated_utc DESC LIMIT 1";
        command.Parameters.AddWithValue("$project", projectId);
        using var reader = command.ExecuteReader();
        if (!reader.Read()) return false;
        var prompt = ReadSource(repoPath, reader.GetString(2));
        var evidence = ReadSource(repoPath, reader.GetString(3));
        if (string.IsNullOrWhiteSpace(prompt) || string.IsNullOrWhiteSpace(evidence)) return false;
        // Use the prompt producer's line-ending semantics; do not trim bound content.
        var path = RunnerIsolationPolicy.RequireContainedPath(repoPath, reader.GetString(2));
        try
        {
            var hash = HostedRouteForbiddenSourceGuard.PromptHash(File.ReadAllText(path));
            using var document = JsonDocument.Parse(evidence);
            var value = document.RootElement;
            return value.ValueKind == JsonValueKind.Object && hash == reader.GetString(1) &&
                   Text(value, "execution_prompt_hash") == reader.GetString(0) &&
                   Text(value, "persisted_prompt_hash") == hash;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException) { return false; }
    }

    private static bool HasCurrentBlocker(SqliteConnection connection, string accountId, string projectId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = """
            SELECT COUNT(*)
            FROM project_diagnostic_spool
            WHERE account_id=$account
              AND project_id=$project
              AND triage_status='unresolved'
              AND severity IN ('P0','P1')
              AND failure_family IN ('route_authority_missing','restore_interrupted','stale_lease')
            """;
        command.Parameters.AddWithValue("$account", accountId);
        command.Parameters.AddWithValue("$project", projectId);
        return Convert.ToInt32(command.ExecuteScalar(), System.Globalization.CultureInfo.InvariantCulture) > 0;
    }

    private static bool HasCurrentGoalState(SqliteConnection connection, string accountId, string projectId)
    {
        using var command = connection.CreateCommand();
        // No active session means this source is not applicable. An active session
        // must have the current goal owned by that session; COUNT(session) is not proof.
        command.CommandText = """
            SELECT COUNT(*) FROM project_iteration_sessions s
            WHERE s.project_id=$project AND s.account_id=$account
              AND s.status IN ('active','running','ready','needs_fix')
              AND (TRIM(s.overall_goal)='' OR NOT EXISTS (
                  SELECT 1 FROM project_iteration_goals g
                  WHERE g.session_id=s.id AND g.goal_index=s.current_goal_index
                    AND TRIM(g.description)<>'' AND g.status NOT IN ('unknown','cancelled')))
            """;
        command.Parameters.AddWithValue("$project", projectId);
        command.Parameters.AddWithValue("$account", accountId);
        return Convert.ToInt32(command.ExecuteScalar(), System.Globalization.CultureInfo.InvariantCulture) == 0;
    }

    private static bool HasCurrentRepairEvidence(SqliteConnection connection, string accountId, string projectId)
    {
        using var command = connection.CreateCommand();
        // No repair intent and no outstanding diagnostic is explicitly not applicable.
        // A needs-fix session without any current diagnostic cannot recover safely.
        command.CommandText = """
            SELECT
              (SELECT COUNT(*) FROM project_iteration_sessions s
               WHERE s.project_id=$project AND s.account_id=$account AND s.status='needs_fix'
                 AND NOT EXISTS (SELECT 1 FROM project_diagnostic_spool d
                     WHERE d.project_id=$project AND d.account_id=$account
                       AND d.triage_status IN ('unresolved','backlog') AND TRIM(d.safe_summary)<>''))
              + (SELECT COUNT(*) FROM project_diagnostic_spool
                 WHERE project_id=$project AND account_id=$account
                   AND triage_status IN ('unresolved','backlog')
                   AND (TRIM(safe_summary)='' OR TRIM(failure_family)='' OR TRIM(route_id)=''))
            """;
        command.Parameters.AddWithValue("$account", accountId);
        command.Parameters.AddWithValue("$project", projectId);
        return Convert.ToInt32(command.ExecuteScalar(), System.Globalization.CultureInfo.InvariantCulture) == 0;
    }

}

public sealed record RouteRecoveryAuthoritySnapshot(
    int AuthorityCount,
    IReadOnlyList<string> SourceEvidence,
    IReadOnlyList<string> Blockers,
    bool CanContinue)
{
    public bool HasCurrentBlocker => Blockers.Count > 0;
    public static RouteRecoveryAuthoritySnapshot Blocked(string code) => new(0, [], [code], false);
}
