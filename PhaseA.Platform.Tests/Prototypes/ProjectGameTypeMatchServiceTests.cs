using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Prototypes;
using Xunit;

namespace PhaseA.Platform.Tests.Prototypes;

public sealed class ProjectGameTypeMatchServiceTests
{
    [Fact]
    public async Task ResolveAsync_ShouldMatchUsingSteamAliasDiagnostics()
    {
        using var repo = new TempRepo();
        repo.WriteGuideCatalog();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(repo.Path, "workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(repo.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        var service = new ProjectGameTypeMatchService(options, new FakeSteamProvider());

        var evidence = await service.ResolveAsync("\u6740\u622e\u5c16\u5854", CancellationToken.None);

        evidence.Status.Should().Be("matched");
        evidence.StatusReason.Should().Be("matched_by_genre_tags");
        evidence.ReferenceQuery.Should().Be("\u6740\u622e\u5c16\u5854");
        evidence.SteamResolvedQuery.Should().Be("Slay the Spire");
        evidence.SteamAttemptedQueries.Should().Equal("\u6740\u622e\u5c16\u5854", "Slay the Spire");
        evidence.SteamName.Should().Be("Slay the Spire");
        evidence.NormalizedGenreTags.Should().Contain(["deckbuilding", "roguelike-deckbuilder", "strategy"]);
        evidence.MatchedGameTypeId.Should().Be("card-game");
        evidence.MatchedGuidePath.Should().Be("docs/game-type-guides/card-game.md");
    }

    private sealed class FakeSteamProvider : ISteamGameTypeMetadataProvider
    {
        public Task<SteamGameTypeMetadata> ResolveAsync(string referenceQuery, CancellationToken cancellationToken)
        {
            return Task.FromResult(new SteamGameTypeMetadata(
                "resolved",
                "steam_metadata_resolved",
                referenceQuery,
                "646570",
                "Slay the Spire",
                ["Deckbuilding", "Roguelike Deckbuilder"],
                ["Single-player"],
                ["Strategy"])
            {
                ResolvedQuery = "Slay the Spire",
                AttemptedQueries = [referenceQuery, "Slay the Spire"]
            });
        }
    }

    private sealed class TempRepo : IDisposable
    {
        public TempRepo()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"phasea-match-service-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void WriteGuideCatalog()
        {
            var dir = System.IO.Path.Combine(Path, "docs", "game-type-guides");
            Directory.CreateDirectory(dir);
            File.WriteAllText(System.IO.Path.Combine(dir, "game-types.csv"), """
                id,name,description,genre_tags,fragment_file
                card-game,Card Game,"Card systems","card,deck-build,deckbuild,deck-builder,deck-building,deckbuilder,deckbuilding,roguelike-deckbuilder,card-battler,strategy",card-game.md
                roguelike,Roguelike,"Run-based generation","roguelike",roguelike.md
                """);
            File.WriteAllText(System.IO.Path.Combine(dir, "card-game.md"), "# Card Game");
            File.WriteAllText(System.IO.Path.Combine(dir, "roguelike.md"), "# Roguelike");
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
