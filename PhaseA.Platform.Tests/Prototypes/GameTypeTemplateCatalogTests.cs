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
        foreach (var fragmentFile in File.ReadAllLines(Path.Combine(skillRoot, "game-types.csv"), System.Text.Encoding.UTF8)
                     .Skip(1)
                     .Where(line => !string.IsNullOrWhiteSpace(line))
                     .Select(line => line[(line.LastIndexOf(',') + 1)..].Trim()))
        {
            File.WriteAllText(Path.Combine(gameTypesRoot, fragmentFile), $"## {fragmentFile} guide\n", System.Text.Encoding.UTF8);
        }
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
    public void BmadCatalog_ShouldPreserveCompleteModuleMatrix_WhenGuideExcerptIsTruncated()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 5000)}

        ### Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        | 1 | `opening_context` | Opening context | Always | Establish context. | Context is visible. |
        | 5 | `battle_or_challenge_resolution` | Battle or challenge resolution | Optional | Resolve conflict. | Conflict is settled. |
        | 10 | `final_first_loop_acceptance` | Final first-loop acceptance | Always | Close the loop. | Selected modules are linked. |
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Should().Contain("RPG Specific Elements");
        rpg!.GuideExcerpt.Should().Contain("Module Matrix");
        rpg.GuideExcerpt.Should().Contain("Compact index");
        rpg.GuideExcerpt.Should().Contain("`opening_context`");
        rpg.GuideExcerpt.Should().Contain("`battle_or_challenge_resolution`");
        rpg.GuideExcerpt.Should().Contain("`final_first_loop_acceptance`");
        rpg.GuideExcerpt.Should().Contain("Selected modules are linked.");
    }

    [Fact]
    public void BmadCatalog_ShouldBoundGuideExcerpt_WhenModuleMatrixHasLargeTrailingSection()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 2600)}

        ## Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        | 1 | `opening_context` | Opening context | Always | Establish context. | Context is visible. |
        | 5 | `battle_or_challenge_resolution` | Battle or challenge resolution | Optional | Resolve conflict. | Conflict is settled. |
        | 10 | `final_first_loop_acceptance` | Final first-loop acceptance | Always | Close the loop. | Selected modules are linked. |

        ## Huge Reference Appendix

        {new string('Z', 10000)}
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Length.Should().BeLessThanOrEqualTo(4200);
        rpg.GuideExcerpt.Should().Contain("Module Matrix");
        rpg.GuideExcerpt.Should().Contain("`battle_or_challenge_resolution`");
        rpg.GuideExcerpt.Should().Contain("`final_first_loop_acceptance`");
        rpg.GuideExcerpt.Should().Contain("Conflict is settled.");
        rpg.GuideExcerpt.Should().NotContain("Huge Reference Appendix");
        rpg.GuideExcerpt.Should().NotContain(new string('Z', 100));
    }

    [Fact]
    public void BmadCatalog_ShouldPrioritizeDefaultPrototypeContract_WhenGuideIsLong()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 5000)}

        ## Default Prototype Contract

        ### Default Scenes

        | scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
        | --- | --- | --- | --- | --- | --- | --- |
        | field_exploration | Field exploration | Explore. | Always | start | combat_encounter | Movement and objective are visible. |
        | combat_encounter | Combat encounter | Fight. | Always | field_exploration | field_exploration | Enemy and result are visible. |

        ### Required Modules

        | module_id | module_name | required_by_default | purpose | minimum_acceptance |
        | --- | --- | --- | --- | --- |
        | character_stats | Character stats | Always | Track actor state. | HP or stats affect play. |

        ## Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        | 1 | `opening_context` | Opening context | Always | Establish context. | Context is visible. |
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Length.Should().BeLessThanOrEqualTo(4200);
        rpg.GuideExcerpt.Should().Contain("Default Prototype Contract");
        rpg.GuideExcerpt.Should().Contain("field_exploration");
        rpg.GuideExcerpt.Should().Contain("combat_encounter");
        rpg.GuideExcerpt.Should().Contain("character_stats");
        rpg.GuideExcerpt.Should().Contain("Module Matrix");
        rpg.GuideExcerpt.Split("Module Matrix").Length.Should().Be(2);
        rpg.GuideExcerpt.Should().Contain("`opening_context`");
        rpg.GuideExcerpt.Should().NotContain(new string('A', 100));
    }

    [Fact]
    public void BmadCatalog_ShouldPreserveAllModuleIds_WhenModuleMatrixExceedsDetailedBudget()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        var rows = string.Join(Environment.NewLine, Enumerable.Range(1, 24).Select(index =>
            $"| {index} | `module_{index:00}` | Very long module title {index} with extra words for budget pressure | Optional | {new string('P', 160)} | {new string('A', 180)} |"));
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 2600)}

        ## Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        {rows}
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Length.Should().BeLessThanOrEqualTo(4200);
        rpg.GuideExcerpt.Should().Contain("Compact id index");
        rpg.GuideExcerpt.Should().Contain("`module_01`");
        rpg.GuideExcerpt.Should().Contain("`module_24`");
    }

    [Fact]
    public void BmadCatalog_ShouldPreserveOneHundredModuleIds_WhenModuleMatrixRequiresMinimalIndex()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        var rows = string.Join(Environment.NewLine, Enumerable.Range(1, 100).Select(index =>
            $"| {index} | `module_{index:000}` | Very long module title {index} with extra words for budget pressure | Optional | {new string('P', 160)} | {new string('A', 180)} |"));
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 2600)}

        ## Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        {rows}
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Length.Should().BeLessThanOrEqualTo(4200);
        rpg.GuideExcerpt.Should().Contain("Compact id index");
        rpg.GuideExcerpt.Should().Contain("`module_001`");
        rpg.GuideExcerpt.Should().Contain("`module_050`");
        rpg.GuideExcerpt.Should().Contain("`module_100`");
    }

    [Fact]
    public void BmadCatalog_ShouldMarkOmittedModuleIds_WhenMinimalIndexStillExceedsBudget()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        var rows = string.Join(Environment.NewLine, Enumerable.Range(1, 300).Select(index =>
            $"| {index} | `very_long_module_identifier_{index:000}` | Very long module title {index} with extra words for budget pressure | Optional | {new string('P', 160)} | {new string('A', 180)} |"));
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 2600)}

        ## Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        {rows}
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Length.Should().BeLessThanOrEqualTo(4200);
        rpg.GuideExcerpt.Should().Contain("Compact id index");
        rpg.GuideExcerpt.Should().Contain("omitted");
        rpg.GuideExcerpt.Should().Contain("module ids");
        rpg.GuideExcerpt.Should().NotContain("preserve every module id");
    }

    [Fact]
    public void BmadCatalog_ShouldParseEscapedPipeCellsInModuleMatrix()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 2600)}

        ## Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        | 1 | `opening_context` | Opening \| context | Always | Shows A \| B choice. | Choice copy stays visible. |
        | 2 | `final_first_loop_acceptance` | Final loop | Always | Close loop. | Loop closes. |
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Should().Contain("`opening_context`");
        rpg.GuideExcerpt.Should().Contain("Opening \\| context");
        rpg.GuideExcerpt.Should().Contain("Shows A \\| B choice.");
        rpg.GuideExcerpt.Should().Contain("`final_first_loop_acceptance`");
    }

    [Fact]
    public void BmadCatalog_ShouldPreserveOrdinaryBackslashesInModuleMatrixCells()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Character progression,rpg,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), $"""
        ## RPG Specific Elements

        {new string('A', 2600)}

        ## Module Matrix

        | No | id | Module | Default | Purpose | Acceptance |
        | --- | --- | --- | --- | --- | --- |
        | 1 | `opening_context` | Regex \d+ context | Always | Uses C:\temp\module path. | Backslashes stay visible. |
        | 2 | `final_first_loop_acceptance` | Final loop | Always | Close loop. | Loop closes. |
        """, System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.GuideExcerpt.Should().Contain(@"Regex \d+ context");
        rpg.GuideExcerpt.Should().Contain(@"Uses C:\temp\module path.");
        rpg.GuideExcerpt.Should().Contain("`final_first_loop_acceptance`");
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

    [Fact]
    public void BmadCatalog_ShouldPreferCanonicalGdsAssetsOverCompatibilityMirror()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var canonicalRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-gdd", "assets");
        var compatibilityRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        Directory.CreateDirectory(Path.Combine(canonicalRoot, "game-types"));
        Directory.CreateDirectory(Path.Combine(compatibilityRoot, "game-types"));
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Canonical description,canonical,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "rpg.md"), "Canonical RPG guide.", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(compatibilityRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Compatibility description,compatibility,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(compatibilityRoot, "game-types", "rpg.md"), "Compatibility RPG guide.", System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var rpg = catalog.Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.Description.Should().Be("Canonical description");
        rpg.FragmentRelativePath.Should().Be(".agents/skills/gds-gdd/assets/game-types/rpg.md");
        rpg.GuideExcerpt.Should().Be("Canonical RPG guide.");
    }

    [Fact]
    public void BmadCatalog_ShouldMergePartialDocsOverCanonicalFallback()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        var canonicalRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-gdd", "assets");
        Directory.CreateDirectory(docsRoot);
        Directory.CreateDirectory(Path.Combine(canonicalRoot, "game-types"));
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Docs description,docs,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(docsRoot, "rpg.md"), "Docs RPG guide.", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Canonical RPG,canonical-rpg,rpg.md
        puzzle,Puzzle,Canonical puzzle,canonical-puzzle,puzzle.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "rpg.md"), "Canonical RPG guide.", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "puzzle.md"), "Canonical puzzle guide.", System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);

        catalog.Entries.Should().HaveCount(2);
        catalog.Find("rpg")!.GuideExcerpt.Should().Be("Docs RPG guide.");
        catalog.Find("rpg")!.FragmentRelativePath.Should().Be("docs/game-type-guides/rpg.md");
        catalog.Find("puzzle")!.GuideExcerpt.Should().Be("Canonical puzzle guide.");
        catalog.Find("puzzle")!.FragmentRelativePath.Should().Be(".agents/skills/gds-gdd/assets/game-types/puzzle.md");
    }

    [Fact]
    public void BmadCatalog_ShouldUseCanonicalFieldsAndGuideWhenDocsRowIsPartial()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        var canonicalRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-gdd", "assets");
        Directory.CreateDirectory(docsRoot);
        Directory.CreateDirectory(Path.Combine(canonicalRoot, "game-types"));
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,,,,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Canonical description,canonical,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "rpg.md"), "Canonical RPG guide.", System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var rpg = new BmadGameTypeDesignCatalog(options).Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.Name.Should().Be("RPG");
        rpg.Description.Should().Be("Canonical description");
        rpg.GenreTags.Should().Be("canonical");
        rpg.GuideExcerpt.Should().Be("Canonical RPG guide.");
        rpg.FragmentRelativePath.Should().Be(".agents/skills/gds-gdd/assets/game-types/rpg.md");
    }

    [Fact]
    public void BmadCatalog_ShouldIgnoreDuplicateDocsIdsAndUseCanonicalCatalog()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        var canonicalRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-gdd", "assets");
        Directory.CreateDirectory(docsRoot);
        Directory.CreateDirectory(Path.Combine(canonicalRoot, "game-types"));
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,First docs row,docs,rpg.md
        RPG,RPG,Duplicate docs row,duplicate,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(docsRoot, "rpg.md"), "Docs RPG guide.", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Canonical description,canonical,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "rpg.md"), "Canonical RPG guide.", System.Text.Encoding.UTF8);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var rpg = new BmadGameTypeDesignCatalog(options).Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.Description.Should().Be("Canonical description");
        rpg.GuideExcerpt.Should().Be("Canonical RPG guide.");
    }

    [Fact]
    public void BmadCatalog_ShouldIgnoreMalformedDocsCsvAndUseCanonicalCatalog()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        var canonicalRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-gdd", "assets");
        Directory.CreateDirectory(docsRoot);
        Directory.CreateDirectory(Path.Combine(canonicalRoot, "game-types"));
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,"Unclosed description,docs,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Canonical description,canonical,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "rpg.md"), "Canonical RPG guide.", System.Text.Encoding.UTF8);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var rpg = new BmadGameTypeDesignCatalog(options).Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.Description.Should().Be("Canonical description");
        rpg.GuideExcerpt.Should().Be("Canonical RPG guide.");
    }

    [Fact]
    public void BmadCatalog_ShouldIgnoreDocsCsvWithMissingRequiredHeader()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        var canonicalRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-gdd", "assets");
        Directory.CreateDirectory(docsRoot);
        Directory.CreateDirectory(Path.Combine(canonicalRoot, "game-types"));
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags
        rpg,RPG,Docs description,docs
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Canonical description,canonical,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "rpg.md"), "Canonical RPG guide.", System.Text.Encoding.UTF8);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var rpg = new BmadGameTypeDesignCatalog(options).Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.Description.Should().Be("Canonical description");
        rpg.GuideExcerpt.Should().Be("Canonical RPG guide.");
    }

    [Fact]
    public void BmadCatalog_ShouldRejectGuideFragmentsOutsideCatalogRoot()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        var canonicalRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-gdd", "assets");
        Directory.CreateDirectory(docsRoot);
        Directory.CreateDirectory(Path.Combine(canonicalRoot, "game-types"));
        File.WriteAllText(Path.Combine(repo.Path, "docs", "secret.md"), "Outside guide content.", System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Escaping docs row,docs,../secret.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,Canonical description,canonical,rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(canonicalRoot, "game-types", "rpg.md"), "Canonical RPG guide.", System.Text.Encoding.UTF8);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var rpg = new BmadGameTypeDesignCatalog(options).Find("rpg");

        rpg.Should().NotBeNull();
        rpg!.Description.Should().Be("Canonical description");
        rpg.GuideExcerpt.Should().Be("Canonical RPG guide.");
        rpg.GuideExcerpt.Should().NotContain("Outside guide content");
    }

    [Theory]
    [InlineData("Vampire Survivors-like")]
    [InlineData("survivors like")]
    [InlineData("arena survival")]
    public void BmadCatalog_ShouldNotImpersonateSurvivalWhenRepositoryExtensionIsUnavailable(string alias)
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var skillRoot = Path.Combine(repo.Path, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        survival,Survival,Resource survival,survival,survival.md
        roguelike,Roguelike,Runs and procedural variation,roguelike,roguelike.md
        shooter,Shooter,Aiming and projectiles,shooter,shooter.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "survival.md"), "Survival guide excerpt.", System.Text.Encoding.UTF8);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);
        var entry = catalog.Find(alias);

        entry.Should().BeNull();
    }

    [Theory]
    [InlineData("Vampire Survivors-like")]
    [InlineData("survivors like")]
    [InlineData("arena survival")]
    public void BmadCatalog_ShouldMapSurvivorsLikeAliasesToRepositoryExtension(string alias)
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        Directory.CreateDirectory(docsRoot);
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        survivorslike,Survivorslike,Arena survival,bullet-heaven,survivorslike.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(docsRoot, "survivorslike.md"), "Survivorslike guide excerpt.", System.Text.Encoding.UTF8);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var entry = new BmadGameTypeDesignCatalog(options).Find(alias);

        entry.Should().NotBeNull();
        entry!.Id.Should().Be("survivorslike");
        entry.GuideExcerpt.Should().Be("Survivorslike guide excerpt.");
    }

    [Theory]
    [InlineData("")]
    [InlineData("survivorslike.md")]
    public void BmadCatalog_ShouldTreatBlankOrMissingRepositoryExtensionGuideAsUnavailable(string fragmentFile)
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        Directory.CreateDirectory(docsRoot);
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), $"""
        id,name,description,genre_tags,fragment_file
        survivorslike,Survivorslike,Arena survival,bullet-heaven,{fragmentFile}
        """, System.Text.Encoding.UTF8);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);

        catalog.Find("survivorslike").Should().BeNull();
        catalog.Find("Vampire Survivors-like").Should().BeNull();
    }

    [Fact]
    public void BmadCatalog_ShouldTreatEmptyRepositoryExtensionGuideAsUnavailable()
    {
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        using var repo = TempDirectory.Create("phase-a-repo");
        var docsRoot = Path.Combine(repo.Path, "docs", "game-type-guides");
        Directory.CreateDirectory(docsRoot);
        File.WriteAllText(Path.Combine(docsRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        survivorslike,Survivorslike,Arena survival,bullet-heaven,survivorslike.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(docsRoot, "survivorslike.md"), "{{placeholder_only}}\n", System.Text.Encoding.UTF8);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path
        });

        var catalog = new BmadGameTypeDesignCatalog(options);

        catalog.Find("survivorslike").Should().BeNull();
        catalog.Find("Vampire Survivors-like").Should().BeNull();
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
