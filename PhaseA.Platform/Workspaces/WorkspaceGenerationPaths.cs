using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace PhaseA.Platform.Workspaces;

public static class WorkspaceGenerationPaths
{
    // ADR-0038/0061: bind evidence to the server-selected source generation
    // without disclosing its host paths or confusing it with stable exports.
    public static string SourceGenerationId(ProjectSnapshot project)
    {
        var paths = new[] { project.WorkspaceRootPath, project.RepoPath, project.RuntimePath, project.MetaPath }
            .Select(path => Path.TrimEndingDirectorySeparator(Path.GetFullPath(path)))
            .Select(path => OperatingSystem.IsWindows() ? path.ToUpperInvariant() : path);
        var identity = new[] { project.AccountId, project.ProjectId, project.WorkspaceId }.Concat(paths);
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(identity))))
            .ToLowerInvariant();
    }

    // ADR-0035/0061: the protected registration owns the stable storage boundary.
    // Active source paths may point at a generation inside that boundary.
    public static string StorageRoot(ProjectSnapshot project)
    {
        if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.WorkspaceRootPath, out var descriptor))
            return project.WorkspaceRootPath;
        if (descriptor.AccountId != project.AccountId || descriptor.ProjectId != project.ProjectId ||
            !WorkspacePathPolicy.IsUnderRoot(descriptor.WorkspaceRoot, project.WorkspaceRootPath))
            throw new UnauthorizedAccessException("Workspace generation registration does not match the project.");
        return descriptor.WorkspaceRoot;
    }
}
