namespace PhaseA.Platform.Data;

public sealed record ArtifactSnapshot(
    string ArtifactId,
    string? RunId,
    string ProjectId,
    string ArtifactType,
    string RelativePath,
    string Summary);
