namespace PhaseA.Platform.Data;

public sealed record ProjectGameTypeMatchFailureSnapshot(
    string FailureId,
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
    string MissingGuidePath,
    string MatchedGameTypeId,
    string MatchedGuidePath,
    string SteamAppId,
    string SteamName,
    string SteamResolvedQuery,
    string SteamAttemptedQueriesJson,
    string CreatedUtc);
