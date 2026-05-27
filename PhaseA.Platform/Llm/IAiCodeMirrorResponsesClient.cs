using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace PhaseA.Platform.Llm;

public interface IAiCodeMirrorResponsesClient
{
    Task<AiCodeMirrorResponsesResult> CompleteTextAsync(
        string baseUrl,
        string bearerToken,
        string model,
        string input,
        string? reasoningEffort = null,
        CancellationToken cancellationToken = default);
}

public sealed record AiCodeMirrorResponsesResult(
    bool Succeeded,
    string? AssistantMessage,
    string? FailureCode,
    string? RequestId,
    string? RawError);

public sealed class AiCodeMirrorResponsesClient : IAiCodeMirrorResponsesClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private readonly HttpClient _httpClient;

    public AiCodeMirrorResponsesClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<AiCodeMirrorResponsesResult> CompleteTextAsync(
        string baseUrl,
        string bearerToken,
        string model,
        string input,
        string? reasoningEffort = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(baseUrl);
        ArgumentException.ThrowIfNullOrWhiteSpace(bearerToken);
        ArgumentException.ThrowIfNullOrWhiteSpace(model);
        ArgumentException.ThrowIfNullOrWhiteSpace(input);

        var endpoint = new Uri(baseUrl.TrimEnd('/') + "/responses");
        using var request = new HttpRequestMessage(HttpMethod.Post, endpoint);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);
        request.Content = new StringContent(
            JsonSerializer.Serialize(new
            {
                model,
                input,
                reasoning = new { effort = string.IsNullOrWhiteSpace(reasoningEffort) ? "low" : reasoningEffort },
                text = new { format = new { type = "text" } },
                store = false
            }, JsonOptions),
            Encoding.UTF8,
            "application/json");

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var raw = await response.Content.ReadAsStringAsync(cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            return new AiCodeMirrorResponsesResult(false, null, $"responses_http_{(int)response.StatusCode}", null, raw);
        }

        try
        {
            using var document = JsonDocument.Parse(raw);
            var root = document.RootElement;
            var requestId = root.TryGetProperty("id", out var idElement) && idElement.ValueKind == JsonValueKind.String
                ? idElement.GetString()
                : null;
            if (!root.TryGetProperty("output", out var outputElement) || outputElement.ValueKind != JsonValueKind.Array)
            {
                return new AiCodeMirrorResponsesResult(false, null, "responses_invalid_output", requestId, raw);
            }

            foreach (var item in outputElement.EnumerateArray())
            {
                if (!item.TryGetProperty("type", out var typeElement) ||
                    typeElement.ValueKind != JsonValueKind.String ||
                    !string.Equals(typeElement.GetString(), "message", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (!item.TryGetProperty("content", out var contentElement) || contentElement.ValueKind != JsonValueKind.Array)
                {
                    continue;
                }

                foreach (var content in contentElement.EnumerateArray())
                {
                    if (!content.TryGetProperty("type", out var contentType) ||
                        contentType.ValueKind != JsonValueKind.String ||
                        !string.Equals(contentType.GetString(), "output_text", StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }

                    if (content.TryGetProperty("text", out var textElement) &&
                        textElement.ValueKind == JsonValueKind.String &&
                        !string.IsNullOrWhiteSpace(textElement.GetString()))
                    {
                        return new AiCodeMirrorResponsesResult(true, textElement.GetString(), null, requestId, null);
                    }
                }
            }

            return new AiCodeMirrorResponsesResult(false, null, "responses_empty_response", requestId, raw);
        }
        catch (JsonException)
        {
            return new AiCodeMirrorResponsesResult(false, null, "responses_invalid_json", null, raw);
        }
    }
}
