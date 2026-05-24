namespace PhaseA.Platform.Readback;

public sealed record ActiveRunReadback(
    bool Busy,
    string? RunId,
    string? ProjectId,
    string? RunType,
    string? Status,
    string? ProgressStep,
    string? ProgressLabel,
    int HeavyRunnerQueuedCount = 0,
    int? HeavyRunnerQueuePosition = null,
    int? HeavyRunnerEstimatedWaitSeconds = null,
    bool HeavyRunnerRunning = false);
