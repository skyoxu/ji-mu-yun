namespace PhaseA.Platform.Data;

public sealed record ProjectCreationFailureCommand(
    string AccountId,
    string ProjectId,
    string ProjectName,
    string GameName,
    string GameTypeSource,
    string TemplateRuleId,
    string WorkspaceRootPath,
    string FailureError);
