namespace PhaseA.Platform.Readback;

public sealed record ProjectPackageReadResult(
    string FileName,
    string ContentType,
    byte[] Content);
