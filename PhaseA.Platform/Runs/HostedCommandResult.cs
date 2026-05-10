using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed record HostedCommandResult(
    string RunId,
    string Status,
    int ExitCode,
    string Stdout,
    string Stderr,
    IReadOnlyList<ArtifactSnapshot> Artifacts,
    IReadOnlyList<string> MissingRequiredFields);
