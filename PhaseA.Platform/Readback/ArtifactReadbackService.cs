using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;
using System.Text.Json;

namespace PhaseA.Platform.Readback;

public sealed class ArtifactReadbackService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;

    public ArtifactReadbackService(PhaseAMetadataStore metadataStore, PhaseAPlatformOptions options)
    {
        _metadataStore = metadataStore;
        _options = options;
    }

    public Task<IReadOnlyList<ProjectListItem>> ListProjectsAsync(string accountId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.ListProjectsAsync(accountId, cancellationToken);
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

    public Task<RunSnapshot?> GetRunAsync(string runId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
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
