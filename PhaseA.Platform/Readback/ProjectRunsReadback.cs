using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record ProjectRunsReadback(
    ProjectSnapshot Project,
    IReadOnlyList<RunSnapshot> Runs);
