using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Llm;

public sealed class NewApiChatClient : INewApiChatClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _httpClient;

    public NewApiChatClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<NewApiChatClientResult> CompleteAsync(
        LlmBindingSnapshot binding,
        string bearerToken,
        string model,
        IReadOnlyList<ChatMessage> messages,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(binding);
        ArgumentException.ThrowIfNullOrWhiteSpace(bearerToken);
        ArgumentException.ThrowIfNullOrWhiteSpace(model);
        ArgumentNullException.ThrowIfNull(messages);

        var endpoint = new Uri(binding.GatewayBaseUrl.TrimEnd('/') + "/chat/completions");
        using var request = new HttpRequestMessage(HttpMethod.Post, endpoint);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);
        request.Content = new StringContent(
            JsonSerializer.Serialize(new
            {
                model,
                messages = messages.Select(message => new
                {
                    role = message.Role,
                    content = message.Content
                }).ToArray()
            }, JsonOptions),
            Encoding.UTF8,
            "application/json");

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var raw = await response.Content.ReadAsStringAsync(cancellationToken);
        var requestId = response.Headers.TryGetValues("x-request-id", out var values) ? values.FirstOrDefault() : null;
        if (!response.IsSuccessStatusCode)
        {
            return new NewApiChatClientResult(false, null, $"llm_gateway_http_{(int)response.StatusCode}", requestId, raw);
        }

        try
        {
            using var document = JsonDocument.Parse(raw);
            var content = document.RootElement
                .GetProperty("choices")[0]
                .GetProperty("message")
                .GetProperty("content")
                .GetString();
            if (string.IsNullOrWhiteSpace(content))
            {
                return new NewApiChatClientResult(false, null, "llm_empty_response", requestId, raw);
            }

            var id = document.RootElement.TryGetProperty("id", out var idElement) ? idElement.GetString() : requestId;
            return new NewApiChatClientResult(true, content, null, id, null);
        }
        catch (JsonException)
        {
            return new NewApiChatClientResult(false, null, "llm_invalid_response", requestId, raw);
        }
    }
}
