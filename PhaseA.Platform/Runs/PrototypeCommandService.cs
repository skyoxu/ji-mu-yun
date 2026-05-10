using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeCommandService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly PrototypeCommandBuilder _commandBuilder;
    private readonly PrototypeTddArtifactIndexer _artifactIndexer;

    public PrototypeCommandService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        PrototypeCommandBuilder commandBuilder,
        PrototypeTddArtifactIndexer artifactIndexer)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _commandBuilder = commandBuilder;
        _artifactIndexer = artifactIndexer;
    }

    public async Task<HostedCommandResult> RunTddAsync(string projectId, PrototypeTddRequest request, CancellationToken cancellationToken = default)
    {
        var missing = PrototypeCommandValidation.MissingTddFields(request);
        if (missing.Count > 0)
        {
            return new HostedCommandResult("", "missing_required_fields", 2, "", "", [], missing);
        }

        return await RunLockedAsync(projectId, $"prototype-tdd-{request.Stage!.ToLowerInvariant()}", PrototypeRecordWriter.SanitizeSlug(request.Slug!), _commandBuilder.BuildTdd(request), cancellationToken);
    }

    public async Task<HostedCommandResult> CreateSceneAsync(string projectId, PrototypeSceneRequest request, CancellationToken cancellationToken = default)
    {
        var missing = PrototypeCommandValidation.MissingSceneFields(request);
        if (missing.Count > 0)
        {
            return new HostedCommandResult("", "missing_required_fields", 2, "", "", [], missing);
        }

        return await RunLockedAsync(projectId, "prototype-scene", PrototypeRecordWriter.SanitizeSlug(request.Slug!), _commandBuilder.BuildScene(request), cancellationToken);
    }

    private async Task<HostedCommandResult> RunLockedAsync(
        string projectId,
        string runType,
        string slug,
        HostedProcessCommand command,
        CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
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
            await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);
            var process = await _processRunner.RunAsync(command, cancellationToken);
            var status = process.ExitCode == 0 ? "succeeded" : "failed";
            var artifacts = _artifactIndexer.Discover(_options.RepositoryRoot, runId, project.ProjectId, slug);
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
            await _metadataStore.CompleteRunAsync(runId, status, process.ExitCode, process.Stdout, process.Stderr, evidenceJson, cancellationToken);
            var storedArtifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
            return new HostedCommandResult(runId, status, process.ExitCode, process.Stdout, process.Stderr, storedArtifacts, []);
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        }
    }
}
