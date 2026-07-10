using System.Text.RegularExpressions;

namespace PhaseA.Platform.Workflow;

public static partial class RouteReadbackPathPolicy
{
    public static bool IsBrowserSafePath(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return true;
        }

        var normalized = value.Replace('\\', '/').Trim();
        if (normalized.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
            normalized.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (normalized.StartsWith("file://", StringComparison.OrdinalIgnoreCase) ||
            normalized.StartsWith("//", StringComparison.Ordinal) ||
            normalized.StartsWith("/", StringComparison.Ordinal) ||
            normalized.Contains("/../", StringComparison.Ordinal) ||
            normalized.StartsWith("../", StringComparison.Ordinal) ||
            WindowsDrivePath().IsMatch(normalized))
        {
            return false;
        }

        return true;
    }

    public static string ToBrowserSafePath(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var normalized = value.Replace('\\', '/').Trim();
        if (IsBrowserSafePath(normalized))
        {
            return normalized;
        }

        var fileName = Path.GetFileName(normalized);
        return string.IsNullOrWhiteSpace(fileName) ? "[redacted-path]" : fileName;
    }

    public static bool IsSafePackageFileName(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var normalized = value.Replace('\\', '/').Trim();
        return IsBrowserSafePath(normalized) &&
               !normalized.Contains('/', StringComparison.Ordinal) &&
               normalized.EndsWith(".zip", StringComparison.OrdinalIgnoreCase);
    }

    [GeneratedRegex("^[A-Za-z]:/")]
    private static partial Regex WindowsDrivePath();
}

