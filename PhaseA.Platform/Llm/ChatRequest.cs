namespace PhaseA.Platform.Llm;

public sealed record ChatRequest(
    string? Message,
    string? Model = null,
    IReadOnlyList<ChatMessage>? History = null,
    string? SkillActionId = null,
    IReadOnlyList<TextAttachment>? Attachments = null);

public sealed record ChatMessage(
    string Role,
    string Content);
