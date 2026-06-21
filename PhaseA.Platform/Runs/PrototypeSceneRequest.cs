namespace PhaseA.Platform.Runs;

public sealed record PrototypeSceneRequest(
    string? Slug,
    string? SceneRoot = null,
    string? PrototypeRoot = null,
    string? GameType = null,
    string? Hypothesis = null,
    string? CorePlayerFantasy = null,
    string? MinimumPlayableLoop = null,
    string? GameFeature = null,
    string? CoreGameplayLoop = null,
    string? WinFailConditions = null,
    string? EngineBackend = null,
    string? EngineApplyMode = null,
    string? EngineConfidence = null,
    string? EngineReason = null,
    bool? EngineRequiresPlugin = null,
    string? EngineInstallTarget = null);
