using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record AdminGameTypeMatchFailuresReadback(
    int Count,
    IReadOnlyList<ProjectGameTypeMatchFailureSnapshot> Failures);

public sealed record AdminGameTypeMatchRecordsReadback(
    int Count,
    IReadOnlyList<AdminGameTypeMatchRecordReadback> Records);

public sealed record AdminGameTypeMatchRecordReadback(
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
    string CreatedUtc,
    ProjectGameTypeContractSnapshotSummary ContractSnapshot)
{
    public static AdminGameTypeMatchRecordReadback FromSnapshot(
        ProjectGameTypeMatchFailureSnapshot snapshot,
        ProjectGameTypeContractSnapshotSummary contractSnapshot)
    {
        return new AdminGameTypeMatchRecordReadback(
            snapshot.FailureId,
            snapshot.AccountId,
            snapshot.ProjectId,
            snapshot.ProjectName,
            snapshot.GameName,
            snapshot.GameTypeSource,
            snapshot.MatchStatus,
            snapshot.StatusReason,
            snapshot.ReferenceQuery,
            snapshot.NormalizedGenreTagsJson,
            snapshot.CandidateScoresJson,
            snapshot.MissingGuidePath,
            snapshot.MatchedGameTypeId,
            snapshot.MatchedGuidePath,
            snapshot.SteamAppId,
            snapshot.SteamName,
            snapshot.SteamResolvedQuery,
            snapshot.SteamAttemptedQueriesJson,
            snapshot.CreatedUtc,
            contractSnapshot);
    }
}

public sealed record ProjectGameTypeContractSnapshotSummary(
    bool HasContract,
    string MatchedGameTypeId,
    string GuidePath,
    string SourceGuideHash,
    int DefaultSceneCount,
    int RequiredModuleCount,
    IReadOnlyList<string> DefaultSceneIds,
    IReadOnlyList<string> RequiredModuleIds,
    string CreatedUtc,
    string UpdatedUtc)
{
    public static ProjectGameTypeContractSnapshotSummary Empty()
    {
        return new ProjectGameTypeContractSnapshotSummary(false, "", "", "", 0, 0, [], [], "", "");
    }
}
