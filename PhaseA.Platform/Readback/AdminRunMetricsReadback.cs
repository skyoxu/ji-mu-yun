namespace PhaseA.Platform.Readback;

public sealed record AdminRunMetricsReadback(
    int Count,
    IReadOnlyList<AdminRunMetricsItem> Runs,
    IReadOnlyList<AdminChatRunMetricsItem> ChatAverages);

public sealed record AdminRunMetricsItem(
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
    double? RuntimeSeconds);

public sealed record AdminChatRunMetricsItem(
    string AccountId,
    string Username,
    int RunCount,
    double? AverageQueueSeconds,
    double? AverageRuntimeSeconds);
