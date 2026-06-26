using System.Text.Json;

namespace PhaseA.Platform.Runs;

internal static class PrototypeGdUnitPathResolver
{
    public static IReadOnlyList<string> ExtractManagedDirectoriesFromRouteStates(IEnumerable<string> routeStates)
    {
        return ExtractGdUnitAddPathsFromRouteStates(routeStates)
            .Select(path => $"Tests.Godot/{path}")
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    public static IReadOnlyList<string> ExtractGdUnitAddPathsFromRouteStates(IEnumerable<string> routeStates)
    {
        var results = new List<string>();
        foreach (var state in routeStates)
        {
            foreach (var path in ExtractGdUnitAddPaths(state))
            {
                if (!results.Contains(path, StringComparer.OrdinalIgnoreCase))
                {
                    results.Add(path);
                }
            }
        }

        return results;
    }

    public static string? NormalizeGdUnitAddPath(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var normalized = value.Trim().Replace('\\', '/');
        const string resPrefix = "res://";
        if (normalized.StartsWith(resPrefix, StringComparison.OrdinalIgnoreCase))
        {
            normalized = normalized[resPrefix.Length..];
        }

        const string godotPrefix = "Tests.Godot/";
        if (normalized.StartsWith(godotPrefix, StringComparison.OrdinalIgnoreCase))
        {
            normalized = normalized[godotPrefix.Length..];
        }

        const string gdUnitPrefix = "tests/Prototype/";
        if (!normalized.StartsWith(gdUnitPrefix, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var remainder = normalized[gdUnitPrefix.Length..];
        var parts = remainder.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0)
        {
            return null;
        }

        var suite = parts[0];
        return IsSafeSuiteSegment(suite) ? $"{gdUnitPrefix}{suite}" : null;
    }

    private static IEnumerable<string> ExtractGdUnitAddPaths(string state)
    {
        if (string.IsNullOrWhiteSpace(state))
        {
            yield break;
        }

        JsonDocument document;
        try
        {
            document = JsonDocument.Parse(state);
        }
        catch (JsonException)
        {
            yield break;
        }

        using (document)
        {
            foreach (var value in EnumerateGdUnitPathStrings(document.RootElement, null, false))
            {
                var normalized = NormalizeGdUnitAddPath(value);
                if (!string.IsNullOrWhiteSpace(normalized))
                {
                    yield return normalized;
                }
            }
        }
    }

    private static IEnumerable<string> EnumerateGdUnitPathStrings(JsonElement element, string? propertyName, bool inGdUnitContext)
    {
        if (IsDirectGdUnitPathProperty(propertyName))
        {
            foreach (var value in EnumerateJsonStrings(element))
            {
                yield return value;
            }

            yield break;
        }

        if (inGdUnitContext && IsContextualGdUnitPathProperty(propertyName))
        {
            foreach (var value in EnumerateJsonStrings(element))
            {
                yield return value;
            }

            yield break;
        }

        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                foreach (var property in element.EnumerateObject())
                {
                    var childInGdUnitContext = inGdUnitContext || IsGdUnitContextProperty(property.Name);
                    foreach (var value in EnumerateGdUnitPathStrings(property.Value, property.Name, childInGdUnitContext))
                    {
                        yield return value;
                    }
                }

                break;
            case JsonValueKind.Array:
                foreach (var item in element.EnumerateArray())
                {
                    foreach (var value in EnumerateGdUnitPathStrings(item, propertyName, inGdUnitContext))
                    {
                        yield return value;
                    }
                }

                break;
        }
    }

    private static IEnumerable<string> EnumerateJsonStrings(JsonElement element)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.String:
                yield return element.GetString() ?? "";
                break;
            case JsonValueKind.Object:
                foreach (var property in element.EnumerateObject())
                {
                    foreach (var value in EnumerateJsonStrings(property.Value))
                    {
                        yield return value;
                    }
                }

                break;
            case JsonValueKind.Array:
                foreach (var item in element.EnumerateArray())
                {
                    foreach (var value in EnumerateJsonStrings(item))
                    {
                        yield return value;
                    }
                }

                break;
        }
    }

    private static bool IsDirectGdUnitPathProperty(string? propertyName)
    {
        return string.Equals(propertyName, "gdunit_path", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "gdunit_paths", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "gdunitPath", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "gdunitPaths", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsContextualGdUnitPathProperty(string? propertyName)
    {
        return string.Equals(propertyName, "path", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "paths", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "add", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "added", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "suite", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "suites", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsGdUnitContextProperty(string? propertyName)
    {
        return string.Equals(propertyName, "gdunit", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "gdunit_validation", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "rpg_gdunit_validation", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "gdunit_context", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "gdunit_tests", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(propertyName, "rpg_gdunit_tests", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsSafeSuiteSegment(string suite)
    {
        return !string.IsNullOrWhiteSpace(suite) &&
               suite != "." &&
               suite != ".." &&
               suite.IndexOfAny(Path.GetInvalidFileNameChars()) < 0 &&
               !suite.Contains(':', StringComparison.Ordinal) &&
               !suite.Contains('/', StringComparison.Ordinal) &&
               !suite.Contains('\\', StringComparison.Ordinal);
    }
}
