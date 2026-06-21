namespace PhaseA.Platform.Runs;

public sealed record PrototypeSceneRequest(
    string? Slug,
    string? SceneRoot = null,
    string? PrototypeRoot = null,
    string? EngineBackend = null,
    string? EngineApplyMode = null,
    string? EngineConfidence = null,
    string? EngineReason = null,
    bool? EngineRequiresPlugin = null,
    string? EngineInstallTarget = null);
