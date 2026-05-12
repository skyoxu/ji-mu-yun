namespace PhaseA.Platform.Runs;

public sealed record PrototypeWorkflowProgress(
    string Status,
    string Step,
    string Substep,
    string Label,
    string? UpdatedUtc,
    string? RunId,
    string? Failure);
