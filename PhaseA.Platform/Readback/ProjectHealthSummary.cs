namespace PhaseA.Platform.Readback;

public sealed record ProjectHealthSummary(
    string Status,
    string GeneratedAt,
    string Stage,
    string StageSummary,
    string DoctorStatus,
    int DoctorFailCount,
    int DoctorWarnCount,
    int DoctorOkCount,
    string BoundaryStatus,
    int BoundaryFailCount,
    int BoundaryWarnCount,
    int ActiveTaskTotal,
    int JsonReportTotal,
    int InvalidJsonReportTotal,
    int OverlayIndexCount,
    int ContractFileCount,
    int UnitTestFileCount,
    string TopRecommendation,
    string DashboardPath);
