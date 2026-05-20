namespace PhaseA.Platform.Runs;

public sealed record HostedProcessCommand(
    string FileName,
    IReadOnlyList<string> Arguments,
    string WorkingDirectory,
    IReadOnlyDictionary<string, string> Environment,
    string? StandardInput = null);
