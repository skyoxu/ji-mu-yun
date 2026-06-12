namespace PhaseA.Platform.Data;

public sealed record RunDurationMetricSnapshot(
    string AccountId,
    string Username,
    string ProjectId,
    string ProjectName,
    string GameName,
    string RunId,
    string RunType,
    string Status,
    string CreatedUtc,
    string? StartedUtc,
    string? FinishedUtc,
    int? QueuePositionAtStart,
    double? QueueSeconds,
    double? RuntimeSeconds,
    int? ExitCode);
