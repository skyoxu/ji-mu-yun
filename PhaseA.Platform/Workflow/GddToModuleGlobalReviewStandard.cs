using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GddToModuleGlobalReviewStandard
{
    public const string StandardId = "phase-a-gdd-to-module-global-review-standard";
    public const string StandardVersion = "v1";
    public const string ExecutionPlanStandardPath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/96-global-review-standard.md";
    public const string WorkflowDocPath = "docs/workflows/phase-a-gdd-to-module-global-review-standard.md";
    public const string SchemaExamplePath = "docs/schemas/gdd-to-module-global-review-standard.v1.example.json";
    public const string SplitDirectory = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/";

    public static readonly IReadOnlyList<string> AuthorityFiles =
    [
        "AGENTS.md",
        "README.md",
        ExecutionPlanStandardPath
    ];

    public static readonly IReadOnlyList<ReviewModeDefinition> ReviewModes =
    [
        Mode("whole-directory", "Full split refactor directory review", true),
        Mode("standard-only", "Only the global review standard file is the target", false),
        Mode("standard-change-self-review", "Changed standard file before applying the changed standard", false)
    ];

    public static readonly IReadOnlyList<string> RequiredSections =
    [
        "Authority Set",
        "Review Modes",
        "Normative Requirement Rule",
        "Standard Change Protocol",
        "Standard Self-Review Gate",
        "Standard Change Log",
        "Required Review Inputs",
        "Complete-Read Rule",
        "Required Review Method",
        "Minimum Mechanical Checks",
        "Scoped Mechanical Checks",
        "Severity Standard",
        "Prior Finding Ledger",
        "Finding Close Format",
        "Review Output Requirements",
        "Review Completion Bar"
    ];

    public static readonly IReadOnlyList<string> WholeDirectoryMechanicalChecks =
    [
        "file_inventory",
        "link_integrity",
        "json_validity",
        "ledger_and_audit_alignment",
        "status_action_schema_vocabulary_consistency"
    ];

    public static readonly IReadOnlyList<string> ScopedMechanicalChecks =
    [
        "authority_file_read_coverage",
        "standard_structure_and_ledger_validity",
        "internal_reference_checks",
        "open_ledger_blocker_checks",
        "standard_change_completeness"
    ];

    public static readonly IReadOnlyList<string> PriorFindingLedgerColumns =
    [
        "finding_id",
        "Severity",
        "Summary",
        "First found",
        "Status",
        "Fix reference",
        "Closure reason",
        "Linked finding",
        "Validation method"
    ];

    public static readonly IReadOnlyList<string> ReviewOutputRequirementIds =
    [
        "state_review_mode",
        "state_standard_change_ids",
        "state_authority_set",
        "state_self_review_gate",
        "mechanical_check_summary",
        "findings_first_by_severity",
        "stable_finding_ids",
        "p0_p1_p2_labels",
        "file_line_references",
        "global_impact",
        "separate_target_findings_from_open_blockers",
        "avoid_optional_issues",
        "skipped_mechanical_checks"
    ];

    public static readonly IReadOnlyList<string> SeverityValues =
    [
        "P0",
        "P1",
        "P2"
    ];

    public static readonly IReadOnlyList<string> FindingStatuses =
    [
        "Open",
        "Closed",
        "OutOfScopeByStandardChange"
    ];

    public static readonly string StandardHash = ComputeHash();

    public static IReadOnlyList<PriorFindingRow> ParsePriorFindingLedger(string markdown)
    {
        var lines = markdown.Replace("\r\n", "\n").Split('\n');
        var tableStart = Array.FindIndex(lines, line => line.StartsWith("| finding_id | Severity | Summary |", StringComparison.Ordinal));
        if (tableStart < 0 || tableStart + 2 >= lines.Length)
        {
            return [];
        }

        var rows = new List<PriorFindingRow>();
        for (var index = tableStart + 2; index < lines.Length; index++)
        {
            var line = lines[index];
            if (!line.StartsWith('|') || string.IsNullOrWhiteSpace(line.Trim('|', ' ')))
            {
                break;
            }

            var cells = line.Split('|')
                .Skip(1)
                .SkipLast(1)
                .Select(CleanCell)
                .ToArray();
            if (cells.Length != PriorFindingLedgerColumns.Count)
            {
                rows.Add(new PriorFindingRow(
                    cells.ElementAtOrDefault(0) ?? string.Empty,
                    cells.ElementAtOrDefault(1) ?? string.Empty,
                    cells.ElementAtOrDefault(4) ?? string.Empty,
                    cells.ElementAtOrDefault(5) ?? string.Empty,
                    cells.ElementAtOrDefault(6) ?? string.Empty,
                    cells.ElementAtOrDefault(7) ?? string.Empty,
                    cells.ElementAtOrDefault(8) ?? string.Empty,
                    cells.Length));
                continue;
            }

            rows.Add(new PriorFindingRow(
                cells[0],
                cells[1],
                cells[4],
                cells[5],
                cells[6],
                cells[7],
                cells[8],
                cells.Length));
        }

        return rows;
    }

    public static IReadOnlyList<GlobalReviewStandardIssue> ValidatePriorFindingLedger(IEnumerable<PriorFindingRow> rows)
    {
        var materialized = rows.ToArray();
        var issues = new List<GlobalReviewStandardIssue>();
        var ids = new HashSet<string>(StringComparer.Ordinal);

        foreach (var row in materialized)
        {
            if (!ids.Add(row.FindingId))
            {
                issues.Add(Issue(row.FindingId, "duplicate_finding_id"));
            }

            if (row.CellCount != PriorFindingLedgerColumns.Count)
            {
                issues.Add(Issue(row.FindingId, "wrong_cell_count"));
            }

            if (!SeverityValues.Contains(row.Severity, StringComparer.Ordinal))
            {
                issues.Add(Issue(row.FindingId, "invalid_severity"));
            }

            if (!FindingStatuses.Contains(row.Status, StringComparer.Ordinal))
            {
                issues.Add(Issue(row.FindingId, "invalid_status"));
            }

            if (row.Status == "Closed")
            {
                if (IsPlaceholder(row.FixReference) || IsPlaceholder(row.ClosureReason) || IsPlaceholder(row.ValidationMethod))
                {
                    issues.Add(Issue(row.FindingId, "closed_row_missing_closure_evidence"));
                }

                if (!row.ValidationMethod.Contains("Source refs:", StringComparison.Ordinal))
                {
                    issues.Add(Issue(row.FindingId, "closed_row_missing_source_refs"));
                }
            }

            if (!string.Equals(row.LinkedFinding, "None", StringComparison.Ordinal) &&
                !LooksLikeFindingId(row.LinkedFinding))
            {
                issues.Add(Issue(row.FindingId, "invalid_linked_finding"));
            }
        }

        return issues;
    }

    public static IReadOnlyList<string> OpenWholeDirectoryBlockerIds(IEnumerable<PriorFindingRow> rows)
    {
        return rows
            .Where(row => row.Status == "Open" && row.FindingId.StartsWith("GRD-", StringComparison.Ordinal))
            .Select(row => row.FindingId)
            .ToArray();
    }

    public static bool HasRequiredSections(string markdown)
    {
        return RequiredSections.All(section => markdown.Contains($"## {section}", StringComparison.Ordinal) ||
                                               markdown.Contains($"### {section}", StringComparison.Ordinal));
    }

    public static bool IsKnownReviewMode(string mode)
    {
        return ReviewModes.Any(item => string.Equals(item.ModeId, mode, StringComparison.Ordinal));
    }

    private static bool LooksLikeFindingId(string value)
    {
        return value.StartsWith("GRS-P", StringComparison.Ordinal) ||
               value.StartsWith("GRD-P", StringComparison.Ordinal);
    }

    private static bool IsPlaceholder(string value)
    {
        return string.IsNullOrWhiteSpace(value) ||
               string.Equals(value, "TBD", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(value, "None", StringComparison.OrdinalIgnoreCase);
    }

    private static string CleanCell(string cell)
    {
        var value = cell.Trim();
        if (value.Length >= 2 && value[0] == '`' && value[^1] == '`')
        {
            value = value[1..^1];
        }

        return value;
    }

    private static ReviewModeDefinition Mode(string modeId, string scope, bool wholeDirectoryCoverageAllowed)
    {
        return new ReviewModeDefinition(modeId, scope, wholeDirectoryCoverageAllowed);
    }

    private static GlobalReviewStandardIssue Issue(string findingId, string reason)
    {
        return new GlobalReviewStandardIssue(findingId, reason);
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n",
            AuthorityFiles
                .Concat(ReviewModes.Select(mode => $"{mode.ModeId}|{mode.Scope}|{mode.WholeDirectoryCoverageAllowed}"))
                .Concat(RequiredSections)
                .Concat(WholeDirectoryMechanicalChecks)
                .Concat(ScopedMechanicalChecks)
                .Concat(PriorFindingLedgerColumns)
                .Concat(ReviewOutputRequirementIds));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }
}

public sealed record ReviewModeDefinition(string ModeId, string Scope, bool WholeDirectoryCoverageAllowed);

public sealed record PriorFindingRow(
    string FindingId,
    string Severity,
    string Status,
    string FixReference,
    string ClosureReason,
    string LinkedFinding,
    string ValidationMethod,
    int CellCount);

public sealed record GlobalReviewStandardIssue(string FindingId, string Reason);
