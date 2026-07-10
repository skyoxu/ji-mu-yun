using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GddToModuleSplitAddedRequirements
{
    public const string LedgerId = "phase-a-gdd-to-module-split-added-requirements";
    public const string LedgerVersion = "v1";
    public const string ExecutionPlanLedgerPath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/97-split-added-requirements-ledger.md";
    public const string WorkflowDocPath = "docs/workflows/phase-a-gdd-to-module-split-added-requirements.md";
    public const string SchemaExamplePath = "docs/schemas/gdd-to-module-split-added-requirements.v1.example.json";

    public static readonly IReadOnlyList<string> LedgerColumns =
    [
        "split_added_id",
        "Requirement",
        "Primary owner doc",
        "Acceptance reference"
    ];

    public static readonly IReadOnlyList<string> CoverageStatuses =
    [
        "implemented",
        "not_applicable",
        "explicitly_deferred"
    ];

    public static readonly IReadOnlyList<string> RequiredCoverageFields =
    [
        "split_added_id",
        "coverage_status",
        "owner_doc_refs",
        "acceptance_evidence_refs",
        "phase_exit_review_ref",
        "owner",
        "expiry_or_recheck_trigger",
        "defer_reason"
    ];

    public static readonly string LedgerHash = ComputeHash();

    public static IReadOnlyList<SplitAddedRequirementRow> ParseLedger(string markdown)
    {
        var lines = markdown.Replace("\r\n", "\n").Split('\n');
        var tableStart = Array.FindIndex(lines, line => line.StartsWith("| split_added_id | Requirement | Primary owner doc |", StringComparison.Ordinal));
        if (tableStart < 0 || tableStart + 2 >= lines.Length)
        {
            return [];
        }

        var rows = new List<SplitAddedRequirementRow>();
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

            if (cells.Length != LedgerColumns.Count)
            {
                rows.Add(new SplitAddedRequirementRow(
                    cells.ElementAtOrDefault(0) ?? string.Empty,
                    cells.ElementAtOrDefault(1) ?? string.Empty,
                    [],
                    cells.ElementAtOrDefault(3) ?? string.Empty,
                    cells.Length));
                continue;
            }

            rows.Add(new SplitAddedRequirementRow(
                cells[0],
                cells[1],
                ExtractCodeRefs(cells[2]),
                cells[3],
                cells.Length));
        }

        return rows;
    }

    public static IReadOnlyList<SplitAddedRequirementIssue> ValidateLedgerRows(IEnumerable<SplitAddedRequirementRow> rows)
    {
        var materialized = rows.ToArray();
        var issues = new List<SplitAddedRequirementIssue>();
        var ids = new HashSet<string>(StringComparer.Ordinal);

        foreach (var row in materialized)
        {
            if (!ids.Add(row.SplitAddedId))
            {
                issues.Add(Issue(row.SplitAddedId, "duplicate_split_added_id"));
            }

            if (!row.SplitAddedId.StartsWith("split_added_", StringComparison.Ordinal))
            {
                issues.Add(Issue(row.SplitAddedId, "invalid_split_added_id"));
            }

            if (row.CellCount != LedgerColumns.Count)
            {
                issues.Add(Issue(row.SplitAddedId, "wrong_cell_count"));
            }

            if (string.IsNullOrWhiteSpace(row.Requirement))
            {
                issues.Add(Issue(row.SplitAddedId, "missing_requirement"));
            }

            if (row.PrimaryOwnerDocs.Count == 0)
            {
                issues.Add(Issue(row.SplitAddedId, "missing_primary_owner_doc"));
            }

            if (string.IsNullOrWhiteSpace(row.AcceptanceReference))
            {
                issues.Add(Issue(row.SplitAddedId, "missing_acceptance_reference"));
            }
        }

        return issues;
    }

    public static IReadOnlyList<SplitAddedRequirementIssue> ValidateCoverage(
        IEnumerable<SplitAddedRequirementRow> ledgerRows,
        IEnumerable<SplitAddedRequirementCoverageRow> coverageRows)
    {
        var ledger = ledgerRows.ToDictionary(row => row.SplitAddedId, StringComparer.Ordinal);
        var coverage = coverageRows.ToArray();
        var issues = new List<SplitAddedRequirementIssue>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        foreach (var row in coverage)
        {
            if (!seen.Add(row.SplitAddedId))
            {
                issues.Add(Issue(row.SplitAddedId, "duplicate_coverage_row"));
            }

            if (!ledger.TryGetValue(row.SplitAddedId, out var ledgerRow))
            {
                issues.Add(Issue(row.SplitAddedId, "orphan_coverage_row"));
                continue;
            }

            if (!CoverageStatuses.Contains(row.CoverageStatus, StringComparer.Ordinal))
            {
                issues.Add(Issue(row.SplitAddedId, "invalid_coverage_status"));
            }

            if (!ledgerRow.PrimaryOwnerDocs.All(owner => row.OwnerDocRefs.Contains(owner, StringComparer.Ordinal)))
            {
                issues.Add(Issue(row.SplitAddedId, "coverage_missing_primary_owner_doc_ref"));
            }

            if (row.AcceptanceEvidenceRefs.Count == 0 || string.IsNullOrWhiteSpace(row.PhaseExitReviewRef))
            {
                issues.Add(Issue(row.SplitAddedId, "coverage_missing_acceptance_or_phase_evidence"));
            }

            if ((row.CoverageStatus == "not_applicable" || row.CoverageStatus == "explicitly_deferred") &&
                (string.IsNullOrWhiteSpace(row.Owner) ||
                 string.IsNullOrWhiteSpace(row.ExpiryOrRecheckTrigger) ||
                 string.IsNullOrWhiteSpace(row.DeferReason)))
            {
                issues.Add(Issue(row.SplitAddedId, "deferred_or_not_applicable_missing_owner_recheck_or_reason"));
            }
        }

        foreach (var id in ledger.Keys)
        {
            if (!seen.Contains(id))
            {
                issues.Add(Issue(id, "missing_coverage_row"));
            }
        }

        return issues;
    }

    private static IReadOnlyList<string> ExtractCodeRefs(string value)
    {
        var refs = new List<string>();
        var parts = value.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        foreach (var part in parts)
        {
            var trimmed = part.Trim();
            if (trimmed.Length >= 2 && trimmed[0] == '`' && trimmed[^1] == '`')
            {
                refs.Add(trimmed[1..^1]);
            }
            else if (!string.IsNullOrWhiteSpace(trimmed))
            {
                refs.Add(trimmed);
            }
        }

        return refs;
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

    private static SplitAddedRequirementIssue Issue(string splitAddedId, string reason)
    {
        return new SplitAddedRequirementIssue(splitAddedId, reason);
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n",
            LedgerColumns
                .Concat(CoverageStatuses)
                .Concat(RequiredCoverageFields));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }
}

public sealed record SplitAddedRequirementRow(
    string SplitAddedId,
    string Requirement,
    IReadOnlyList<string> PrimaryOwnerDocs,
    string AcceptanceReference,
    int CellCount);

public sealed record SplitAddedRequirementCoverageRow(
    string SplitAddedId,
    string CoverageStatus,
    IReadOnlyList<string> OwnerDocRefs,
    IReadOnlyList<string> AcceptanceEvidenceRefs,
    string PhaseExitReviewRef,
    string Owner,
    string ExpiryOrRecheckTrigger,
    string DeferReason);

public sealed record SplitAddedRequirementIssue(string SplitAddedId, string Reason);
