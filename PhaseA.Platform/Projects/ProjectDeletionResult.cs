namespace PhaseA.Platform.Projects;

public sealed record ProjectDeletionResult(
    bool Succeeded,
    string? ProjectId,
    string? FailureCode)
{
    public static ProjectDeletionResult Deleted(string projectId)
    {
        return new ProjectDeletionResult(true, projectId, null);
    }

    public static ProjectDeletionResult Failure(string failureCode)
    {
        return new ProjectDeletionResult(false, null, failureCode);
    }
}
