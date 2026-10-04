using PhaseA.Platform.Data;
using PhaseA.Platform.Security;

namespace PhaseA.Platform.Workspaces;

public static class WorkspaceGenerationPaths
{
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
