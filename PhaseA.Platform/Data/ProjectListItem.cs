namespace PhaseA.Platform.Data;

public sealed record ProjectListItem(
    string ProjectId,
    string AccountId,
    string Name,
    string GameName,
    string GameTypeSource,
    string TemplateRuleId,
    string WorkspaceRootPath);
