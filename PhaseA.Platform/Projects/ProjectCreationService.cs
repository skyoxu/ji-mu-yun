using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Projects;

public sealed class ProjectCreationService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly ProjectRuleCatalog _ruleCatalog;

    public ProjectCreationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ProjectRuleCatalog ruleCatalog)
    {
        _metadataStore = metadataStore;
        _options = options;
        _ruleCatalog = ruleCatalog;
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

        return result;
    }
}
