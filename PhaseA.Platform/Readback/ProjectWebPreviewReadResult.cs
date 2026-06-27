namespace PhaseA.Platform.Readback;

public sealed record ProjectWebPreviewReadResult(
    string FileName,
    string ContentType,
    string FilePath);
