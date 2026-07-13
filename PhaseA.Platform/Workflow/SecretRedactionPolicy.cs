using System.Text.RegularExpressions;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PhaseA.Platform.Workflow;

public static partial class SecretRedactionPolicy
{
    public static readonly IReadOnlyList<string> SecretFieldNames =
    [
        "PHASEA_ADMIN_TOKEN",
        "PHASEA_ADMIN_TOKEN_HASH",
        "Authorization",
        "Bearer",
        "OPENAI_API_KEY",
        "AICODEMIRROR_API_KEY",
        "token_hash",
        "provider_key",
        "api_key",
        "access_token"
    ];

    public static IReadOnlyList<string> FindViolations(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return [];
        }

        var violations = new List<string>();
        foreach (var field in SecretFieldNames)
        {
            if (text.Contains(field, StringComparison.OrdinalIgnoreCase))
            {
                violations.Add($"secret_field:{field}");
            }
        }

        if (BearerToken().IsMatch(text))
        {
            violations.Add("secret_pattern:bearer_token");
        }

        if (ProviderKey().IsMatch(text))
        {
            violations.Add("secret_pattern:provider_key");
        }

        return violations.Distinct(StringComparer.Ordinal).ToArray();
    }

    public static string Redact(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return "";
        }

        var redacted = text;
        redacted = BearerToken().Replace(redacted, "Bearer [redacted]");
        redacted = ProviderKey().Replace(redacted, "[redacted-provider-key]");
        foreach (var field in SecretFieldNames)
        {
            redacted = Regex.Replace(
                redacted,
                $"(?<prefix>[\\\"']?{Regex.Escape(field)}[\\\"']?\\s*[:=]\\s*[\\\"']?)[^\\\"'\\s,;}}]+",
                "${prefix}[redacted]",
                RegexOptions.IgnoreCase);
        }

        return redacted;
    }

    public static string RedactForPersistence(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return "";
        }

        try
        {
            var node = JsonNode.Parse(text);
            if (node is not null)
            {
                if (node is JsonValue rootValue && rootValue.TryGetValue<string>(out var rootString))
                {
                    return JsonSerializer.Serialize(RedactTextForPersistence(rootString));
                }
                RedactJsonNode(node);
                return node.ToJsonString();
            }
        }
        catch (JsonException)
        {
        }

        return RedactTextForPersistence(text);
    }

    private static void RedactJsonNode(JsonNode node)
    {
        if (node is JsonObject jsonObject)
        {
            foreach (var property in jsonObject.ToArray())
            {
                if (SecretFieldNames.Contains(property.Key, StringComparer.OrdinalIgnoreCase))
                {
                    jsonObject[property.Key] = "[redacted]";
                }
                else if (property.Value is not null)
                {
                    RedactJsonNode(property.Value);
                }
            }
            return;
        }

        if (node is JsonArray jsonArray)
        {
            for (var index = 0; index < jsonArray.Count; index++)
            {
                var item = jsonArray[index];
                if (item is not null)
                {
                    RedactJsonNode(item);
                }
            }
            return;
        }

        if (node is JsonValue value && value.TryGetValue<string>(out var stringValue))
        {
            value.ReplaceWith(JsonValue.Create(RedactTextForPersistence(stringValue)));
        }
    }

    private static string RedactTextForPersistence(string text)
    {
        return RedactWindowsHostPaths(Redact(text));
    }

    private static string RedactWindowsHostPaths(string text)
    {
        var output = new System.Text.StringBuilder(text.Length);
        var offset = 0;
        while (offset < text.Length)
        {
            var drive = WindowsDrivePathPrefix().Match(text, offset);
            var unc = WindowsUncPathPrefix().Match(text, offset);
            var match = !drive.Success ? unc : !unc.Success || drive.Index <= unc.Index ? drive : unc;
            if (!match.Success)
            {
                output.Append(text, offset, text.Length - offset);
                break;
            }

            output.Append(text, offset, match.Index - offset);
            var end = match.Index + match.Length;
            while (end < text.Length && text[end] is not ('\r' or '\n' or '"' or '\'' or ',' or ';' or '}' or ']'))
            {
                end++;
            }
            output.Append("[redacted-host-path]");
            offset = end;
        }

        return output.ToString();
    }

    [GeneratedRegex("Bearer\\s+[A-Za-z0-9._~+\\-/]+=*", RegexOptions.IgnoreCase)]
    private static partial Regex BearerToken();

    [GeneratedRegex("(sk-[A-Za-z0-9]{12,}|aicm-[A-Za-z0-9]{12,})", RegexOptions.IgnoreCase)]
    private static partial Regex ProviderKey();

    [GeneratedRegex("(?:\\\\\\\\\\?\\\\)?[A-Za-z]:[\\\\/]", RegexOptions.IgnoreCase)]
    private static partial Regex WindowsDrivePathPrefix();

    [GeneratedRegex("\\\\\\\\(?:\\?\\\\UNC\\\\)?[^\\\\/\\r\\n]+[\\\\/][^\\\\/\\r\\n]+(?:[\\\\/]|(?=$|[\\r\\n\\\"',;}\\]]))", RegexOptions.IgnoreCase)]
    private static partial Regex WindowsUncPathPrefix();
}
