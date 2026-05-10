namespace PhaseA.Platform.Data;

public sealed record ProjectCreationResult(
    bool Succeeded,
    string? ProjectId,
    string? WorkspaceId,
    string? WorkspaceRootPath,
    string? TemplateRuleId,
    bool? LlmBindingRequired,
    IReadOnlyList<string> AllowedWorkflows,
    string? FailureCode,
    int? ProjectLimit)
{
    public static ProjectCreationResult Created(string projectId)
    {
        return new ProjectCreationResult(true, projectId, null, null, null, null, [], null, null);
    }

    public static ProjectCreationResult Created(
        string projectId,
        string workspaceId,
        string workspaceRootPath,
        string templateRuleId,
        bool llmBindingRequired,
        IReadOnlyList<string> allowedWorkflows)
    {
        return new ProjectCreationResult(
            true,
            projectId,
            workspaceId,
            workspaceRootPath,
            templateRuleId,
            llmBindingRequired,
            allowedWorkflows,
            null,
            null);
    }

    public static ProjectCreationResult QuotaExceeded(int projectLimit)
    {
        return Failure("project_quota_exceeded", projectLimit);
    }

    public static ProjectCreationResult Failure(string failureCode, int? projectLimit = null)
    {
        return new ProjectCreationResult(false, null, null, null, null, null, [], failureCode, projectLimit);
    }
}
