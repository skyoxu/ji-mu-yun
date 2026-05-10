namespace PhaseA.Platform.Runs;

public sealed record PrototypeTddRequest(
    string? Slug,
    string? Stage,
    string? Expect = null,
    string? RecordPath = null,
    string? Filter = null,
    int? TimeoutSec = null);
