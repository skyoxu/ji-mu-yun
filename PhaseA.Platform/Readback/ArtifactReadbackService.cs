using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace PhaseA.Platform.Readback;

public sealed class ArtifactReadbackService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;

    public ArtifactReadbackService(PhaseAMetadataStore metadataStore, PhaseAPlatformOptions options, HeavyRunnerQueueService? heavyRunnerQueue = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
    }

    public Task<IReadOnlyList<ProjectListItem>> ListProjectsAsync(string accountId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.ListProjectsAsync(accountId, cancellationToken);
    }

    public async Task<ActiveRunReadback> GetActiveRunAsync(string accountId, CancellationToken cancellationToken = default)
    {
        var run = await _metadataStore.GetActiveRunForAccountAsync(accountId, cancellationToken);
        var queue = _heavyRunnerQueue.GetReadback(accountId, includeAll: false);
        return run is null
            ? new ActiveRunReadback(
                queue.CurrentAccountPosition.HasValue,
                null,
                null,
                null,
                null,
                null,
                null,
                queue.QueuedCount,
                queue.CurrentAccountPosition,
                queue.CurrentAccountEstimatedWaitSeconds,
                queue.Running)
            : new ActiveRunReadback(
                true,
                run.RunId,
                run.ProjectId,
                run.RunType,
                run.Status,
                run.ProgressStep,
                run.ProgressLabel,
                queue.QueuedCount,
                queue.CurrentAccountPosition,
                queue.CurrentAccountEstimatedWaitSeconds,
                queue.Running);
    }

    public HeavyRunnerQueueReadback GetHeavyRunnerQueue(string accountId, bool includeAll = false)
    {
        return _heavyRunnerQueue.GetReadback(accountId, includeAll);
    }

    public async Task<AccountLlmUsageReadback> GetAccountLlmUsageAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        var costJson = await _metadataStore.ListAccountLlmCostJsonForUtcDayAsync(accountId, today, cancellationToken);
        var recent = await _metadataStore.ListLlmRunsForAccountAsync(accountId, limit: 20, cancellationToken);
        var items = new List<RunReadbackItem>();
        foreach (var run in recent)
        {
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(run.RunId, cancellationToken);
            items.Add(RunReadbackItem.FromSnapshot(run, artifacts));
        }

        return new AccountLlmUsageReadback(
            today.ToString("O", CultureInfo.InvariantCulture),
            costJson.Count,
            costJson.Sum(ReadEstimatedCostCny),
            items);
    }

    public async Task<AdminLlmUsageReadback> GetAdminLlmUsageAsync(CancellationToken cancellationToken = default)
    {
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        var accounts = await _metadataStore.ListAccountsAsync(cancellationToken);
        var items = new List<AdminLlmAccountUsageItem>();
        foreach (var account in accounts)
        {
            var costJson = await _metadataStore.ListAccountLlmCostJsonForUtcDayAsync(account.AccountId, today, cancellationToken);
            items.Add(new AdminLlmAccountUsageItem(
                account.AccountId,
                account.Username,
                account.IsAdmin,
                account.IsDisabled,
                account.ProjectCount,
                costJson.Count,
                costJson.Sum(ReadEstimatedCostCny)));
        }

        return new AdminLlmUsageReadback(
            today.ToString("O", CultureInfo.InvariantCulture),
            items.Count,
            items.Sum(item => item.CallCount),
            items.Sum(item => item.EstimatedCostCny),
            items);
    }

    public async Task<AdminLlmRunAuditReadback> GetAdminLlmRunAuditAsync(
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        var boundedLimit = Math.Clamp(limit, 1, 200);
        var rows = await _metadataStore.ListLlmRunsForAdminAsync(boundedLimit, cancellationToken);
        var items = rows.Select(row => new AdminLlmRunAuditItem(
            row.Account.AccountId,
            row.Account.Username,
            row.Run.ProjectId,
            row.Run.RunId,
            row.Run.RunType,
            row.Run.Status,
            row.Run.LlmGateway,
            row.Run.LlmModel,
            row.Run.LlmRequestId,
            row.Run.LlmCostJson)).ToArray();
        return new AdminLlmRunAuditReadback(items.Length, items);
    }

    public async Task<AdminRunMetricsReadback> GetAdminRunMetricsAsync(
        string? accountId,
        string? runType,
        int limit = 200,
        CancellationToken cancellationToken = default)
    {
        var boundedLimit = Math.Clamp(limit, 1, 500);
        var rows = await _metadataStore.ListRunMetricsForAdminAsync(accountId, runType, boundedLimit, cancellationToken);
        var includeChatAverages = string.IsNullOrWhiteSpace(runType) ||
                                  string.Equals(runType.Trim(), "prototype-chat", StringComparison.OrdinalIgnoreCase);
        var chatRows = includeChatAverages
            ? await _metadataStore.ListChatRunMetricsForAdminAsync(accountId, cancellationToken)
            : Array.Empty<AdminChatRunMetricsRow>();
        var nonChatRuns = rows
            .Where(row => !string.Equals(row.Run.RunType, "prototype-chat", StringComparison.OrdinalIgnoreCase))
            .Select(row => new AdminRunMetricsItem(
                row.AccountId,
                row.Username,
                row.ProjectId,
                row.ProjectName,
                row.GameName,
                row.Run.RunId,
                row.Run.RunType,
                row.Run.Status,
                row.Run.CreatedUtc,
                row.Run.StartedUtc,
                row.Run.FinishedUtc,
                row.Run.QueuePositionAtStart,
                SecondsBetween(row.Run.CreatedUtc, row.Run.StartedUtc),
                SecondsBetween(row.Run.StartedUtc, row.Run.FinishedUtc)))
            .ToArray();
        var chatAverages = chatRows
            .Select(row => new AdminChatRunMetricsItem(
                row.AccountId,
                row.Username,
                row.RunCount,
                row.AverageQueueSeconds,
                row.AverageRuntimeSeconds))
            .ToArray();

        return new AdminRunMetricsReadback(nonChatRuns.Length, nonChatRuns, chatAverages);
    }

    public async Task<AdminLlmUsageAggregateReadback> GetAdminLlmUsageAggregateAsync(
        string? grain,
        string? split,
        string? fromUtc,
        string? toUtc,
        CancellationToken cancellationToken = default)
    {
        var normalizedGrain = NormalizeGrain(grain);
        var normalizedSplit = NormalizeSplit(split);
        var (from, to) = NormalizeRange(fromUtc, toUtc, normalizedGrain);
        var rows = await _metadataStore.ListLlmUsageRowsForAdminAsync(
            from.ToString("O", CultureInfo.InvariantCulture),
            to.ToString("O", CultureInfo.InvariantCulture),
            cancellationToken);

        var groups = rows
            .GroupBy(row =>
            {
                var bucket = BucketUtc(DateTimeOffset.Parse(row.CreatedUtc, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind), normalizedGrain);
                var projectId = normalizedSplit is "project" or "account-project" ? row.ProjectId : null;
                return new
                {
                    Bucket = bucket,
                    row.AccountId,
                    row.Username,
                    ProjectId = projectId,
                    ProjectName = projectId is null ? null : row.ProjectName,
                    GameName = projectId is null ? null : row.GameName
                };
            })
            .Select(group => new AdminLlmUsageAggregateItem(
                group.Key.Bucket.ToString("O", CultureInfo.InvariantCulture),
                group.Key.AccountId,
                group.Key.Username,
                group.Key.ProjectId,
                group.Key.ProjectName,
                group.Key.GameName,
                group.Count(),
                group.Sum(row => ReadEstimatedCostCny(row.LlmCostJson))))
            .OrderByDescending(item => item.BucketUtc, StringComparer.Ordinal)
            .ThenBy(item => item.Username, StringComparer.OrdinalIgnoreCase)
            .ThenBy(item => item.ProjectName, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        return new AdminLlmUsageAggregateReadback(
            normalizedGrain,
            normalizedSplit,
            from.ToString("O", CultureInfo.InvariantCulture),
            to.ToString("O", CultureInfo.InvariantCulture),
            groups.Select(item => item.BucketUtc).Distinct(StringComparer.Ordinal).Count(),
            groups.Sum(item => item.CallCount),
            groups.Sum(item => item.EstimatedCostCny),
            groups);
    }

    public static string ExportAdminLlmUsageCsv(AdminLlmUsageReadback usage)
    {
        ArgumentNullException.ThrowIfNull(usage);

        var builder = new StringBuilder();
        builder.AppendLine("utc_day,account_id,username,is_admin,is_disabled,project_count,llm_call_count,estimated_cost_cny");
        foreach (var account in usage.Accounts)
        {
            builder
                .Append(Csv(usage.UtcDay)).Append(',')
                .Append(Csv(account.AccountId)).Append(',')
                .Append(Csv(account.Username)).Append(',')
                .Append(account.IsAdmin ? "true" : "false").Append(',')
                .Append(account.IsDisabled ? "true" : "false").Append(',')
                .Append(account.ProjectCount.ToString(CultureInfo.InvariantCulture)).Append(',')
                .Append(account.CallCount.ToString(CultureInfo.InvariantCulture)).Append(',')
                .Append(account.EstimatedCostCny.ToString(CultureInfo.InvariantCulture))
                .AppendLine();
        }

        return builder.ToString();
    }

    public static string ExportAdminAccountAuditCsv(IReadOnlyList<AdminAccountAuditEvent> events)
    {
        ArgumentNullException.ThrowIfNull(events);

        var builder = new StringBuilder();
        builder.AppendLine("event_id,actor_account_id,action,target_account_id,created_utc,metadata_json");
        foreach (var item in events)
        {
            builder
                .Append(Csv(item.EventId)).Append(',')
                .Append(Csv(item.ActorAccountId)).Append(',')
                .Append(Csv(item.Action)).Append(',')
                .Append(Csv(item.TargetAccountId)).Append(',')
                .Append(Csv(item.CreatedUtc)).Append(',')
                .Append(Csv(item.MetadataJson))
                .AppendLine();
        }

        return builder.ToString();
    }

    public Task<ProjectCreationFailureSnapshot?> GetLatestProjectCreationFailureAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        return _metadataStore.GetLatestProjectCreationFailureAsync(accountId, cancellationToken);
    }

    public async Task<ProjectRunsReadback?> GetProjectRunsAsync(string projectId, CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        var items = new List<RunReadbackItem>();
        foreach (var run in runs)
        {
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(run.RunId, cancellationToken);
            items.Add(RunReadbackItem.FromSnapshot(run, artifacts));
        }

        return new ProjectRunsReadback(project, items, ReadProjectHealthSummary(project.RepoPath));
    }

    public async Task<ProjectRunsReadback?> GetProjectRunsForAccountAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var readback = await GetProjectRunsAsync(projectId, cancellationToken);
        return readback is null || !string.Equals(readback.Project.AccountId, accountId, StringComparison.Ordinal)
            ? null
            : readback;
    }

    public Task<RunSnapshot?> GetRunAsync(string runId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
    }

    public async Task<RunSnapshot?> GetRunForAccountAsync(
        string accountId,
        string runId,
        CancellationToken cancellationToken = default)
    {
        var run = await _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
        if (run is null)
        {
            return null;
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(run.ProjectId, cancellationToken);
        return project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal)
            ? null
            : run;
    }

    public Task<IReadOnlyList<ArtifactSnapshot>> ListArtifactsForRunAsync(string runId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
    }

    public async Task<ArtifactReadResult?> ReadArtifactAsync(string artifactId, CancellationToken cancellationToken = default)
    {
        var artifact = await _metadataStore.GetArtifactAsync(artifactId, cancellationToken);
        if (artifact is null)
        {
            return null;
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(artifact.ProjectId, cancellationToken);
        return project is null ? null : ReadArtifact(project.RepoPath, artifact);
    }

    public async Task<ArtifactReadResult?> ReadArtifactForAccountAsync(
        string accountId,
        string artifactId,
        CancellationToken cancellationToken = default)
    {
        var artifact = await _metadataStore.GetArtifactAsync(artifactId, cancellationToken);
        if (artifact is null)
        {
            return null;
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(artifact.ProjectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        return ReadArtifact(project.RepoPath, artifact);
    }

    public ArtifactReadResult? ReadProjectHealth(string relativePath)
    {
        if (!relativePath.StartsWith("logs/ci/project-health/", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var artifact = new ArtifactSnapshot(
            "project-health",
            null,
            "project-health",
            relativePath.EndsWith(".html", StringComparison.OrdinalIgnoreCase) ? "project-health-html" : "project-health-json",
            relativePath,
            "Project health readback");
        return ReadArtifact(_options.RepositoryRoot, artifact);
    }

    public ProjectHealthSummary? ReadProjectHealthSummary()
    {
        return ReadProjectHealthSummary(_options.RepositoryRoot);
    }

    public ProjectHealthSummary? ReadProjectHealthSummary(string repositoryRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        var latestPath = Path.GetFullPath(Path.Combine(repositoryRoot, "logs", "ci", "project-health", "latest.json"));
        if (!WorkspacePathPolicy.IsUnderRoot(repositoryRoot, latestPath) || !File.Exists(latestPath))
        {
            return null;
        }

        using var latestDocument = JsonDocument.Parse(File.ReadAllText(latestPath, System.Text.Encoding.UTF8));
        var latest = latestDocument.RootElement;
        var scan = ReadOptionalJson(repositoryRoot, "logs/ci/project-health/project-health-scan.latest.json");

        var records = latest.TryGetProperty("records", out var recordsElement) && recordsElement.ValueKind == JsonValueKind.Array
            ? recordsElement.EnumerateArray().ToArray()
            : [];
        var stageRecord = records.FirstOrDefault(record => GetString(record, "kind") == "detect-project-stage");
        var doctorRecord = records.FirstOrDefault(record => GetString(record, "kind") == "doctor-project");
        var boundaryRecord = records.FirstOrDefault(record => GetString(record, "kind") == "check-directory-boundaries");
        var doctorResult = FindScanResult(scan, "doctor-project");
        var boundaryResult = FindScanResult(scan, "check-directory-boundaries");
        var stageResult = FindScanResult(scan, "detect-project-stage");
        var signals = stageResult.HasValue && stageResult.Value.TryGetProperty("signals", out var signalsElement)
            ? signalsElement
            : default;
        var doctorCounts = doctorResult.HasValue && doctorResult.Value.TryGetProperty("counts", out var countsElement)
            ? countsElement
            : default;
        var reportCatalog = latest.TryGetProperty("report_catalog_summary", out var catalogElement)
            ? catalogElement
            : default;
        var activeTasks = latest.TryGetProperty("active_task_summary", out var activeTaskElement)
            ? activeTaskElement
            : default;

        return new ProjectHealthSummary(
            Status: GetString(latest, "status", "unknown"),
            GeneratedAt: GetString(latest, "generated_at", ""),
            Stage: GetString(stageRecord, "stage", GetString(stageResult, "stage", "")),
            StageSummary: GetString(stageRecord, "summary", GetString(stageResult, "summary", "")),
            DoctorStatus: GetString(doctorRecord, "status", GetString(doctorResult, "status", "unknown")),
            DoctorFailCount: GetInt(doctorCounts, "fail"),
            DoctorWarnCount: GetInt(doctorCounts, "warn"),
            DoctorOkCount: GetInt(doctorCounts, "ok"),
            BoundaryStatus: GetString(boundaryRecord, "status", GetString(boundaryResult, "status", "unknown")),
            BoundaryFailCount: CountArray(boundaryResult, "violations"),
            BoundaryWarnCount: CountArray(boundaryResult, "warnings"),
            ActiveTaskTotal: GetInt(activeTasks, "total"),
            JsonReportTotal: GetInt(reportCatalog, "total_json"),
            InvalidJsonReportTotal: GetInt(reportCatalog, "invalid_json"),
            OverlayIndexCount: GetInt(signals, "overlay_indexes"),
            ContractFileCount: GetInt(signals, "contract_files"),
            UnitTestFileCount: GetInt(signals, "unit_test_files"),
            TopRecommendation: FindTopRecommendation(doctorResult),
            DashboardPath: "logs/ci/project-health/latest.html");
    }

    private static decimal ReadEstimatedCostCny(string json)
    {
        return LlmUsageAuditJson.SumEstimatedCostCny(json);
    }

    private static double? SecondsBetween(string? fromUtc, string? toUtc)
    {
        if (!DateTimeOffset.TryParse(fromUtc, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var from) ||
            !DateTimeOffset.TryParse(toUtc, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var to))
        {
            return null;
        }

        return Math.Round(Math.Max(0, (to - from).TotalSeconds), 3);
    }

    private static string NormalizeGrain(string? grain)
    {
        var value = string.IsNullOrWhiteSpace(grain) ? "day" : grain.Trim().ToLowerInvariant();
        return value is "hour" or "day" or "month"
            ? value
            : throw new ArgumentOutOfRangeException(nameof(grain), "Unsupported LLM usage grain.");
    }

    private static string NormalizeSplit(string? split)
    {
        var value = string.IsNullOrWhiteSpace(split) ? "account" : split.Trim().ToLowerInvariant();
        return value is "account" or "project" or "account-project"
            ? value
            : throw new ArgumentOutOfRangeException(nameof(split), "Unsupported LLM usage split.");
    }

    private static (DateTimeOffset From, DateTimeOffset To) NormalizeRange(string? fromUtc, string? toUtc, string grain)
    {
        var now = DateTimeOffset.UtcNow;
        var to = ParseUtc(toUtc) ?? now;
        var from = ParseUtc(fromUtc) ?? grain switch
        {
            "hour" => to.AddHours(-24),
            "month" => to.AddMonths(-12),
            _ => to.AddDays(-30)
        };

        if (from >= to)
        {
            throw new ArgumentOutOfRangeException(nameof(fromUtc), "fromUtc must be before toUtc.");
        }

        return (from, to);
    }

    private static DateTimeOffset? ParseUtc(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        return DateTimeOffset.TryParse(value.Trim(), CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out var parsed)
            ? parsed.ToUniversalTime()
            : throw new ArgumentOutOfRangeException(nameof(value), "Invalid UTC date.");
    }

    private static DateTimeOffset BucketUtc(DateTimeOffset value, string grain)
    {
        var utc = value.ToUniversalTime();
        return grain switch
        {
            "hour" => new DateTimeOffset(utc.Year, utc.Month, utc.Day, utc.Hour, 0, 0, TimeSpan.Zero),
            "month" => new DateTimeOffset(utc.Year, utc.Month, 1, 0, 0, 0, TimeSpan.Zero),
            _ => new DateTimeOffset(utc.Year, utc.Month, utc.Day, 0, 0, 0, TimeSpan.Zero)
        };
    }

    private static string Csv(string? value)
    {
        var text = value ?? "";
        return "\"" + text.Replace("\"", "\"\"", StringComparison.Ordinal) + "\"";
    }

    private ArtifactReadResult? ReadArtifact(string repositoryRoot, ArtifactSnapshot artifact)
    {
        var fullPath = Path.GetFullPath(Path.Combine(repositoryRoot, artifact.RelativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(repositoryRoot, fullPath))
        {
            throw new InvalidOperationException("Artifact path escaped repository root.");
        }

        if (!File.Exists(fullPath))
        {
            return null;
        }

        var content = File.ReadAllText(fullPath, System.Text.Encoding.UTF8);
        var contentType = artifact.RelativePath.EndsWith(".html", StringComparison.OrdinalIgnoreCase)
            ? "text/html; charset=utf-8"
            : "text/plain; charset=utf-8";

        return new ArtifactReadResult(
            artifact.ArtifactId,
            artifact.ArtifactType,
            artifact.RelativePath,
            artifact.Summary,
            content,
            contentType);
    }

    private JsonElement? ReadOptionalJson(string repositoryRoot, string relativePath)
    {
        var fullPath = Path.GetFullPath(Path.Combine(repositoryRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(repositoryRoot, fullPath) || !File.Exists(fullPath))
        {
            return null;
        }

        using var document = JsonDocument.Parse(File.ReadAllText(fullPath, System.Text.Encoding.UTF8));
        return document.RootElement.Clone();
    }

    private static JsonElement? FindScanResult(JsonElement? scan, string kind)
    {
        if (!scan.HasValue || !scan.Value.TryGetProperty("results", out var results) || results.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        foreach (var result in results.EnumerateArray())
        {
            if (GetString(result, "kind") == kind)
            {
                return result;
            }
        }

        return null;
    }

    private static string FindTopRecommendation(JsonElement? doctorResult)
    {
        if (!doctorResult.HasValue ||
            !doctorResult.Value.TryGetProperty("checks", out var checks) ||
            checks.ValueKind != JsonValueKind.Array)
        {
            return "";
        }

        foreach (var check in checks.EnumerateArray())
        {
            var status = GetString(check, "status");
            if (status == "fail" || status == "warn")
            {
                return GetString(check, "recommendation", GetString(check, "summary"));
            }
        }

        return "";
    }

    private static int CountArray(JsonElement? element, string propertyName)
    {
        return element.HasValue &&
            element.Value.TryGetProperty(propertyName, out var property) &&
            property.ValueKind == JsonValueKind.Array
            ? property.GetArrayLength()
            : 0;
    }

    private static string GetString(JsonElement? element, string propertyName, string fallback = "")
    {
        return element.HasValue ? GetString(element.Value, propertyName, fallback) : fallback;
    }

    private static string GetString(JsonElement element, string propertyName, string fallback = "")
    {
        return element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(propertyName, out var property) &&
            property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? fallback
            : fallback;
    }

    private static int GetInt(JsonElement element, string propertyName)
    {
        return element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(propertyName, out var property) &&
            property.ValueKind == JsonValueKind.Number &&
            property.TryGetInt32(out var value)
            ? value
            : 0;
    }
}
