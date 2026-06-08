namespace PhaseA.Platform.Data;

public sealed record AdminRunMetricsRow(
    string AccountId,
    string Username,
    string ProjectId,
    string ProjectName,
    string GameName,
    RunSnapshot Run);
