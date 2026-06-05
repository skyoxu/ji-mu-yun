using System.Text;
using System.Text.Json;
using System.Diagnostics;

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
    string Model,
    string? FailureCode,
    string? FailureCategory,
    int ExitCode,
    string Stdout,
    string Stderr,
    CodexChatClientResult? RawResult,
    long DurationMs,
    int PromptLength,
    int PromptUtf8Bytes,
    int EstimatedPromptTokens);

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
        var stopwatch = Stopwatch.StartNew();
        var completion = await _codexChatClient.CompleteAsync(
            request.WorkspaceRoot,
            request.Model,
            request.Prompt,
            request.Options,
            request.BillingAccountId,
            cancellationToken);
        stopwatch.Stop();

        if (!completion.Succeeded)
        {
            var failureCode = completion.FailureCode ?? "llm_failed";
            PersistTelemetry(request, completion, request.Purpose, stopwatch.ElapsedMilliseconds, failureCode);
            return FromCodexResult(request, completion, null, failureCode, stopwatch.ElapsedMilliseconds);
        }

        if (!request.RequireJsonObject)
        {
            PersistTelemetry(request, completion, request.Purpose, stopwatch.ElapsedMilliseconds, null);
            return FromCodexResult(request, completion, null, null, stopwatch.ElapsedMilliseconds);
        }

        var json = ExtractFirstJsonObject(completion.AssistantMessage);
        if (string.IsNullOrWhiteSpace(json) || !IsValidJsonObject(json))
        {
            PersistTelemetry(request, completion, $"{request.Purpose}-json-parse", stopwatch.ElapsedMilliseconds, "llm_json_parse_failed");
            return FromCodexResult(request, completion, json, "llm_json_parse_failed", stopwatch.ElapsedMilliseconds);
        }

        PersistTelemetry(request, completion, request.Purpose, stopwatch.ElapsedMilliseconds, null);
        return FromCodexResult(request, completion, json, null, stopwatch.ElapsedMilliseconds);
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
        LlmRouteRequest request,
        CodexChatClientResult completion,
        string? jsonObjectText,
        string? failureCode,
        long durationMs)
    {
        var promptUtf8Bytes = Encoding.UTF8.GetByteCount(request.Prompt);
        return new LlmRouteResult(
            string.IsNullOrWhiteSpace(failureCode),
            completion.AssistantMessage,
            jsonObjectText,
            request.Model,
            failureCode,
            ClassifyFailure(failureCode, completion.ExitCode, completion.AssistantMessage),
            completion.ExitCode,
            completion.Stdout,
            completion.Stderr,
            completion,
            durationMs,
            request.Prompt.Length,
            promptUtf8Bytes,
            EstimateTokensFromUtf8Bytes(promptUtf8Bytes));
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

    private static void PersistTelemetry(
        LlmRouteRequest request,
        CodexChatClientResult completion,
        string purpose,
        long durationMs,
        string? failureCode)
    {
        try
        {
            var dir = Path.Combine(request.WorkspaceRoot, "logs", "phase-a-chat");
            Directory.CreateDirectory(dir);
            var stamp = DateTimeOffset.UtcNow.ToString("yyyyMMdd-HHmmss-fff");
            var prefix = Path.Combine(dir, $"{stamp}-{SanitizeFileSegment(purpose)}");
            var promptUtf8Bytes = Encoding.UTF8.GetByteCount(request.Prompt);
            var metadata = JsonSerializer.Serialize(new
            {
                route_engine = "llm-route-engine",
                purpose,
                routePurpose = request.Purpose,
                request.Model,
                promptLength = request.Prompt.Length,
                promptUtf8Bytes,
                estimatedPromptTokens = EstimateTokensFromUtf8Bytes(promptUtf8Bytes),
                requireJsonObject = request.RequireJsonObject,
                failureCode,
                failureCategory = ClassifyFailure(failureCode, completion.ExitCode, completion.AssistantMessage),
                completion.ExitCode,
                durationMs,
                outputLength = completion.AssistantMessage?.Length ?? 0,
                stdoutLength = completion.Stdout?.Length ?? 0,
                stderrLength = completion.Stderr?.Length ?? 0
            }, new JsonSerializerOptions { WriteIndented = true });

            File.WriteAllText($"{prefix}.metrics.json", metadata, Encoding.UTF8);
            if (!string.IsNullOrWhiteSpace(failureCode))
            {
                File.WriteAllText($"{prefix}.failure.json", metadata, Encoding.UTF8);
                File.WriteAllText($"{prefix}.stdout.txt", completion.Stdout ?? "", Encoding.UTF8);
                File.WriteAllText($"{prefix}.stderr.txt", completion.Stderr ?? "", Encoding.UTF8);
                if (!string.IsNullOrWhiteSpace(completion.AssistantMessage))
                {
                    File.WriteAllText($"{prefix}.output.txt", completion.AssistantMessage, Encoding.UTF8);
                }
            }
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static int EstimateTokensFromUtf8Bytes(int utf8Bytes)
    {
        return Math.Max(1, (int)Math.Ceiling(utf8Bytes / 4.0d));
    }

    private static string? ClassifyFailure(string? failureCode, int exitCode, string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(failureCode))
        {
            return null;
        }

        var code = failureCode.Trim().ToLowerInvariant();
        if (code.Contains("timeout", StringComparison.Ordinal) || exitCode == 124)
        {
            return "timeout";
        }

        if (code.Contains("503", StringComparison.Ordinal) ||
            code.Contains("service_unavailable", StringComparison.Ordinal) ||
            code.Contains("provider_unavailable", StringComparison.Ordinal))
        {
            return "provider_unavailable";
        }

        if (code.Contains("json", StringComparison.Ordinal) || code.Contains("parse", StringComparison.Ordinal))
        {
            return "invalid_json";
        }

        if (code.Contains("credential", StringComparison.Ordinal) || code.Contains("key", StringComparison.Ordinal))
        {
            return "credential";
        }

        if (code.Contains("stop_loss", StringComparison.Ordinal))
        {
            return "budget_guard";
        }

        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return "empty_output";
        }

        return "llm_failed";
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
