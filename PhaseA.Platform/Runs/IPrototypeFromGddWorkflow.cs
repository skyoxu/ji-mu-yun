namespace PhaseA.Platform.Runs;

public interface IPrototypeFromGddWorkflow
{
    Task<PrototypeWorkflowResult> QueueFromGddAsync(
        string accountId,
        string projectId,
        PrototypeFromGddRequest request,
        CancellationToken cancellationToken = default);
}
