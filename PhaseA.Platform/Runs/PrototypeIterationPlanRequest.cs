namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanRequest(
    string? Message,
    string? SourceKind = null,
    IReadOnlyList<TextAttachment>? Attachments = null,
    string? Model = null);
