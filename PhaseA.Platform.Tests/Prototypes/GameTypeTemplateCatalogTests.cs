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
