namespace PhaseA.Platform.Readback;

public sealed record ProjectWebPreviewPackageStatus(
    string Status,
    string? PreviewId,
    string? PreviewUrl,
    string? Mode,
    string? CreatedUtc,
    string? RunId = null,
    string? FailureCode = null,
    string? UpdatedUtc = null,
    int? QueuePosition = null,
    int? EstimatedWaitSeconds = null,
    string? FidelityTier = null,
    string? PlayableSurface = null,
    string? GameTypeId = null,
    string? GameTypeGuide = null);
