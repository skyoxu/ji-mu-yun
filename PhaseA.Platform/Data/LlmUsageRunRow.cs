namespace PhaseA.Platform.Data;

public sealed record LlmUsageRunRow(
    string AccountId,
    string Username,
    bool IsAdmin,
    bool IsDisabled,
    string ProjectId,
    string ProjectName,
    string GameName,
    string RunId,
    string RunType,
    string Status,
    string CreatedUtc,
    string? LlmModel,
    string LlmCostJson);
