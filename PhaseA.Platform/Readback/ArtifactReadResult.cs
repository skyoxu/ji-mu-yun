namespace PhaseA.Platform.Readback;

public sealed record ArtifactReadResult(
    string ArtifactId,
    string ArtifactType,
    string RelativePath,
    string Summary,
    string Content,
    string ContentType);
