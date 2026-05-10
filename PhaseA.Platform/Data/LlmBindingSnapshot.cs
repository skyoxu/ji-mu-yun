namespace PhaseA.Platform.Data;

public sealed record LlmBindingSnapshot(
    string AccountId,
    string GatewayProvider,
    string GatewayBaseUrl,
    string ExternalAccountRef,
    string TokenRef);
