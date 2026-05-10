using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class ProjectHealthArtifactIndexer
{
    private static readonly (string RelativePath, string ArtifactType, string Summary)[] ProjectHealthArtifacts =
    [
        ("logs/ci/project-health/latest.html", "project-health-html", "Project health dashboard HTML"),
        ("logs/ci/project-health/latest.json", "project-health-json", "Project health dashboard index JSON"),
        ("logs/ci/project-health/project-health-scan.latest.json", "project-health-scan-json", "Project health scan aggregate JSON")
    ];

    public IReadOnlyList<ArtifactCreationCommand> Discover(string repositoryRoot, string runId, string projectId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var artifacts = new List<ArtifactCreationCommand>();
        foreach (var artifact in ProjectHealthArtifacts)
        {
            var absolutePath = Path.Combine(repositoryRoot, artifact.RelativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(absolutePath))
            {
                continue;
            }

            artifacts.Add(new ArtifactCreationCommand(
                runId,
                projectId,
                artifact.ArtifactType,
                artifact.RelativePath,
                artifact.Summary));
        }

        return artifacts;
    }
}
