using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class Chapter2BootstrapService
{
    private const string RunType = "chapter2-bootstrap";

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly Chapter2BootstrapCommandBuilder _commandBuilder;
    private readonly ProjectHealthArtifactIndexer _artifactIndexer;

    public Chapter2BootstrapService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        Chapter2BootstrapCommandBuilder commandBuilder,
        ProjectHealthArtifactIndexer artifactIndexer)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _commandBuilder = commandBuilder;
        _artifactIndexer = artifactIndexer;
    }

    public async Task<Chapter2BootstrapResult> RunAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        var hardChecks = await _processRunner.RunAsync(_commandBuilder.BuildLocalHardChecksCommand(), cancellationToken);
        var healthScan = await _processRunner.RunAsync(_commandBuilder.BuildProjectHealthScanCommand(), cancellationToken);
        var exitCode = hardChecks.ExitCode != 0 ? hardChecks.ExitCode : healthScan.ExitCode;
        var status = exitCode == 0 ? "succeeded" : "failed";
        var stdout = hardChecks.Stdout + healthScan.Stdout;
        var stderr = hardChecks.Stderr + healthScan.Stderr;
        var discoveredArtifacts = _artifactIndexer.Discover(_options.RepositoryRoot, runId, project.ProjectId);

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
}
