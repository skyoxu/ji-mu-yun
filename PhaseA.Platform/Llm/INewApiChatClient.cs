namespace PhaseA.Platform.Llm;

using PhaseA.Platform.Data;

public interface INewApiChatClient
{
    Task<NewApiChatClientResult> CompleteAsync(
        LlmBindingSnapshot binding,
        string bearerToken,
        string model,
        IReadOnlyList<ChatMessage> messages,
        CancellationToken cancellationToken = default);
}

public sealed record NewApiChatClientResult(
    bool Succeeded,
    string? AssistantMessage,
    string? FailureCode,
    string? RequestId,
    string? RawError);
