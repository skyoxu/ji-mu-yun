using System.Net;
using FluentAssertions;
using PhaseA.Platform.Prototypes;
using Xunit;

namespace PhaseA.Platform.Tests.Prototypes;

public sealed class SteamGameTypeMetadataProviderTests
{
    [Fact]
    public async Task ResolveAsync_ReadsEnglishDetailsAndStoreTags()
    {
        var handler = new FakeSteamHandler
        {
            EnglishSearchJson = """{"items":[{"id":123,"name":"Slay the Spire"}]}""",
            AppDetailsJson = """
                {"123":{"success":true,"data":{"name":"Slay the Spire","categories":[{"description":"Single-player"}],"genres":[{"description":"Strategy"},{"description":"RPG"}]}}}
                """,
            StoreHtml = """
                <html><body>
                  <a class="app_tag" href="#"> Deckbuilding </a>
                  <a class="app_tag" href="#">Roguelike Deckbuilder</a>
                  <a class="app_tag" href="#">Deckbuilding</a>
                </body></html>
                """
        };
        var provider = new SteamGameTypeMetadataProvider(new HttpClient(handler));

        var result = await provider.ResolveAsync("Slay the Spire", CancellationToken.None);

        result.Status.Should().Be("resolved");
        result.StatusReason.Should().Be("steam_metadata_resolved");
        result.SteamAppId.Should().Be("123");
        result.SteamName.Should().Be("Slay the Spire");
        result.Tags.Should().Equal("Deckbuilding", "Roguelike Deckbuilder");
        result.Categories.Should().Equal("Single-player");
        result.Genres.Should().Equal("Strategy", "RPG");
    }

    [Fact]
    public async Task ResolveAsync_FallsBackToLocalizedSearchAndStillUsesEnglishMetadata()
    {
        var handler = new FakeSteamHandler
        {
            EnglishSearchJson = """{"items":[]}""",
            SimplifiedChineseSearchJson = """{"items":[{"id":456,"name":"戴森球计划"}]}""",
            AppDetailsJson = """
                {"456":{"success":true,"data":{"name":"Dyson Sphere Program","categories":[{"description":"Single-player"}],"genres":[{"description":"Simulation"}]}}}
                """,
            StoreHtml = """<a class="app_tag" href="#">Automation</a><a class="app_tag" href="#">Base Building</a>"""
        };
        var provider = new SteamGameTypeMetadataProvider(new HttpClient(handler));

        var result = await provider.ResolveAsync("戴森球计划", CancellationToken.None);

        result.Status.Should().Be("resolved");
        result.SteamAppId.Should().Be("456");
        result.SteamName.Should().Be("Dyson Sphere Program");
        result.Tags.Should().Equal("Automation", "Base Building");
        result.Genres.Should().Equal("Simulation");
        handler.SearchLanguages.Should().Equal("english", "schinese");
    }

    [Fact]
    public async Task ResolveAsync_ReturnsHttpFailure_WhenSteamRequestFails()
    {
        var handler = new FakeSteamHandler
        {
            FailSearch = true
        };
        var provider = new SteamGameTypeMetadataProvider(new HttpClient(handler));

        var result = await provider.ResolveAsync("missing", CancellationToken.None);

        result.Status.Should().Be("failed");
        result.StatusReason.Should().Be("steam_lookup_http_failed");
        result.Tags.Should().BeEmpty();
        result.Categories.Should().BeEmpty();
        result.Genres.Should().BeEmpty();
    }

    private sealed class FakeSteamHandler : HttpMessageHandler
    {
        public string EnglishSearchJson { get; init; } = """{"items":[]}""";
        public string SimplifiedChineseSearchJson { get; init; } = """{"items":[]}""";
        public string JapaneseSearchJson { get; init; } = """{"items":[]}""";
        public string AppDetailsJson { get; init; } = "{}";
        public string StoreHtml { get; init; } = "";
        public bool FailSearch { get; init; }
        public List<string> SearchLanguages { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var uri = request.RequestUri ?? throw new InvalidOperationException("Missing request URI.");
            if (uri.AbsolutePath == "/api/storesearch/")
            {
                if (FailSearch)
                {
                    return Task.FromResult(new HttpResponseMessage(HttpStatusCode.InternalServerError));
                }

                var language = QueryValue(uri.Query, "l");
                SearchLanguages.Add(language);
                return Task.FromResult(Json(language switch
                {
                    "english" => EnglishSearchJson,
                    "schinese" => SimplifiedChineseSearchJson,
                    "japanese" => JapaneseSearchJson,
                    _ => """{"items":[]}"""
                }));
            }

            if (uri.AbsolutePath == "/api/appdetails")
            {
                return Task.FromResult(Json(AppDetailsJson));
            }

            if (uri.AbsolutePath.StartsWith("/app/", StringComparison.Ordinal))
            {
                return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent(StoreHtml)
                });
            }

            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound));
        }

        private static HttpResponseMessage Json(string content)
        {
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(content)
            };
        }

        private static string QueryValue(string query, string key)
        {
            var trimmed = query.TrimStart('?');
            foreach (var part in trimmed.Split('&', StringSplitOptions.RemoveEmptyEntries))
            {
                var pieces = part.Split('=', 2);
                if (pieces.Length == 2 && string.Equals(Uri.UnescapeDataString(pieces[0]), key, StringComparison.Ordinal))
                {
                    return Uri.UnescapeDataString(pieces[1]);
                }
            }

            return "";
        }
    }
}
