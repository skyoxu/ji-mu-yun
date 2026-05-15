namespace PhaseA.Platform.Data;

public sealed record StaleProjectInitializationSnapshot(
    string ProjectId,
    string AccountId,
    string Name,
    string GameName,
    string GameTypeSource,
    string TemplateRuleId,
    string WorkspaceRootPath,
    string RunId,
    string RunStatus,
    string CreatedUtc,
    string? StartedUtc);
