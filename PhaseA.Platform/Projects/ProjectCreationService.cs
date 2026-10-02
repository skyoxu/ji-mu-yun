using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace PhaseA.Platform.Projects;

public sealed class ProjectCreationService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly ProjectRuleCatalog _ruleCatalog;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly PrototypeRouteStateWriter _routeStateWriter;
    private readonly ProjectCreationConcurrencyLimiter _creationConcurrencyLimiter;
    private readonly IProjectGameTypeMatchService _gameTypeMatchService;
    private readonly ILogger<ProjectCreationService>? _logger;
    private readonly IProjectRunnerProvisioner? _runnerProvisioner;

    public ProjectCreationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ProjectRuleCatalog ruleCatalog)
        : this(metadataStore, options, ruleCatalog, new ProjectWorkspaceSeeder(options), new PrototypeRouteStateWriter(), new ProjectCreationConcurrencyLimiter(), ProjectGameTypeMatchService.Offline(options))
    {
    }

    public ProjectCreationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ProjectRuleCatalog ruleCatalog,
        IProjectWorkspaceSeeder workspaceSeeder,
        PrototypeRouteStateWriter? routeStateWriter = null,
        ProjectCreationConcurrencyLimiter? creationConcurrencyLimiter = null,
        IProjectGameTypeMatchService? gameTypeMatchService = null,
        ILogger<ProjectCreationService>? logger = null,
        IProjectRunnerProvisioner? runnerProvisioner = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _ruleCatalog = ruleCatalog;
        _workspaceSeeder = workspaceSeeder;
        _routeStateWriter = routeStateWriter ?? new PrototypeRouteStateWriter();
        _creationConcurrencyLimiter = creationConcurrencyLimiter ?? new ProjectCreationConcurrencyLimiter();
        _gameTypeMatchService = gameTypeMatchService ?? ProjectGameTypeMatchService.Offline(options);
        _logger = logger;
        _runnerProvisioner = runnerProvisioner;
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

        var concurrency = await _creationConcurrencyLimiter.TryAcquireAsync(accountId, cancellationToken);
        if (concurrency.Lease is null)
        {
            return ProjectCreationResult.Failure(concurrency.FailureCode ?? "project_creation_concurrency_limit_exceeded");
        }

        await using var lease = concurrency.Lease;
        var projectId = Guid.NewGuid().ToString("N");
        var layout = WorkspaceLayoutBuilder.Build(_options.HostedWorkspaceRoot, accountId, projectId);
        var gameTypeMatch = await ResolveGameTypeMatchAsync(request.GameTypeSource.Trim(), cancellationToken);

        var command = new ProjectCreationCommand(
            projectId,
            accountId,
            ProjectName: string.IsNullOrWhiteSpace(request.ProjectName) ? request.GameName.Trim() : request.ProjectName.Trim(),
            GameName: request.GameName.Trim(),
            GameTypeSource: request.GameTypeSource.Trim(),
            GameTypeMatchJson: gameTypeMatch.ToJson(),
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

        var workspaceAlreadyExisted = Directory.Exists(layout.RootPath);
        try
        {
            PhaseA.Platform.Security.RunnerIsolationPolicy.RequireNoReparsePoint(
                Path.GetPathRoot(layout.RootPath)!, layout.RootPath);
            Directory.CreateDirectory(layout.RepoPath);
            Directory.CreateDirectory(layout.RuntimePath);
            Directory.CreateDirectory(layout.MetaPath);
            _workspaceSeeder.EnsureSeeded(layout.RepoPath);
            _routeStateWriter.WriteProjectReadme(
                layout.RepoPath,
                projectId,
                accountId,
                command.ProjectName,
                command.GameName,
                command.GameTypeSource,
                command.TemplateRuleId,
                result.WorkspaceId ?? string.Empty,
                layout.MetaPath);
            // ADR-0035/0061: the production host supplies the provisioner. Direct domain
            // fixtures may omit it, but such workspaces cannot dispatch an isolated Runner.
            _runnerProvisioner?.Provision(accountId, projectId, layout);
        }
        catch (Exception ex)
        {
            await _metadataStore.RecordProjectCreationFailureAsync(new ProjectCreationFailureCommand(
                accountId,
                projectId,
                command.ProjectName,
                command.GameName,
                command.GameTypeSource,
                command.TemplateRuleId,
                command.WorkspaceRootPath,
                $"Project workspace initialization failed before Chapter 2 bootstrap could start. {ex.GetType().Name}: {ex.Message}"), CancellationToken.None);
            await _metadataStore.DeleteProjectAsync(projectId, CancellationToken.None);
            if (!workspaceAlreadyExisted)
            {
                try { Directory.Delete(layout.RootPath, recursive: true); }
                catch (Exception cleanupError) when (cleanupError is IOException or UnauthorizedAccessException)
                { _logger?.LogWarning("Project workspace cleanup failed for {ProjectId}: {ErrorType}", projectId, cleanupError.GetType().Name); }
            }
            return ProjectCreationResult.Failure("project_creation_failed");
        }

        await RecordGameTypeMatchRecordBestEffortAsync(
            BuildGameTypeMatchRecord(accountId, projectId, command.ProjectName, command.GameName, command.GameTypeSource, gameTypeMatch),
            cancellationToken);

        return result;
    }

    private async Task RecordGameTypeMatchRecordBestEffortAsync(
        ProjectGameTypeMatchFailureCommand record,
        CancellationToken cancellationToken)
    {
        try
        {
            await _metadataStore.RecordProjectGameTypeMatchFailureAsync(record, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(
                ex,
                "Failed to record game type match record for project {ProjectId}.",
                record.ProjectId);
        }
    }

    private static ProjectGameTypeMatchFailureCommand BuildGameTypeMatchRecord(
        string accountId,
        string projectId,
        string projectName,
        string gameName,
        string gameTypeSource,
        ProjectGameTypeMatchEvidence evidence)
    {
        return new ProjectGameTypeMatchFailureCommand(
            accountId,
            projectId,
            projectName,
            gameName,
            gameTypeSource,
            evidence.Status,
            evidence.StatusReason,
            evidence.ReferenceQuery,
            JsonSerializer.Serialize(evidence.NormalizedGenreTags, ProjectGameTypeMatchEvidence.JsonOptions),
            JsonSerializer.Serialize(evidence.CandidateScores, ProjectGameTypeMatchEvidence.JsonOptions),
            evidence.MissingGuidePath,
            evidence.MatchedGameTypeId,
            evidence.MatchedGuidePath,
            evidence.SteamAppId,
            evidence.SteamName,
            evidence.SteamResolvedQuery,
            JsonSerializer.Serialize(evidence.SteamAttemptedQueries, ProjectGameTypeMatchEvidence.JsonOptions));
    }

    private async Task<ProjectGameTypeMatchEvidence> ResolveGameTypeMatchAsync(string gameTypeSource, CancellationToken cancellationToken)
    {
        try
        {
            return await _gameTypeMatchService.ResolveAsync(gameTypeSource, cancellationToken);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return ProjectGameTypeMatchEvidence.Empty("game_type_match_cancelled");
        }
        catch (Exception)
        {
            return ProjectGameTypeMatchEvidence.Empty("game_type_match_failed");
        }
    }

    public async Task<ProjectDeletionResult> DeleteProjectAsync(
        string accountId,
        string projectId,
        ProjectDeletionRequest request,
        CancellationToken cancellationToken = default)
    {
        return await DeleteProjectAsync(accountId, isAdmin: false, projectId, request, cancellationToken);
    }

    public async Task<ProjectDeletionResult> DeleteProjectAsync(
        string accountId,
        bool isAdmin,
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
        if (project is null)
        {
            // S20/AD-11: a repeated confirmed delete is an idempotent protected-cleanup request.
            // The tombstone retains owner resolution after the normal project view is withdrawn.
            var tombstone = (await _metadataStore.ListProjectDeleteTombstonesForAdminAsync(cancellationToken: cancellationToken))
                .SingleOrDefault(item => item.ProjectId == projectId);
            if (tombstone is null || (!isAdmin && !string.Equals(tombstone.AccountId, accountId, StringComparison.Ordinal)))
            {
                return ProjectDeletionResult.Failure("project_not_found");
            }

            await _metadataStore.SoftDeleteProjectAsync(projectId, cancellationToken);
            return ProjectDeletionResult.Deleted(projectId);
        }

        if (!isAdmin && !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return ProjectDeletionResult.Failure("project_not_found");
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasActiveRunAsync(projectId, cancellationToken) ||
            await _metadataStore.HasRunnerLockAsync(projectId, cancellationToken))
        {
            return ProjectDeletionResult.Failure("project_busy");
        }

        await _metadataStore.SoftDeleteProjectAsync(projectId, cancellationToken);
        return ProjectDeletionResult.Deleted(projectId);
    }
}
