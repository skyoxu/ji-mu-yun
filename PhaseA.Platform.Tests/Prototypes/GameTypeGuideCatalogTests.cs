using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Prototypes;
using Xunit;

namespace PhaseA.Platform.Tests.Prototypes;

public sealed class GameTypeGuideCatalogTests
{
    [Fact]
    public void MatchByGenreTags_ShouldResolveGuideFromGenreTags()
    {
        using var repo = new TempRepo();
        repo.WriteGuideCatalog();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(repo.Path, "workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(repo.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });
        var catalog = new GameTypeGuideCatalog(options);

        var match = catalog.MatchByGenreTags(["Deck Building", "Card Battler", "Singleplayer"]);

        match.Status.Should().Be("matched");
        match.MatchedGameTypeId.Should().Be("card-game");
        match.MatchedGuidePath.Should().Be("docs/game-type-guides/card-game.md");
        match.NormalizedGenreTags.Should().Contain(["deck-building", "card-battler"]);
        match.NormalizedGenreTags.Should().NotContain("singleplayer");
    }

    private sealed class TempRepo : IDisposable
    {
        public TempRepo()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"phasea-guide-catalog-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void WriteGuideCatalog()
        {
            var dir = System.IO.Path.Combine(Path, "docs", "game-type-guides");
            Directory.CreateDirectory(dir);
            File.WriteAllText(System.IO.Path.Combine(dir, "game-types.csv"), """
                id,name,description,genre_tags,fragment_file
                card-game,Card Game,"Card systems","card,deck-building,card-battler",card-game.md
                rpg,RPG,"Role playing","rpg,role-playing",rpg.md
                """);
            File.WriteAllText(System.IO.Path.Combine(dir, "card-game.md"), "# Card Game");
            File.WriteAllText(System.IO.Path.Combine(dir, "rpg.md"), "# RPG");
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
