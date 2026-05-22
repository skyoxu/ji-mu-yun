namespace PhaseA.Platform.Readback;

public sealed record AdminLlmRunAuditReadback(
    int Count,
    IReadOnlyList<AdminLlmRunAuditItem> Runs);
