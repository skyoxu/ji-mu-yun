namespace PhaseA.Platform.Readback;

public sealed record AdminLlmRunAuditItem(
    string AccountId,
    string Username,
    string ProjectId,
    string RunId,
    string RunType,
    string Status,
    string? LlmGateway,
    string? LlmModel,
    string? LlmRequestId,
    string? LlmCostJson);
