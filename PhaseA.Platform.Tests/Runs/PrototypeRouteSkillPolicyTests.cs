using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeRouteSkillPolicyTests
{
    [Fact]
    public void Resolve_ShouldUseRpgSkill_ForLatestSuccessfulAdminRpgBaselineShape()
    {
        var project = Project(
            name: "rpgdemo26",
            gameName: "rpgdemo26",
            gameTypeSource: "勇者斗恶龙",
            repoPath: Path.GetTempPath());

        var context = PrototypeRouteSkillPolicy.Resolve(project);
        var prompt = PrototypeRouteSkillPolicy.BuildPromptBlock(project);

        context.RouteSkillId.Should().Be("prototype-rpg-godot-zh");
        context.SkillRelativePath.Should().Be(".agents/skills/prototype-rpg-godot-zh/SKILL.md");
        context.ContractRelativePath.Should().Be(".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md");
        prompt.Should().Contain("MandatorySkillEntry: $prototype-rpg-godot-zh");
        prompt.Should().Contain("do not run a bare/generic prototype route");
    }

    [Fact]
    public void CheckAvailable_ShouldBlockBareBusinessRoute_WhenRequiredSkillIsMissing()
    {
        using var temp = TempDirectory.Create();
        var project = Project(
            name: "rpgdemo26",
            gameName: "rpgdemo26",
            gameTypeSource: "勇者斗恶龙",
            repoPath: temp.Path);

        var availability = PrototypeRouteSkillPolicy.CheckAvailable(project);

        availability.IsAvailable.Should().BeFalse();
        availability.FailureCode.Should().Be("route_skill_required");
        availability.FailureMessage.Should().Contain(".agents/skills/prototype-rpg-godot-zh/SKILL.md");
    }

    [Fact]
    public void CheckAvailable_ShouldPass_WhenRequiredSkillAndContractExist()
    {
        using var temp = TempDirectory.Create();
        Write(temp.Path, ".agents/skills/prototype-rpg-godot-zh/SKILL.md", "name: prototype-rpg-godot-zh\n");
        Write(temp.Path, ".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md", "# RPG Prototype Contract\n");
        var project = Project(
            name: "rpgdemo26",
            gameName: "rpgdemo26",
            gameTypeSource: "勇者斗恶龙",
            repoPath: temp.Path);

        var availability = PrototypeRouteSkillPolicy.CheckAvailable(project);

        availability.IsAvailable.Should().BeTrue();
        availability.FailureCode.Should().BeEmpty();
    }

    private static ProjectSnapshot Project(string name, string gameName, string gameTypeSource, string repoPath)
    {
        return new ProjectSnapshot(
            ProjectId: "project-id",
            AccountId: "account-id",
            Name: name,
            GameName: gameName,
            GameTypeSource: gameTypeSource,
            TemplateRuleId: "godot-prototype-default",
            LlmBindingRequired: true,
            AllowedWorkflowsJson: "[\"chapter2-bootstrap\",\"prototype-7day-playable\",\"prototype-tdd\",\"prototype-scene\"]",
            BootstrapStatus: "succeeded",
            BootstrapError: null,
            WorkspaceId: "workspace-id",
            WorkspaceRootPath: repoPath,
            RepoPath: repoPath,
            RuntimePath: Path.Combine(repoPath, ".runtime"),
            MetaPath: Path.Combine(repoPath, ".phasea"));
    }

    private static void Write(string root, string relativePath, string content)
    {
        var path = Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create()
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"phasea-route-skill-{Guid.NewGuid():N}");
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
