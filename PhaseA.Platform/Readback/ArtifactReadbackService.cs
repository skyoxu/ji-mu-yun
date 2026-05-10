using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Readback;

public sealed class ArtifactReadbackService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;

    public ArtifactReadbackService(PhaseAMetadataStore metadataStore, PhaseAPlatformOptions options)
    {
        _metadataStore = metadataStore;
        _options = options;
    }

    public Task<IReadOnlyList<ProjectListItem>> ListProjectsAsync(string accountId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.ListProjectsAsync(accountId, cancellationToken);
    }

    public async Task<ProjectRunsReadback?> GetProjectRunsAsync(string projectId, CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return new ProjectRunsReadback(project, runs);
    }

    public Task<RunSnapshot?> GetRunAsync(string runId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
    }

    public Task<IReadOnlyList<ArtifactSnapshot>> ListArtifactsForRunAsync(string runId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
    }

    public async Task<ArtifactReadResult?> ReadArtifactAsync(string artifactId, CancellationToken cancellationToken = default)
    {
        var artifact = await _metadataStore.GetArtifactAsync(artifactId, cancellationToken);
        if (artifact is null)
        {
            return null;
        }

        return ReadArtifact(artifact);
    }

    public ArtifactReadResult? ReadProjectHealth(string relativePath)
    {
        if (!relativePath.StartsWith("logs/ci/project-health/", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var artifact = new ArtifactSnapshot(
            "project-health",
            null,
            "project-health",
            relativePath.EndsWith(".html", StringComparison.OrdinalIgnoreCase) ? "project-health-html" : "project-health-json",
            relativePath,
            "Project health readback");
        return ReadArtifact(artifact);
    }

    private ArtifactReadResult? ReadArtifact(ArtifactSnapshot artifact)
    {
        var fullPath = Path.GetFullPath(Path.Combine(_options.RepositoryRoot, artifact.RelativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(_options.RepositoryRoot, fullPath))
        {
            throw new InvalidOperationException("Artifact path escaped repository root.");
        }

        if (!File.Exists(fullPath))
        {
            return null;
        }

        var content = File.ReadAllText(fullPath, System.Text.Encoding.UTF8);
        var contentType = artifact.RelativePath.EndsWith(".html", StringComparison.OrdinalIgnoreCase)
            ? "text/html; charset=utf-8"
            : "text/plain; charset=utf-8";

        return new ArtifactReadResult(
            artifact.ArtifactId,
            artifact.ArtifactType,
            artifact.RelativePath,
            artifact.Summary,
            content,
            contentType);
    }
}
