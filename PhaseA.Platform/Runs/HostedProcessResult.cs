namespace PhaseA.Platform.Runs;

public sealed record HostedProcessResult(
    int ExitCode,
    string Stdout,
    string Stderr);
