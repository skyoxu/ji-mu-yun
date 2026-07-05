using PhaseA.Platform.Configuration;
using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Prototypes;

public sealed record GameTypeGuideEntry(
    string Id,
    string Name,
    string Description,
    IReadOnlyList<string> GenreTags,
    string FragmentFile,
    string FragmentRelativePath,
    bool GuideExists);

public sealed class GameTypeGuideCatalog
{
    private readonly IReadOnlyDictionary<string, GameTypeGuideEntry> _entries;
    private readonly string _catalogHash;

    public GameTypeGuideCatalog(PhaseAPlatformOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);

        var docsRoot = Path.Combine(Path.GetFullPath(options.RepositoryRoot), "docs", "game-type-guides");
        var csvPath = Path.Combine(docsRoot, "game-types.csv");
        _catalogHash = File.Exists(csvPath)
            ? Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(csvPath))).ToLowerInvariant()
            : "";
        _entries = Load(csvPath, docsRoot);
    }

    public IReadOnlyCollection<GameTypeGuideEntry> Entries => _entries.Values.ToArray();

    public string CatalogHash => _catalogHash;

    public GameTypeGuideEntry? FindById(string? id)
    {
        var normalized = NormalizeTag(id);
        return string.IsNullOrWhiteSpace(normalized) ? null : _entries.GetValueOrDefault(normalized);
    }

    public GameTypeGuideMatchResult MatchByGenreTags(IReadOnlyList<string> rawTags)
    {
        var normalizedTags = NormalizeTags(rawTags);
        if (_entries.Count == 0)
        {
            return new GameTypeGuideMatchResult("catalog_missing", "game_type_catalog_missing", normalizedTags, "", "", 0, [], "");
        }

        if (normalizedTags.Count == 0)
        {
            return new GameTypeGuideMatchResult("no_match", "normalized_genre_tags_empty", normalizedTags, "", "", 0, [], "");
        }

        var candidates = _entries.Values
            .Select(entry => ScoreEntry(entry, normalizedTags))
            .Where(candidate => candidate.Score > 0)
            .OrderByDescending(candidate => candidate.Score)
            .ThenBy(candidate => candidate.GameTypeId, StringComparer.Ordinal)
            .ToArray();

        if (candidates.Length == 0)
        {
            return new GameTypeGuideMatchResult("no_match", "no_genre_tag_overlap", normalizedTags, "", "", 0, [], "");
        }

        var top = candidates[0];
        var closeSecond = candidates.Length > 1 && candidates[1].Score >= top.Score - 4;
        if (top.Score < 12)
        {
            return new GameTypeGuideMatchResult("no_match", "match_score_below_threshold", normalizedTags, "", "", top.Score, candidates.Take(5).ToArray(), "");
        }

        if (closeSecond)
        {
            return new GameTypeGuideMatchResult("ambiguous", "multiple_game_types_have_close_scores", normalizedTags, "", "", top.Score, candidates.Take(5).ToArray(), "");
        }

        var entry = FindById(top.GameTypeId);
        if (entry is null)
        {
            return new GameTypeGuideMatchResult("no_match", "matched_entry_missing", normalizedTags, "", "", top.Score, candidates.Take(5).ToArray(), "");
        }

        if (!entry.GuideExists)
        {
            return new GameTypeGuideMatchResult("no_match", "matched_guide_file_missing", normalizedTags, entry.Id, entry.FragmentRelativePath, top.Score, candidates.Take(5).ToArray(), entry.FragmentRelativePath);
        }

        return new GameTypeGuideMatchResult("matched", "matched_by_genre_tags", normalizedTags, entry.Id, entry.FragmentRelativePath, top.Score, candidates.Take(5).ToArray(), "");
    }

    public static IReadOnlyList<string> NormalizeTags(IReadOnlyList<string> rawTags)
    {
        return rawTags
            .Select(NormalizeTag)
            .Where(tag => tag.Length > 0)
            .Where(tag => !StopTags.Contains(tag))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(tag => tag, StringComparer.Ordinal)
            .ToArray();
    }

    public static string NormalizeTag(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var builder = new StringBuilder(value.Trim().ToLowerInvariant().Length);
        var lastWasDash = false;
        foreach (var ch in value.Trim().ToLowerInvariant())
        {
            if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9'))
            {
                builder.Append(ch);
                lastWasDash = false;
                continue;
            }

            if (!lastWasDash)
            {
                builder.Append('-');
                lastWasDash = true;
            }
        }

        return builder.ToString().Trim('-');
    }

    private static GameTypeGuideCandidate ScoreEntry(GameTypeGuideEntry entry, IReadOnlyList<string> normalizedTags)
    {
        var entryTags = NormalizeTags(entry.GenreTags);
        var matched = new List<string>();
        var score = 0;
        foreach (var tag in normalizedTags)
        {
            if (string.Equals(tag, entry.Id, StringComparison.Ordinal))
            {
                score += 16;
                matched.Add(tag);
                continue;
            }

            if (entryTags.Contains(tag, StringComparer.Ordinal))
            {
                score += 10;
                matched.Add(tag);
                continue;
            }

            if (entryTags.Any(entryTag => entryTag.Length >= 4 && tag.Contains(entryTag, StringComparison.Ordinal)))
            {
                score += 3;
                matched.Add(tag);
            }
        }

        return new GameTypeGuideCandidate(entry.Id, entry.FragmentRelativePath, score, matched.Distinct(StringComparer.Ordinal).OrderBy(value => value, StringComparer.Ordinal).ToArray(), !entry.GuideExists);
    }

    private static IReadOnlyDictionary<string, GameTypeGuideEntry> Load(string csvPath, string docsRoot)
    {
        if (!File.Exists(csvPath))
        {
            return new Dictionary<string, GameTypeGuideEntry>(StringComparer.Ordinal);
        }

        var lines = File.ReadAllLines(csvPath, Encoding.UTF8);
        if (lines.Length < 2)
        {
            return new Dictionary<string, GameTypeGuideEntry>(StringComparer.Ordinal);
        }

        var headers = ParseCsvLine(lines[0]);
        var entries = new Dictionary<string, GameTypeGuideEntry>(StringComparer.Ordinal);
        foreach (var line in lines.Skip(1))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var row = ToRow(headers, ParseCsvLine(line));
            var id = NormalizeTag(Read(row, "id"));
            if (string.IsNullOrWhiteSpace(id))
            {
                continue;
            }

            var fragmentFile = Read(row, "fragment_file").Trim();
            var relativePath = string.IsNullOrWhiteSpace(fragmentFile) ? "" : $"docs/game-type-guides/{fragmentFile}";
            entries[id] = new GameTypeGuideEntry(
                id,
                Read(row, "name"),
                Read(row, "description"),
                SplitTags(Read(row, "genre_tags")),
                fragmentFile,
                relativePath,
                !string.IsNullOrWhiteSpace(fragmentFile) && File.Exists(Path.Combine(docsRoot, fragmentFile)));
        }

        return entries;
    }

    private static IReadOnlyList<string> SplitTags(string value)
    {
        return value
            .Split([',', ';', '|'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(tag => !string.IsNullOrWhiteSpace(tag))
            .ToArray();
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

    private static string Read(IReadOnlyDictionary<string, string> row, string key)
    {
        return row.TryGetValue(key, out var value) ? value : "";
    }

    private static IReadOnlyList<string> ParseCsvLine(string line)
    {
        var values = new List<string>();
        var builder = new StringBuilder();
        var inQuotes = false;
        for (var index = 0; index < line.Length; index++)
        {
            var ch = line[index];
            if (ch == '"')
            {
                if (inQuotes && index + 1 < line.Length && line[index + 1] == '"')
                {
                    builder.Append('"');
                    index++;
                    continue;
                }

                inQuotes = !inQuotes;
                continue;
            }

            if (ch == ',' && !inQuotes)
            {
                values.Add(builder.ToString());
                builder.Clear();
                continue;
            }

            builder.Append(ch);
        }

        values.Add(builder.ToString());
        return values;
    }

    private static readonly IReadOnlySet<string> StopTags = new HashSet<string>(StringComparer.Ordinal)
    {
        "indie",
        "singleplayer",
        "single-player",
        "multiplayer",
        "co-op",
        "online-co-op",
        "steam-achievements",
        "full-controller-support",
        "partial-controller-support",
        "remote-play-together",
        "family-sharing",
        "early-access"
    };
}

public sealed record GameTypeGuideMatchResult(
    string Status,
    string StatusReason,
    IReadOnlyList<string> NormalizedGenreTags,
    string MatchedGameTypeId,
    string MatchedGuidePath,
    int MatchScore,
    IReadOnlyList<GameTypeGuideCandidate> CandidateScores,
    string MissingGuidePath);

public sealed record GameTypeGuideCandidate(
    string GameTypeId,
    string GuidePath,
    int Score,
    IReadOnlyList<string> MatchedTags,
    bool MissingGuide);
