namespace PhaseA.Platform.Workspaces;

public enum RestoreAttemptStatus
{
    Requested,
    Staging,
    Published,
    Quarantined,
    Failed
}

public sealed record RestoreAttempt(string AttemptId, string SnapshotId, string WorkspaceId, RestoreAttemptStatus Status)
{
    public RestoreAttempt Advance(RestoreAttemptStatus next)
    {
        if (next < Status || (Status == RestoreAttemptStatus.Published && next != Status))
        {
            throw new InvalidOperationException("restore attempt state cannot move backwards or after publication");
        }

        return this with { Status = next };
    }

    public bool IsRetryable => Status is RestoreAttemptStatus.Quarantined or RestoreAttemptStatus.Failed;

    public RestoreAttempt Retry()
    {
        if (!IsRetryable)
        {
            throw new InvalidOperationException("only failed or quarantined restore attempts can be retried");
        }

        return this with { Status = RestoreAttemptStatus.Staging };
    }
}
