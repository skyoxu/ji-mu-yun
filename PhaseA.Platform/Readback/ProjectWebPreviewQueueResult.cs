namespace PhaseA.Platform.Readback;

public sealed record ProjectWebPreviewQueueResult(
    string ProjectId,
    string RunId,
    string Status,
    string FileName,
    string? FailureCode);
