using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Projects;

public sealed class ProjectCreationService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly ProjectRuleCatalog _ruleCatalog;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;

    public ProjectCreationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ProjectRuleCatalog ruleCatalog)
        : this(metadataStore, options, ruleCatalog, new ProjectWorkspaceSeeder(options))
    {
    }

    public ProjectCreationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ProjectRuleCatalog ruleCatalog,
        IProjectWorkspaceSeeder workspaceSeeder)
    {
        _metadataStore = metadataStore;
        _options = options;
        _ruleCatalog = ruleCatalog;
        _workspaceSeeder = workspaceSeeder;
    }

    public async Task<ProjectCreationResult> CreateProjectAsync(
        string accountId,
        ProjectCreationRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentNullException.ThrowIfNull(request);

        if (!string.IsNullOrWhiteSpace(request.GitUrl) ||
            !string.IsNullOrWhiteSpace(request.RepositoryUrl) ||
            !string.IsNullOrWhiteSpace(request.RepoUrl))
        {
            return ProjectCreationResult.Failure("git_url_not_allowed");
        }

        if (string.IsNullOrWhiteSpace(request.GameName))
        {
            return ProjectCreationResult.Failure("game_name_required");
        }

        if (string.IsNullOrWhiteSpace(request.GameTypeSource))
        {
            return ProjectCreationResult.Failure("game_type_source_required");
        }

        var rule = _ruleCatalog.Find(request.TemplateRuleId);
        if (rule is null)
        {
            return ProjectCreationResult.Failure("unknown_project_rule");
        }

        var projectId = Guid.NewGuid().ToString("N");
        var layout = WorkspaceLayoutBuilder.Build(_options.HostedWorkspaceRoot, accountId, projectId);

        var command = new ProjectCreationCommand(
            projectId,
            accountId,
            ProjectName: string.IsNullOrWhiteSpace(request.ProjectName) ? request.GameName.Trim() : request.ProjectName.Trim(),
            GameName: request.GameName.Trim(),
            GameTypeSource: request.GameTypeSource.Trim(),
            TemplateRuleId: rule.Id,
            LlmBindingRequired: rule.LlmBindingRequired,
            AllowedWorkflows: rule.AllowedWorkflows,
            WorkspaceRootPath: layout.RootPath,
            RepoPath: layout.RepoPath,
            RuntimePath: layout.RuntimePath,
            MetaPath: layout.MetaPath);

        var result = await _metadataStore.CreateProjectAsync(command, cancellationToken);
        if (!result.Succeeded)
        {
            return result;
        }

        Directory.CreateDirectory(layout.RepoPath);
        Directory.CreateDirectory(layout.RuntimePath);
        Directory.CreateDirectory(layout.MetaPath);
        _workspaceSeeder.EnsureSeeded(layout.RepoPath);

        return result;
    }

    public async Task<ProjectDeletionResult> DeleteProjectAsync(
        string accountId,
        string projectId,
        ProjectDeletionRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        if (!string.Equals(request.ConfirmOne, "delete", StringComparison.Ordinal) ||
            !string.Equals(request.ConfirmTwo, "delete", StringComparison.Ordinal))
        {
            return ProjectDeletionResult.Failure("delete_confirmation_required");
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return ProjectDeletionResult.Failure("project_not_found");
        }

        if (project.BootstrapStatus == "running" || await _metadataStore.HasRunnerLockAsync(projectId, cancellationToken))
        {
            return ProjectDeletionResult.Failure("project_busy");
        }

        await _metadataStore.DeleteProjectAsync(projectId, cancellationToken);
        if (Directory.Exists(project.WorkspaceRootPath))
        {
            Directory.Delete(project.WorkspaceRootPath, recursive: true);
        }

        return ProjectDeletionResult.Deleted(projectId);
    }
}
