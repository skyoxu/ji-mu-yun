namespace PhaseA.Platform.Runs;

public sealed record PrototypeSceneRequest(
    string? Slug,
    string? SceneRoot = null,
    string? PrototypeRoot = null);
