using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Serialization;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Prototypes;

public sealed record ProjectGameTypeContractSnapshot(
    int SchemaVersion,
    string MatchedGameTypeId,
    string GuidePath,
    string SourceGuideHash,
    IReadOnlyList<ProjectGameTypeContractScene> DefaultScenes,
    IReadOnlyList<ProjectGameTypeContractModule> RequiredModules,
    IReadOnlyList<string> Overrides,
    string CreatedUtc,
    string UpdatedUtc)
{
    [JsonIgnore]
    public bool HasContract =>
        !string.IsNullOrWhiteSpace(MatchedGameTypeId) &&
        (DefaultScenes.Count > 0 || RequiredModules.Count > 0);

    public static ProjectGameTypeContractSnapshot Empty()
    {
        var now = DateTimeOffset.UtcNow.ToString("O");
        return new ProjectGameTypeContractSnapshot(1, "", "", "", [], [], [], now, now);
    }

    public static ProjectGameTypeContractSnapshot FromProjectMatch(
        PhaseAPlatformOptions? options,
        ProjectGameTypeMatchEvidence evidence)
    {
        if (options is null || string.IsNullOrWhiteSpace(evidence.MatchedGameTypeId))
        {
            return Empty();
        }

        var entry = new BmadGameTypeDesignCatalog(options).Find(evidence.MatchedGameTypeId);
        return entry is null ? Empty() : FromEntry(entry);
    }

    public static ProjectGameTypeContractSnapshot RefreshFromProjectMatch(
        PhaseAPlatformOptions? options,
        ProjectGameTypeMatchEvidence evidence)
    {
        var refreshed = FromProjectMatch(options, evidence);
        if (!refreshed.HasContract)
        {
            return refreshed;
        }

        var current = Normalize(evidence.ContractSnapshot);
        return refreshed with
        {
            CreatedUtc = current.HasContract ? current.CreatedUtc : refreshed.CreatedUtc
        };
    }

    public static ProjectGameTypeContractSnapshot FromEntry(BmadGameTypeDesignEntry entry)
    {
        ArgumentNullException.ThrowIfNull(entry);

        var now = DateTimeOffset.UtcNow.ToString("O");
        var scenes = ParseDefaultScenes(entry.GuideExcerpt);
        var modules = ParseRequiredModules(entry.GuideExcerpt);
        return new ProjectGameTypeContractSnapshot(
            1,
            entry.Id,
            entry.FragmentRelativePath,
            Sha256(entry.GuideExcerpt),
            scenes,
            modules,
            [],
            now,
            now);
    }

    public static ProjectGameTypeContractSnapshot Normalize(ProjectGameTypeContractSnapshot? snapshot)
    {
        if (snapshot is null)
        {
            return Empty();
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        return snapshot with
        {
            SchemaVersion = snapshot.SchemaVersion <= 0 ? 1 : snapshot.SchemaVersion,
            MatchedGameTypeId = snapshot.MatchedGameTypeId ?? "",
            GuidePath = snapshot.GuidePath ?? "",
            SourceGuideHash = snapshot.SourceGuideHash ?? "",
            DefaultScenes = snapshot.DefaultScenes?.Select(ProjectGameTypeContractScene.Normalize).ToArray() ?? [],
            RequiredModules = snapshot.RequiredModules?.Select(ProjectGameTypeContractModule.Normalize).ToArray() ?? [],
            Overrides = snapshot.Overrides?.Where(value => !string.IsNullOrWhiteSpace(value)).Select(value => value.Trim()).ToArray() ?? [],
            CreatedUtc = string.IsNullOrWhiteSpace(snapshot.CreatedUtc) ? now : snapshot.CreatedUtc,
            UpdatedUtc = string.IsNullOrWhiteSpace(snapshot.UpdatedUtc) ? now : snapshot.UpdatedUtc
        };
    }

    private static IReadOnlyList<ProjectGameTypeContractScene> ParseDefaultScenes(string guideExcerpt)
    {
        return ParseMarkdownSectionTable(guideExcerpt, "Default Scenes")
            .Where(columns => columns.Length >= 7)
            .Select(columns => new ProjectGameTypeContractScene(
                NormalizeId(columns[0]),
                Trim(columns[1], 80),
                Trim(columns[2], 240),
                Trim(columns[3], 40),
                Trim(columns[4], 160),
                Trim(columns[5], 160),
                Trim(columns[6], 260)))
            .Where(scene => !string.IsNullOrWhiteSpace(scene.SceneId))
            .ToArray();
    }

    private static IReadOnlyList<ProjectGameTypeContractModule> ParseRequiredModules(string guideExcerpt)
    {
        return ParseMarkdownSectionTable(guideExcerpt, "Required Modules")
            .Where(columns => columns.Length >= 5)
            .Select(columns => new ProjectGameTypeContractModule(
                NormalizeId(columns[0]),
                Trim(columns[1], 100),
                Trim(columns[2], 40),
                Trim(columns[3], 240),
                Trim(columns[4], 280)))
            .Where(module => !string.IsNullOrWhiteSpace(module.ModuleId))
            .ToArray();
    }

    private static IEnumerable<string[]> ParseMarkdownSectionTable(string text, string sectionTitle)
    {
        var lines = (text ?? "")
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Replace('\r', '\n')
            .Split('\n', StringSplitOptions.TrimEntries);
        var inSection = false;
        foreach (var line in lines)
        {
            if (line.StartsWith($"### {sectionTitle}", StringComparison.OrdinalIgnoreCase))
            {
                inSection = true;
                continue;
            }

            if (inSection && line.StartsWith("### ", StringComparison.Ordinal))
            {
                yield break;
            }

            if (!inSection || !line.StartsWith("|", StringComparison.Ordinal))
            {
                continue;
            }

            var columns = SplitMarkdownTableRow(line);
            if (columns.Length == 0 ||
                columns[0].Contains("---", StringComparison.Ordinal) ||
                string.Equals(columns[0], "scene_id", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(columns[0], "module_id", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            yield return columns;
        }
    }

    private static string[] SplitMarkdownTableRow(string line)
    {
        return line.Trim().Trim('|')
            .Split('|', StringSplitOptions.TrimEntries)
            .Select(column => column.Replace("\\|", "|", StringComparison.Ordinal).Trim())
            .ToArray();
    }

    private static string NormalizeId(string value)
    {
        var normalized = new string((value ?? "").Trim().ToLowerInvariant()
            .Select(ch => char.IsLetterOrDigit(ch) ? ch : '_')
            .ToArray());
        while (normalized.Contains("__", StringComparison.Ordinal))
        {
            normalized = normalized.Replace("__", "_", StringComparison.Ordinal);
        }

        return normalized.Trim('_');
    }

    private static string Trim(string? value, int maxLength)
    {
        var trimmed = (value ?? "").Trim();
        return trimmed.Length <= maxLength ? trimmed : trimmed[..maxLength].Trim();
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value ?? ""));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}

public sealed record ProjectGameTypeContractScene(
    string SceneId,
    string SceneName,
    string Purpose,
    string Required,
    string EntryFrom,
    string ExitsTo,
    string MinimumPlayableContent)
{
    public static ProjectGameTypeContractScene Normalize(ProjectGameTypeContractScene? scene)
    {
        return new ProjectGameTypeContractScene(
            scene?.SceneId ?? "",
            scene?.SceneName ?? "",
            scene?.Purpose ?? "",
            scene?.Required ?? "",
            scene?.EntryFrom ?? "",
            scene?.ExitsTo ?? "",
            scene?.MinimumPlayableContent ?? "");
    }
}

public sealed record ProjectGameTypeContractModule(
    string ModuleId,
    string ModuleName,
    string RequiredByDefault,
    string Purpose,
    string MinimumAcceptance)
{
    [JsonIgnore]
    public bool IsAlways => string.Equals(RequiredByDefault, "Always", StringComparison.OrdinalIgnoreCase);

    public static ProjectGameTypeContractModule Normalize(ProjectGameTypeContractModule? module)
    {
        return new ProjectGameTypeContractModule(
            module?.ModuleId ?? "",
            module?.ModuleName ?? "",
            module?.RequiredByDefault ?? "",
            module?.Purpose ?? "",
            module?.MinimumAcceptance ?? "");
    }
}
