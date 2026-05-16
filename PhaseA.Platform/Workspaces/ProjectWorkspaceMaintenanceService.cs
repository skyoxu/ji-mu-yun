using PhaseA.Platform.Data;

namespace PhaseA.Platform.Workspaces;

public sealed class ProjectWorkspaceMaintenanceService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly ILogger<ProjectWorkspaceMaintenanceService> _logger;

    public ProjectWorkspaceMaintenanceService(
        PhaseAMetadataStore metadataStore,
        IProjectWorkspaceSeeder workspaceSeeder,
        ILogger<ProjectWorkspaceMaintenanceService> logger)
    {
        _metadataStore = metadataStore;
        _workspaceSeeder = workspaceSeeder;
        _logger = logger;
    }

    public async Task EnsureAllWorkspacesSeededAsync(CancellationToken cancellationToken = default)
    {
        var projects = await _metadataStore.ListProjectSnapshotsAsync(cancellationToken);
        foreach (var project in projects)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                _workspaceSeeder.EnsureSeeded(project.RepoPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(
                    ex,
                    "Failed to repair hosted workspace for project {ProjectId}. RepoPath={RepoPath}",
                    project.ProjectId,
                    project.RepoPath);
            }
        }
    }
}
