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

        await metadataStore.RecordProjectCreationFailureAsync(new ProjectCreationFailureCommand(
            project.AccountId,
            project.ProjectId,
            project.Name,
            project.GameName,
            project.GameTypeSource,
            project.TemplateRuleId,
            project.WorkspaceRootPath,
            failureError));
        await metadataStore.DeleteProjectAsync(projectId);
        if (Directory.Exists(project.WorkspaceRootPath))
        {
            Directory.Delete(project.WorkspaceRootPath, recursive: true);
        }
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
