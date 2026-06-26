namespace PhaseA.Platform.Runs;

internal static class PrototypePromptText
{
    public static string TrimHeadAndTail(string? value, int maxLength, string emptyValue = "")
    {
        if (maxLength <= 0)
        {
            return "";
        }

        if (string.IsNullOrWhiteSpace(value))
        {
            return emptyValue.Length > maxLength
                ? emptyValue[..maxLength]
                : emptyValue;
        }

        var trimmed = value.Trim();
        if (trimmed.Length <= maxLength)
        {
            return trimmed;
        }

        var marker = $"\n[truncated {trimmed.Length - maxLength} chars; showing head and tail]\n";
        var available = maxLength - marker.Length;
        if (available < 20)
        {
            return trimmed[..maxLength];
        }

        var headLength = available / 2;
        var tailLength = available - headLength;
        var omitted = trimmed.Length - headLength - tailLength;
        marker = $"\n[truncated {omitted} chars; showing head and tail]\n";
        var overflow = headLength + tailLength + marker.Length - maxLength;
        if (overflow > 0)
        {
            tailLength = Math.Max(1, tailLength - overflow);
            omitted = trimmed.Length - headLength - tailLength;
            marker = $"\n[truncated {omitted} chars; showing head and tail]\n";
        }

        return $"{trimmed[..headLength]}{marker}{trimmed[^tailLength..]}";
    }
}
