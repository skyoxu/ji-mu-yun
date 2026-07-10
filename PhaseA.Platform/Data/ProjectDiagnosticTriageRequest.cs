namespace PhaseA.Platform.Data;

public sealed record ProjectDiagnosticTriageRequest(
    string TriageStatus,
    string TriageDecisionReason,
    string? ReplacementEvidenceRefsJson = null);
