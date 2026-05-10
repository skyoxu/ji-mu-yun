namespace PhaseA.Platform.Llm;

public sealed record LlmStopLossDecision(
    bool Allowed,
    string? FailureCode,
    decimal EstimatedCostCny,
    decimal DailyTotalAfterCny);
