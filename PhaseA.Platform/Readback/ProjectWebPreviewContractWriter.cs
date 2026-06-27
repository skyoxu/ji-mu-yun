using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace PhaseA.Platform.Readback;

internal static class ProjectWebPreviewContractWriter
{
    public const string FileName = "preview-contract.json";
    public const string SchemaVersion = "phasea-web-preview-contract-v1";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    public static async Task WriteAsync(
        string webRoot,
        ProjectWebPreviewContractSnapshot snapshot,
        CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(webRoot);
        await File.WriteAllTextAsync(
            Path.Combine(webRoot, FileName),
            JsonSerializer.Serialize(snapshot with { SchemaVersion = SchemaVersion }, JsonOptions),
            new UTF8Encoding(false),
            cancellationToken);
    }
}

internal sealed record ProjectWebPreviewContractSnapshot(
    [property: JsonPropertyName("schema_version")] string SchemaVersion,
    [property: JsonPropertyName("project_id")] string ProjectId,
    [property: JsonPropertyName("project_name")] string ProjectName,
    [property: JsonPropertyName("game_name")] string GameName,
    [property: JsonPropertyName("game_type_id")] string GameTypeId,
    [property: JsonPropertyName("game_type_guide")] string GameTypeGuide,
    [property: JsonPropertyName("package_file")] string PackageFile,
    [property: JsonPropertyName("package_sha256")] string PackageSha256,
    [property: JsonPropertyName("package_size_bytes")] long PackageSizeBytes,
    [property: JsonPropertyName("preview_id")] string PreviewId,
    [property: JsonPropertyName("asset_version")] string AssetVersion,
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("converter_id")] string ConverterId,
    [property: JsonPropertyName("converter_compatibility_id")] string ConverterCompatibilityId,
    [property: JsonPropertyName("fidelity_tier")] string FidelityTier,
    [property: JsonPropertyName("playable_surface")] string PlayableSurface,
    [property: JsonPropertyName("source_scene_sha256")] string SourceSceneSha256,
    [property: JsonPropertyName("text_catalog_sha256")] string TextCatalogSha256,
    [property: JsonPropertyName("manifest_sha256")] string ManifestSha256,
    [property: JsonPropertyName("created_utc")] string CreatedUtc);
