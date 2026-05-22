namespace PhaseA.Platform.Readback;

public sealed record ProjectAssetInventoryResult(
    string ProjectId,
    bool CanReadInventory,
    string? DisabledReason,
    IReadOnlyList<ProjectAssetUsageItem> UsedAssets,
    IReadOnlyList<ProjectAssetGenerationCandidate> GenerationCandidates);

public sealed record ProjectAssetUsageItem(
    string InstanceName,
    string NodeType,
    string ScenePath,
    string ResourcePath,
    string IntendedUse,
    int? PixelWidth,
    int? PixelHeight,
    string PreviewUrl);

public sealed record ProjectAssetGenerationCandidate(
    string InstanceName,
    string NodeType,
    string ScenePath,
    string SuggestedAssetKind,
    string IntendedUse,
    string Reason,
    string LlmJudgementStatus);

public sealed record ProjectAssetPreviewReadResult(
    string FileName,
    string ContentType,
    byte[] Content);

public sealed record AssetPreviewTicketRequest(string? ResourcePath);
