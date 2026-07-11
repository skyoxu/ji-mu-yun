using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace PhaseA.Platform.Workflow;

public static partial class GddToModuleOriginalSplitAudit
{
    public const string AuditId = "phase-a-gdd-to-module-original-split-audit";
    public const string AuditVersion = "v1";
    public const string ExecutionPlanAuditPath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/98-original-to-split-audit.md";
    public const string SourceCoveragePath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/99-source-coverage.md";
    public const string WorkflowDocPath = "docs/workflows/phase-a-gdd-to-module-original-split-audit.md";
    public const string SchemaExamplePath = "docs/schemas/gdd-to-module-original-split-audit.v1.example.json";
    public const int OriginalSourceLineCount = 2739;

    public static readonly IReadOnlyList<string> RequiredInventoryEntries =
    [
        "00-index.md",
        "01-overview-workflow.md",
        "02a-route-state-artifacts.md",
        "02b-backend-api-contracts.md",
        "02c-frontend-migration-compatibility.md",
        "03-testing-observability-admin.md",
        "04a-route-contracts-and-guards.md",
        "04b-route-readback-recovery-and-freshness.md",
        "04c-route-operation-governance.md",
        "04d-godot-engine-semantics-and-reference-examples.md",
        "05-godot-ui-capability-contract.md",
        "06a-ui-style-migration-overview-and-catalog.md",
        "06b-ui-style-snapshot-schema.md",
        "schemas/godot-ui-style-contract.v1.profile.json",
        "schemas/godot-ui-style-contract.v1.field-map.json",
        "schemas/gdd-to-module-capability-inventory.v1.json",
        "schemas/split-added-acceptance-registry.v1.json",
        "schemas/workflow-action-contracts.v1.json",
        "schemas/godot-ui-style-contract.v1.example.json",
        "06c-style-aware-ui-closure.md",
        "06d-ui-style-schema-acceptance.md",
        "07-godot-diagnostics-quality-gates.md",
        "08-implementation-phases.md",
        "09-risks-dod-open-questions.md",
        "10-recommended-first-slice.md",
        "96-global-review-standard.md",
        "97-split-added-requirements-ledger.md",
        "98-original-to-split-audit.md",
        "99-source-coverage.md"
    ];

    public static readonly IReadOnlyList<string> RequiredNormalizationNotes =
    [
        "split_added_tracked_separately",
        "monolith_source_history_only",
        "no_new_normative_requirements_in_monolith",
        "post_split_04d_tracked_by_97",
        "commit_pr_readiness_includes_split_and_schemas",
        "style_schema_block_represented_by_json_fixture",
        "additive_hardening_not_omissions"
    ];

    public static readonly string AuditHash = ComputeHash();

    public static IReadOnlyList<SourceRangeCoverageRow> ParseSourceRanges(string markdown)
    {
        var rows = new List<SourceRangeCoverageRow>();
        var lines = markdown.Replace("\r\n", "\n").Split('\n');
        var tableStart = Array.FindIndex(lines, line => line.StartsWith("| Original source lines | Split output |", StringComparison.Ordinal));
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

            rows.Add(new SourceRangeCoverageRow(
                int.Parse(match.Groups["start"].Value),
                int.Parse(match.Groups["end"].Value),
                ExtractMarkdownLinks(cells[1]),
                cells[2]));
        }

        return rows;
    }

    public static IReadOnlyList<string> ParseSplitOutputInventory(string markdown)
    {
        var entries = new List<string>();
        var lines = markdown.Replace("\r\n", "\n").Split('\n');
        var tableStart = Array.FindIndex(lines, line => line.StartsWith("| Split output | Purpose |", StringComparison.Ordinal));
        if (tableStart < 0)
        {
            return entries;
        }

        for (var index = tableStart + 2; index < lines.Length; index++)
        {
            var line = lines[index];
            if (!line.StartsWith('|') || string.IsNullOrWhiteSpace(line.Trim('|', ' ')))
            {
                break;
            }

            var firstCell = line.Split('|').Skip(1).FirstOrDefault()?.Trim() ?? string.Empty;
            entries.AddRange(ExtractMarkdownLinks(firstCell));
        }

        return entries;
    }

    public static IReadOnlyList<OriginalSplitAuditIssue> ValidateSourceRanges(IEnumerable<SourceRangeCoverageRow> rows)
    {
        var ordered = rows.OrderBy(row => row.StartLine).ToArray();
        var issues = new List<OriginalSplitAuditIssue>();
        var expectedStart = 1;

        foreach (var row in ordered)
        {
            if (row.StartLine != expectedStart)
            {
                issues.Add(Issue("source_range_gap_or_overlap", $"{row.StartLine}-{row.EndLine} expected {expectedStart}"));
            }

            if (row.EndLine < row.StartLine)
            {
                issues.Add(Issue("source_range_invalid", $"{row.StartLine}-{row.EndLine}"));
            }

            if (!row.CoverageResult.Contains("Covered", StringComparison.Ordinal))
            {
                issues.Add(Issue("source_range_not_covered", $"{row.StartLine}-{row.EndLine}"));
            }

            if (row.SplitOutputs.Count == 0)
            {
                issues.Add(Issue("source_range_missing_split_output", $"{row.StartLine}-{row.EndLine}"));
            }

            expectedStart = row.EndLine + 1;
        }

        if (expectedStart != OriginalSourceLineCount + 1)
        {
            issues.Add(Issue("source_range_does_not_reach_original_end", $"{expectedStart - 1}"));
        }

        return issues;
    }

    public static IReadOnlyList<OriginalSplitAuditIssue> ValidateInventory(IEnumerable<string> inventoryEntries)
    {
        var entries = inventoryEntries.ToHashSet(StringComparer.Ordinal);
        var issues = new List<OriginalSplitAuditIssue>();

        foreach (var required in RequiredInventoryEntries)
        {
            if (!entries.Contains(required))
            {
                issues.Add(Issue("missing_inventory_entry", required));
            }
        }

        foreach (var duplicate in inventoryEntries.GroupBy(item => item, StringComparer.Ordinal).Where(group => group.Count() > 1))
        {
            issues.Add(Issue("duplicate_inventory_entry", duplicate.Key));
        }

        foreach (var unexpected in entries.Where(item => !RequiredInventoryEntries.Contains(item, StringComparer.Ordinal)))
        {
            issues.Add(Issue("unexpected_inventory_entry", unexpected));
        }

        return issues;
    }

    public static bool HasSourceHistoryBoundary(string markdown)
    {
        return markdown.Contains("source history only", StringComparison.Ordinal) &&
               markdown.Contains("must not be added to the monolithic source document", StringComparison.Ordinal) &&
               markdown.Contains("no untracked split-plan files", StringComparison.Ordinal);
    }

    private static IReadOnlyList<string> ExtractMarkdownLinks(string value)
    {
        return MarkdownLinkRegex()
            .Matches(value)
            .Select(match => match.Groups["target"].Value)
            .ToArray();
    }

    private static OriginalSplitAuditIssue Issue(string reason, string detail)
    {
        return new OriginalSplitAuditIssue(reason, detail);
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n",
            RequiredInventoryEntries
                .Concat(RequiredNormalizationNotes)
                .Append(OriginalSourceLineCount.ToString()));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }

    [GeneratedRegex(@"^(?<start>\d+)-(?<end>\d+)$", RegexOptions.CultureInvariant)]
    private static partial Regex SourceRangeRegex();

    [GeneratedRegex(@"\[[^\]]+\]\((?<target>[^)]+)\)", RegexOptions.CultureInvariant)]
    private static partial Regex MarkdownLinkRegex();
}

public sealed record SourceRangeCoverageRow(
    int StartLine,
    int EndLine,
    IReadOnlyList<string> SplitOutputs,
    string CoverageResult);

public sealed record OriginalSplitAuditIssue(string Reason, string Detail);
