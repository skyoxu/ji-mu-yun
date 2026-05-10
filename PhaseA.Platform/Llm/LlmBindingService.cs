using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Llm;

public sealed class LlmBindingService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;

    public LlmBindingService(PhaseAMetadataStore metadataStore, PhaseAPlatformOptions options)
    {
        _metadataStore = metadataStore;
        _options = options;
    }

    public async Task<LlmBindingResult> BindAsync(string accountId, LlmBindingRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentNullException.ThrowIfNull(request);

        if (ContainsProviderSecret(request))
        {
            return LlmBindingResult.Failure("provider_key_not_allowed");
        }

        var provider = string.IsNullOrWhiteSpace(request.GatewayProvider) ? _options.LlmGatewayProvider : request.GatewayProvider.Trim();
        if (!string.Equals(provider, "new-api", StringComparison.OrdinalIgnoreCase))
        {
            return LlmBindingResult.Failure("unsupported_llm_gateway");
        }

        var baseUrl = string.IsNullOrWhiteSpace(request.GatewayBaseUrl) ? _options.LlmGatewayBaseUrl : request.GatewayBaseUrl.Trim();
        if (!Uri.TryCreate(baseUrl, UriKind.Absolute, out var uri) || uri.Scheme != Uri.UriSchemeHttps)
        {
            return LlmBindingResult.Failure("invalid_gateway_base_url");
        }

        if (string.IsNullOrWhiteSpace(request.ExternalAccountRef))
        {
            return LlmBindingResult.Failure("external_account_ref_required");
        }

        if (string.IsNullOrWhiteSpace(request.TokenRef))
        {
            return LlmBindingResult.Failure("token_ref_required");
        }

        var command = new LlmBindingCommand(
            accountId,
            provider,
            uri.ToString().TrimEnd('/'),
            request.ExternalAccountRef.Trim(),
            request.TokenRef.Trim());
        await _metadataStore.UpsertLlmBindingAsync(command, cancellationToken);
        var binding = await _metadataStore.GetLlmBindingAsync(accountId, cancellationToken);
        return LlmBindingResult.Ok(binding!);
    }

    public Task<LlmBindingSnapshot?> GetAsync(string accountId, CancellationToken cancellationToken = default)
    {
        return _metadataStore.GetLlmBindingAsync(accountId, cancellationToken);
    }

    private static bool ContainsProviderSecret(LlmBindingRequest request)
    {
        return !string.IsNullOrWhiteSpace(request.ApiKey) ||
               !string.IsNullOrWhiteSpace(request.ProviderKey) ||
               !string.IsNullOrWhiteSpace(request.UpstreamProviderKey) ||
               !string.IsNullOrWhiteSpace(request.Secret);
    }
}
