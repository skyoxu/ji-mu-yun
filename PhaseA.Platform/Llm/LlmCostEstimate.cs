namespace PhaseA.Platform.Llm;

public sealed record LlmCostEstimate(
    decimal EstimatedCostCny,
    string? Model = null,
    string? RequestId = null);
