namespace PhaseA.Platform.Projects;

public sealed record ProjectCreationRequest(
    string? ProjectName,
    string? GameName,
    string? GameTypeSource,
    string? TemplateRuleId,
    string? GitUrl,
    string? RepositoryUrl,
    string? RepoUrl);
