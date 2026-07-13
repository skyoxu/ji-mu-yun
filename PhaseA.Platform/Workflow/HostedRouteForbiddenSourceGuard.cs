using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace PhaseA.Platform.Workflow;

public static class HostedRouteForbiddenSourceGuard
{
    public const string PolicyVersion = "hosted-route-forbidden-source-scan.v1";

    public static HostedRouteForbiddenSourceScan Scan(
        string prompt,
        IReadOnlyList<string> forbiddenPatterns,
        IReadOnlyList<HostedRouteForbiddenContentFingerprint>? forbiddenContent = null,
        bool requireForbiddenContentFingerprints = false,
        IReadOnlyList<string>? allowedSourceReferences = null,
        IReadOnlyList<string>? allowedContentExcerpts = null,
        bool? forbiddenContentFingerprintSetComplete = null)
    {
        ArgumentNullException.ThrowIfNull(prompt);
        ArgumentNullException.ThrowIfNull(forbiddenPatterns);
        var allowedReferences = (allowedSourceReferences ?? [])
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Select(item => item.Trim().Replace('\\', '/'))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(item => item, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var patternScanPrompt = prompt.Replace('\\', '/');
        foreach (var allowedReference in allowedReferences)
        {
            patternScanPrompt = Regex.Replace(
                patternScanPrompt,
                $@"(?<![A-Za-z0-9_./:\\-]){Regex.Escape(allowedReference)}(?![A-Za-z0-9_./:\\-])",
                "",
                RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        }
        var violations = new List<string>();
        foreach (var pattern in forbiddenPatterns)
        {
            if (PatternNeedles(pattern).Any(needle =>
                    patternScanPrompt.Contains(needle, StringComparison.OrdinalIgnoreCase)))
            {
                violations.Add(pattern);
            }
        }

        var content = (forbiddenContent ?? [])
            .Where(item => !string.IsNullOrWhiteSpace(item.Content))
            .Select(item => item with
            {
                ContentHash = string.IsNullOrWhiteSpace(item.ContentHash) ? Sha256(NormalizeForMatch(item.Content)) : item.ContentHash
            })
            .OrderBy(item => item.ContentHash, StringComparer.Ordinal)
            .ToArray();
        var normalizedPrompt = NormalizeForMatch(prompt);
        foreach (var allowedContentExcerpt in allowedContentExcerpts ?? [])
        {
            var normalizedAllowedContent = NormalizeForMatch(allowedContentExcerpt);
            if (normalizedAllowedContent.Length > 0)
            {
                normalizedPrompt = normalizedPrompt.Replace(normalizedAllowedContent, "", StringComparison.Ordinal);
            }
        }
        var promptWords = normalizedPrompt.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var promptWordPositions = BuildWordPositions(promptWords);
        var matchedContentHashes = content
            .Where(item => ContainsExactOrNearCopy(
                normalizedPrompt,
                promptWords,
                promptWordPositions,
                NormalizeForMatch(item.Content)))
            .Select(item => item.ContentHash)
            .Distinct(StringComparer.Ordinal)
            .OrderBy(item => item, StringComparer.Ordinal)
            .ToArray();
        var fingerprintSetStatus = !requireForbiddenContentFingerprints
            ? "complete"
            : forbiddenContentFingerprintSetComplete switch
            {
                true => "complete",
                false => "incomplete",
                _ => content.Length > 0 ? "complete" : "missing"
            };
        if (string.Equals(fingerprintSetStatus, "missing", StringComparison.Ordinal))
        {
            violations.Add("forbidden_content_fingerprint_set_missing");
        }
        else if (string.Equals(fingerprintSetStatus, "incomplete", StringComparison.Ordinal))
        {
            violations.Add("forbidden_content_fingerprint_set_incomplete");
        }
        if (matchedContentHashes.Length > 0)
        {
            violations.Add("raw_mutable_guide_excerpt_after_freeze");
        }

        return new HostedRouteForbiddenSourceScan(
            PolicyVersion,
            Sha256(prompt),
            forbiddenPatterns.ToArray(),
            content.Select(item => item.ContentHash).Distinct(StringComparer.Ordinal).OrderBy(item => item, StringComparer.Ordinal).ToArray(),
            matchedContentHashes,
            fingerprintSetStatus,
            allowedReferences,
            violations.Distinct(StringComparer.Ordinal).ToArray(),
            violations.Count == 0 ? "clean" : "blocked");
    }

    public static bool IsValidEvidence(
        JsonElement root,
        IReadOnlyList<string> expectedPatterns,
        IReadOnlyList<string>? expectedContentHashes = null,
        bool requireForbiddenContentFingerprints = false,
        IReadOnlyList<string>? expectedAllowedSourceReferences = null,
        bool? forbiddenContentFingerprintSetComplete = null)
    {
        var contentHashes = (expectedContentHashes ?? []).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var allowedReferences = (expectedAllowedSourceReferences ?? [])
            .OrderBy(item => item, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var expectedFingerprintSetStatus = !requireForbiddenContentFingerprints
            ? "complete"
            : forbiddenContentFingerprintSetComplete switch
            {
                true => "complete",
                false => "incomplete",
                _ => contentHashes.Length > 0 ? "complete" : "missing"
            };
        if (!root.TryGetProperty("forbidden_source_scan", out var scan) ||
            scan.ValueKind != JsonValueKind.Object ||
            !string.Equals(ReadString(scan, "policy_version"), PolicyVersion, StringComparison.Ordinal) ||
            !string.Equals(ReadString(scan, "status"), "clean", StringComparison.Ordinal) ||
            !IsSha256(ReadString(scan, "prompt_hash")) ||
            !ReadStringArray(scan, "patterns").SequenceEqual(expectedPatterns, StringComparer.Ordinal) ||
            !ReadStringArray(scan, "forbidden_content_hashes").SequenceEqual(contentHashes, StringComparer.Ordinal) ||
            ReadStringArray(scan, "matched_content_hashes").Count != 0 ||
            !ReadStringArray(scan, "allowed_source_references").SequenceEqual(allowedReferences, StringComparer.OrdinalIgnoreCase) ||
             !string.Equals(
                 ReadString(scan, "fingerprint_set_status"),
                 expectedFingerprintSetStatus,
                 StringComparison.Ordinal) ||
            !string.Equals(expectedFingerprintSetStatus, "complete", StringComparison.Ordinal) ||
            ReadStringArray(scan, "violations").Count != 0)
        {
            return false;
        }

        return true;
    }

    private static IReadOnlyList<string> PatternNeedles(string pattern)
    {
        if (pattern.Contains("docs/game-type-guides", StringComparison.OrdinalIgnoreCase))
        {
            return ["docs/game-type-guides/"];
        }
        if (pattern.Contains("unapproved raw game-type guide", StringComparison.OrdinalIgnoreCase))
        {
            return
            [
                "docs/game-type-guides/",
                ".agents/skills/gds-gdd/assets/game-types/",
                ".agents/skills/gds-create-gdd/game-types/"
            ];
        }
        if (pattern.Contains("assistant summary", StringComparison.OrdinalIgnoreCase))
        {
            return ["assistant summary"];
        }
        if (pattern.Contains("style guide", StringComparison.OrdinalIgnoreCase))
        {
            return ["docs/ui-style-guides/"];
        }
        return [];
    }

    private static bool IsSha256(string value)
    {
        return value.Length == 64 && value.All(character => Uri.IsHexDigit(character));
    }

    private static string Sha256(string value)
    {
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value.Replace("\r\n", "\n")))).ToLowerInvariant();
    }

    public static string ContentHash(string content)
    {
        ArgumentNullException.ThrowIfNull(content);
        return Sha256(NormalizeForMatch(content));
    }

    public static string PromptHash(string prompt)
    {
        ArgumentNullException.ThrowIfNull(prompt);
        return Sha256(prompt);
    }

    public static IReadOnlyList<HostedRouteForbiddenContentFingerprint> CreateContentFingerprints(
        string sourceId,
        string content)
    {
        ArgumentNullException.ThrowIfNull(content);
        var normalized = content.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n').Trim();
        var fingerprintParagraphs = Regex.Split(normalized, @"\n\s*\n")
            .SelectMany(CreateFingerprintParagraphs)
            .Where(chunk => chunk.Length >= 16)
            .ToArray();
        var chunks = fingerprintParagraphs
            .SelectMany(paragraph => CreateMatchWindows(paragraph))
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        if (chunks.Length == 0 && NormalizeForMatch(normalized).Length > 0)
        {
            chunks = [NormalizeForMatch(normalized)];
        }

        return chunks.Select((chunk, index) => new HostedRouteForbiddenContentFingerprint(
                $"{sourceId}#chunk-{index + 1}",
                Sha256(chunk),
                chunk))
            .ToArray();
    }

    private static IEnumerable<string> CreateFingerprintParagraphs(string paragraph)
    {
        var lines = paragraph.Split('\n')
            .Select(line => line.Trim())
            .Where(line => line.Length > 0)
            .ToArray();
        var tableLines = lines.Where(line => line.Contains('|')).ToArray();
        if (tableLines.Length < 2)
        {
            yield return NormalizeForMatch(paragraph);
            yield break;
        }

        var prose = NormalizeForMatch(string.Join(' ', lines.Where(line => !line.Contains('|'))));
        if (prose.Length > 0)
        {
            yield return prose;
        }

        var separatorIndex = Array.FindIndex(tableLines, IsMarkdownTableSeparator);
        var dataRows = separatorIndex >= 0 ? tableLines.Skip(separatorIndex + 1) : tableLines;
        foreach (var row in dataRows.Select(NormalizeForMatch).Where(row => row.Length > 0))
        {
            yield return row;
        }
    }

    private static bool IsMarkdownTableSeparator(string line)
    {
        var cells = line.Trim().Trim('|').Split('|', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        return cells.Length > 0 && cells.All(cell => Regex.IsMatch(cell, @"^:?-{3,}:?$", RegexOptions.CultureInvariant));
    }

    private static IEnumerable<string> CreateMatchWindows(string paragraph)
    {
        yield return paragraph;
        var words = paragraph.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        const int windowSize = 16;
        const int windowStep = 8;
        if (words.Length < windowSize)
        {
            yield break;
        }

        for (var start = 0; start < words.Length; start += windowStep)
        {
            var length = Math.Min(windowSize, words.Length - start);
            if (length < windowSize && start > 0)
            {
                start = Math.Max(0, words.Length - windowSize);
                length = windowSize;
            }
            yield return string.Join(' ', words, start, length);
            if (start + length >= words.Length)
            {
                yield break;
            }
        }
    }

    private static bool ContainsExactOrNearCopy(
        string normalizedPrompt,
        IReadOnlyList<string> promptWords,
        IReadOnlyDictionary<string, IReadOnlyList<int>> promptWordPositions,
        string normalizedContent)
    {
        if (normalizedPrompt.Contains(normalizedContent, StringComparison.Ordinal))
        {
            return true;
        }

        var sourceWords = normalizedContent.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (sourceWords.Length < 4 || sourceWords.Length > 32)
        {
            return false;
        }

        var requiredMatches = (int)Math.Ceiling(sourceWords.Length * (sourceWords.Length < 16 ? 0.80 : 0.75));
        var maxEdits = sourceWords.Length - requiredMatches;
        var minimumPromptLength = Math.Max(1, sourceWords.Length - maxEdits);
        if (promptWords.Count < minimumPromptLength)
        {
            return false;
        }

        var sharedWordCount = sourceWords
            .GroupBy(word => word, StringComparer.Ordinal)
            .Sum(group => promptWordPositions.TryGetValue(group.Key, out var promptIndexes)
                ? Math.Min(group.Count(), promptIndexes.Count)
                : 0);
        if (sharedWordCount < requiredMatches)
        {
            return false;
        }

        var candidateStarts = new HashSet<int>();
        var rarestAnchors = new List<(int SourceIndex, IReadOnlyList<int> PromptIndexes)>();
        var rarestPromptCount = int.MaxValue;
        for (var sourceIndex = 0; sourceIndex < sourceWords.Length; sourceIndex++)
        {
            if (!promptWordPositions.TryGetValue(sourceWords[sourceIndex], out var promptIndexes))
            {
                continue;
            }

            if (promptIndexes.Count < rarestPromptCount)
            {
                rarestPromptCount = promptIndexes.Count;
                rarestAnchors.Clear();
                rarestAnchors.Add((sourceIndex, promptIndexes));
            }
            else if (promptIndexes.Count == rarestPromptCount)
            {
                rarestAnchors.Add((sourceIndex, promptIndexes));
            }
        }

        if (rarestAnchors.Count == 0)
        {
            return false;
        }

        foreach (var (sourceIndex, promptIndexes) in rarestAnchors)
        {
            foreach (var promptIndex in promptIndexes)
            {
                var alignedStart = promptIndex - sourceIndex;
                for (var offset = -maxEdits; offset <= maxEdits; offset++)
                {
                    var candidateStart = alignedStart + offset;
                    if (candidateStart >= 0 && candidateStart + minimumPromptLength <= promptWords.Count)
                    {
                        candidateStarts.Add(candidateStart);
                    }
                }
            }
        }

        foreach (var start in candidateStarts)
        {
            var maximumPromptLength = Math.Min(promptWords.Count - start, sourceWords.Length + maxEdits);
            for (var promptLength = minimumPromptLength; promptLength <= maximumPromptLength; promptLength++)
            {
                if (HasTokenEditDistanceAtMost(sourceWords, promptWords, start, promptLength, maxEdits))
                {
                    return true;
                }
            }
        }

        return false;
    }

    private static bool HasTokenEditDistanceAtMost(
        IReadOnlyList<string> sourceWords,
        IReadOnlyList<string> promptWords,
        int promptStart,
        int promptLength,
        int maxEdits)
    {
        if (Math.Abs(sourceWords.Count - promptLength) > maxEdits)
        {
            return false;
        }

        var previous = new int[promptLength + 1];
        var current = new int[promptLength + 1];
        for (var promptIndex = 0; promptIndex <= promptLength; promptIndex++)
        {
            previous[promptIndex] = promptIndex;
        }

        for (var sourceIndex = 1; sourceIndex <= sourceWords.Count; sourceIndex++)
        {
            current[0] = sourceIndex;
            var rowMinimum = current[0];
            for (var promptIndex = 1; promptIndex <= promptLength; promptIndex++)
            {
                var substitutionCost = string.Equals(
                    sourceWords[sourceIndex - 1],
                    promptWords[promptStart + promptIndex - 1],
                    StringComparison.Ordinal)
                    ? 0
                    : 1;
                current[promptIndex] = Math.Min(
                    Math.Min(previous[promptIndex] + 1, current[promptIndex - 1] + 1),
                    previous[promptIndex - 1] + substitutionCost);
                rowMinimum = Math.Min(rowMinimum, current[promptIndex]);
            }

            if (rowMinimum > maxEdits)
            {
                return false;
            }

            (previous, current) = (current, previous);
        }

        return previous[promptLength] <= maxEdits;
    }

    private static IReadOnlyDictionary<string, IReadOnlyList<int>> BuildWordPositions(IReadOnlyList<string> words)
    {
        var positions = new Dictionary<string, List<int>>(StringComparer.Ordinal);
        for (var index = 0; index < words.Count; index++)
        {
            if (!positions.TryGetValue(words[index], out var indexes))
            {
                indexes = [];
                positions[words[index]] = indexes;
            }
            indexes.Add(index);
        }

        return positions.ToDictionary(
            item => item.Key,
            item => (IReadOnlyList<int>)item.Value,
            StringComparer.Ordinal);
    }

    private static string NormalizeForMatch(string value)
    {
        return Regex.Replace(
            value.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n'),
            @"\s+",
            " ").Trim().ToLowerInvariant();
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
}

public sealed record HostedRouteForbiddenSourceScan(
    [property: System.Text.Json.Serialization.JsonPropertyName("policy_version")] string PolicyVersion,
    [property: System.Text.Json.Serialization.JsonPropertyName("prompt_hash")] string PromptHash,
    [property: System.Text.Json.Serialization.JsonPropertyName("patterns")] IReadOnlyList<string> Patterns,
    [property: System.Text.Json.Serialization.JsonPropertyName("forbidden_content_hashes")] IReadOnlyList<string> ForbiddenContentHashes,
    [property: System.Text.Json.Serialization.JsonPropertyName("matched_content_hashes")] IReadOnlyList<string> MatchedContentHashes,
    [property: System.Text.Json.Serialization.JsonPropertyName("fingerprint_set_status")] string FingerprintSetStatus,
    [property: System.Text.Json.Serialization.JsonPropertyName("allowed_source_references")] IReadOnlyList<string> AllowedSourceReferences,
    [property: System.Text.Json.Serialization.JsonPropertyName("violations")] IReadOnlyList<string> Violations,
    [property: System.Text.Json.Serialization.JsonPropertyName("status")] string Status);

public sealed record HostedRouteForbiddenContentFingerprint(
    string SourceId,
    string ContentHash,
    string Content);
