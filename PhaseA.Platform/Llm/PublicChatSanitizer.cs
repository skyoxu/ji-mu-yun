using System.Text.RegularExpressions;

namespace PhaseA.Platform.Llm;

public static class PublicChatSanitizer
{
    private const string RedactedText = "";
    private static readonly Regex WindowsPathRegex = new(@"[A-Za-z]:[\\/][^\s`'""，。；：、）)]+", RegexOptions.Compiled);
    private static readonly Regex UnixPathRegex = new(@"(?<![\w.])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+", RegexOptions.Compiled);
    private static readonly Regex ScriptFileRegex = new(@"(?<![\w.-])[\w.-]+\.(?:ps1|cmd|bat|sh|py|csproj|sln|json|toml|yaml|yml|md|log)(?![\w.-])", RegexOptions.Compiled | RegexOptions.IgnoreCase);
    private static readonly Regex CommandLineRegex = new(@"(?im)^\s*(?:&\s*)?(?:(?:dotnet\s+(?:test|run|build|publish|restore))|(?:py(?:thon)?\s+[-\w./\\])|(?:powershell(?:\.exe)?\s+[-/]\w+)|(?:cmd(?:\.exe)?\s+/[ck])|(?:codex(?:\.cmd)?\s+(?:exec|run|review|--|-))|(?:caddy(?:\.exe)?\s+(?:run|reload|fmt|--|-))|(?:git\s+\w+)|(?:rg\s+.+)|(?:node\s+.+)|(?:npm\s+\w+))[^\r\n]*", RegexOptions.Compiled);
    private static readonly Regex InlineCommandRegex = new(@"\b(?:(?:dotnet\s+(?:test|run|build|publish|restore))|(?:py(?:thon)?\s+[-\w./\\])|(?:powershell(?:\.exe)?\s+[-/]\w+)|(?:cmd(?:\.exe)?\s+/[ck])|(?:codex(?:\.cmd)?\s+(?:exec|run|review|--|-))|(?:caddy(?:\.exe)?\s+(?:run|reload|fmt|--|-))|(?:git\s+\w+)|(?:rg\s+.+)|(?:node\s+.+)|(?:npm\s+\w+))[^，。；\r\n]*", RegexOptions.Compiled | RegexOptions.IgnoreCase);
    private static readonly Regex InternalMarkerRegex = new(@"\b(?:logs\/ci|logs\\ci|active-prototypes|workspaces|GODOT_BIN|PHASEA_[A-Z0-9_]+)\b[^\r\n，。；]*", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    public static string Sanitize(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var sanitized = WindowsPathRegex.Replace(value, RedactedText);
        sanitized = UnixPathRegex.Replace(sanitized, RedactedText);
        sanitized = CommandLineRegex.Replace(sanitized, RedactedText);
        sanitized = InlineCommandRegex.Replace(sanitized, RedactedText);
        sanitized = ScriptFileRegex.Replace(sanitized, RedactedText);
        sanitized = InternalMarkerRegex.Replace(sanitized, RedactedText);
        return Cleanup(sanitized).Trim();
    }

    private static string Cleanup(string value)
    {
        var sanitized = Regex.Replace(value, @"[ \t]{2,}", " ");
        sanitized = Regex.Replace(sanitized, @"\s+([，。；：、,.!?！？])", "$1");
        sanitized = Regex.Replace(sanitized, @"([（(【\[])\s+", "$1");
        sanitized = Regex.Replace(sanitized, @"\s+([）)】\]])", "$1");
        sanitized = Regex.Replace(sanitized, @"(?:请查看|然后运行|运行|执行)\s*(?=[，。；,.!?！？]|$)", "");
        sanitized = Regex.Replace(sanitized, @"[，、]\s*[，、]+", "，");
        sanitized = Regex.Replace(sanitized, @"\n{3,}", "\n\n");
        return sanitized;
    }
}
