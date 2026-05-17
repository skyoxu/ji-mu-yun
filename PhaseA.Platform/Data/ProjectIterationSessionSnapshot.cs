namespace PhaseA.Platform.Data;

public sealed record ProjectIterationSessionSnapshot(
    string SessionId,
    string ProjectId,
    string AccountId,
    string SourceKind,
    string SourceMessage,
    string OverallGoal,
    string Status,
    int CurrentGoalIndex,
    string? LatestSummary,
    string CreatedUtc,
    string UpdatedUtc,
    string? CompletedUtc);

public sealed record ProjectIterationGoalSnapshot(
    string GoalId,
    string SessionId,
    int GoalIndex,
    string Title,
    string Description,
    string? AcceptanceHint,
    string Status,
    string? ResultSummary,
    string CreatedUtc,
    string UpdatedUtc,
    string? CompletedUtc);

public sealed record ProjectIterationGoalRunSnapshot(
    string GoalRunId,
    string SessionId,
    string GoalId,
    string RunId,
    string RunType,
    string CreatedUtc);

public sealed record ProjectIterationSessionDetails(
    ProjectIterationSessionSnapshot Session,
    IReadOnlyList<ProjectIterationGoalSnapshot> Goals,
    IReadOnlyList<ProjectIterationGoalRunSnapshot> GoalRuns);
