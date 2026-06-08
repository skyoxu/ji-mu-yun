namespace PhaseA.Platform.Data;

public sealed record AdminChatRunMetricsRow(
    string AccountId,
    string Username,
    int RunCount,
    double? AverageQueueSeconds,
    double? AverageRuntimeSeconds);
