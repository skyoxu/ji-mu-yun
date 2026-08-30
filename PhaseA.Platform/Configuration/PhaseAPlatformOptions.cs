namespace PhaseA.Platform.Configuration;

public sealed record HostedContextSigningKeyRing(
    string ActiveKeyId,
    IReadOnlyDictionary<string, string> Keys);

public sealed record PhaseAPlatformOptions(
    string HostedWorkspaceRoot,
    int HostedProjectLimit,
    string HttpsTermination,
    string AppBindUrl,
    string PublicBaseUrl,
    string LlmGatewayProvider,
    string LlmGatewayBaseUrl,
    string LlmGatewayTokenMode,
    string LlmGatewayBindingMode,
    decimal LlmCostStopLossPerRunCny,
    decimal LlmCostStopLossDailyAccountCny,
    string MetadataDatabasePath,
    string RepositoryRoot,
    string PythonCommand,
    string? GodotBin,
    string DeliveryProfile,
    string AdminUsername,
    string? AdminPasswordHash,
    string? AdminTokenHash,
    string? TicketSigningSecret,
    string? WebPreviewSigningSecret,
    HostedContextSigningKeyRing? HostedContextSigningKeyRing,
    int MaxConcurrentChats,
    int MaxConcurrentChatsPerAccount,
    int MaxConcurrentQuestionForms,
    int MaxConcurrentQuestionFormsPerAccount,
    int MaxConcurrentProjectCreations,
    int MaxConcurrentProjectCreationsPerAccount,
    int MaxConcurrentOtherRuns,
    int MaxConcurrentPrototypeCreations,
    int MaxConcurrentAssetGenerations,
    int MaxConcurrentWebPreviews,
    int MaxConcurrentWebPreviewsPerAccount,
    int Godot3WebPreviewExportTimeoutSeconds,
    int Godot3WebPreviewExportInactivityTimeoutSeconds,
    int MaxConcurrentAssetGenerationsPerAccount,
    bool AiCodeMirrorBillingEnabled,
    string AiCodeMirrorBaseUrl,
    string? AiCodeMirrorCookie,
    string? AiCodeMirrorApiKeyName,
    string AiCodeMirrorCodexHomeRoot,
    IReadOnlyList<string> AssetAllowedUrlPrefixes)
{
    public string PhaseServiceState { get; init; } = PhaseServiceStates.Development;

    public bool GovernanceChecksEnabled =>
        PhaseServiceStates.GovernanceChecksEnabled(PhaseServiceState);
}

public static class PhaseServiceStates
{
    public const string Development = "development";
    public const string Test = "test";
    public const string Production = "production";

    public static bool GovernanceChecksEnabled(string state) =>
        state == Test || state == Production;
}
