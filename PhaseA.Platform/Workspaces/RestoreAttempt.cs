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
}
