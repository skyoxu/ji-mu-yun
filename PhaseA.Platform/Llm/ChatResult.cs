namespace PhaseA.Platform.Llm;

public sealed record ChatResult(
    string RunId,
    string Status,
    int ExitCode,
    string? AssistantMessage,
    string? FailureCode,
    string? Model);
