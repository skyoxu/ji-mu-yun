namespace PhaseA.Platform.Runs;

public sealed record GameDesignDocumentRequest(
    string? Message,
    string? Model = null,
    IReadOnlyList<TextAttachment>? Attachments = null);
