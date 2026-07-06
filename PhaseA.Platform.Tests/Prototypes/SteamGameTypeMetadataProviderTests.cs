using System.Net;
using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Prototypes;
using Xunit;

namespace PhaseA.Platform.Tests.Prototypes;

public sealed class SteamGameTypeMetadataProviderTests
{
    [Fact]
    public void Constructor_WithOptions_IsMarkedForDependencyInjection()
    {
        var constructor = typeof(SteamGameTypeMetadataProvider)
            .GetConstructor([typeof(HttpClient), typeof(PhaseAPlatformOptions)]);

        constructor.Should().NotBeNull();
        constructor!.GetCustomAttributes(typeof(ActivatorUtilitiesConstructorAttribute), inherit: false)
            .Should()
            .ContainSingle();
    }

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
    public async Task ResolveAsync_FallsBackToKnownEnglishReferenceAlias()
    {
        const string source = "\u6740\u622e\u5c16\u5854";
        using var repo = new TempRepo();
        repo.WriteSteamAliasesCsv();
        var handler = new FakeSteamHandler
        {
            AppDetailsJson = """
                {"646570":{"success":true,"data":{"name":"Slay the Spire","categories":[{"description":"Single-player"}],"genres":[{"description":"Strategy"}]}}}
                """,
            StoreHtml = """<a class="app_tag" href="#">Deckbuilding</a><a class="app_tag" href="#">Roguelike Deckbuilder</a>"""
        };
        handler.SearchJsonByLanguageAndTerm["english\nSlay the Spire"] = """{"items":[{"id":2868840,"name":"Slay the Spire 2"},{"id":646570,"name":"Slay the Spire"}]}""";
        var provider = new SteamGameTypeMetadataProvider(new HttpClient(handler), repo.Options);

        var result = await provider.ResolveAsync(source, CancellationToken.None);

        result.Status.Should().Be("resolved");
        result.ReferenceQuery.Should().Be(source);
        result.ResolvedQuery.Should().Be("Slay the Spire");
        result.AttemptedQueries.Should().Equal(source, "Slay the Spire");
        result.SteamAppId.Should().Be("646570");
        result.SteamName.Should().Be("Slay the Spire");
        result.Tags.Should().Equal("Deckbuilding", "Roguelike Deckbuilder");
        handler.SearchRequests.Should().ContainInOrder(
            ("english", source),
            ("schinese", source),
            ("japanese", source),
            ("english", "Slay the Spire"));
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
        public List<(string Language, string Term)> SearchRequests { get; } = [];
        public Dictionary<string, string> SearchJsonByLanguageAndTerm { get; } = new(StringComparer.Ordinal);

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
                var term = QueryValue(uri.Query, "term");
                SearchLanguages.Add(language);
                SearchRequests.Add((language, term));
                if (SearchJsonByLanguageAndTerm.TryGetValue($"{language}\n{term}", out var searchJson))
                {
                    return Task.FromResult(Json(searchJson));
                }

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

    private sealed class TempRepo : IDisposable
    {
        public TempRepo()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"phasea-steam-aliases-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
            Options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = System.IO.Path.Combine(Path, "workspaces"),
                ["PHASEA_METADATA_DB_PATH"] = System.IO.Path.Combine(Path, "metadata.sqlite3"),
                ["PHASEA_REPOSITORY_ROOT"] = Path
            });
        }

        public string Path { get; }

        public PhaseAPlatformOptions Options { get; }

        public void WriteSteamAliasesCsv()
        {
            var dir = System.IO.Path.Combine(Path, "docs", "game-type-guides");
            Directory.CreateDirectory(dir);
            File.WriteAllText(
                System.IO.Path.Combine(dir, "steam-reference-aliases.csv"),
                "source_query,steam_query\n\\u6740\\u622e\\u5c16\\u5854,Slay the Spire\n");
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
