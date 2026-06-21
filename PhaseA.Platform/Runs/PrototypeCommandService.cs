using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeCommandService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly PrototypeCommandBuilder _commandBuilder;
    private readonly PrototypeTddArtifactIndexer _artifactIndexer;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;

    public PrototypeCommandService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        PrototypeCommandBuilder commandBuilder,
        PrototypeTddArtifactIndexer artifactIndexer)
        : this(metadataStore, options, processRunner, commandBuilder, artifactIndexer, new ProjectWorkspaceSeeder(options))
    {
    }

    public PrototypeCommandService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        PrototypeCommandBuilder commandBuilder,
        PrototypeTddArtifactIndexer artifactIndexer,
        IProjectWorkspaceSeeder workspaceSeeder,
        HeavyRunnerQueueService? heavyRunnerQueue = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _commandBuilder = commandBuilder;
        _artifactIndexer = artifactIndexer;
        _workspaceSeeder = workspaceSeeder;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
    }

    public async Task<HostedCommandResult> RunTddAsync(string accountId, string projectId, PrototypeTddRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        var missing = PrototypeCommandValidation.MissingTddFields(request);
        if (missing.Count > 0)
        {
            return new HostedCommandResult("", "missing_required_fields", 2, "", "", [], missing);
        }

        return await RunLockedAsync(
            accountId,
            projectId,
            $"prototype-tdd-{request.Stage!.ToLowerInvariant()}",
            PrototypeRecordWriter.SanitizeSlug(request.Slug!),
            project => _commandBuilder.BuildTdd(request, project.RepoPath),
            cancellationToken);
    }

    public async Task<HostedCommandResult> CreateSceneAsync(string accountId, string projectId, PrototypeSceneRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        var missing = PrototypeCommandValidation.MissingSceneFields(request);
        if (missing.Count > 0)
        {
            return new HostedCommandResult("", "missing_required_fields", 2, "", "", [], missing);
        }

        return await RunLockedAsync(
            accountId,
            projectId,
            "prototype-scene",
            PrototypeRecordWriter.SanitizeSlug(request.Slug!),
            project => _commandBuilder.BuildScene(request, project.RepoPath),
            cancellationToken);
    }

    private async Task<HostedCommandResult> RunLockedAsync(
        string accountId,
        string projectId,
        string runType,
        string slug,
        Func<ProjectSnapshot, HostedProcessCommand> commandFactory,
        CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, runType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new HostedCommandResult(runId, "blocked", 423, "", "runner lock already held", [], []);
        }

        try
        {
            await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, runType, CancellationToken.None);
            await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, cancellationToken);
            _workspaceSeeder.EnsureSeeded(project.RepoPath);
            var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
            if (!routeSkill.IsAvailable)
            {
                var routeSkillEvidenceJson = JsonSerializer.Serialize(new
                {
                    run_type = runType,
                    slug,
                    route_skill = routeSkill.Context,
                    failure_code = routeSkill.FailureCode
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 428, "", routeSkill.FailureMessage, routeSkillEvidenceJson, cancellationToken);
                return new HostedCommandResult(runId, routeSkill.FailureCode, 428, "", routeSkill.FailureMessage, [], []);
            }

            var command = commandFactory(project);
            var process = await _processRunner.RunAsync(command.WithRunId(runId), cancellationToken);
            var normalizedExitCode = NormalizeExitCode(runType, process);
            var status = normalizedExitCode == 0 ? "succeeded" : "failed";
            var artifacts = _artifactIndexer.Discover(project.RepoPath, runId, project.ProjectId, slug);
            foreach (var artifact in artifacts)
            {
                await _metadataStore.AddArtifactAsync(artifact, cancellationToken);
            }

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = runType,
                slug,
                artifacts = artifacts.Select(a => a.RelativePath).ToArray()
            });
            await _metadataStore.CompleteRunAsync(runId, status, normalizedExitCode, process.Stdout, process.Stderr, evidenceJson, cancellationToken);
            var storedArtifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
            return new HostedCommandResult(runId, status, normalizedExitCode, process.Stdout, process.Stderr, storedArtifacts, []);
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        }
    }

    private static int NormalizeExitCode(string runType, HostedProcessResult process)
    {
        if (string.Equals(runType, "prototype-scene", StringComparison.OrdinalIgnoreCase) &&
            process.ExitCode != 0 &&
            ContainsExistingScaffoldMessage(process))
        {
            return 0;
        }

        return process.ExitCode;
    }

    private static bool ContainsExistingScaffoldMessage(HostedProcessResult process)
    {
        return (process.Stdout.Contains("scaffold already exists for slug=", StringComparison.OrdinalIgnoreCase) ||
                process.Stderr.Contains("scaffold already exists for slug=", StringComparison.OrdinalIgnoreCase));
    }
}
