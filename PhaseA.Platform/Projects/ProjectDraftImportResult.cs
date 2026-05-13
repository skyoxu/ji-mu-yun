namespace PhaseA.Platform.Projects;

public sealed record ProjectDraftImportResult(
    string Status,
    string RunId,
    string FileName,
    string? ProjectName,
    string? GameName,
    string? GameTypeSource,
    string? PrototypeSlug,
    string? Hypothesis,
    string? CorePlayerFantasy,
    string? MinimumPlayableLoop,
    IReadOnlyList<string> SuccessCriteria,
    string? GameFeature,
    string? CoreGameplayLoop,
    string? WinFailConditions,
    IReadOnlyList<string> MatchedFields,
    IReadOnlyList<string> Warnings,
    IReadOnlyList<string> UnparsedLines,
    int LineCount,
    int ByteCount,
    string? FailureCode = null);
