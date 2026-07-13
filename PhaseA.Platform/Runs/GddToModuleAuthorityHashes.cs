using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Prototypes;

namespace PhaseA.Platform.Runs;

internal static class GddToModuleAuthorityHashes
{
    public static string ComputeStructuredGameTypeHash(string gameTypeMatchJson)
    {
        return Sha256(gameTypeMatchJson);
    }

    public static string ComputeContractSnapshotHash(string gameTypeMatchJson)
    {
        var snapshot = ProjectGameTypeMatchEvidence.FromJson(gameTypeMatchJson).ContractSnapshot;
        return Sha256(JsonSerializer.Serialize(snapshot, JsonOptions()));
    }

    public static string ComputeSceneRouteHash(JsonElement root)
    {
        if (!HasValidSceneRouteShape(root))
        {
            return "";
        }

        var payload = new
        {
            scene_count_intent = ReadString(root, "scene_count_intent"),
            entry_scene = ReadString(root, "entry_scene"),
            scenes = CloneOrEmptyArray(root, "scenes"),
            transitions = CloneOrEmptyArray(root, "transitions"),
            single_scene_confirmation = CloneOrEmptyObject(root, "single_scene_confirmation"),
            notes = ReadStringArray(root, "notes")
        };
        return Sha256(JsonSerializer.Serialize(payload, JsonOptions()));
    }

    private static bool HasValidSceneRouteShape(JsonElement root)
    {
        return root.ValueKind == JsonValueKind.Object &&
               HasPropertyKind(root, "scene_count_intent", JsonValueKind.String) &&
               HasPropertyKind(root, "entry_scene", JsonValueKind.String) &&
               HasPropertyKind(root, "scenes", JsonValueKind.Array) &&
               HasPropertyKind(root, "transitions", JsonValueKind.Array) &&
               HasPropertyKind(root, "single_scene_confirmation", JsonValueKind.Object) &&
               (!root.TryGetProperty("notes", out var notes) ||
                (notes.ValueKind == JsonValueKind.Array && notes.EnumerateArray().All(item => item.ValueKind == JsonValueKind.String)));
    }

    private static bool HasPropertyKind(JsonElement root, string propertyName, JsonValueKind valueKind)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == valueKind;
    }

    public static string Sha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value.Replace("\r\n", "\n").Trim()))).ToLowerInvariant();
    }

    private static JsonElement CloneOrEmptyArray(JsonElement root, string propertyName)
    {
        if (root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Array)
        {
            return value.Clone();
        }
        using var document = JsonDocument.Parse("[]");
        return document.RootElement.Clone();
    }

    private static JsonElement CloneOrEmptyObject(JsonElement root, string propertyName)
    {
        if (root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Object)
        {
            return value.Clone();
        }
        using var document = JsonDocument.Parse("{}");
        return document.RootElement.Clone();
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? ""
            : "";
    }

    private static IReadOnlyList<string> ReadStringArray(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.Array
            ? value.EnumerateArray().Where(item => item.ValueKind == JsonValueKind.String).Select(item => item.GetString() ?? "").ToArray()
            : [];
    }

    private static JsonSerializerOptions JsonOptions()
    {
        return new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true };
    }
}
