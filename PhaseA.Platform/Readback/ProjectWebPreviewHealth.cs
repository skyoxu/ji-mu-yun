namespace PhaseA.Platform.Readback;

public sealed record ProjectWebPreviewHealth(
    string Status,
    string? Godot3Bin,
    bool Godot3BinExists,
    string TemplateDirectory,
    bool Html5TemplatesExist,
    string SmokeStatus,
    string? SmokeError,
    int ExportTimeoutSeconds = 180,
    int ExportInactivityTimeoutSeconds = 45);
