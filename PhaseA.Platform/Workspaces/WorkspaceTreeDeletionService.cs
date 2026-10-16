namespace PhaseA.Platform.Workspaces;

public sealed record WorkspaceDeletionResult(bool Succeeded, string? FailureCode = null);

public sealed class WorkspaceTreeDeletionService
{
    private readonly string _workspaceRoot;

    public WorkspaceTreeDeletionService(string workspaceRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        _workspaceRoot = Path.GetFullPath(workspaceRoot).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var filesystemRoot = Path.GetPathRoot(_workspaceRoot)?.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (string.Equals(filesystemRoot, _workspaceRoot, StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("workspace_root_must_not_be_filesystem_root", nameof(workspaceRoot));
    }

    public WorkspaceDeletionResult Delete(string accountId, string projectId, string recordedRootPath)
    {
        if (!IsHex32(accountId) || !IsHex32(projectId))
            return new(false, "workspace_identity_invalid");

        var expected = Path.GetFullPath(Path.Combine(_workspaceRoot, accountId, projectId));
        var recorded = Path.GetFullPath(recordedRootPath);
        if (!string.Equals(expected, recorded, StringComparison.OrdinalIgnoreCase) ||
            !IsDirectChildPath(recorded, _workspaceRoot))
            return new(false, "workspace_path_mismatch");

        try
        {
            if (Directory.Exists(_workspaceRoot) && HasReparsePoint(_workspaceRoot))
                return new(false, "workspace_root_reparse_point");
            if (!Directory.Exists(recorded) && !File.Exists(recorded))
                return new(true);
            if (HasReparsePoint(recorded))
                return new(false, "workspace_root_reparse_point");
            DeleteDirectoryContents(recorded);
            Directory.Delete(recorded, false);
            return new(true);
        }
        catch (UnauthorizedAccessException)
        {
            return new(false, "workspace_delete_access_denied");
        }
        catch (IOException)
        {
            return new(false, "workspace_delete_io_error");
        }
    }

    private static void DeleteDirectoryContents(string directory)
    {
        foreach (var entry in Directory.EnumerateFileSystemEntries(directory))
        {
            if (HasReparsePoint(entry))
            {
                if (Directory.Exists(entry)) Directory.Delete(entry, false);
                else File.Delete(entry);
                continue;
            }

            if (Directory.Exists(entry))
            {
                DeleteDirectoryContents(entry);
                Directory.Delete(entry, false);
            }
            else
            {
                File.Delete(entry);
            }
        }
    }

    private static bool HasReparsePoint(string path)
    {
        try
        {
            return (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0;
        }
        catch (IOException)
        {
            throw;
        }
        catch (UnauthorizedAccessException)
        {
            throw;
        }
    }

    private static bool IsHex32(string value) =>
        value.Length == 32 && value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f' or >= 'A' and <= 'F');

    private static bool IsDirectChildPath(string path, string root)
    {
        var relative = Path.GetRelativePath(root, path);
        var parts = relative.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries);
        return parts.Length == 2 && IsHex32(parts[0]) && IsHex32(parts[1]);
    }
}
