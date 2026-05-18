using System.Text.Json;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Prototypes;

public sealed record GameTypeTemplateEntry(
    string GameType,
    string TemplateId,
    string SourceMode,
    string RepoTemplatePath,
    string ManifestPath,
    string ImportSourcePath,
    bool Enabled);

public sealed class GameTypeTemplateCatalog
{
    private readonly IReadOnlyDictionary<string, GameTypeTemplateEntry> _entries;

    public GameTypeTemplateCatalog(PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);

        var root = Path.GetFullPath(options.RepositoryRoot);
        var catalogPath = Path.Combine(root, "docs", "prototype-type-kits", "game-type-template-catalog.json");
        _entries = LoadCatalog(catalogPath);
    }

    public GameTypeTemplateEntry? Find(string? gameType)
    {
        var normalized = NormalizeGameType(gameType);
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return null;
        }

        return _entries.TryGetValue(normalized, out var entry) ? entry : null;
    }

    private static IReadOnlyDictionary<string, GameTypeTemplateEntry> LoadCatalog(string catalogPath)
    {
        if (!File.Exists(catalogPath))
        {
            return new Dictionary<string, GameTypeTemplateEntry>(StringComparer.OrdinalIgnoreCase);
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(catalogPath, System.Text.Encoding.UTF8));
            if (!document.RootElement.TryGetProperty("entries", out var entriesElement) || entriesElement.ValueKind != JsonValueKind.Array)
            {
                return new Dictionary<string, GameTypeTemplateEntry>(StringComparer.OrdinalIgnoreCase);
            }

            var entries = new Dictionary<string, GameTypeTemplateEntry>(StringComparer.OrdinalIgnoreCase);
            foreach (var item in entriesElement.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object)
                {
                    continue;
                }

                var gameType = NormalizeGameType(ReadRequiredString(item, "game_type"));
                if (string.IsNullOrWhiteSpace(gameType))
                {
                    continue;
                }

                var entry = new GameTypeTemplateEntry(
                    gameType,
                    ReadRequiredString(item, "template_id"),
                    ReadRequiredString(item, "source_mode"),
                    ReadRequiredString(item, "repo_template_path"),
                    ReadRequiredString(item, "manifest_path"),
                    ReadRequiredString(item, "import_source_path"),
                    item.TryGetProperty("enabled", out var enabledElement) && enabledElement.ValueKind is JsonValueKind.True or JsonValueKind.False
                        ? enabledElement.GetBoolean()
                        : true);
                entries[gameType] = entry;
            }

            return entries;
        }
        catch (JsonException)
        {
            return new Dictionary<string, GameTypeTemplateEntry>(StringComparer.OrdinalIgnoreCase);
        }
        catch (IOException)
        {
            return new Dictionary<string, GameTypeTemplateEntry>(StringComparer.OrdinalIgnoreCase);
        }
    }

    private static string ReadRequiredString(JsonElement element, string name)
    {
        return element.TryGetProperty(name, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? ""
            : "";
    }

    private static string NormalizeGameType(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "" : value.Trim().ToLowerInvariant();
    }
}
