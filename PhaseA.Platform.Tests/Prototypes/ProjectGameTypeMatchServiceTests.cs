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
        evidence.ContractSnapshot.HasContract.Should().BeTrue();
        evidence.ContractSnapshot.MatchedGameTypeId.Should().Be("card-game");
        evidence.ContractSnapshot.DefaultScenes.Select(scene => scene.SceneId)
            .Should()
            .Equal("class_selection", "route_map", "card_battle", "reward_choice");
        evidence.ContractSnapshot.RequiredModules.Select(module => module.ModuleId)
            .Should()
            .Equal("route_map_path_selection", "hand_card_dragging");
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
            File.WriteAllText(System.IO.Path.Combine(dir, "card-game.md"), """
                # Card Game

                ## Default Prototype Contract

                ### Default Scenes

                | scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
                | --- | --- | --- | --- | --- | --- | --- |
                | class_selection | Class Selection | Let the player choose a starting class. | Always | start | route_map | A class can be selected. |
                | route_map | Route Map | Present route choices. | Always | class_selection,reward_choice | card_battle | Connected route nodes can be selected. |
                | card_battle | Card Battle | Resolve card combat. | Always | route_map | reward_choice | A card can be dragged and resolved. |
                | reward_choice | Reward Choice | Choose post-battle rewards. | Always | card_battle | route_map | A reward changes deck or run state. |

                ### Required Modules

                | module_id | module_name | required_by_default | purpose | minimum_acceptance |
                | --- | --- | --- | --- | --- |
                | route_map_path_selection | Route map path selection | Always | Branching route choice. | Reachable next nodes are enforced. |
                | hand_card_dragging | Hand card dragging | Always | Tactile hand interaction. | Cards drag, preview, cancel, and resolve. |
                """);
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
