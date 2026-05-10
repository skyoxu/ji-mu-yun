using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeTddArtifactIndexer
{
    public IReadOnlyList<ArtifactCreationCommand> Discover(string repositoryRoot, string runId, string projectId, string slug)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(slug);

        var artifacts = new List<ArtifactCreationCommand>();
        var logsRoot = Path.Combine(repositoryRoot, "logs");
        if (!Directory.Exists(logsRoot))
        {
            return artifacts;
        }

        foreach (var summaryPath in Directory.EnumerateFiles(logsRoot, "summary.json", SearchOption.AllDirectories))
        {
            var normalized = summaryPath.Replace(Path.DirectorySeparatorChar, '/');
            if (!normalized.Contains($"prototype-tdd-{slug}-", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            artifacts.Add(Create(repositoryRoot, summaryPath, runId, projectId, "prototype-tdd-summary", "Prototype TDD summary JSON"));
        }

        foreach (var reportPath in Directory.EnumerateFiles(logsRoot, "report.*", SearchOption.AllDirectories))
        {
            var normalized = reportPath.Replace(Path.DirectorySeparatorChar, '/');
            if (!normalized.Contains($"prototype-tdd-{slug}-", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            artifacts.Add(Create(repositoryRoot, reportPath, runId, projectId, "prototype-tdd-report", "Prototype TDD report"));
        }

        var sidecar = Path.Combine(repositoryRoot, "docs", "prototypes", $"{slug}.prototype.json");
        if (File.Exists(sidecar))
        {
            artifacts.Add(Create(repositoryRoot, sidecar, runId, projectId, "prototype-sidecar-json", "Prototype JSON sidecar"));
        }

        return artifacts;
    }

    private static ArtifactCreationCommand Create(string repositoryRoot, string absolutePath, string runId, string projectId, string type, string summary)
    {
        var relativePath = Path.GetRelativePath(repositoryRoot, absolutePath).Replace(Path.DirectorySeparatorChar, '/');
        return new ArtifactCreationCommand(runId, projectId, type, relativePath, summary);
    }
}
