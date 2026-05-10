namespace PhaseA.Platform.Data;

public sealed record ProjectCreationCommand(
    string ProjectId,
    string AccountId,
    string ProjectName,
    string GameName,
    string GameTypeSource,
    string TemplateRuleId,
    bool LlmBindingRequired,
    IReadOnlyList<string> AllowedWorkflows,
    string WorkspaceRootPath,
    string RepoPath,
    string RuntimePath,
    string MetaPath);
