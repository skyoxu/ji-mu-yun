using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record AdminGameTypeMatchFailuresReadback(
    int Count,
    IReadOnlyList<ProjectGameTypeMatchFailureSnapshot> Failures);
