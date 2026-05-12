using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class Chapter2BootstrapService
{
    private const string RunType = "chapter2-bootstrap";

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly Chapter2BootstrapCommandBuilder _commandBuilder;
    private readonly ProjectHealthArtifactIndexer _artifactIndexer;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;

    public Chapter2BootstrapService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        Chapter2BootstrapCommandBuilder commandBuilder,
        ProjectHealthArtifactIndexer artifactIndexer)
        : this(metadataStore, options, processRunner, commandBuilder, artifactIndexer, new ProjectWorkspaceSeeder(options))
    {
    }

    public Chapter2BootstrapService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        Chapter2BootstrapCommandBuilder commandBuilder,
        ProjectHealthArtifactIndexer artifactIndexer,
        IProjectWorkspaceSeeder workspaceSeeder)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _commandBuilder = commandBuilder;
        _artifactIndexer = artifactIndexer;
        _workspaceSeeder = workspaceSeeder;
    }

    public async Task<Chapter2BootstrapResult> RunAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        var existingRuns = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var completed = existingRuns.FirstOrDefault(run => run.RunType == RunType && run.Status == "succeeded");
        if (completed is not null)
        {
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(completed.RunId, cancellationToken);
            return new Chapter2BootstrapResult(
                completed.RunId,
                "already_succeeded",
                completed.ExitCode ?? 0,
                "Chapter 2 bootstrap already succeeded for this project.",
                "",
                artifacts);
        }

        var active = existingRuns.FirstOrDefault(run =>
            run.RunType == RunType &&
            (run.Status == "queued" || run.Status == "running"));
        if (active is not null)
        {
            return new Chapter2BootstrapResult(
                active.RunId,
                "blocked",
                StatusCodes.Status423Locked,
                "",
                "Chapter 2 bootstrap is already running for this project.",
                []);
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(
                runId,
                "blocked",
                StatusCodes.Status423Locked,
                "",
                "Project runner lock is already held.",
                "{}",
                cancellationToken);
            return new Chapter2BootstrapResult(runId, "blocked", StatusCodes.Status423Locked, "", "Project runner lock is already held.", []);
        }

        try
        {
            await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

            _workspaceSeeder.EnsureSeeded(project.RepoPath);
            var hardChecks = await _processRunner.RunAsync(_commandBuilder.BuildLocalHardChecksCommand(project.RepoPath), cancellationToken);
            var exitCode = hardChecks.ExitCode;
            var status = exitCode == 0 ? "succeeded" : "failed";
            var stdout = hardChecks.Stdout;
            var stderr = hardChecks.Stderr;
            var discoveredArtifacts = _artifactIndexer.Discover(project.RepoPath, runId, project.ProjectId);

            foreach (var artifact in discoveredArtifacts)
            {
                await _metadataStore.AddArtifactAsync(artifact, cancellationToken);
            }

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                project_health_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray()
            });
            await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, cancellationToken);

            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
            return new Chapter2BootstrapResult(runId, status, exitCode, stdout, stderr, artifacts);
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        }
    }
}
