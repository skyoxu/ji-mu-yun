using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed record PrototypeWorkflowResult(
    string RunId,
    string Status,
    int ExitCode,
    string PrototypeRecordPath,
    string Stdout,
    string Stderr,
    IReadOnlyList<ArtifactSnapshot> Artifacts,
    IReadOnlyList<string> MissingRequiredFields);
