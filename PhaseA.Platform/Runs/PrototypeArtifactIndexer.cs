using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeArtifactIndexer
{
    public IReadOnlyList<ArtifactCreationCommand> Discover(string repositoryRoot, string runId, string projectId, string slug, string prototypeRecordPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(slug);
        ArgumentException.ThrowIfNullOrWhiteSpace(prototypeRecordPath);

        var candidates = new (string RelativePath, string Type, string Summary)[]
        {
            (prototypeRecordPath, "prototype-record", "Prototype markdown record"),
            ($"docs/prototypes/{slug}.prototype.json", "prototype-sidecar-json", "Prototype JSON sidecar"),
            ($"logs/ci/active-prototypes/{slug}.active.json", "active-prototype-json", "Active prototype state"),
            ($"logs/ci/active-prototypes/{slug}.packaging.json", "prototype-packaging-summary", "Prototype packaging summary JSON"),
            ($"logs/ci/active-prototypes/{slug}.completion.md", "prototype-completion-report", "Prototype completion report markdown"),
            ("logs/ci/project-health/latest.html", "project-health-html", "Project health dashboard HTML"),
            ("logs/ci/project-health/latest.json", "project-health-json", "Project health dashboard index JSON")
        };

        var artifacts = new List<ArtifactCreationCommand>();
        foreach (var candidate in candidates)
        {
            var path = Path.Combine(repositoryRoot, candidate.RelativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path))
            {
                continue;
            }

            artifacts.Add(new ArtifactCreationCommand(runId, projectId, candidate.Type, candidate.RelativePath, candidate.Summary));
        }

        return artifacts;
    }
}
