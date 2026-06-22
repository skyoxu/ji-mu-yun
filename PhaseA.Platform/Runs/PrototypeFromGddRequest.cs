namespace PhaseA.Platform.Runs;

public sealed record PrototypeFromGddRequest(
    bool Confirm = true,
    int? StopAfterDay = null,
    string? ScoreEngine = null,
    string? Model = null);
