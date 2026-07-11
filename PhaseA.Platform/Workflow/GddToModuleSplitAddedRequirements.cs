using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace PhaseA.Platform.Workflow;

public static class GddToModuleSplitAddedRequirements
{
    public const string LedgerId = "phase-a-gdd-to-module-split-added-requirements";
    public const string LedgerVersion = "v1";
    public const string ExecutionPlanLedgerPath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/97-split-added-requirements-ledger.md";
    public const string WorkflowDocPath = "docs/workflows/phase-a-gdd-to-module-split-added-requirements.md";
    public const string SchemaExamplePath = "docs/schemas/gdd-to-module-split-added-requirements.v1.example.json";
    public const string AcceptanceRegistryPath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/schemas/split-added-acceptance-registry.v1.json";
    public const string AcceptanceRegistrySchemaVersion = "split-added-acceptance-registry.v1";
    public const string AcceptanceRegistryPathBase = "split_directory";

    public static readonly IReadOnlyList<string> LedgerColumns =
    [
        "split_added_id",
        "Requirement",
        "owner_id",
        "First required phase",
        "Primary owner docs",
        "acceptance_ids"
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
        "acceptance_ids",
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
        var tableStart = Array.FindIndex(lines, line => line.StartsWith("| split_added_id | Requirement | owner_id | First required phase | Primary owner docs | acceptance_ids |", StringComparison.Ordinal));
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
                .Select(cell => cell.Trim())
                .ToArray();

            if (cells.Length != LedgerColumns.Count)
            {
                rows.Add(new SplitAddedRequirementRow(
                    CleanCell(cells.ElementAtOrDefault(0) ?? string.Empty),
                    cells.ElementAtOrDefault(1) ?? string.Empty,
                    CleanCell(cells.ElementAtOrDefault(2) ?? string.Empty),
                    cells.ElementAtOrDefault(3) ?? string.Empty,
                    [],
                    [],
                    cells.Length));
                continue;
            }

            rows.Add(new SplitAddedRequirementRow(
                CleanCell(cells[0]),
                cells[1],
                CleanCell(cells[2]),
                cells[3],
                ExtractCodeRefs(cells[4]),
                ExtractCodeRefs(cells[5]),
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

            if (string.IsNullOrWhiteSpace(row.OwnerId))
            {
                issues.Add(Issue(row.SplitAddedId, "missing_owner_id"));
            }
            else if (!row.OwnerId.StartsWith("OWNER-", StringComparison.Ordinal))
            {
                issues.Add(Issue(row.SplitAddedId, "invalid_owner_id"));
            }

            if (string.IsNullOrWhiteSpace(row.FirstRequiredPhase))
            {
                issues.Add(Issue(row.SplitAddedId, "missing_first_required_phase"));
            }

            if (row.PrimaryOwnerDocs.Count == 0)
            {
                issues.Add(Issue(row.SplitAddedId, "missing_primary_owner_doc"));
            }
            else if (HasDuplicates(row.PrimaryOwnerDocs))
            {
                issues.Add(Issue(row.SplitAddedId, "duplicate_primary_owner_doc"));
            }

            if (row.AcceptanceIds.Count == 0)
            {
                issues.Add(Issue(row.SplitAddedId, "missing_acceptance_id"));
            }
            else if (HasDuplicates(row.AcceptanceIds))
            {
                issues.Add(Issue(row.SplitAddedId, "duplicate_acceptance_id"));
            }
        }

        return issues;
    }

    public static SplitAddedAcceptanceRegistry ParseAcceptanceRegistry(string json)
    {
        var issues = new List<SplitAddedRequirementIssue>();
        var owners = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
        var acceptanceRefs = new Dictionary<string, SplitAddedAcceptanceReference>(StringComparer.Ordinal);
        var expectedRequirements = new Dictionary<string, SplitAddedExpectedRequirement>(StringComparer.Ordinal);
        JsonDocument document;
        try
        {
            document = JsonDocument.Parse(json);
        }
        catch (JsonException)
        {
            issues.Add(Issue(AcceptanceRegistryPath, "invalid_registry_json"));
            return new SplitAddedAcceptanceRegistry("", "", owners, acceptanceRefs, expectedRequirements, issues);
        }

        using (document)
        {
            var root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                issues.Add(Issue(AcceptanceRegistryPath, "invalid_registry_root"));
                return new SplitAddedAcceptanceRegistry("", "", owners, acceptanceRefs, expectedRequirements, issues);
            }

            var schemaVersion = ReadRequiredString(root, "schema_version", AcceptanceRegistryPath, "missing_registry_schema_version", issues);
            var pathBase = ReadRequiredString(root, "path_base", AcceptanceRegistryPath, "missing_registry_path_base", issues);
            if (!string.IsNullOrWhiteSpace(schemaVersion) && !string.Equals(schemaVersion, AcceptanceRegistrySchemaVersion, StringComparison.Ordinal))
            {
                issues.Add(Issue(AcceptanceRegistryPath, "invalid_registry_schema_version"));
            }

            if (!string.IsNullOrWhiteSpace(pathBase) && !string.Equals(pathBase, AcceptanceRegistryPathBase, StringComparison.Ordinal))
            {
                issues.Add(Issue(AcceptanceRegistryPath, "invalid_registry_path_base"));
            }

            if (TryGetObject(root, "owners", AcceptanceRegistryPath, "missing_registry_owners", issues, out var ownersElement))
            {
                foreach (var property in ownersElement.EnumerateObject())
                {
                    var docs = ReadStringArray(property.Value, property.Name, "invalid_registry_owner_docs", issues);
                    if (docs.Count == 0)
                    {
                        issues.Add(Issue(property.Name, "missing_registry_owner_doc"));
                    }

                    if (HasDuplicates(docs))
                    {
                        issues.Add(Issue(property.Name, "duplicate_registry_owner_doc"));
                    }

                    if (!owners.TryAdd(property.Name, docs))
                    {
                        issues.Add(Issue(property.Name, "duplicate_owner_id"));
                    }
                }
            }

            if (TryGetObject(root, "acceptance_refs", AcceptanceRegistryPath, "missing_registry_acceptance_refs", issues, out var acceptanceElement))
            {
                foreach (var property in acceptanceElement.EnumerateObject())
                {
                    if (property.Value.ValueKind != JsonValueKind.Object)
                    {
                        issues.Add(Issue(property.Name, "invalid_acceptance_ref"));
                        continue;
                    }

                    var acceptanceReference = new SplitAddedAcceptanceReference(
                        ReadRequiredString(property.Value, "owner_id", property.Name, "missing_acceptance_ref_owner_id", issues),
                        ReadRequiredString(property.Value, "file", property.Name, "missing_acceptance_ref_file", issues),
                        ReadRequiredString(property.Value, "section", property.Name, "missing_acceptance_ref_section", issues),
                        ReadRequiredString(property.Value, "match_text", property.Name, "missing_acceptance_ref_match_text", issues));
                    if (!acceptanceRefs.TryAdd(property.Name, acceptanceReference))
                    {
                        issues.Add(Issue(property.Name, "duplicate_acceptance_id"));
                    }
                }
            }

            if (TryGetObject(root, "expected_split_added_requirements", AcceptanceRegistryPath, "missing_registry_expected_requirements", issues, out var expectedElement))
            {
                foreach (var property in expectedElement.EnumerateObject())
                {
                    if (property.Value.ValueKind != JsonValueKind.Object)
                    {
                        issues.Add(Issue(property.Name, "invalid_expected_requirement"));
                        continue;
                    }

                    var acceptanceIds = property.Value.TryGetProperty("acceptance_ids", out var idsElement)
                        ? ReadStringArray(idsElement, property.Name, "invalid_expected_acceptance_ids", issues)
                        : [];
                    if (!property.Value.TryGetProperty("acceptance_ids", out _))
                    {
                        issues.Add(Issue(property.Name, "missing_expected_acceptance_ids"));
                    }
                    else if (acceptanceIds.Count == 0)
                    {
                        issues.Add(Issue(property.Name, "missing_expected_acceptance_id"));
                    }

                    if (HasDuplicates(acceptanceIds))
                    {
                        issues.Add(Issue(property.Name, "duplicate_expected_acceptance_id"));
                    }

                    var expected = new SplitAddedExpectedRequirement(
                        ReadRequiredString(property.Value, "owner_id", property.Name, "missing_expected_owner_id", issues),
                        acceptanceIds);
                    if (!expectedRequirements.TryAdd(property.Name, expected))
                    {
                        issues.Add(Issue(property.Name, "duplicate_expected_requirement"));
                    }
                }
            }

            return new SplitAddedAcceptanceRegistry(schemaVersion, pathBase, owners, acceptanceRefs, expectedRequirements, issues);
        }
    }

    public static IReadOnlyList<SplitAddedRequirementIssue> ValidateAcceptanceRegistry(
        IEnumerable<SplitAddedRequirementRow> ledgerRows,
        SplitAddedAcceptanceRegistry registry)
    {
        var rows = ledgerRows.ToArray();
        var issues = new List<SplitAddedRequirementIssue>(registry.ParseIssues);
        var ledgerIds = rows.Select(row => row.SplitAddedId).ToHashSet(StringComparer.Ordinal);
        var referencedOwnerIds = new HashSet<string>(rows.Select(row => row.OwnerId), StringComparer.Ordinal);
        var referencedAcceptanceIds = new HashSet<string>(StringComparer.Ordinal);

        foreach (var row in rows)
        {
            if (!registry.Owners.ContainsKey(row.OwnerId))
            {
                issues.Add(Issue(row.SplitAddedId, "unknown_owner_id"));
            }

            if (!registry.ExpectedRequirements.TryGetValue(row.SplitAddedId, out var expected))
            {
                issues.Add(Issue(row.SplitAddedId, "missing_expected_requirement"));
            }
            else
            {
                if (!string.Equals(expected.OwnerId, row.OwnerId, StringComparison.Ordinal))
                {
                    issues.Add(Issue(row.SplitAddedId, "expected_owner_mismatch"));
                }

                if (!expected.AcceptanceIds.Order(StringComparer.Ordinal)
                        .SequenceEqual(row.AcceptanceIds.Order(StringComparer.Ordinal), StringComparer.Ordinal))
                {
                    issues.Add(Issue(row.SplitAddedId, "expected_acceptance_ids_mismatch"));
                }
            }

            foreach (var acceptanceId in row.AcceptanceIds)
            {
                referencedAcceptanceIds.Add(acceptanceId);
                if (!registry.AcceptanceRefs.TryGetValue(acceptanceId, out var acceptanceReference))
                {
                    issues.Add(Issue(row.SplitAddedId, "unknown_acceptance_id"));
                }
                else if (!string.Equals(acceptanceReference.OwnerId, row.OwnerId, StringComparison.Ordinal))
                {
                    issues.Add(Issue(row.SplitAddedId, "acceptance_owner_mismatch"));
                }
            }
        }

        foreach (var expectedId in registry.ExpectedRequirements.Keys.Where(id => !ledgerIds.Contains(id)))
        {
            issues.Add(Issue(expectedId, "orphan_expected_requirement"));
        }


        foreach (var acceptanceReference in registry.AcceptanceRefs.Values)
        {
            referencedOwnerIds.Add(acceptanceReference.OwnerId);
            if (!registry.Owners.ContainsKey(acceptanceReference.OwnerId))
            {
                issues.Add(Issue(acceptanceReference.OwnerId, "acceptance_ref_unknown_owner_id"));
            }
        }

        foreach (var ownerId in registry.Owners.Keys.Where(id => !referencedOwnerIds.Contains(id)))
        {
            issues.Add(Issue(ownerId, "orphan_owner_id"));
        }

        foreach (var acceptanceId in registry.AcceptanceRefs.Keys.Where(id =>
                     !referencedAcceptanceIds.Contains(id) && !IsSharedAcceptanceId(id)))
        {
            issues.Add(Issue(acceptanceId, "orphan_acceptance_id"));
        }

        return issues;
    }

    public static IReadOnlyList<SplitAddedRequirementIssue> ValidateCoverage(
        IEnumerable<SplitAddedRequirementRow> ledgerRows,
        IEnumerable<SplitAddedRequirementCoverageRow> coverageRows)
    {
        var ledger = ledgerRows.GroupBy(row => row.SplitAddedId, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
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


            if (HasDuplicates(row.AcceptanceIds) ||
                !row.AcceptanceIds.Order(StringComparer.Ordinal)
                    .SequenceEqual(ledgerRow.AcceptanceIds.Order(StringComparer.Ordinal), StringComparer.Ordinal))
            {
                issues.Add(Issue(row.SplitAddedId, "coverage_acceptance_ids_mismatch"));
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

    private static bool TryGetObject(
        JsonElement parent,
        string propertyName,
        string issueId,
        string missingReason,
        ICollection<SplitAddedRequirementIssue> issues,
        out JsonElement value)
    {
        if (!parent.TryGetProperty(propertyName, out value) || value.ValueKind != JsonValueKind.Object)
        {
            issues.Add(Issue(issueId, missingReason));
            value = default;
            return false;
        }

        return true;
    }

    private static string ReadRequiredString(
        JsonElement parent,
        string propertyName,
        string issueId,
        string missingReason,
        ICollection<SplitAddedRequirementIssue> issues)
    {
        if (!parent.TryGetProperty(propertyName, out var value) ||
            value.ValueKind != JsonValueKind.String ||
            string.IsNullOrWhiteSpace(value.GetString()))
        {
            issues.Add(Issue(issueId, missingReason));
            return string.Empty;
        }

        return value.GetString()!;
    }

    private static IReadOnlyList<string> ReadStringArray(
        JsonElement value,
        string issueId,
        string invalidReason,
        ICollection<SplitAddedRequirementIssue> issues)
    {
        if (value.ValueKind != JsonValueKind.Array)
        {
            issues.Add(Issue(issueId, invalidReason));
            return [];
        }

        var result = new List<string>();
        foreach (var item in value.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(item.GetString()))
            {
                issues.Add(Issue(issueId, invalidReason));
                continue;
            }

            result.Add(item.GetString()!);
        }

        return result;
    }

    private static bool HasDuplicates(IEnumerable<string> values)
    {
        var seen = new HashSet<string>(StringComparer.Ordinal);
        return values.Any(value => !seen.Add(value));
    }

    private static bool IsSharedAcceptanceId(string acceptanceId)
    {
        return acceptanceId.StartsWith("GUSC-AC-", StringComparison.Ordinal) ||
               acceptanceId.StartsWith("AC-CAPABILITY-INVENTORY-", StringComparison.Ordinal);
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
    string OwnerId,
    string FirstRequiredPhase,
    IReadOnlyList<string> PrimaryOwnerDocs,
    IReadOnlyList<string> AcceptanceIds,
    int CellCount);

public sealed record SplitAddedAcceptanceReference(
    string OwnerId,
    string File,
    string Section,
    string MatchText);

public sealed record SplitAddedExpectedRequirement(
    string OwnerId,
    IReadOnlyList<string> AcceptanceIds);

public sealed record SplitAddedAcceptanceRegistry(
    string SchemaVersion,
    string PathBase,
    IReadOnlyDictionary<string, IReadOnlyList<string>> Owners,
    IReadOnlyDictionary<string, SplitAddedAcceptanceReference> AcceptanceRefs,
    IReadOnlyDictionary<string, SplitAddedExpectedRequirement> ExpectedRequirements,
    IReadOnlyList<SplitAddedRequirementIssue> ParseIssues);

public sealed record SplitAddedRequirementCoverageRow(
    string SplitAddedId,
    string CoverageStatus,
    IReadOnlyList<string> AcceptanceIds,
    IReadOnlyList<string> OwnerDocRefs,
    IReadOnlyList<string> AcceptanceEvidenceRefs,
    string PhaseExitReviewRef,
    string Owner,
    string ExpiryOrRecheckTrigger,
    string DeferReason);

public sealed record SplitAddedRequirementIssue(string SplitAddedId, string Reason);
