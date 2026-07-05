using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;

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
    IReadOnlyList<string> Genres);

public sealed class SteamGameTypeMetadataProvider : ISteamGameTypeMetadataProvider
{
    private readonly HttpClient _httpClient;

    public SteamGameTypeMetadataProvider(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<SteamGameTypeMetadata> ResolveAsync(string referenceQuery, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(referenceQuery))
        {
            return Failure(referenceQuery, "steam_query_empty");
        }

        try
        {
            var app = await ResolveFirstAppAsync(referenceQuery, cancellationToken);
            if (app is null)
            {
                return Failure(referenceQuery, "steam_app_not_found");
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
                details.Genres);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return Failure(referenceQuery, "steam_lookup_timeout");
        }
        catch (HttpRequestException)
        {
            return Failure(referenceQuery, "steam_lookup_http_failed");
        }
        catch (JsonException)
        {
            return Failure(referenceQuery, "steam_lookup_json_invalid");
        }
    }

    private async Task<SteamSearchApp?> ResolveFirstAppAsync(string query, CancellationToken cancellationToken)
    {
        foreach (var language in SearchLanguages)
        {
            var url = $"https://store.steampowered.com/api/storesearch/?cc=us&l={language}&term=" + Uri.EscapeDataString(query.Trim());
            using var document = await GetJsonAsync(url, cancellationToken);
            if (!document.RootElement.TryGetProperty("items", out var items) || items.ValueKind != JsonValueKind.Array)
            {
                continue;
            }

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
                return new SteamSearchApp(appId, name);
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

    private static SteamGameTypeMetadata Failure(string referenceQuery, string reason)
    {
        return new SteamGameTypeMetadata("failed", reason, referenceQuery.Trim(), "", "", [], [], []);
    }

    private static string FirstNonEmpty(params string[] values)
    {
        return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    }

    private readonly record struct SteamSearchApp(string AppId, string Name);

    private sealed record SteamAppDetails(string Name, IReadOnlyList<string> Categories, IReadOnlyList<string> Genres);

    private static readonly string[] SearchLanguages = ["english", "schinese", "japanese"];
}
