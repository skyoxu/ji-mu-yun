namespace PhaseA.Platform.Runs;

public sealed class ProjectCreationRunnerQueue
{
    public ProjectCreationRunnerQueue(HeavyRunnerQueueService queue)
    {
        Queue = queue;
    }

    public HeavyRunnerQueueService Queue { get; }
}
