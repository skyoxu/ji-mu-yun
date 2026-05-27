namespace PhaseA.Platform.Llm;

public interface ICodexChatClient
{
    Task<CodexChatClientResult> CompleteAsync(
        string projectRoot,
        string model,
        string prompt,
        CodexChatClientOptions? options = null,
        string? billingApiKeyName = null,
        CancellationToken cancellationToken = default);
}

public sealed record CodexChatClientOptions(
    bool IgnoreRules = false,
    string? OutputSchemaPath = null,
    string? ReasoningEffort = null);

public sealed record CodexChatClientResult(
    bool Succeeded,
    string? AssistantMessage,
    string? FailureCode,
    int ExitCode,
    string Stdout,
    string Stderr,
    CodexTokenUsage? TokenUsage = null,
    AiCodeMirrorBillingDelta? ProviderBilling = null);
