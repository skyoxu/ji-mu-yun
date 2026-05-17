namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanRequest(
    string? Message,
    string? SourceKind = null);
