namespace PhaseA.Platform.Data;

public sealed record ProjectChatMessageSnapshot(
    string MessageId,
    string AccountId,
    string ProjectId,
    string Role,
    string Content,
    string? Kind,
    string CreatedUtc);
