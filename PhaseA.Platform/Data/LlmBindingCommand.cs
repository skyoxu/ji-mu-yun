namespace PhaseA.Platform.Data;

public sealed record LlmBindingCommand(
    string AccountId,
    string GatewayProvider,
    string GatewayBaseUrl,
    string ExternalAccountRef,
    string TokenRef);
