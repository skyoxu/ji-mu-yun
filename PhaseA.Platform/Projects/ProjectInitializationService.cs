using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;

namespace PhaseA.Platform.Projects;

public sealed class ProjectInitializationService
{
    private static readonly TimeSpan StaleInitializationAge = TimeSpan.FromMinutes(15);

    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<ProjectInitializationService> _logger;

    public ProjectInitializationService(
        IServiceScopeFactory scopeFactory,
        ILogger<ProjectInitializationService> logger)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
    }

    public void StartChapter2Bootstrap(string projectId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        _ = Task.Run(() => RunChapter2BootstrapAsync(projectId));
    }

    public Task ReconcileInterruptedInitializationsAsync(CancellationToken cancellationToken = default)
    {
        return ReconcileInitializationsOlderThanAsync(TimeSpan.Zero, cancellationToken);
    }

    public async Task ReconcileStaleInitializationsAsync(CancellationToken cancellationToken = default)
    {
        await ReconcileInitializationsOlderThanAsync(StaleInitializationAge, cancellationToken);
    }

    private async Task ReconcileInitializationsOlderThanAsync(
        TimeSpan maxAge,
        CancellationToken cancellationToken)
    {
        using var scope = _scopeFactory.CreateScope();
        var metadataStore = scope.ServiceProvider.GetRequiredService<PhaseAMetadataStore>();
        var staleProjects = await metadataStore.ListStaleProjectInitializationsAsync(maxAge, cancellationToken);
        foreach (var stale in staleProjects)
        {
            var failure = maxAge == TimeSpan.Zero
                ? "Project initialization was interrupted because the service restarted before completion."
                : $"Project initialization timed out after {StaleInitializationAge.TotalMinutes:0} minutes.";
            _logger.LogWarning(
                "Cleaning stale project initialization. ProjectId={ProjectId} RunId={RunId} Status={Status}",
                stale.ProjectId,
                stale.RunId,
                stale.RunStatus);
            await metadataStore.RecordProjectCreationFailureAsync(new ProjectCreationFailureCommand(
                stale.AccountId,
                stale.ProjectId,
                stale.Name,
                stale.GameName,
                stale.GameTypeSource,
                stale.TemplateRuleId,
                stale.WorkspaceRootPath,
                failure), cancellationToken);
            await metadataStore.DeleteProjectAsync(stale.ProjectId, cancellationToken);
            if (Directory.Exists(stale.WorkspaceRootPath))
            {
                Directory.Delete(stale.WorkspaceRootPath, recursive: true);
            }
        }
    }

    private async Task RunChapter2BootstrapAsync(string projectId)
    {
        using var scope = _scopeFactory.CreateScope();
        var metadataStore = scope.ServiceProvider.GetRequiredService<PhaseAMetadataStore>();
        var chapter2 = scope.ServiceProvider.GetRequiredService<Chapter2BootstrapService>();

        try
        {
            await metadataStore.SetProjectBootstrapStatusAsync(projectId, "running", null);
            var result = await chapter2.RunAsync(projectId);
            if (result.Status is "succeeded" or "already_succeeded")
            {
                await metadataStore.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
                return;
            }

            await metadataStore.SetProjectBootstrapStatusAsync(
                projectId,
                "failed",
                FirstNonEmpty(ExtractFailureSummary(result.Stdout), result.Stderr, result.Stdout, result.Status));
            await RecordFailureAndDeleteProjectAsync(
                metadataStore,
                projectId,
                FirstNonEmpty(ExtractFailureSummary(result.Stdout), result.Stderr, result.Stdout, result.Status));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Project initialization failed for {ProjectId}", projectId);
            await RecordFailureAndDeleteProjectAsync(metadataStore, projectId, ex.Message);
        }
    }

    private static async Task RecordFailureAndDeleteProjectAsync(
        PhaseAMetadataStore metadataStore,
        string projectId,
        string failureError)
    {
        var project = await metadataStore.GetProjectSnapshotAsync(projectId);
        if (project is null)
        {
            return;
        }

        var enrichedFailure = FirstNonEmpty(
            BuildInitializationFailureDiagnostics(project.RepoPath),
            failureError);
        await metadataStore.RecordProjectCreationFailureAsync(new ProjectCreationFailureCommand(
            project.AccountId,
            project.ProjectId,
            project.Name,
            project.GameName,
            project.GameTypeSource,
            project.TemplateRuleId,
            project.WorkspaceRootPath,
            enrichedFailure));
        await metadataStore.DeleteProjectAsync(projectId);
        if (Directory.Exists(project.WorkspaceRootPath))
        {
            Directory.Delete(project.WorkspaceRootPath, recursive: true);
        }
    }

    private static string? BuildInitializationFailureDiagnostics(string repoPath)
    {
        if (string.IsNullOrWhiteSpace(repoPath) || !Directory.Exists(repoPath))
        {
            return null;
        }

        var latest = Directory.EnumerateFiles(Path.Combine(repoPath, "logs", "ci"), "local-hard-checks-latest.json", SearchOption.AllDirectories)
            .Select(path => new FileInfo(path))
            .OrderByDescending(file => file.LastWriteTimeUtc)
            .FirstOrDefault();
        if (latest is null)
        {
            return null;
        }

        try
        {
            using var latestDoc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(latest.FullName));
            var summaryPath = latestDoc.RootElement.TryGetProperty("summary_path", out var summaryPathElement)
                ? summaryPathElement.GetString()
                : null;
            var summaryFullPath = ResolveRepoRelativePath(repoPath, summaryPath);
            if (summaryFullPath is null || !File.Exists(summaryFullPath))
            {
                return $"LOCAL_HARD_CHECKS status=fail latest={ToRepoRelative(repoPath, latest.FullName)}";
            }

            using var summaryDoc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(summaryFullPath));
            var failedStep = summaryDoc.RootElement.TryGetProperty("failed_step", out var failedStepElement)
                ? failedStepElement.GetString()
                : "";
            var details = new List<string>
            {
                "LOCAL_HARD_CHECKS status=fail",
                $"failed_step={failedStep}",
                $"summary={ToRepoRelative(repoPath, summaryFullPath)}"
            };

            if (string.Equals(failedStep, "gate-bundle-hard", StringComparison.OrdinalIgnoreCase) &&
                TryFindGateBundleFailure(repoPath, summaryDoc.RootElement, out var gateDetails))
            {
                details.Add(gateDetails);
            }

            return string.Join(Environment.NewLine, details.Where(static line => !string.IsNullOrWhiteSpace(line)));
        }
        catch (Exception ex)
        {
            return $"LOCAL_HARD_CHECKS status=fail diagnostics_error={ex.GetType().Name}:{ex.Message}";
        }
    }

    private static bool TryFindGateBundleFailure(string repoPath, System.Text.Json.JsonElement summary, out string details)
    {
        details = "";
        if (!summary.TryGetProperty("steps", out var steps) || steps.ValueKind != System.Text.Json.JsonValueKind.Array)
        {
            return false;
        }

        foreach (var step in steps.EnumerateArray())
        {
            var name = step.TryGetProperty("name", out var nameElement) ? nameElement.GetString() : "";
            if (!string.Equals(name, "gate-bundle-hard", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var summaryFile = step.TryGetProperty("summary_file", out var summaryFileElement)
                ? summaryFileElement.GetString()
                : null;
            var gateSummaryPath = ResolveRepoRelativePath(repoPath, summaryFile);
            if (gateSummaryPath is not null &&
                File.Exists(Path.Combine(Path.GetDirectoryName(gateSummaryPath) ?? "", "hard", "summary.json")))
            {
                gateSummaryPath = Path.Combine(Path.GetDirectoryName(gateSummaryPath)!, "hard", "summary.json");
            }

            if (gateSummaryPath is null || !File.Exists(gateSummaryPath))
            {
                details = $"gate_bundle_summary={summaryFile}";
                return true;
            }

            using var gateDoc = System.Text.Json.JsonDocument.Parse(File.ReadAllText(gateSummaryPath));
            var failedGates = new List<string>();
            if (gateDoc.RootElement.TryGetProperty("gates", out var gates) && gates.ValueKind == System.Text.Json.JsonValueKind.Array)
            {
                foreach (var gate in gates.EnumerateArray())
                {
                    var status = gate.TryGetProperty("status", out var statusElement) ? statusElement.GetString() : "";
                    var rc = gate.TryGetProperty("rc", out var rcElement) && rcElement.TryGetInt32(out var rcValue)
                        ? rcValue
                        : 0;
                    if (!string.Equals(status, "fail", StringComparison.OrdinalIgnoreCase) && rc == 0)
                    {
                        continue;
                    }

                    var gateName = gate.TryGetProperty("name", out var gateNameElement) ? gateNameElement.GetString() : "";
                    failedGates.Add($"{gateName}(rc={rc})");
                }
            }

            details = $"gate_bundle_summary={ToRepoRelative(repoPath, gateSummaryPath)} failed_gates={string.Join(",", failedGates)}";
            return true;
        }

        return false;
    }

    private static string? ResolveRepoRelativePath(string repoPath, string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        var normalized = path.Replace('/', Path.DirectorySeparatorChar);
        return Path.IsPathRooted(normalized)
            ? normalized
            : Path.Combine(repoPath, normalized);
    }

    private static string ToRepoRelative(string repoPath, string path)
    {
        return Path.GetRelativePath(repoPath, path).Replace(Path.DirectorySeparatorChar, '/');
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Length > 1600 ? value[^1600..] : value;
            }
        }

        return "Project initialization failed.";
    }

    private static string? ExtractFailureSummary(string stdout)
    {
        if (string.IsNullOrWhiteSpace(stdout))
        {
            return null;
        }

        var marker = "LOCAL_HARD_CHECKS status=fail";
        var markerIndex = stdout.LastIndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (markerIndex >= 0)
        {
            return stdout[markerIndex..].Trim();
        }

        marker = "\"failed_step\"";
        markerIndex = stdout.LastIndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (markerIndex >= 0)
        {
            return stdout[markerIndex..].Trim();
        }

        return null;
    }
}
