using System.Globalization;
using System.Net.Http.Headers;
using System.Text.Json;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Llm;

public sealed record AiCodeMirrorBillingSnapshot(
    bool Enabled,
    string Status,
    decimal? WalletBalanceCny,
    decimal? WalletBonusBalanceCny,
    decimal? ApiKeyTotalConsumedCny,
    long? RawApiKeyTotalConsumed,
    string? ApiKeyName,
    string? FailureCode)
{
    public static AiCodeMirrorBillingSnapshot Disabled(string reason) =>
        new(false, "disabled", null, null, null, null, null, reason);

    public static AiCodeMirrorBillingSnapshot Failed(string failureCode) =>
        new(true, "failed", null, null, null, null, null, failureCode);
}

public sealed record AiCodeMirrorBillingDelta(
    AiCodeMirrorBillingSnapshot Before,
    AiCodeMirrorBillingSnapshot After)
{
    public decimal? ApiKeyConsumedDeltaCny =>
        Before.ApiKeyTotalConsumedCny is { } before && After.ApiKeyTotalConsumedCny is { } after
            ? Math.Max(0m, after - before)
            : null;

    public string Status =>
        ApiKeyConsumedDeltaCny is not null
            ? "captured"
            : After.Enabled
                ? "provider_sampled"
                : "disabled";
}

public interface IAiCodeMirrorBillingClient
{
    Task<AiCodeMirrorBillingSnapshot> CaptureAsync(CancellationToken cancellationToken = default);
    Task<AiCodeMirrorBillingSnapshot> CaptureAsync(string? apiKeyName, CancellationToken cancellationToken = default);
}

public static class AiCodeMirrorBillingCapture
{
    public static async Task<AiCodeMirrorBillingDelta> CaptureDeltaAsync(
        IAiCodeMirrorBillingClient billingClient,
        Func<CancellationToken, Task> action,
        CancellationToken cancellationToken = default)
    {
        var before = await billingClient.CaptureAsync(cancellationToken);
        await action(cancellationToken);
        var after = await billingClient.CaptureAsync(CancellationToken.None);
        return new AiCodeMirrorBillingDelta(before, after);
    }

    public static async Task<AiCodeMirrorBillingDelta> CaptureDeltaAsync(
        IAiCodeMirrorBillingClient billingClient,
        string? apiKeyName,
        Func<CancellationToken, Task> action,
        CancellationToken cancellationToken = default)
    {
        var before = await billingClient.CaptureAsync(apiKeyName, cancellationToken);
        await action(cancellationToken);
        var after = await billingClient.CaptureAsync(apiKeyName, CancellationToken.None);
        return new AiCodeMirrorBillingDelta(before, after);
    }
}

public sealed class DisabledAiCodeMirrorBillingClient : IAiCodeMirrorBillingClient
{
    public Task<AiCodeMirrorBillingSnapshot> CaptureAsync(CancellationToken cancellationToken = default)
    {
        return Task.FromResult(AiCodeMirrorBillingSnapshot.Disabled("billing_client_not_configured"));
    }

    public Task<AiCodeMirrorBillingSnapshot> CaptureAsync(string? apiKeyName, CancellationToken cancellationToken = default)
    {
        return CaptureAsync(cancellationToken);
    }
}

public sealed class AiCodeMirrorBillingClient : IAiCodeMirrorBillingClient
{
    private readonly HttpClient _httpClient;
    private readonly PhaseAPlatformOptions _options;

    public AiCodeMirrorBillingClient(HttpClient httpClient, PhaseAPlatformOptions options)
    {
        _httpClient = httpClient;
        _options = options;
    }

    public async Task<AiCodeMirrorBillingSnapshot> CaptureAsync(CancellationToken cancellationToken = default)
    {
        return await CaptureAsync(_options.AiCodeMirrorApiKeyName, cancellationToken);
    }

    public async Task<AiCodeMirrorBillingSnapshot> CaptureAsync(string? apiKeyName, CancellationToken cancellationToken = default)
    {
        if (!_options.AiCodeMirrorBillingEnabled)
        {
            return AiCodeMirrorBillingSnapshot.Disabled("billing_disabled");
        }

        if (string.IsNullOrWhiteSpace(_options.AiCodeMirrorCookie))
        {
            return AiCodeMirrorBillingSnapshot.Disabled("missing_aicodemirror_cookie");
        }

        try
        {
            var wallet = await ReadWalletAsync(cancellationToken);
            var apiKey = await ReadApiKeyAsync(apiKeyName, cancellationToken);
            return new AiCodeMirrorBillingSnapshot(
                true,
                "ok",
                wallet.BalanceCny,
                wallet.BonusBalanceCny,
                apiKey.TotalConsumedCny,
                apiKey.RawTotalConsumed,
                apiKey.Name,
                null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or JsonException or InvalidOperationException)
        {
            return AiCodeMirrorBillingSnapshot.Failed("aicodemirror_billing_sample_failed");
        }
    }

    private async Task<WalletResult> ReadWalletAsync(CancellationToken cancellationToken)
    {
        using var request = BuildRequest(HttpMethod.Get, "/api/wallet");
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        var data = RequireObject(document.RootElement, "data");
        return new WalletResult(ReadMoney(data, "balance"), ReadMoney(data, "bonusBalance"));
    }

    private async Task<ApiKeyResult> ReadApiKeyAsync(string? apiKeyName, CancellationToken cancellationToken)
    {
        using var request = BuildRequest(HttpMethod.Get, "/api/apikeys?page=1&pageSize=20");
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        var data = RequireObject(document.RootElement, "data");
        var keys = FindArray(data, "list") ?? FindArray(data, "items") ?? FindArray(data, "records") ?? FindArray(data, "data");
        if (keys is null)
        {
            return new ApiKeyResult(null, null, null);
        }

        JsonElement? selected = null;
        foreach (var item in keys.Value.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            var name = ReadString(item, "name") ?? ReadString(item, "keyName") ?? ReadString(item, "title");
            if (string.IsNullOrWhiteSpace(apiKeyName) ||
                string.Equals(name, apiKeyName, StringComparison.OrdinalIgnoreCase))
            {
                selected = item;
                break;
            }
        }

        if (selected is null && !string.IsNullOrWhiteSpace(apiKeyName))
        {
            return new ApiKeyResult(apiKeyName, null, null);
        }

        if (selected is null)
        {
            return new ApiKeyResult(null, null, null);
        }

        var raw = ReadLong(selected.Value, "totalConsumed") ?? ReadLong(selected.Value, "consumed") ?? ReadLong(selected.Value, "usage");
        var selectedName = ReadString(selected.Value, "name") ?? ReadString(selected.Value, "keyName") ?? ReadString(selected.Value, "title");
        return new ApiKeyResult(selectedName, raw, raw is null ? null : RawMoneyToCny(raw.Value));
    }

    private HttpRequestMessage BuildRequest(HttpMethod method, string pathAndQuery)
    {
        var request = new HttpRequestMessage(method, new Uri(new Uri(_options.AiCodeMirrorBaseUrl), pathAndQuery));
        request.Headers.TryAddWithoutValidation("Cookie", _options.AiCodeMirrorCookie);
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        request.Headers.UserAgent.ParseAdd("JiMuYun-PhaseA/1.0");
        return request;
    }

    private static JsonElement RequireObject(JsonElement element, string propertyName)
    {
        if (element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(propertyName, out var property) &&
            property.ValueKind == JsonValueKind.Object)
        {
            return property;
        }

        return element;
    }

    private static JsonElement? FindArray(JsonElement element, string propertyName)
    {
        return element.ValueKind == JsonValueKind.Object &&
               element.TryGetProperty(propertyName, out var property) &&
               property.ValueKind == JsonValueKind.Array
            ? property
            : null;
    }

    private static decimal? ReadMoney(JsonElement element, string propertyName)
    {
        var raw = ReadLong(element, propertyName);
        return raw is null ? null : RawMoneyToCny(raw.Value);
    }

    private static decimal RawMoneyToCny(long raw)
    {
        return raw / 1000m;
    }

    private static long? ReadLong(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var property))
        {
            return null;
        }

        if (property.ValueKind == JsonValueKind.Number && property.TryGetInt64(out var value))
        {
            return value;
        }

        if (property.ValueKind == JsonValueKind.String &&
            long.TryParse(property.GetString(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed))
        {
            return parsed;
        }

        return null;
    }

    private static string? ReadString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString()
            : null;
    }

    private sealed record WalletResult(decimal? BalanceCny, decimal? BonusBalanceCny);
    private sealed record ApiKeyResult(string? Name, long? RawTotalConsumed, decimal? TotalConsumedCny);
}
