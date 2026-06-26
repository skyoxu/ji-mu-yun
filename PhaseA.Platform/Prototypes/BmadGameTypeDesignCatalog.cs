using System.Text;
using System.Text.RegularExpressions;
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

        if (_entries.TryGetValue(normalized, out var entry))
        {
            return entry;
        }

        foreach (var alias in ResolveAliases(normalized))
        {
            if (_entries.TryGetValue(alias, out entry))
            {
                return entry;
            }
        }

        return null;
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
            return BuildGuideExcerpt(text);
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

    private static string BuildGuideExcerpt(string text)
    {
        if (text.Length <= MaxGuideExcerptChars)
        {
            return text;
        }

        var moduleMatrixStart = FindModuleMatrixStart(text);
        if (moduleMatrixStart < 0)
        {
            return TruncateTail(text, MaxGuideExcerptChars);
        }

        var prefix = text[..moduleMatrixStart].Trim();
        var separator = "\n...\n\n";
        var matrixBudget = string.IsNullOrWhiteSpace(prefix)
            ? MaxGuideExcerptChars
            : Math.Max(MaxGuideExcerptChars / 2, MaxGuideExcerptChars - separator.Length - Math.Min(prefix.Length, MaxGuideExcerptChars / 4));
        var moduleMatrix = ExtractModuleMatrixSection(text, moduleMatrixStart);
        var compactModuleMatrix = CompactModuleMatrix(moduleMatrix, matrixBudget);
        if (string.IsNullOrWhiteSpace(prefix))
        {
            return TruncateTail(compactModuleMatrix, MaxGuideExcerptChars);
        }

        matrixBudget = Math.Min(compactModuleMatrix.Length, matrixBudget);
        var prefixBudget = Math.Max(1, MaxGuideExcerptChars - separator.Length - matrixBudget);
        var excerpt = $"{TruncateTail(prefix, prefixBudget)}{separator}{TruncateTail(compactModuleMatrix, matrixBudget)}";
        return TruncateTail(excerpt, MaxGuideExcerptChars);
    }

    private static int FindModuleMatrixStart(string text)
    {
        foreach (Match match in Regex.Matches(text, @"(?im)^\s*#{1,6}\s+Module Matrix\s*$"))
        {
            if (match.Success)
            {
                return match.Index;
            }
        }

        return -1;
    }

    private static string ExtractModuleMatrixSection(string text, int moduleMatrixStart)
    {
        var headingMatch = Regex.Match(text[moduleMatrixStart..], @"(?m)^\s*(#{1,6})\s+Module Matrix\s*$");
        if (!headingMatch.Success)
        {
            return text[moduleMatrixStart..].Trim();
        }

        var headingLevel = headingMatch.Groups[1].Value.Length;
        var bodyStart = moduleMatrixStart + headingMatch.Index + headingMatch.Length;
        var nextHeading = Regex.Match(text[bodyStart..], $@"(?m)^\s*#{{1,{headingLevel}}}\s+\S");
        var sectionEnd = nextHeading.Success ? bodyStart + nextHeading.Index : text.Length;
        return text[moduleMatrixStart..sectionEnd].Trim();
    }

    private static string CompactModuleMatrix(string moduleMatrix, int maxChars)
    {
        var lines = moduleMatrix.Replace("\r\n", "\n", StringComparison.Ordinal)
            .Replace('\r', '\n')
            .Split('\n', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var rows = new List<ModuleMatrixRow>();
        foreach (var line in lines)
        {
            if (!line.StartsWith("|", StringComparison.Ordinal))
            {
                continue;
            }

            var columns = SplitMarkdownTableRow(line);
            if (columns.Length < 4 ||
                columns[0].Contains("---", StringComparison.Ordinal) ||
                string.Equals(columns[0], "No", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            rows.Add(new ModuleMatrixRow(
                columns[0],
                columns[1],
                columns[2],
                columns[3],
                columns.Length > 4 ? columns[4] : "",
                columns.Length > 5 ? columns[5] : ""));
        }

        if (rows.Count == 0)
        {
            return moduleMatrix;
        }

        var detailed = BuildCompactModuleMatrixTable(rows, includeDetails: true);
        if (detailed.Length <= maxChars)
        {
            return detailed;
        }

        var idTable = BuildCompactModuleMatrixTable(rows, includeDetails: false);
        if (idTable.Length <= maxChars)
        {
            return idTable;
        }

        return BuildCompactModuleIdList(rows, maxChars);
    }

    private static string BuildCompactModuleMatrixTable(IReadOnlyList<ModuleMatrixRow> rows, bool includeDetails)
    {
        if (!includeDetails)
        {
            return string.Join(Environment.NewLine, new[]
            {
                "## Module Matrix",
                "",
                "Compact id index. Purpose and Acceptance text is omitted here to preserve every module id.",
                "",
                "| No | id | Module | Default |",
                "| --- | --- | --- | --- |"
            }.Concat(rows.Select(row => $"| {EscapeMarkdownTableCell(row.No)} | {EscapeMarkdownTableCell(row.Id)} | {EscapeMarkdownTableCell(CompactMatrixCell(row.Module, 40))} | {EscapeMarkdownTableCell(row.Default)} |")));
        }

        return string.Join(Environment.NewLine, new[]
        {
            "## Module Matrix",
            "",
            "Compact index. Purpose and Acceptance cells are shortened; full text stays in the guide file.",
            "",
            "| No | id | Module | Default | Purpose | Acceptance |",
            "| --- | --- | --- | --- | --- | --- |"
        }.Concat(rows.Select(row =>
            $"| {EscapeMarkdownTableCell(row.No)} | {EscapeMarkdownTableCell(row.Id)} | {EscapeMarkdownTableCell(CompactMatrixCell(row.Module, 52))} | {EscapeMarkdownTableCell(row.Default)} | {EscapeMarkdownTableCell(CompactMatrixCell(row.Purpose, 32))} | {EscapeMarkdownTableCell(CompactMatrixCell(row.Acceptance, 32))} |")));
    }

    private static string BuildCompactModuleIdList(IReadOnlyList<ModuleMatrixRow> rows, int maxChars)
    {
        var descriptive = string.Join(Environment.NewLine, new[]
        {
            "## Module Matrix",
            "",
            "Compact id index. Purpose, Acceptance, and long module text are omitted here to preserve every module id.",
            "",
            string.Join("; ", rows.Select(row => $"{row.No} {row.Id}"))
        });
        if (descriptive.Length <= maxChars)
        {
            return descriptive;
        }

        var minimal = string.Join(Environment.NewLine, new[]
        {
            "## Module Matrix",
            "",
            "Compact id index:",
            string.Join("; ", rows.Select(row => $"{row.No}:{row.Id}"))
        });
        if (minimal.Length <= maxChars)
        {
            return minimal;
        }

        var suffix = "; ... omitted";
        var values = rows.Select(row => $"{row.No}:{row.Id}").ToArray();
        var result = "## Module Matrix\n\nCompact id index: ";
        var included = 0;
        foreach (var value in values)
        {
            var separator = included == 0 ? "" : "; ";
            var omittedCount = values.Length - included - 1;
            var omittedSuffix = omittedCount > 0 ? $"{suffix} {omittedCount} module ids" : "";
            if (result.Length + separator.Length + value.Length + omittedSuffix.Length > maxChars)
            {
                break;
            }

            result += separator + value;
            included++;
        }

        var remaining = values.Length - included;
        if (remaining > 0)
        {
            var omittedSuffix = $"{suffix} {remaining} module ids";
            result = TruncateTail(result, Math.Max(0, maxChars - omittedSuffix.Length)) + omittedSuffix;
        }

        return TruncateTail(result, maxChars);
    }

    private static string CompactMatrixCell(string value, int maxCellChars)
    {
        var compact = Regex.Replace(value, @"\s+", " ").Trim();
        return compact.Length <= maxCellChars ? compact : $"{compact[..(maxCellChars - 3)]}...";
    }

    private static string EscapeMarkdownTableCell(string value)
    {
        return value.Replace("|", "\\|", StringComparison.Ordinal);
    }

    private static string[] SplitMarkdownTableRow(string line)
    {
        var trimmed = line.Trim();
        if (trimmed.StartsWith('|'))
        {
            trimmed = trimmed[1..];
        }

        if (trimmed.EndsWith('|'))
        {
            trimmed = trimmed[..^1];
        }

        var columns = new List<string>();
        var current = new StringBuilder();
        for (var index = 0; index < trimmed.Length; index++)
        {
            var ch = trimmed[index];
            if (ch == '\\' && index + 1 < trimmed.Length && trimmed[index + 1] == '|')
            {
                current.Append('|');
                index++;
                continue;
            }

            if (ch == '|')
            {
                columns.Add(current.ToString().Trim());
                current.Clear();
                continue;
            }

            current.Append(ch);
        }

        columns.Add(current.ToString().Trim());
        return columns.ToArray();
    }

    private sealed record ModuleMatrixRow(string No, string Id, string Module, string Default, string Purpose, string Acceptance);

    private static string TruncateTail(string text, int maxChars)
    {
        if (text.Length <= maxChars)
        {
            return text;
        }

        const string suffix = "\n...";
        if (maxChars <= suffix.Length)
        {
            return text[..maxChars];
        }

        return $"{text[..(maxChars - suffix.Length)].TrimEnd()}{suffix}";
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

    private static IReadOnlyList<string> ResolveAliases(string normalized)
    {
        if (normalized is "survivorslike" or "survivors like" or "survivors-like" or "survivor like" or "survivor-like" or
            "vampire survivors-like" or "vampire survivors" or "bullet heaven" or "auto shooter" or
            "arena survival" or "horde survival")
        {
            return ["survival", "roguelike", "shooter"];
        }

        return [];
    }
}
