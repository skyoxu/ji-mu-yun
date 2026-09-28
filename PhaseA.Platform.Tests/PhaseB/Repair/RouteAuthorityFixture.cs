using Microsoft.Data.Sqlite;
using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

internal static class RouteAuthorityFixture
{
    private static string Route(string route, string schema) => JsonSerializer.Serialize(new {
        route, schema_version = schema, status_dimension = "route_readback", status = "ready",
        status_allowed_values = new[] { "ready", "blocked", "stale", "unknown" }
    });

    private static string Contract(string repoRoot, string projectId)
    {
        const string gdd = "Fixture GDD";
        const string requirements = "{\"requirements\":[{\"id\":\"R1\"}]}";
        var scene = JsonSerializer.SerializeToElement(new { scene_count_intent = "single", entry_scene = "res://main.tscn",
            scenes = new[] { new { path = "res://main.tscn" } }, transitions = Array.Empty<object>(), single_scene_confirmation = new { confirmed = true } });
        foreach (var (relative, content) in new[] { ("docs/gdd/GDD.md", gdd),
            ("meta/routes/scene-route/latest.json", scene.GetRawText()), ("meta/routes/gdd-requirements/latest.json", requirements) })
        {
            var path = Path.Combine(repoRoot, relative); Directory.CreateDirectory(Path.GetDirectoryName(path)!); File.WriteAllText(path, content);
        }
        var value = new Dictionary<string, object?> {
            ["schema_version"] = "prototype-contract.v2", ["route"] = "prototype-contract", ["project_id"] = projectId,
            ["source_gdd_hash"] = GddToModuleAuthorityHashes.Sha256(gdd),
            ["source_scene_route_hash"] = GddToModuleAuthorityHashes.ComputeSceneRouteHash(scene),
            ["source_requirement_map_hash"] = GddToModuleAuthorityHashes.Sha256(requirements),
            ["source_contract_snapshot_hash"] = GddToModuleAuthorityHashes.ComputeContractSnapshotHash("{\"game_type\":\"manual\"}"),
            ["godot_ui_contract_version"] = "fixture", ["source_godot_ui_contract_hash"] = "fixture", ["ui_style_id"] = "fixture",
            ["ui_style_version"] = "fixture", ["source_ui_style_contract_hash"] = "fixture", ["ui_style_snapshot_hash"] = "fixture",
            ["ui_style_applicability"] = new { status = "not_applicable" }, ["requirement_traceability"] = Array.Empty<object>(),
            ["status_dimension"] = "route_readback", ["status_allowed_values"] = new[] { "ready", "blocked", "stale", "unknown" },
            ["status"] = "ready", ["freshness"] = new { status = "fresh" }
        };
        value["contract_hash"] = PrototypeContractFreezeService.ComputeRecordedContractHash(JsonSerializer.SerializeToElement(value));
        return JsonSerializer.Serialize(value);
    }

    public static void Seed(string connectionString, string accountId, string projectId, string projectRoot)
    {
        // ADR-0061: restore fixtures must provide real current route sources.
        var repoRoot = Path.Combine(projectRoot, "repo");
        Directory.CreateDirectory(Path.Combine(repoRoot, "meta", "routes", "prototype"));
        Directory.CreateDirectory(Path.Combine(repoRoot, "routes", "prototype-contract"));
        File.WriteAllText(Path.Combine(repoRoot, "meta", "project-execution-guide.md"), "Test execution guide");
        File.WriteAllText(Path.Combine(repoRoot, "routes", "prototype-contract", "latest.json"), Contract(repoRoot, projectId));
        File.WriteAllText(Path.Combine(repoRoot, "meta", "routes", "prototype", "latest.json"), Route("prototype", "prototype.v1"));
        var metadataRoot = Path.Combine(projectRoot, "meta");
        Directory.CreateDirectory(Path.Combine(metadataRoot, "routes", "prototype"));
        File.WriteAllText(Path.Combine(metadataRoot, "routes", "prototype", "latest.json"), Route("prototype", "prototype.v1"));
        var prompt = "Current fixture route prompt";
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(prompt))).ToLowerInvariant();
        File.WriteAllText(Path.Combine(repoRoot, "meta", "prompt.json"), prompt);
        File.WriteAllText(Path.Combine(repoRoot, "meta", "prompt-evidence.json"), JsonSerializer.Serialize(new { execution_prompt_hash = hash, persisted_prompt_hash = hash }));

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
                VALUES($project,'restore-route',$hash,$hash,
                       'meta/prompt.json','meta/prompt-evidence.json',$utc)
                """;
            binding.Parameters.AddWithValue("$project", projectId);
            binding.Parameters.AddWithValue("$hash", hash);
            binding.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O"));
            binding.ExecuteNonQuery();
        }
        var result = new RouteRecoveryAuthorityResolver(connectionString).Resolve(accountId, projectId);
        if (!result.CanContinue)
            throw new InvalidOperationException("Current route fixture is incomplete: " + string.Join(",", result.Blockers));
    }
}
