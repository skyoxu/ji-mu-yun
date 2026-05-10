namespace PhaseA.Platform.Configuration;

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
    string? AdminTokenHash);
