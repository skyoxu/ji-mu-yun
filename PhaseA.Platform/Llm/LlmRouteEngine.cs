using System.Text;
using System.Text.Json;

namespace PhaseA.Platform.Llm;

public interface ILlmRouteEngine
{
    Task<LlmRouteResult> CompleteAsync(
        LlmRouteRequest request,
        CancellationToken cancellationToken = default);
}

public sealed record LlmRouteRequest(
    string WorkspaceRoot,
    string Purpose,
    string Model,
    string Prompt,
    CodexChatClientOptions? Options = null,
    string? BillingAccountId = null,
    bool RequireJsonObject = false);

public sealed record LlmRouteResult(
    bool Succeeded,
    string? AssistantMessage,
    string? JsonObjectText,
    string? FailureCode,
    int ExitCode,
    string Stdout,
    string Stderr,
    CodexChatClientResult? RawResult);

public sealed class LlmRouteEngine : ILlmRouteEngine
{
    private readonly ICodexChatClient _codexChatClient;

    public LlmRouteEngine(ICodexChatClient codexChatClient)
    {
        _codexChatClient = codexChatClient;
    }

    public async Task<LlmRouteResult> CompleteAsync(
        LlmRouteRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(request.WorkspaceRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Purpose);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Model);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Prompt);

        Directory.CreateDirectory(request.WorkspaceRoot);
        var completion = await _codexChatClient.CompleteAsync(
            request.WorkspaceRoot,
            request.Model,
            request.Prompt,
            request.Options,
            request.BillingAccountId,
            cancellationToken);

        if (!completion.Succeeded)
        {
            PersistFailure(request, completion, request.Purpose);
            return FromCodexResult(completion, null, completion.FailureCode ?? "llm_failed");
        }

        if (!request.RequireJsonObject)
        {
            return FromCodexResult(completion, null, null);
        }

        var json = ExtractFirstJsonObject(completion.AssistantMessage);
        if (string.IsNullOrWhiteSpace(json) || !IsValidJsonObject(json))
        {
            PersistFailure(request, completion, $"{request.Purpose}-json-parse");
            return FromCodexResult(completion, json, "llm_json_parse_failed");
        }

        return FromCodexResult(completion, json, null);
    }

    public static string? ExtractFirstJsonObject(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var start = text.IndexOf('{');
        if (start < 0)
        {
            return null;
        }

        var depth = 0;
        var inString = false;
        var escaped = false;
        for (var index = start; index < text.Length; index++)
        {
            var current = text[index];
            if (inString)
            {
                if (escaped)
                {
                    escaped = false;
                }
                else if (current == '\\')
                {
                    escaped = true;
                }
                else if (current == '"')
                {
                    inString = false;
                }

                continue;
            }

            if (current == '"')
            {
                inString = true;
                continue;
            }

            if (current == '{')
            {
                depth++;
            }
            else if (current == '}')
            {
                depth--;
                if (depth == 0)
                {
                    return text[start..(index + 1)];
                }
            }
        }

        return null;
    }

    private static LlmRouteResult FromCodexResult(
        CodexChatClientResult completion,
        string? jsonObjectText,
        string? failureCode)
    {
        return new LlmRouteResult(
            string.IsNullOrWhiteSpace(failureCode),
            completion.AssistantMessage,
            jsonObjectText,
            failureCode,
            completion.ExitCode,
            completion.Stdout,
            completion.Stderr,
            completion);
    }

    private static bool IsValidJsonObject(string json)
    {
        try
        {
            using var document = JsonDocument.Parse(json);
            return document.RootElement.ValueKind == JsonValueKind.Object;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static void PersistFailure(
        LlmRouteRequest request,
        CodexChatClientResult completion,
        string purpose)
    {
        try
        {
            var dir = Path.Combine(request.WorkspaceRoot, "logs", "phase-a-chat");
            Directory.CreateDirectory(dir);
            var stamp = DateTimeOffset.UtcNow.ToString("yyyyMMdd-HHmmss-fff");
            var prefix = Path.Combine(dir, $"{stamp}-{SanitizeFileSegment(purpose)}");
            var metadata = JsonSerializer.Serialize(new
            {
                route_engine = "llm-route-engine",
                purpose,
                routePurpose = request.Purpose,
                request.Model,
                promptLength = request.Prompt.Length,
                requireJsonObject = request.RequireJsonObject,
                completion.FailureCode,
                completion.ExitCode,
                outputLength = completion.AssistantMessage?.Length ?? 0,
                stdoutLength = completion.Stdout?.Length ?? 0,
                stderrLength = completion.Stderr?.Length ?? 0
            }, new JsonSerializerOptions { WriteIndented = true });

            File.WriteAllText($"{prefix}.failure.json", metadata, Encoding.UTF8);
            File.WriteAllText($"{prefix}.stdout.txt", completion.Stdout ?? "", Encoding.UTF8);
            File.WriteAllText($"{prefix}.stderr.txt", completion.Stderr ?? "", Encoding.UTF8);
            if (!string.IsNullOrWhiteSpace(completion.AssistantMessage))
            {
                File.WriteAllText($"{prefix}.output.txt", completion.AssistantMessage, Encoding.UTF8);
            }
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static string SanitizeFileSegment(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (var c in value)
        {
            builder.Append(char.IsLetterOrDigit(c) || c is '-' or '_' ? c : '-');
        }

        return builder.Length == 0 ? "llm" : builder.ToString();
    }
}
