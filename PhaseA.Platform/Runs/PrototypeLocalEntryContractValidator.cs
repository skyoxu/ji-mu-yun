using System.Text.Json;

namespace PhaseA.Platform.Runs;

internal static class PrototypeLocalEntryContractValidator
{
    public static PrototypeLocalEntryValidationResult Validate(string projectRepoPath, string? prototypeStateJson)
    {
        if (string.IsNullOrWhiteSpace(prototypeStateJson))
        {
            return PrototypeLocalEntryValidationResult.Failed("local_entry_route_state_missing", "Prototype route state is missing.");
        }

        try
        {
            using var document = JsonDocument.Parse(prototypeStateJson);
            var root = document.RootElement;
            var defaultScene = ReadString(root, "default_scene");
            var smokeScene = ReadString(root, "smoke_scene");
            var playableScene = ReadString(root, "playable_scene");
            var missing = new List<string>();

            if (string.IsNullOrWhiteSpace(defaultScene))
            {
                missing.Add("default_scene");
            }

            if (string.IsNullOrWhiteSpace(smokeScene))
            {
                missing.Add("smoke_scene");
            }

            if (string.IsNullOrWhiteSpace(playableScene))
            {
                missing.Add("playable_scene");
            }

            if (!root.TryGetProperty("local_entry_contract", out var localEntryContract) ||
                localEntryContract.ValueKind != JsonValueKind.Object)
            {
                missing.Add("local_entry_contract");
            }

            if (missing.Count > 0)
            {
                return PrototypeLocalEntryValidationResult.Failed(
                    "local_entry_contract_missing_fields",
                    $"Prototype local entry contract is missing required fields: {string.Join(", ", missing)}.");
            }

            var contractStatus = ReadString(localEntryContract, "status");
            if (string.IsNullOrWhiteSpace(contractStatus))
            {
                return PrototypeLocalEntryValidationResult.Failed(
                    "local_entry_contract_missing_fields",
                    "Prototype local entry contract is missing required fields: local_entry_contract.status.");
            }

            if (!string.Equals(contractStatus, "ready", StringComparison.OrdinalIgnoreCase))
            {
                return PrototypeLocalEntryValidationResult.Failed(
                    "local_entry_contract_not_ready",
                    $"Prototype local entry contract is not ready: status={contractStatus}.");
            }

            var defaultSceneResult = ResolveRequiredScene(projectRepoPath, defaultScene, "default_scene");
            if (!defaultSceneResult.Passed)
            {
                return defaultSceneResult;
            }

            var smokeSceneResult = ResolveRequiredScene(projectRepoPath, smokeScene, "smoke_scene");
            if (!smokeSceneResult.Passed)
            {
                return smokeSceneResult;
            }

            var playableSceneResult = ResolveRequiredScene(projectRepoPath, playableScene, "playable_scene");
            if (!playableSceneResult.Passed)
            {
                return playableSceneResult;
            }

            defaultScene = defaultSceneResult.DefaultScene!;
            smokeScene = smokeSceneResult.DefaultScene!;
            playableScene = playableSceneResult.DefaultScene!;

            var expectedEntryScene = ReadExpectedEntryScene(projectRepoPath);
            if (!string.IsNullOrWhiteSpace(expectedEntryScene) &&
                !string.Equals(defaultScene, expectedEntryScene, StringComparison.OrdinalIgnoreCase))
            {
                return PrototypeLocalEntryValidationResult.Failed(
                    "local_entry_project_specific_scene_mismatch",
                    $"Prototype default scene must match the project-specific entry scene from prototype contract: expected={expectedEntryScene}; actual={defaultScene}.",
                    defaultScene,
                    smokeScene,
                    playableScene);
            }

            if (!string.Equals(defaultScene, playableScene, StringComparison.OrdinalIgnoreCase))
            {
                var contractDeclaresInstance = localEntryContract.TryGetProperty("entry_scene_instances_playable_scene", out var instanceFlag) &&
                                               instanceFlag.ValueKind == JsonValueKind.True;
                if (!contractDeclaresInstance)
                {
                    return PrototypeLocalEntryValidationResult.Failed(
                        "local_entry_contract_instance_flag_missing",
                        "Prototype local entry contract must declare entry_scene_instances_playable_scene=true when default_scene differs from playable_scene.",
                        defaultScene,
                        smokeScene,
                        playableScene);
                }

                if (!PrototypeSceneReferenceInspector.EntrySceneInstancesScene(projectRepoPath, defaultScene, playableScene))
                {
                    return PrototypeLocalEntryValidationResult.Failed(
                        "local_entry_playable_scene_not_instanced",
                        $"Prototype entry scene does not instance playable scene: default_scene={defaultScene}; playable_scene={playableScene}.",
                        defaultScene,
                        smokeScene,
                        playableScene);
                }
            }

            return PrototypeLocalEntryValidationResult.Pass(defaultScene, smokeScene, playableScene);
        }
        catch (JsonException)
        {
            return PrototypeLocalEntryValidationResult.Failed("local_entry_route_state_invalid_json", "Prototype route state is not valid JSON.");
        }
    }

    private static PrototypeLocalEntryValidationResult ResolveRequiredScene(string projectRepoPath, string scene, string fieldName)
    {
        var resolved = PrototypeGodotSmokeService.ResolveSceneReference(projectRepoPath, scene);
        return string.IsNullOrWhiteSpace(resolved)
            ? PrototypeLocalEntryValidationResult.Failed(
                "local_entry_scene_invalid",
                $"Prototype local entry contract has an invalid {fieldName}: {scene}.")
            : PrototypeLocalEntryValidationResult.Pass(resolved, null, null);
    }

    private static string ReadExpectedEntryScene(string projectRepoPath)
    {
        foreach (var relativePath in new[]
                 {
                     Path.Combine("meta", "routes", "prototype-contract", "latest.json"),
                     Path.Combine("routes", "prototype-contract", "latest.json")
                 })
        {
            var path = Path.Combine(projectRepoPath, relativePath);
            if (!File.Exists(path))
            {
                continue;
            }

            try
            {
                using var document = JsonDocument.Parse(File.ReadAllText(path, System.Text.Encoding.UTF8));
                var root = document.RootElement;
                if (!root.TryGetProperty("local_entry_contract", out var contract) ||
                    contract.ValueKind != JsonValueKind.Object)
                {
                    continue;
                }

                var expected = ReadString(contract, "expected_entry_scene");
                if (!string.IsNullOrWhiteSpace(expected))
                {
                    return expected;
                }
            }
            catch (JsonException)
            {
                continue;
            }
            catch (IOException)
            {
                continue;
            }
        }

        return "";
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? ""
            : "";
    }
}

internal sealed record PrototypeLocalEntryValidationResult(
    bool Passed,
    string Status,
    string Summary,
    string? DefaultScene = null,
    string? SmokeScene = null,
    string? PlayableScene = null)
{
    public static PrototypeLocalEntryValidationResult Pass(string defaultScene, string? smokeScene, string? playableScene)
    {
        return new PrototypeLocalEntryValidationResult(
            true,
            "passed",
            "Prototype local entry contract passed.",
            defaultScene,
            smokeScene ?? defaultScene,
            playableScene ?? defaultScene);
    }

    public static PrototypeLocalEntryValidationResult Failed(
        string status,
        string summary,
        string? defaultScene = null,
        string? smokeScene = null,
        string? playableScene = null)
    {
        return new PrototypeLocalEntryValidationResult(false, status, summary, defaultScene, smokeScene, playableScene);
    }
}
