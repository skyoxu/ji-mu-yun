using System.Text.Json;
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
            SELECT p.game_type_source, p.game_type_match_json, w.repo_path, w.meta_path
            FROM projects p JOIN workspaces w ON w.project_id = p.id
            WHERE p.id=$project AND p.account_id=$account LIMIT 1";
        command.Parameters.AddWithValue("$project", projectId);
        command.Parameters.AddWithValue("$account", accountId);
        using var reader = command.ExecuteReader();
        if (!reader.Read()) return RouteRecoveryAuthoritySnapshot.Blocked("project_source_missing");

        var repoPath = reader.GetString(2);
        var metaPath = reader.GetString(3);
        var sources = new List<string>();
        var blockers = new List<string>();

        var parsedProfile = !string.IsNullOrWhiteSpace(reader.GetString(0)) &&
                            IsJsonObjectWithContent(reader.IsDBNull(1) ? "{}" : reader.GetString(1));
        sources.Add($"{HostedRouteRecoveryContract.ParsedRouteProfileSource}:{parsedProfile}");
        if (!parsedProfile) blockers.Add("parsed_game_type_route_profile_missing");

        var promptBinding = HasPromptBinding(connection, projectId);
        sources.Add($"{HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource}:{promptBinding}");
        if (!promptBinding) blockers.Add("selected_route_skill_prompt_block_missing");

        var executionGuide = Existing(repoPath, "meta/project-execution-guide.md");
        sources.Add($"meta/project-execution-guide.md:{executionGuide}");
        if (!executionGuide) blockers.Add("project_execution_guide_missing");

        var contract = Existing(repoPath, "routes/prototype-contract/latest.json");
        sources.Add($"routes/prototype-contract/latest.json:{contract}");
        if (!contract) blockers.Add("prototype_contract_missing");

        var routeDirectory = Path.Combine(metaPath, "routes");
        var routeState = Directory.Exists(routeDirectory) &&
                         Directory.EnumerateFiles(routeDirectory, "latest.json", SearchOption.AllDirectories).Any();
        sources.Add($"current route latest state:{routeState}");
        if (!routeState) blockers.Add("current_route_state_missing");

        var goalState = HasCurrentGoalState(connection, projectId);
        sources.Add($"current goal/step/session state when applicable:{goalState}");
        var repairEvidence = HasCurrentRepairEvidence(connection, accountId, projectId);
        sources.Add($"repair ledger and failing acceptance/Godot diagnostic evidence when applicable:{repairEvidence}");

        var liveBlocker = HasCurrentBlocker(connection, accountId, projectId);
        sources.Add($"latest live platform acceptance blocker:{!liveBlocker}");
        if (liveBlocker) blockers.Add("latest_live_platform_acceptance_blocker");

        return new RouteRecoveryAuthoritySnapshot(sources.Count, sources, blockers, blockers.Count == 0);
    }

    private static bool Existing(string root, string relative)
    {
        try { return File.Exists(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar))); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException) { return false; }
    }

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

    private static bool HasPromptBinding(SqliteConnection connection, string projectId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM project_route_prompt_evidence_bindings WHERE project_id=$project AND execution_prompt_hash <> '' AND persisted_prompt_hash <> '' AND prompt_artifact_ref <> '' AND prompt_evidence_ref <> ''";
        command.Parameters.AddWithValue("$project", projectId);
        return Convert.ToInt32(command.ExecuteScalar(), System.Globalization.CultureInfo.InvariantCulture) > 0;
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

    private static bool HasCurrentGoalState(SqliteConnection connection, string projectId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM project_iteration_sessions WHERE project_id=$project AND status IN ('active','running','ready','needs_fix')";
        command.Parameters.AddWithValue("$project", projectId);
        return Convert.ToInt32(command.ExecuteScalar(), System.Globalization.CultureInfo.InvariantCulture) > 0;
    }

    private static bool HasCurrentRepairEvidence(SqliteConnection connection, string accountId, string projectId)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM project_diagnostic_spool WHERE account_id=$account AND project_id=$project AND triage_status IN ('unresolved','backlog')";
        command.Parameters.AddWithValue("$account", accountId);
        command.Parameters.AddWithValue("$project", projectId);
        return Convert.ToInt32(command.ExecuteScalar(), System.Globalization.CultureInfo.InvariantCulture) > 0;
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
