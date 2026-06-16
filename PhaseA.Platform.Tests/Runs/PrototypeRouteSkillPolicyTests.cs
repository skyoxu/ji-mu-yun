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
        prompt.Should().Contain("GameTypeId: rpg");
        prompt.Should().Contain("ProfileId: godot-rpg-v1");
        prompt.Should().Contain("RouteSetId: rpg-prototype-routes-v1");
        prompt.Should().Contain("PromptProtocolId: rpg-prompt-protocol-v1");
        prompt.Should().Contain("ILlmRouteEngine");
        prompt.Should().Contain("CodexHostedProcessCommandFactory");
        prompt.Should().Contain("do not run a bare/generic prototype route");
        prompt.Should().Contain("do not use AGENTS.md as hosted project memory");
        prompt.Should().Contain("Player-visible text rule");
        prompt.Should().Contain("must default to Chinese");
        prompt.Should().Contain("Do not rename platform-validated fixed nodes");
    }

    [Fact]
    public void ResolveProfile_ShouldExposeRpgRouteProtocol()
    {
        var project = Project(
            name: "rpgdemo26",
            gameName: "rpgdemo26",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);

        profile.GameTypeId.Should().Be("rpg");
        profile.ProfileId.Should().Be("godot-rpg-v1");
        profile.RouteSetId.Should().Be("rpg-prototype-routes-v1");
        profile.PlannerId.Should().Be("rpg-iteration-planner-v1");
        profile.EvaluatorId.Should().Be("rpg-plan-evaluator-v1");
        profile.ExecutorId.Should().Be("rpg-goal-executor-v1");
        profile.NeedsFixId.Should().Be("rpg-needs-fix-v1");
        profile.FinalAcceptanceId.Should().Be("rpg-final-acceptance-v1");
    }

    [Fact]
    public void ResolveProfile_ShouldExposeSurvivorsLikeRouteProtocol()
    {
        var project = Project(
            name: "vampire-demo",
            gameName: "Vampire Demo",
            gameTypeSource: "Vampire Survivors-like",
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var prompt = PrototypeRouteSkillPolicy.BuildPromptBlock(project);

        profile.GameTypeId.Should().Be("survivorslike");
        profile.ProfileId.Should().Be("godot-survivorslike-v1");
        profile.RouteSetId.Should().Be("survivorslike-prototype-routes-v1");
        profile.PlannerId.Should().Be("survivorslike-iteration-planner-v1");
        profile.EvaluatorId.Should().Be("survivorslike-plan-evaluator-v1");
        profile.ExecutorId.Should().Be("survivorslike-goal-executor-v1");
        profile.NeedsFixId.Should().Be("survivorslike-needs-fix-v1");
        profile.FinalAcceptanceId.Should().Be("survivorslike-final-acceptance-v1");
        profile.RouteSkill.RouteSkillId.Should().Be("prototype-survivorslike-godot-zh");
        profile.RouteSkill.ContractRelativePath.Should().Be(".agents/skills/prototype-survivorslike-godot-zh/references/survivorslike-prototype-contract.md");
        prompt.Should().Contain("MandatorySkillEntry: $prototype-survivorslike-godot-zh");
        prompt.Should().Contain("GameTypeId: survivorslike");
        prompt.Should().Contain("Player-visible text rule");
    }

    [Fact]
    public void ResolveProfile_ShouldPreferSurvivorsLike_WhenProjectNameContainsRpg()
    {
        var project = Project(
            name: "rpg-survivors-demo",
            gameName: "RPG Survivors Demo",
            gameTypeSource: "Vampire Survivors-like",
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);

        profile.GameTypeId.Should().Be("survivorslike");
    }

    [Theory]
    [InlineData("survivor like")]
    [InlineData("survivors like")]
    [InlineData("Arena Survival")]
    [InlineData("Horde Survival")]
    [InlineData("\u5e78\u5b58\u8005\u7c7b")]
    public void ResolveProfile_ShouldRecognizeSurvivorsLikeAliases(string gameTypeSource)
    {
        var project = Project(
            name: "arena-demo",
            gameName: "Arena Demo",
            gameTypeSource: gameTypeSource,
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);

        profile.GameTypeId.Should().Be("survivorslike");
    }

    [Fact]
    public void CheckAvailable_ShouldPass_WhenSurvivorsLikeSkillAndContractExist()
    {
        using var temp = TempDirectory.Create();
        Write(temp.Path, ".agents/skills/prototype-survivorslike-godot-zh/SKILL.md", "name: prototype-survivorslike-godot-zh\n");
        Write(temp.Path, ".agents/skills/prototype-survivorslike-godot-zh/references/survivorslike-prototype-contract.md", "# Survivors-like Prototype Contract\n");
        var project = Project(
            name: "vampire-demo",
            gameName: "Vampire Demo",
            gameTypeSource: "Bullet Heaven",
            repoPath: temp.Path);

        var availability = PrototypeRouteSkillPolicy.CheckAvailable(project);

        availability.IsAvailable.Should().BeTrue();
        availability.FailureCode.Should().BeEmpty();
    }

    [Fact]
    public void EnsureAvailable_ShouldSeedSurvivorsLikeSkillFromHostRepository()
    {
        using var temp = TempDirectory.Create();
        var project = Project(
            name: "vampire-demo",
            gameName: "Vampire Demo",
            gameTypeSource: "Vampire Survivors-like",
            repoPath: temp.Path);

        var availability = PrototypeRouteSkillPolicy.EnsureAvailable(project);

        availability.IsAvailable.Should().BeTrue();
        File.Exists(Path.Combine(temp.Path, ".agents", "skills", "prototype-survivorslike-godot-zh", "SKILL.md")).Should().BeTrue();
        File.Exists(Path.Combine(temp.Path, ".agents", "skills", "prototype-survivorslike-godot-zh", "references", "survivorslike-prototype-contract.md")).Should().BeTrue();
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldExposeSurvivorsLikeHardAcceptance()
    {
        var project = Project(
            name: "vampire-demo",
            gameName: "Vampire Demo",
            gameTypeSource: "Vampire Survivors-like",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "Vampire Survivors-like First Loop: auto-attack or core weapon loop",
            "Validate repeated core weapon behavior.",
            "Pass only when the core weapon repeatedly attacks and hits spawned enemies.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var prompt = PrototypeGoalAcceptancePromptBuilder.Build(project, goal);

        prompt.Should().Contain("Platform hard acceptance for Vampire Survivors-like core weapon");
        prompt.Should().Contain("auto-attack");
        prompt.Should().Contain("STATUS: needs_fix");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldUseContractKindInsteadOfGoalIndex_ForRpgSceneSwitching()
    {
        var project = Project(
            name: "rpgdemo",
            gameName: "rpgdemo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "Repair RPG scene switching for town route",
            "Validate main prototype scene switching for a town route.",
            "Scene switching passes for selected map and continuation flow.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var prompt = PrototypeGoalAcceptancePromptBuilder.Build(project, goal);

        prompt.Should().Contain("Platform hard acceptance for RPG scene switching");
        prompt.Should().NotContain("Platform hard acceptance for RPG Step 4");
        prompt.Should().NotContain("ShowRewardScene");
        prompt.Should().NotContain("RewardOptions.Count");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldConditionEnemyAsset_ForJrpgFieldNavigation()
    {
        var project = Project(
            name: "rpgdemo",
            gameName: "rpgdemo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            2,
            "JRPG First Loop: field navigation and stable control",
            "Validate Start Adventure to visible town map and stable movement.",
            "Pass when the town map opens and movement is stable.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var prompt = PrototypeGoalAcceptancePromptBuilder.Build(project, goal);

        prompt.Should().Contain("Platform hard acceptance for JRPG field navigation");
        prompt.Should().Contain("Add RpgEnemyAsset only when");
        prompt.Should().NotContain("RpgPlayerAsset, RpgEnemyAsset nodes");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldKeepRewardPrompt_ForRewardContractKind()
    {
        var project = Project(
            name: "rpgdemo",
            gameName: "rpgdemo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "RPG Step 4: reward 3-choice understandability validation",
            "Validate reward choices.",
            "Reward choice proof passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var prompt = PrototypeGoalAcceptancePromptBuilder.Build(project, goal);

        prompt.Should().Contain("Platform hard acceptance for RPG Step 4");
        prompt.Should().Contain("RewardOptions.Count");
    }

    [Fact]
    public void GodotSmokePolicy_ShouldValidateSurvivorsLikeFirstLoopGoals()
    {
        var project = Project(
            name: "vampire-demo",
            gameName: "Vampire Demo",
            gameTypeSource: "Vampire Survivors-like",
            repoPath: Path.GetTempPath());
        var finalGoal = Goal(10, "Vampire Survivors-like First Loop: run end, summary, and restart loop");
        var earlyGoal = Goal(1, "Vampire Survivors-like First Loop: run start and survival objective");

        PrototypeGodotSmokeService.ShouldValidateGoal(project, finalGoal).Should().BeTrue();
        PrototypeGodotSmokeService.ShouldValidateGoal(project, earlyGoal).Should().BeTrue();
    }

    [Fact]
    public void GodotSmokePolicy_ShouldNotValidateDefaultNonSpecializedGoals()
    {
        var project = Project(
            name: "action-demo",
            gameName: "Action Demo",
            gameTypeSource: "Action",
            repoPath: Path.GetTempPath());
        var goal = Goal(10, "Final Step: full playable prototype acceptance");

        PrototypeGodotSmokeService.ShouldValidateGoal(project, goal).Should().BeFalse();
    }

    [Fact]
    public void RpgRouteStrategy_ShouldTreatFinalGdUnitRepairGoalAsFinalAcceptance()
    {
        var project = Project(
            name: "rpgdemo",
            gameName: "rpgdemo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "Rerun RPG project-specific GdUnit and final prototype acceptance",
            "Run final RPG validation against the same blocker that generated this repair plan.",
            "Final RPG GdUnit and prototype acceptance pass.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("rpg-final-full-playable-acceptance");
        contract.FinalAcceptance.Should().BeTrue();
    }

    [Fact]
    public void RpgRouteStrategy_ShouldNotTreatAssetImportGdUnitRepairGoalAsFinalAcceptance()
    {
        var project = Project(
            name: "rpgdemo",
            gameName: "rpgdemo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            1,
            "Repair RPG runtime assets and Godot imports for GdUnit",
            "Fix missing PNG or imported resources before project-specific GdUnit can load the scene.",
            "This step passes only when active dq-rpg scenes no longer reference missing PNG or .ctex resources.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("rpg-asset-usage-validation");
        contract.FinalAcceptance.Should().BeFalse();
    }

    [Fact]
    public void ResolveProfile_ShouldExposeDefaultRouteProtocol_ForNonRpgProject()
    {
        var project = Project(
            name: "action-demo",
            gameName: "Action Demo",
            gameTypeSource: "Action",
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var prompt = PrototypeRouteSkillPolicy.BuildPromptBlock(project);

        profile.GameTypeId.Should().Be("default");
        profile.RouteSkill.RouteSkillId.Should().Be("prototype-7day-playable-godot-zh");
        profile.RouteSetId.Should().Be("default-prototype-routes-v1");
        profile.RouteSkill.ContractRelativePath.Should().BeNull();
        prompt.Should().Contain("Player-visible text rule");
        prompt.Should().Contain("must default to Chinese");
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

    [Fact]
    public void MutationGuard_ShouldBlockTestFrameworkShadowing_ForSurvivorsLikeProject()
    {
        using var temp = TempDirectory.Create();
        var testsRoot = Path.Combine(temp.Path, "Game.Core.Tests", "Prototypes");
        Directory.CreateDirectory(testsRoot);
        File.WriteAllText(Path.Combine(testsRoot, "SurvivorsLikePrototypeLoopTests.cs"), """
namespace Xunit
{
    public sealed class FactAttribute : System.Attribute { }
    public static class Assert { }
}
""");
        var project = Project(
            name: "arena-demo",
            gameName: "Arena Demo",
            gameTypeSource: "survivors like",
            repoPath: temp.Path);

        var result = PrototypeRepairMutationGuard.Validate(project, Goal(1, "Vampire Survivors-like First Loop: run start and survival objective"));

        result.Status.Should().Be("failed");
        result.Reason.Should().Be("test_framework_shadowing_detected");
        result.Violations.Should().Contain(violation => violation.Rule == "namespace_xunit");
        result.Violations.Should().Contain(violation => violation.Rule == "xunit_assert_shadow");
    }

    [Fact]
    public void MutationGuard_ShouldAllowProgress_WhenNotRequiredForDefaultProject()
    {
        var project = Project(
            name: "action-demo",
            gameName: "Action Demo",
            gameTypeSource: "Action",
            repoPath: Path.GetTempPath());

        var result = PrototypeRepairMutationGuard.Validate(project, Goal(1, "Restore prototype route evidence"));

        result.Status.Should().Be("not_required");
        result.AllowsProgress.Should().BeTrue();
        result.Passed.Should().BeFalse();
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

    private static ProjectIterationGoalSnapshot Goal(int index, string title)
    {
        return new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            index,
            title,
            "Description",
            "Acceptance",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
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
