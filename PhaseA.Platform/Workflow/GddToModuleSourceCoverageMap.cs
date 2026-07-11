using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace PhaseA.Platform.Workflow;

public static partial class GddToModuleSourceCoverageMap
{
    public const string CoverageMapId = "phase-a-gdd-to-module-source-coverage-map";
    public const string CoverageMapVersion = "v1";
    public const string ExecutionPlanCoveragePath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/99-source-coverage.md";
    public const string WorkflowDocPath = "docs/workflows/phase-a-gdd-to-module-source-coverage-map.md";
    public const string SchemaExamplePath = "docs/schemas/gdd-to-module-source-coverage-map.v1.example.json";
    public const int OriginalSourceLineCount = GddToModuleOriginalSplitAudit.OriginalSourceLineCount;

    public static readonly IReadOnlyList<string> RequiredSplitAddedBoundaryRefs =
    [
        "97-split-added-requirements-ledger.md",
        "04d-godot-engine-semantics-and-reference-examples.md"
    ];

    public static readonly IReadOnlyList<string> AllowedSplitAddedSourceRefs =
    [
        "schemas/gdd-to-module-capability-inventory.v1.json",
        "schemas/split-added-acceptance-registry.v1.json"
    ];

    public const int AllowedSplitAddedSourceRangeStart = 1378;
    public const int AllowedSplitAddedSourceRangeEnd = 2178;

    public static readonly string CoverageHash = ComputeHash();

    public static IReadOnlyList<SourceCoverageMapRow> ParseCoverageRows(string markdown)
    {
        var rows = new List<SourceCoverageMapRow>();
        var lines = markdown.Replace("\r\n", "\n").Split('\n');
        var tableStart = Array.FindIndex(lines, line => line.StartsWith("| Source lines | Split document |", StringComparison.Ordinal));
        if (tableStart < 0)
        {
            return rows;
        }

        for (var index = tableStart + 2; index < lines.Length; index++)
        {
            var line = lines[index];
            if (!line.StartsWith('|') || string.IsNullOrWhiteSpace(line.Trim('|', ' ')))
            {
                break;
            }

            var cells = line.Split('|').Skip(1).SkipLast(1).Select(cell => cell.Trim()).ToArray();
            if (cells.Length < 3)
            {
                continue;
            }

            var match = SourceRangeRegex().Match(cells[0]);
            if (!match.Success)
            {
                continue;
            }

            rows.Add(new SourceCoverageMapRow(
                int.Parse(match.Groups["start"].Value),
                int.Parse(match.Groups["end"].Value),
                ExtractMarkdownLinks(cells[1]),
                cells[2]));
        }

        return rows;
    }

    public static IReadOnlyList<SourceCoverageMapIssue> ValidateCoverageRows(IEnumerable<SourceCoverageMapRow> rows)
    {
        var auditRows = rows
            .Select(row => new SourceRangeCoverageRow(row.StartLine, row.EndLine, row.SplitDocuments, "Covered"))
            .ToArray();
        return GddToModuleOriginalSplitAudit.ValidateSourceRanges(auditRows)
            .Select(issue => new SourceCoverageMapIssue(issue.Reason, issue.Detail))
            .ToArray();
    }

    public static bool HasCoverageAssertion(string markdown)
    {
        return markdown.Contains("cover source lines 1-2739", StringComparison.Ordinal) &&
               markdown.Contains("no intentional omissions", StringComparison.Ordinal) &&
               markdown.Contains("machine-contract bundle", StringComparison.Ordinal) &&
               markdown.Contains("example fixture proves the complete field shape remains parseable", StringComparison.Ordinal);
    }

    public static bool HasSplitAddedBoundary(string markdown)
    {
        return RequiredSplitAddedBoundaryRefs.All(item => markdown.Contains(item, StringComparison.Ordinal)) &&
               markdown.Contains("original source-line coverage alone is not sufficient implementation readiness evidence", StringComparison.Ordinal);
    }

    public static bool MatchesOriginalSplitAudit(IReadOnlyList<SourceCoverageMapRow> coverageRows, IReadOnlyList<SourceRangeCoverageRow> auditRows)
    {
        if (coverageRows.Count != auditRows.Count)
        {
            return false;
        }

        for (var index = 0; index < coverageRows.Count; index++)
        {
            var coverage = coverageRows[index];
            var audit = auditRows[index];
            var additionalRefs = coverage.SplitDocuments.Except(audit.SplitOutputs, StringComparer.Ordinal).ToArray();
            if (coverage.StartLine != audit.StartLine ||
                coverage.EndLine != audit.EndLine ||
                HasDuplicates(coverage.SplitDocuments) ||
                HasDuplicates(audit.SplitOutputs) ||
                !IsOrderedSubset(audit.SplitOutputs, coverage.SplitDocuments) ||
                additionalRefs.Any(item => !AllowedSplitAddedSourceRefs.Contains(item, StringComparer.Ordinal)) ||
                (additionalRefs.Length > 0 &&
                 (coverage.StartLine != AllowedSplitAddedSourceRangeStart || coverage.EndLine != AllowedSplitAddedSourceRangeEnd)))
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsOrderedSubset(IReadOnlyList<string> expected, IReadOnlyList<string> actual)
    {
        var expectedIndex = 0;
        foreach (var item in actual)
        {
            if (expectedIndex < expected.Count &&
                string.Equals(expected[expectedIndex], item, StringComparison.Ordinal))
            {
                expectedIndex++;
            }
        }

        return expectedIndex == expected.Count;
    }

    private static bool HasDuplicates(IEnumerable<string> values)
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        return values.Any(value => !seen.Add(value));
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n",
            RequiredSplitAddedBoundaryRefs
                .Concat(AllowedSplitAddedSourceRefs)
                .Append($"{AllowedSplitAddedSourceRangeStart}-{AllowedSplitAddedSourceRangeEnd}")
                .Append(OriginalSourceLineCount.ToString()));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }

    private static IReadOnlyList<string> ExtractMarkdownLinks(string value)
    {
        return MarkdownLinkRegex()
            .Matches(value)
            .Select(match => match.Groups["target"].Value)
            .ToArray();
    }

    [GeneratedRegex(@"^(?<start>\d+)-(?<end>\d+)$", RegexOptions.CultureInvariant)]
    private static partial Regex SourceRangeRegex();

    [GeneratedRegex(@"\[[^\]]+\]\((?<target>[^)]+)\)", RegexOptions.CultureInvariant)]
    private static partial Regex MarkdownLinkRegex();
}

public sealed record SourceCoverageMapRow(
    int StartLine,
    int EndLine,
    IReadOnlyList<string> SplitDocuments,
    string Notes);

public sealed record SourceCoverageMapIssue(string Reason, string Detail);
