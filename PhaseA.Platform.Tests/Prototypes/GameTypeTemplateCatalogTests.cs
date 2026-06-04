using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Prototypes;
using Xunit;

namespace PhaseA.Platform.Tests.Prototypes;

public sealed class GameTypeTemplateCatalogTests
{
    [Fact]
    public void Find_ShouldReturnRpgEntry_WhenCatalogExists()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var catalogPath = Path.Combine(repo.Path, "docs", "prototype-type-kits", "game-type-template-catalog.json");
        Directory.CreateDirectory(Path.GetDirectoryName(catalogPath)!);
        File.WriteAllText(catalogPath, """
        {
          "schema_version": 1,
          "entries": [
            {
              "game_type": "rpg",
              "template_id": "default-rpg-template",
              "source_mode": "repo-imported",
              "repo_template_path": "Game.Godot/Prototypes/DefaultRpgTemplate",
              "manifest_path": "docs/prototype-type-kits/default-rpg-template.manifest.json",
              "import_source_path": "C:/gametype/rpgdemo",
              "enabled": true
            }
          ]
        }
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new GameTypeTemplateCatalog(options);
        var entry = catalog.Find("rpg");

        entry.Should().NotBeNull();
        entry!.TemplateId.Should().Be("default-rpg-template");
        entry.ManifestPath.Should().Be("docs/prototype-type-kits/default-rpg-template.manifest.json");
    }

    [Fact]
    public void BmadCatalog_ShouldLoadCanonicalGameTypeRowsAndGuideExcerpt()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        action-platformer,Action Platformer,Jumping and action,action,action-platformer.md
        puzzle,Puzzle,Logic challenges,puzzle,puzzle.md
        rpg,RPG,"Character progression, stats, inventory, quests","rpg,stats,inventory,quests,narrative",rpg.md
        strategy,Strategy,Planning and resources,strategy,strategy.md
        shooter,Shooter,Aiming and projectiles,shooter,shooter.md
        adventure,Adventure,Exploration and narrative,adventure,adventure.md
        simulation,Simulation,System simulation,simulation,simulation.md
        roguelike,Roguelike,Runs and procedural variation,roguelike,roguelike.md
        moba,MOBA,Lane team battles,moba,moba.md
        fighting,Fighting,Character duels,fighting,fighting.md
        racing,Racing,Vehicle racing,racing,racing.md
        sports,Sports,Sport rules,sports,sports.md
        survival,Survival,Resource survival,survival,survival.md
        horror,Horror,Fear and tension,horror,horror.md
        idle-incremental,Idle/Incremental,Incremental progression,idle,idle-incremental.md
        card-game,Card Game,Cards and deck rules,cards,card-game.md
        tower-defense,Tower Defense,Towers and waves,tower-defense,tower-defense.md
        metroidvania,Metroidvania,Exploration ability gates,metroidvania,metroidvania.md
        visual-novel,Visual Novel,Dialogue choices,visual-novel,visual-novel.md
        rhythm,Rhythm,Timing input,rhythm,rhythm.md
        turn-based-tactics,Turn-Based Tactics,Grid tactics,tactics,turn-based-tactics.md
        sandbox,Sandbox,Player-authored systems,sandbox,sandbox.md
        text-based,Text-Based,Text interface,text,text-based.md
        party-game,Party Game,Local multiplayer party,party,party-game.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), """
        ## RPG Specific Elements

        {{character_system}}

        ### Character System

        - Stats
        - Leveling system

        ### Quest System

        - Main story quests
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("RPG");

        catalog.Entries.Should().HaveCount(24);
        rpg.Should().NotBeNull();
        rpg!.Description.Should().Contain("Character progression");
        rpg.GuideExcerpt.Should().Contain("RPG Specific Elements");
        rpg.GuideExcerpt.Should().Contain("Leveling system");
        rpg.GuideExcerpt.Should().NotContain("{{character_system}}");
    }

    [Fact]
    public void BmadCatalog_ShouldPreferExtractedDocsGuidesOverSkillFallback()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        Directory.CreateDirectory(docsRoot);
        Directory.CreateDirectory(Path.Combine(skillRoot, "game-types"));
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Docs description,docs,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(docsRoot, "rpg.md"), "Docs RPG guide.", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Skill fallback description,skill,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(skillRoot, "game-types", "rpg.md"), "Skill fallback RPG guide.", System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.Description.Should().Be("Docs description");
        rpg.FragmentRelativePath.Should().Be("docs/game-type-guides/rpg.md");
        rpg.GuideExcerpt.Should().Be("Docs RPG guide.");
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
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
