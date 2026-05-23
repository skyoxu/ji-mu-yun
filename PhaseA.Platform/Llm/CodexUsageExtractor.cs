using System.Text.Json;

namespace PhaseA.Platform.Llm;

public sealed record CodexTokenUsage(
    int? InputTokens,
    int? OutputTokens,
    int? CachedInputTokens)
{
    public bool HasAny => InputTokens is not null || OutputTokens is not null || CachedInputTokens is not null;
}

public static class CodexUsageExtractor
{
    public static CodexTokenUsage Extract(params string?[] streams)
    {
        int? inputTokens = null;
        int? outputTokens = null;
        int? cachedInputTokens = null;

        foreach (var stream in streams)
        {
            if (string.IsNullOrWhiteSpace(stream))
            {
                continue;
            }

            var lines = stream.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n').Split('\n');
            foreach (var line in lines)
            {
                var trimmed = line.Trim();
                if (trimmed.Length == 0 || trimmed[0] != '{')
                {
                    continue;
                }

                try
                {
                    using var document = JsonDocument.Parse(trimmed);
                    Walk(document.RootElement, ref inputTokens, ref outputTokens, ref cachedInputTokens);
                }
                catch (JsonException)
                {
                }
            }
        }

        return new CodexTokenUsage(inputTokens, outputTokens, cachedInputTokens);
    }

    private static void Walk(JsonElement element, ref int? inputTokens, ref int? outputTokens, ref int? cachedInputTokens)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                ReadKnownTokenFields(element, ref inputTokens, ref outputTokens, ref cachedInputTokens);
                foreach (var property in element.EnumerateObject())
                {
                    Walk(property.Value, ref inputTokens, ref outputTokens, ref cachedInputTokens);
                }

                break;
            case JsonValueKind.Array:
                foreach (var item in element.EnumerateArray())
                {
                    Walk(item, ref inputTokens, ref outputTokens, ref cachedInputTokens);
                }

                break;
        }
    }

    private static void ReadKnownTokenFields(JsonElement element, ref int? inputTokens, ref int? outputTokens, ref int? cachedInputTokens)
    {
        inputTokens = PreferLatest(inputTokens,
            ReadInt(element, "input_tokens") ??
            ReadInt(element, "prompt_tokens") ??
            ReadInt(element, "inputTokens") ??
            ReadInt(element, "promptTokens"));
        outputTokens = PreferLatest(outputTokens,
            ReadInt(element, "output_tokens") ??
            ReadInt(element, "completion_tokens") ??
            ReadInt(element, "outputTokens") ??
            ReadInt(element, "completionTokens"));
        cachedInputTokens = PreferLatest(cachedInputTokens,
            ReadInt(element, "cached_input_tokens") ??
            ReadInt(element, "cached_tokens") ??
            ReadInt(element, "cachedInputTokens") ??
            ReadInt(element, "cachedTokens"));
    }

    private static int? PreferLatest(int? current, int? incoming)
    {
        return incoming ?? current;
    }

    private static int? ReadInt(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var property))
        {
            return null;
        }

        if (property.ValueKind == JsonValueKind.Number && property.TryGetInt32(out var value))
        {
            return value;
        }

        return null;
    }
}
