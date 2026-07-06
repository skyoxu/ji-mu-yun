namespace PhaseA.Platform.Projects;

public sealed record ProjectDeletionResult(
    bool Succeeded,
    string? ProjectId,
    string? FailureCode,
    string? WarningCode = null)
{
    public static ProjectDeletionResult Deleted(string projectId, string? warningCode = null)
    {
        return new ProjectDeletionResult(true, projectId, null, warningCode);
    }

    public static ProjectDeletionResult Failure(string failureCode)
    {
        return new ProjectDeletionResult(false, null, failureCode);
    }
}
