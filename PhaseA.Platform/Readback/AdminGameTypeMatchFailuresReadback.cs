using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record AdminGameTypeMatchFailuresReadback(
    int Count,
    IReadOnlyList<ProjectGameTypeMatchFailureSnapshot> Failures);

public sealed record AdminGameTypeMatchRecordsReadback(
    int Count,
    IReadOnlyList<ProjectGameTypeMatchFailureSnapshot> Records);
