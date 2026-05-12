namespace PhaseA.Platform.Llm;

public interface ICodexChatClient
{
    Task<CodexChatClientResult> CompleteAsync(
        string projectRoot,
        string model,
        string prompt,
        CancellationToken cancellationToken = default);
}

public sealed record CodexChatClientResult(
    bool Succeeded,
    string? AssistantMessage,
    string? FailureCode,
    int ExitCode,
    string Stdout,
    string Stderr);
