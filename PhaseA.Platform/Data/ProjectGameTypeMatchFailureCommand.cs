namespace PhaseA.Platform.Data;

public sealed record ProjectGameTypeMatchFailureCommand(
    string AccountId,
    string ProjectId,
    string ProjectName,
    string GameName,
    string GameTypeSource,
    string MatchStatus,
    string StatusReason,
    string ReferenceQuery,
    string NormalizedGenreTagsJson,
    string CandidateScoresJson,
    string MissingGuidePath);
