using System.Text;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Prototypes;

public sealed record BmadGameTypeDesignEntry(
    string Id,
    string Name,
    string Description,
    string GenreTags,
    string FragmentFile,
    string FragmentRelativePath,
    string GuideExcerpt);

public sealed class BmadGameTypeDesignCatalog
{
    private const int MaxGuideExcerptChars = 2400;
    private readonly IReadOnlyDictionary<string, BmadGameTypeDesignEntry> _entries;

    public BmadGameTypeDesignCatalog(PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);

        var root = Path.GetFullPath(options.RepositoryRoot);
        _entries = Load(
            Path.Combine(root, "docs", "game-type-guides"),
            Path.Combine(root, ".agents", "skills", "gds-create-gdd"));
    }

    public IReadOnlyCollection<BmadGameTypeDesignEntry> Entries => _entries.Values.ToArray();

    public BmadGameTypeDesignEntry? Find(string? gameType)
    {
        var normalized = NormalizeId(gameType);
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return null;
        }

        return _entries.TryGetValue(normalized, out var entry) ? entry : null;
    }

    private static IReadOnlyDictionary<string, BmadGameTypeDesignEntry> Load(string docsRoot, string skillRoot)
    {
        var fromDocs = LoadFromPaths(
            Path.Combine(docsRoot, "game-types.csv"),
            docsRoot,
            "docs/game-type-guides");
        if (fromDocs.Count > 0)
        {
            return fromDocs;
        }

        return LoadFromPaths(
            Path.Combine(skillRoot, "game-types.csv"),
            Path.Combine(skillRoot, "game-types"),
            ".agents/skills/gds-create-gdd/game-types");
    }

    private static IReadOnlyDictionary<string, BmadGameTypeDesignEntry> LoadFromPaths(
        string csvPath,
        string gameTypesRoot,
        string relativeRoot)
    {
        if (!File.Exists(csvPath))
        {
            return new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase);
        }

        try
        {
            var lines = File.ReadAllLines(csvPath, Encoding.UTF8);
            if (lines.Length < 2)
            {
                return new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase);
            }

            var headers = ParseCsvLine(lines[0]);
            var entries = new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase);
            foreach (var line in lines.Skip(1))
            {
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                var row = ToRow(headers, ParseCsvLine(line));
                var id = NormalizeId(Read(row, "id"));
                if (string.IsNullOrWhiteSpace(id))
                {
                    continue;
                }

                var fragmentFile = Read(row, "fragment_file");
                var fragmentRelativePath = string.IsNullOrWhiteSpace(fragmentFile)
                    ? ""
                    : $"{relativeRoot.TrimEnd('/')}/{fragmentFile}";
                var guidePath = string.IsNullOrWhiteSpace(fragmentFile) ? "" : Path.Combine(gameTypesRoot, fragmentFile);
                entries[id] = new BmadGameTypeDesignEntry(
                    id,
                    Read(row, "name"),
                    Read(row, "description"),
                    Read(row, "genre_tags"),
                    fragmentFile,
                    fragmentRelativePath,
                    ReadGuideExcerpt(guidePath));
            }

            return entries;
        }
        catch (IOException)
        {
            return new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase);
        }
        catch (UnauthorizedAccessException)
        {
            return new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase);
        }
    }

    private static Dictionary<string, string> ToRow(IReadOnlyList<string> headers, IReadOnlyList<string> values)
    {
        var row = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < headers.Count; index++)
        {
            row[headers[index]] = index < values.Count ? values[index] : "";
        }

        return row;
    }

    private static IReadOnlyList<string> ParseCsvLine(string line)
    {
        var values = new List<string>();
        var current = new StringBuilder();
        var inQuotes = false;
        for (var index = 0; index < line.Length; index++)
        {
            var ch = line[index];
            if (ch == '"')
            {
                if (inQuotes && index + 1 < line.Length && line[index + 1] == '"')
                {
                    current.Append('"');
                    index++;
                }
                else
                {
                    inQuotes = !inQuotes;
                }

                continue;
            }

            if (ch == ',' && !inQuotes)
            {
                values.Add(current.ToString());
                current.Clear();
                continue;
            }

            current.Append(ch);
        }

        values.Add(current.ToString());
        return values;
    }

    private static string Read(Dictionary<string, string> row, string key)
    {
        return row.TryGetValue(key, out var value) ? value.Trim() : "";
    }

    private static string ReadGuideExcerpt(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            return "";
        }

        try
        {
            var text = File.ReadAllText(path, Encoding.UTF8);
            text = NormalizeGuideText(text);
            return text.Length <= MaxGuideExcerptChars
                ? text
                : $"{text[..MaxGuideExcerptChars].TrimEnd()}\n...";
        }
        catch (IOException)
        {
            return "";
        }
        catch (UnauthorizedAccessException)
        {
            return "";
        }
    }

    private static string NormalizeGuideText(string text)
    {
        var lines = text.Replace("\r\n", "\n", StringComparison.Ordinal)
            .Replace('\r', '\n')
            .Split('\n')
            .Select(line => line.TrimEnd())
            .Where(line => !line.TrimStart().StartsWith("{{", StringComparison.Ordinal))
            .ToArray();
        return string.Join('\n', lines).Trim();
    }

    private static string NormalizeId(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "" : value.Trim().ToLowerInvariant();
    }
}
