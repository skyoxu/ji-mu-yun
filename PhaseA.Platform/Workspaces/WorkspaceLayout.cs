namespace PhaseA.Platform.Workspaces;

public sealed record WorkspaceLayout(
    string RootPath,
    string RepoPath,
    string RuntimePath,
    string MetaPath);
