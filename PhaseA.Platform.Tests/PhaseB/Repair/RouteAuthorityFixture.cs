using Microsoft.Data.Sqlite;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

internal static class RouteAuthorityFixture
{
    public static void Seed(string connectionString, string accountId, string projectId, string projectRoot)
    {
        // ADR-0061: restore fixtures must provide real current route sources.
        var repoRoot = Path.Combine(projectRoot, "repo");
        Directory.CreateDirectory(Path.Combine(repoRoot, "meta", "routes", "prototype"));
        Directory.CreateDirectory(Path.Combine(repoRoot, "routes", "prototype-contract"));
        File.WriteAllText(Path.Combine(repoRoot, "meta", "project-execution-guide.md"), "Test execution guide");
        File.WriteAllText(Path.Combine(repoRoot, "routes", "prototype-contract", "latest.json"), "{}");
        File.WriteAllText(Path.Combine(repoRoot, "meta", "routes", "prototype", "latest.json"), "{}");
        var metadataRoot = Path.Combine(projectRoot, "meta");
        Directory.CreateDirectory(Path.Combine(metadataRoot, "routes", "prototype"));
        File.WriteAllText(Path.Combine(metadataRoot, "routes", "prototype", "latest.json"), "{}");

        using var connection = new SqliteConnection(connectionString);
        connection.Open();
        using (var update = connection.CreateCommand())
        {
            update.CommandText = "UPDATE projects SET game_type_match_json=$profile WHERE id=$project";
            update.Parameters.AddWithValue("$profile", "{\"game_type\":\"manual\"}");
            update.Parameters.AddWithValue("$project", projectId);
            if (update.ExecuteNonQuery() != 1)
                throw new InvalidOperationException("Route fixture project was not found.");
        }

        using (var binding = connection.CreateCommand())
        {
            binding.CommandText = """
                INSERT INTO project_route_prompt_evidence_bindings
                    (project_id,route_id,execution_prompt_hash,persisted_prompt_hash,
                     prompt_artifact_ref,prompt_evidence_ref,updated_utc)
                VALUES($project,'restore-route','test-execution-hash','test-persisted-hash',
                       'meta/prompt.json','meta/prompt-evidence.json',$utc)
                """;
            binding.Parameters.AddWithValue("$project", projectId);
            binding.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O"));
            binding.ExecuteNonQuery();
        }
        var result = new RouteRecoveryAuthorityResolver(connectionString).Resolve(accountId, projectId);
        if (!result.CanContinue)
            throw new InvalidOperationException("Current route fixture is incomplete: " + string.Join(",", result.Blockers));
    }
}
