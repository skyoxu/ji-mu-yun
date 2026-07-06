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

    [Theory]
    [InlineData("Deckbuild")]
    [InlineData("Deck Builder")]
    [InlineData("Deckbuilder")]
    [InlineData("Deckbuilding")]
    public void MatchByGenreTags_ShouldResolveCardGameFromSingleHighConfidenceDeckbuilderTag(string tag)
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

        var match = catalog.MatchByGenreTags([tag]);

        match.Status.Should().Be("matched");
        match.MatchedGameTypeId.Should().Be("card-game");
        match.MatchScore.Should().BeGreaterThanOrEqualTo(12);
    }

    [Fact]
    public void MatchByGenreTags_ShouldPreferCardGameForRoguelikeDeckbuilderTag()
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

        var match = catalog.MatchByGenreTags(["Roguelike Deckbuilder"]);

        match.Status.Should().Be("matched");
        match.MatchedGameTypeId.Should().Be("card-game");
        match.CandidateScores.Should().Contain(candidate => candidate.GameTypeId == "roguelike");
    }

    [Fact]
    public void MatchByGenreTags_ShouldResolveDeckBuilderFromRepositoryCatalog()
    {
        var repoRoot = ResolveRepositoryRoot();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(repoRoot, "logs", "test-workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(repoRoot, "logs", "test-metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot
        });
        var catalog = new GameTypeGuideCatalog(options);

        var match = catalog.MatchByGenreTags(["Deck Builder"]);

        match.Status.Should().Be("matched");
        match.MatchedGameTypeId.Should().Be("card-game");
    }

    private static string ResolveRepositoryRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            if (File.Exists(System.IO.Path.Combine(current.FullName, "docs", "game-type-guides", "game-types.csv")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return Directory.GetCurrentDirectory();
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
                card-game,Card Game,"Card systems","card,deck-build,deckbuild,deck-builder,deck-building,deckbuilder,deckbuilding,roguelike-deckbuilder,card-battler",card-game.md
                rpg,RPG,"Role playing","rpg,role-playing",rpg.md
                roguelike,Roguelike,"Run-based generation","roguelike,roguelike-deckbuilder",roguelike.md
                """);
            File.WriteAllText(System.IO.Path.Combine(dir, "card-game.md"), "# Card Game");
            File.WriteAllText(System.IO.Path.Combine(dir, "rpg.md"), "# RPG");
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
