namespace PhaseA.Platform.Runs;

public sealed record GameDesignDocumentReadResult(
    string FileName,
    string ContentType,
    byte[] Content,
    string RelativePath,
    long SizeBytes,
    string LastUpdatedUtc);
