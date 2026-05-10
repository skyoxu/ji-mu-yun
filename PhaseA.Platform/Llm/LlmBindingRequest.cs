namespace PhaseA.Platform.Llm;

public sealed record LlmBindingRequest(
    string? GatewayProvider,
    string? GatewayBaseUrl,
    string? ExternalAccountRef,
    string? TokenRef,
    string? ApiKey = null,
    string? ProviderKey = null,
    string? UpstreamProviderKey = null,
    string? Secret = null);
