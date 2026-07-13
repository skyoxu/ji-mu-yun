using System.Text;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Workflow;
using PhaseA.Platform.Workspaces;

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
    private const int MaxGuideExcerptChars = 4200;
    private readonly IReadOnlyDictionary<string, BmadGameTypeDesignEntry> _entries;
    private readonly IReadOnlyList<BmadGameTypeDesignEntry> _sourceEntries;

    public BmadGameTypeDesignCatalog(PhaseAPlatformOptions options)
        : this(options?.RepositoryRoot ?? throw new ArgumentNullException(nameof(options)))
    {
    }

    public BmadGameTypeDesignCatalog(string repositoryRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        var root = Path.GetFullPath(repositoryRoot);
        var loadResult = Load(
            root,
            Path.Combine(root, "docs", "game-type-guides"),
            Path.Combine(root, ".agents", "skills", "gds-gdd", "assets"),
            Path.Combine(root, ".agents", "skills", "gds-create-gdd"));
        _entries = loadResult.Entries;
        _sourceEntries = loadResult.SourceEntries;
        IsComplete = loadResult.IsComplete;
    }

    public IReadOnlyCollection<BmadGameTypeDesignEntry> Entries => _entries.Values.ToArray();
    public IReadOnlyCollection<BmadGameTypeDesignEntry> SourceEntries => _sourceEntries;
    public bool IsComplete { get; }

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

    private static CatalogLoadResult Load(
        string repositoryRoot,
        string docsRoot,
        string canonicalSkillAssetsRoot,
        string compatibilitySkillRoot)
    {
        var fromCompatibilitySkill = LoadFromPaths(
            repositoryRoot,
            Path.Combine(compatibilitySkillRoot, "game-types.csv"),
            Path.Combine(compatibilitySkillRoot, "game-types"),
            ".agents/skills/gds-create-gdd/game-types");
        var fromCanonicalSkill = LoadFromPaths(
            repositoryRoot,
            Path.Combine(canonicalSkillAssetsRoot, "game-types.csv"),
            Path.Combine(canonicalSkillAssetsRoot, "game-types"),
            ".agents/skills/gds-gdd/assets/game-types");
        var fromDocs = LoadFromPaths(
            repositoryRoot,
            Path.Combine(docsRoot, "game-types.csv"),
            docsRoot,
            "docs/game-type-guides");

        var availableCatalogs = new[] { fromCompatibilitySkill, fromCanonicalSkill, fromDocs }
            .Where(item => item.IsPresent)
            .ToArray();
        var sourceEntries = availableCatalogs
            .SelectMany(item => item.Entries.Values)
            .GroupBy(
                item => $"{item.FragmentRelativePath}\n{HostedRouteForbiddenSourceGuard.ContentHash(item.GuideExcerpt)}",
                StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .OrderBy(item => item.FragmentRelativePath, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        return new CatalogLoadResult(
            MergeCatalogs(availableCatalogs.Select(item => item.Entries).ToArray()),
            sourceEntries,
            availableCatalogs.Length > 0 && availableCatalogs.All(item => item.IsComplete));
    }

    private static IReadOnlyDictionary<string, BmadGameTypeDesignEntry> MergeCatalogs(
        params IReadOnlyDictionary<string, BmadGameTypeDesignEntry>[] catalogs)
    {
        var merged = new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase);
        foreach (var catalog in catalogs)
        {
            foreach (var (id, candidate) in catalog)
            {
                if (merged.TryGetValue(id, out var fallback))
                {
                    merged[id] = MergeEntry(fallback, candidate);
                    continue;
                }

                merged[id] = candidate;
            }
        }

        return merged;
    }

    private static BmadGameTypeDesignEntry MergeEntry(
        BmadGameTypeDesignEntry fallback,
        BmadGameTypeDesignEntry candidate)
    {
        var useCandidateGuide = !string.IsNullOrWhiteSpace(candidate.GuideExcerpt);
        return candidate with
        {
            Name = FirstNonEmpty(candidate.Name, fallback.Name),
            Description = FirstNonEmpty(candidate.Description, fallback.Description),
            GenreTags = FirstNonEmpty(candidate.GenreTags, fallback.GenreTags),
            FragmentFile = useCandidateGuide ? candidate.FragmentFile : fallback.FragmentFile,
            FragmentRelativePath = useCandidateGuide ? candidate.FragmentRelativePath : fallback.FragmentRelativePath,
            GuideExcerpt = useCandidateGuide ? candidate.GuideExcerpt : fallback.GuideExcerpt
        };
    }

    private static string FirstNonEmpty(string preferred, string fallback)
    {
        return string.IsNullOrWhiteSpace(preferred) ? fallback : preferred;
    }

    private static CatalogSourceLoadResult LoadFromPaths(
        string repositoryRoot,
        string csvPath,
        string gameTypesRoot,
        string relativeRoot)
    {
        if (!IsSafeExistingFile(repositoryRoot, csvPath))
        {
            return new CatalogSourceLoadResult(
                new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase),
                IsPresent: File.Exists(csvPath),
                IsComplete: false);
        }

        try
        {
            var lines = File.ReadAllLines(csvPath, Encoding.UTF8);
            if (lines.Length < 2)
            {
                return InvalidPresentCatalog();
            }

            if (!TryParseCsvLine(lines[0], out var headers) ||
                headers.Count == 0 ||
                headers.Distinct(StringComparer.OrdinalIgnoreCase).Count() != headers.Count ||
                new[] { "id", "name", "description", "genre_tags", "fragment_file" }
                    .Any(required => !headers.Contains(required, StringComparer.OrdinalIgnoreCase)))
            {
                return InvalidPresentCatalog();
            }
            var entries = new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase);
            foreach (var line in lines.Skip(1))
            {
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                if (!TryParseCsvLine(line, out var values) || values.Count != headers.Count)
                {
                    return InvalidPresentCatalog();
                }

                var row = ToRow(headers, values);
                var id = NormalizeId(Read(row, "id"));
                if (string.IsNullOrWhiteSpace(id))
                {
                    return InvalidPresentCatalog();
                }

                if (entries.ContainsKey(id))
                {
                    return InvalidPresentCatalog();
                }

                var fragmentFile = Read(row, "fragment_file");
                if (string.IsNullOrWhiteSpace(fragmentFile))
                {
                    return InvalidPresentCatalog();
                }
                var fragmentRelativePath = $"{relativeRoot.TrimEnd('/')}/{fragmentFile}";
                var guidePath = ResolveGuidePath(repositoryRoot, gameTypesRoot, fragmentFile);
                if (string.IsNullOrWhiteSpace(guidePath))
                {
                    return InvalidPresentCatalog();
                }
                var guideExcerpt = ReadGuideExcerpt(guidePath);
                if (string.IsNullOrWhiteSpace(guideExcerpt))
                {
                    return InvalidPresentCatalog();
                }
                entries[id] = new BmadGameTypeDesignEntry(
                    id,
                    Read(row, "name"),
                    Read(row, "description"),
                    Read(row, "genre_tags"),
                    fragmentFile,
                    fragmentRelativePath,
                    guideExcerpt);
            }

            return entries.Count > 0
                ? new CatalogSourceLoadResult(entries, IsPresent: true, IsComplete: true)
                : InvalidPresentCatalog();
        }
        catch (IOException)
        {
            return InvalidPresentCatalog();
        }
        catch (UnauthorizedAccessException)
        {
            return InvalidPresentCatalog();
        }
    }

    private static CatalogSourceLoadResult InvalidPresentCatalog()
    {
        return new CatalogSourceLoadResult(
            new Dictionary<string, BmadGameTypeDesignEntry>(StringComparer.OrdinalIgnoreCase),
            IsPresent: true,
            IsComplete: false);
    }

    private static string ResolveGuidePath(string repositoryRoot, string gameTypesRoot, string fragmentFile)
    {
        if (string.IsNullOrWhiteSpace(fragmentFile))
        {
            return "";
        }

        try
        {
            var candidate = Path.GetFullPath(Path.Combine(gameTypesRoot, fragmentFile));
            return WorkspacePathPolicy.IsUnderRoot(gameTypesRoot, candidate) &&
                   IsSafeExistingFile(repositoryRoot, candidate)
                ? candidate
                : "";
        }
        catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException or IOException or UnauthorizedAccessException)
        {
            return "";
        }
    }

    private static bool IsSafeExistingFile(string repositoryRoot, string candidate)
    {
        try
        {
            return WorkspacePathPolicy.IsUnderRoot(repositoryRoot, candidate) &&
                   File.Exists(candidate) &&
                   !HasReparsePoint(repositoryRoot, candidate);
        }
        catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException or IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static bool HasReparsePoint(string root, string candidate)
    {
        var relative = Path.GetRelativePath(Path.GetFullPath(root), Path.GetFullPath(candidate));
        var current = Path.GetFullPath(root);
        foreach (var segment in relative.Split(
                     [Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar],
                     StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
            {
                return true;
            }
        }

        return false;
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

    private static bool TryParseCsvLine(string line, out IReadOnlyList<string> parsedValues)
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
        parsedValues = values;
        return !inQuotes;
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

        var defaultContractStart = FindSectionStart(text, "Default Prototype Contract");
        var moduleMatrixStart = FindModuleMatrixStart(text);
        if (defaultContractStart >= 0)
        {
            var contract = ExtractDefaultPrototypeContractSection(text, defaultContractStart).Trim();
            var contractBudget = moduleMatrixStart >= 0 ? (MaxGuideExcerptChars * 2 / 3) : MaxGuideExcerptChars;
            var parts = new List<string> { TruncateTail(contract, Math.Min(contract.Length, contractBudget)) };
            if (moduleMatrixStart >= 0)
            {
                var remainingBudget = Math.Max(MaxGuideExcerptChars / 4, MaxGuideExcerptChars - parts[0].Length - 8);
                var contractModuleMatrix = ExtractModuleMatrixSection(text, moduleMatrixStart);
                var compactContractModuleMatrix = CompactModuleMatrix(contractModuleMatrix, remainingBudget);
                parts.Add(TruncateTail(compactContractModuleMatrix, remainingBudget));
            }

            return TruncateTail(string.Join("\n...\n\n", parts.Where(part => !string.IsNullOrWhiteSpace(part))), MaxGuideExcerptChars);
        }

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
        return FindSectionStart(text, "Module Matrix");
    }

    private static int FindSectionStart(string text, string title)
    {
        foreach (Match match in Regex.Matches(text, $@"(?im)^\s*#{{1,6}}\s+{Regex.Escape(title)}\s*$"))
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
        return ExtractMarkdownSection(text, moduleMatrixStart);
    }

    private static string ExtractDefaultPrototypeContractSection(string text, int defaultContractStart)
    {
        var section = ExtractMarkdownSection(text, defaultContractStart);
        var moduleMatrix = Regex.Match(section, @"(?im)^\s*#{1,6}\s+Module Matrix\s*$");
        return moduleMatrix.Success && moduleMatrix.Index > 0
            ? section[..moduleMatrix.Index].Trim()
            : section.Trim();
    }

    private static string ExtractMarkdownSection(string text, int sectionStart)
    {
        var headingMatch = Regex.Match(text[sectionStart..], @"(?m)^\s*(#{1,6})\s+\S.*$");
        if (!headingMatch.Success)
        {
            return text[sectionStart..].Trim();
        }

        var headingLevel = headingMatch.Groups[1].Value.Length;
        var bodyStart = sectionStart + headingMatch.Index + headingMatch.Length;
        var nextHeading = Regex.Match(text[bodyStart..], $@"(?m)^\s*#{{1,{headingLevel}}}\s+\S");
        var sectionEnd = nextHeading.Success ? bodyStart + nextHeading.Index : text.Length;
        return text[sectionStart..sectionEnd].Trim();
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
    private sealed record CatalogLoadResult(
        IReadOnlyDictionary<string, BmadGameTypeDesignEntry> Entries,
        IReadOnlyList<BmadGameTypeDesignEntry> SourceEntries,
        bool IsComplete);
    private sealed record CatalogSourceLoadResult(
        IReadOnlyDictionary<string, BmadGameTypeDesignEntry> Entries,
        bool IsPresent,
        bool IsComplete);

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
            return ["survivorslike"];
        }

        return [];
    }
}
