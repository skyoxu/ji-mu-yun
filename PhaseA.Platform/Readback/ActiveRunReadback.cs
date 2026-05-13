namespace PhaseA.Platform.Readback;

public sealed record ActiveRunReadback(
    bool Busy,
    string? RunId,
    string? ProjectId,
    string? RunType,
    string? Status,
    string? ProgressStep,
    string? ProgressLabel);
