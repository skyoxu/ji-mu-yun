namespace PhaseA.Platform.Workspaces;

public static class WorkspacePathPolicy
{
    public static bool IsUnderRoot(string workspaceRoot, string candidatePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(candidatePath);

        var normalizedRoot = EnsureTrailingSeparator(Path.GetFullPath(workspaceRoot));
        var normalizedCandidate = Path.GetFullPath(candidatePath);

        return normalizedCandidate.StartsWith(normalizedRoot, StringComparison.OrdinalIgnoreCase);
    }

    private static string EnsureTrailingSeparator(string path)
    {
        return path.EndsWith(Path.DirectorySeparatorChar)
            ? path
            : path + Path.DirectorySeparatorChar;
    }
}
