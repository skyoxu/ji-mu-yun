namespace PhaseA.Platform.Data;

public sealed record InterruptedRunSnapshot(
    string RunId,
    string ProjectId,
    string RunType,
    string Status,
    string CreatedUtc,
    string? StartedUtc,
    string? ProgressUpdatedUtc);
