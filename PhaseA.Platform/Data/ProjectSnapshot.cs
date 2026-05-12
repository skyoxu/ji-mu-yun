namespace PhaseA.Platform.Data;

public sealed record ProjectSnapshot(
    string ProjectId,
    string AccountId,
    string Name,
    string GameName,
    string GameTypeSource,
    string TemplateRuleId,
    bool LlmBindingRequired,
    string AllowedWorkflowsJson,
    string BootstrapStatus,
    string? BootstrapError,
    string WorkspaceId,
    string WorkspaceRootPath,
    string RepoPath,
    string RuntimePath,
    string MetaPath);
