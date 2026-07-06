using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Extensions.DependencyInjection;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Prototypes;

public interface ISteamGameTypeMetadataProvider
{
    Task<SteamGameTypeMetadata> ResolveAsync(string referenceQuery, CancellationToken cancellationToken);
}

public sealed record SteamGameTypeMetadata(
    string Status,
    string StatusReason,
    string ReferenceQuery,
    string SteamAppId,
    string SteamName,
    IReadOnlyList<string> Tags,
    IReadOnlyList<string> Categories,
    IReadOnlyList<string> Genres)
{
    public string ResolvedQuery { get; init; } = "";

    public IReadOnlyList<string> AttemptedQueries { get; init; } = [];
}

public sealed class SteamGameTypeMetadataProvider : ISteamGameTypeMetadataProvider
{
    private readonly HttpClient _httpClient;
    private readonly IReadOnlyDictionary<string, string[]> _referenceAliases;

    public SteamGameTypeMetadataProvider(HttpClient httpClient)
        : this(httpClient, null)
    {
    }

    [ActivatorUtilitiesConstructor]
    public SteamGameTypeMetadataProvider(HttpClient httpClient, PhaseAPlatformOptions? options)
    {
        _httpClient = httpClient;
        _referenceAliases = LoadReferenceAliases(options?.RepositoryRoot);
    }

    public async Task<SteamGameTypeMetadata> ResolveAsync(string referenceQuery, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(referenceQuery))
        {
            return Failure(referenceQuery, "steam_query_empty", []);
        }

        var queries = BuildSearchQueries(referenceQuery);
        try
        {
            var app = await ResolveFirstAppAsync(queries, cancellationToken);
            if (app is null)
            {
                return Failure(referenceQuery, "steam_app_not_found", queries);
            }

            var details = await ResolveDetailsAsync(app.Value.AppId, cancellationToken);
            var tags = await ResolveStoreTagsAsync(app.Value.AppId, cancellationToken);
            return new SteamGameTypeMetadata(
                "resolved",
                "steam_metadata_resolved",
                referenceQuery.Trim(),
                app.Value.AppId,
                FirstNonEmpty(details.Name, app.Value.Name),
                tags,
                details.Categories,
                details.Genres)
            {
                ResolvedQuery = app.Value.Query,
                AttemptedQueries = queries
            };
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return Failure(referenceQuery, "steam_lookup_timeout", queries);
        }
        catch (HttpRequestException)
        {
            return Failure(referenceQuery, "steam_lookup_http_failed", queries);
        }
        catch (JsonException)
        {
            return Failure(referenceQuery, "steam_lookup_json_invalid", queries);
        }
    }

    private async Task<SteamSearchApp?> ResolveFirstAppAsync(IReadOnlyList<string> queries, CancellationToken cancellationToken)
    {
        foreach (var query in queries)
        {
            foreach (var language in SearchLanguages)
            {
                var url = $"https://store.steampowered.com/api/storesearch/?cc=us&l={language}&term=" + Uri.EscapeDataString(query.Trim());
                using var document = await GetJsonAsync(url, cancellationToken);
                if (!document.RootElement.TryGetProperty("items", out var items) || items.ValueKind != JsonValueKind.Array)
                {
                    continue;
                }

                var apps = new List<SteamSearchApp>();
                foreach (var item in items.EnumerateArray())
                {
                    if (!item.TryGetProperty("id", out var idElement))
                    {
                        continue;
                    }

                    var appId = idElement.ValueKind == JsonValueKind.Number
                        ? idElement.GetInt32().ToString()
                        : idElement.GetString() ?? "";
                    if (string.IsNullOrWhiteSpace(appId))
                    {
                        continue;
                    }

                    var name = item.TryGetProperty("name", out var nameElement) && nameElement.ValueKind == JsonValueKind.String
                        ? nameElement.GetString() ?? ""
                        : "";
                    apps.Add(new SteamSearchApp(appId, name, query));
                }

                var selected = SelectBestSearchApp(apps, query);
                if (selected is not null)
                {
                    return selected;
                }
            }
        }

        return null;
    }

    private async Task<SteamAppDetails> ResolveDetailsAsync(string appId, CancellationToken cancellationToken)
    {
        var url = $"https://store.steampowered.com/api/appdetails?appids={Uri.EscapeDataString(appId)}&cc=us&l=english";
        using var document = await GetJsonAsync(url, cancellationToken);
        if (!document.RootElement.TryGetProperty(appId, out var appElement) ||
            !appElement.TryGetProperty("success", out var successElement) ||
            successElement.ValueKind != JsonValueKind.True ||
            !appElement.TryGetProperty("data", out var dataElement))
        {
            return new SteamAppDetails("", [], []);
        }

        var name = dataElement.TryGetProperty("name", out var nameElement) && nameElement.ValueKind == JsonValueKind.String
            ? nameElement.GetString() ?? ""
            : "";
        return new SteamAppDetails(
            name,
            ReadDescriptionNames(dataElement, "categories"),
            ReadDescriptionNames(dataElement, "genres"));
    }

    private async Task<IReadOnlyList<string>> ResolveStoreTagsAsync(string appId, CancellationToken cancellationToken)
    {
        var html = await _httpClient.GetStringAsync($"https://store.steampowered.com/app/{Uri.EscapeDataString(appId)}/?cc=us&l=english", cancellationToken);
        var matches = Regex.Matches(html, @"<a[^>]*class=""[^""]*app_tag[^""]*""[^>]*>(?<tag>.*?)</a>", RegexOptions.IgnoreCase | RegexOptions.Singleline);
        return matches
            .Select(match => WebUtility.HtmlDecode(Regex.Replace(match.Groups["tag"].Value, "<.*?>", "").Trim()))
            .Where(tag => !string.IsNullOrWhiteSpace(tag))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(25)
            .ToArray();
    }

    private async Task<JsonDocument> GetJsonAsync(string url, CancellationToken cancellationToken)
    {
        await using var stream = await _httpClient.GetStreamAsync(url, cancellationToken);
        return await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
    }

    private static IReadOnlyList<string> ReadDescriptionNames(JsonElement dataElement, string propertyName)
    {
        if (!dataElement.TryGetProperty(propertyName, out var arrayElement) || arrayElement.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        return arrayElement.EnumerateArray()
            .Select(item => item.TryGetProperty("description", out var description) && description.ValueKind == JsonValueKind.String ? description.GetString() ?? "" : "")
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static SteamGameTypeMetadata Failure(string referenceQuery, string reason, IReadOnlyList<string> attemptedQueries)
    {
        return new SteamGameTypeMetadata("failed", reason, referenceQuery.Trim(), "", "", [], [], [])
        {
            AttemptedQueries = attemptedQueries
        };
    }

    private static string FirstNonEmpty(params string[] values)
    {
        return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    }

    private IReadOnlyList<string> BuildSearchQueries(string referenceQuery)
    {
        var trimmed = referenceQuery.Trim();
        var queries = new List<string> { trimmed };
        if (_referenceAliases.TryGetValue(trimmed, out var aliases))
        {
            queries.AddRange(aliases);
        }

        return queries
            .Where(query => !string.IsNullOrWhiteSpace(query))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static SteamSearchApp? SelectBestSearchApp(IReadOnlyList<SteamSearchApp> apps, string query)
    {
        if (apps.Count == 0)
        {
            return null;
        }

        var normalizedQuery = NormalizeSearchTitle(query);
        var exact = apps.FirstOrDefault(app => string.Equals(NormalizeSearchTitle(app.Name), normalizedQuery, StringComparison.Ordinal));
        return string.IsNullOrWhiteSpace(exact.AppId) ? apps[0] : exact;
    }

    private static string NormalizeSearchTitle(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var normalized = new string(value
            .Trim()
            .ToLowerInvariant()
            .Where(char.IsLetterOrDigit)
            .ToArray());
        return normalized;
    }

    private static IReadOnlyDictionary<string, string[]> LoadReferenceAliases(string? repositoryRoot)
    {
        if (string.IsNullOrWhiteSpace(repositoryRoot))
        {
            return new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase);
        }

        var path = Path.Combine(repositoryRoot, "docs", "game-type-guides", "steam-reference-aliases.csv");
        if (!File.Exists(path))
        {
            return new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase);
        }

        var aliases = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in File.ReadLines(path, Encoding.UTF8).Skip(1))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var values = ParseCsvLine(line);
            if (values.Count < 2)
            {
                continue;
            }

            var sourceQuery = DecodeEscapedUnicode(values[0].Trim());
            var steamQuery = values[1].Trim();
            if (string.IsNullOrWhiteSpace(sourceQuery) || string.IsNullOrWhiteSpace(steamQuery))
            {
                continue;
            }

            if (!aliases.TryGetValue(sourceQuery, out var list))
            {
                list = [];
                aliases[sourceQuery] = list;
            }

            if (!list.Contains(steamQuery, StringComparer.OrdinalIgnoreCase))
            {
                list.Add(steamQuery);
            }
        }

        return aliases.ToDictionary(
            pair => pair.Key,
            pair => pair.Value.ToArray(),
            StringComparer.OrdinalIgnoreCase);
    }

    private static IReadOnlyList<string> ParseCsvLine(string line)
    {
        var values = new List<string>();
        var builder = new StringBuilder();
        var inQuotes = false;
        for (var index = 0; index < line.Length; index++)
        {
            var ch = line[index];
            if (ch == '"')
            {
                if (inQuotes && index + 1 < line.Length && line[index + 1] == '"')
                {
                    builder.Append('"');
                    index++;
                    continue;
                }

                inQuotes = !inQuotes;
                continue;
            }

            if (ch == ',' && !inQuotes)
            {
                values.Add(builder.ToString());
                builder.Clear();
                continue;
            }

            builder.Append(ch);
        }

        values.Add(builder.ToString());
        return values;
    }

    private static string DecodeEscapedUnicode(string value)
    {
        return Regex.Replace(value, @"\\u(?<hex>[0-9a-fA-F]{4})", match =>
        {
            var code = Convert.ToInt32(match.Groups["hex"].Value, 16);
            return char.ConvertFromUtf32(code);
        });
    }

    private readonly record struct SteamSearchApp(string AppId, string Name, string Query);

    private sealed record SteamAppDetails(string Name, IReadOnlyList<string> Categories, IReadOnlyList<string> Genres);

    private static readonly string[] SearchLanguages = ["english", "schinese", "japanese"];

}
