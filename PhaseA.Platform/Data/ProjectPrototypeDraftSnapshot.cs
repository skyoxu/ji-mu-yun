namespace PhaseA.Platform.Data;

public sealed record ProjectPrototypeDraftSnapshot(
    string ProjectId,
    string Status,
    string? RunId,
    string? FileName,
    string? PrototypeSlug,
    string? Hypothesis,
    string? CorePlayerFantasy,
    string? MinimumPlayableLoop,
    string SuccessCriteriaJson,
    string? GameFeature,
    string? CoreGameplayLoop,
    string? WinFailConditions,
    string MatchedFieldsJson,
    string WarningsJson,
    string? FailureCode,
    int LineCount,
    int ByteCount,
    string UpdatedUtc);
