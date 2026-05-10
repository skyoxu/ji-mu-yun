namespace PhaseA.Platform.Workspaces;

public static class WorkspaceLayoutBuilder
{
    public static WorkspaceLayout Build(string hostedWorkspaceRoot, string accountId, string projectId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(hostedWorkspaceRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var rootPath = Path.GetFullPath(Path.Combine(hostedWorkspaceRoot, SanitizeSegment(accountId), SanitizeSegment(projectId)));
        var repoPath = Path.Combine(rootPath, "repo");
        var runtimePath = Path.Combine(rootPath, "runtime");
        var metaPath = Path.Combine(rootPath, "meta");

        foreach (var candidate in new[] { rootPath, repoPath, runtimePath, metaPath })
        {
            if (!WorkspacePathPolicy.IsUnderRoot(hostedWorkspaceRoot, candidate))
            {
                throw new InvalidOperationException("Workspace path escaped the configured root.");
            }
        }

        return new WorkspaceLayout(rootPath, repoPath, runtimePath, metaPath);
    }

    private static string SanitizeSegment(string segment)
    {
        if (segment.Any(c => Path.GetInvalidFileNameChars().Contains(c)) || segment is "." or "..")
        {
            throw new ArgumentException("Workspace path segment contains invalid characters.", nameof(segment));
        }

        return segment;
    }
}
