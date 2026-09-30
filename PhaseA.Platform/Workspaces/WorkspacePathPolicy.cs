namespace PhaseA.Platform.Workspaces;

public static class WorkspacePathPolicy
{
    public static bool AreAllUnderRoot(string workspaceRoot, params string[] candidatePaths)
    {
        ArgumentNullException.ThrowIfNull(candidatePaths);

        foreach (var candidatePath in candidatePaths)
        {
            if (!IsUnderRoot(workspaceRoot, candidatePath))
            {
                return false;
            }
        }

        return true;
    }

    public static bool IsUnderRoot(string workspaceRoot, string candidatePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(candidatePath);

        var normalizedRoot = EnsureTrailingSeparator(Path.GetFullPath(workspaceRoot));
        var normalizedCandidate = Path.GetFullPath(candidatePath);

        if (!normalizedCandidate.Equals(normalizedRoot.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase) &&
            !normalizedCandidate.StartsWith(normalizedRoot, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        // ADR-0061: lexical containment is insufficient when a workspace segment
        // is a junction or symbolic link that resolves outside the owned root.
        return !ContainsReparsePoint(normalizedRoot, normalizedCandidate);
    }

    private static bool ContainsReparsePoint(string normalizedRoot, string normalizedCandidate)
    {
        var root = normalizedRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var relativePath = Path.GetRelativePath(root, normalizedCandidate);
        var current = root;

        if (HasReparsePoint(current))
        {
            return true;
        }

        foreach (var segment in relativePath.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
        {
            if (string.IsNullOrEmpty(segment) || segment == ".")
            {
                continue;
            }

            current = Path.Combine(current, segment);
            if (HasReparsePoint(current))
            {
                return true;
            }
        }

        return false;
    }

    private static bool HasReparsePoint(string path)
    {
        try
        {
            return File.Exists(path) || Directory.Exists(path)
                ? (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0
                : false;
        }
        catch (IOException)
        {
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return true;
        }
    }

    private static string EnsureTrailingSeparator(string path)
    {
        return path.EndsWith(Path.DirectorySeparatorChar)
            ? path
            : path + Path.DirectorySeparatorChar;
    }
}
