namespace PhaseA.Platform.Runs;

public interface IPrototypeLightweightValidationService
{
    Task<PrototypeWorkflowResult> ValidateAsync(string accountId, string projectId, CancellationToken cancellationToken = default);
}

public sealed class PrototypeLightweightValidationService : IPrototypeLightweightValidationService
{
    private readonly PrototypeWorkflowService _prototypeWorkflowService;

    public PrototypeLightweightValidationService(PrototypeWorkflowService prototypeWorkflowService)
    {
        _prototypeWorkflowService = prototypeWorkflowService;
    }

    public Task<PrototypeWorkflowResult> ValidateAsync(string accountId, string projectId, CancellationToken cancellationToken = default)
    {
        return _prototypeWorkflowService.ValidateSkeletonAsync(accountId, projectId, cancellationToken);
    }
}
