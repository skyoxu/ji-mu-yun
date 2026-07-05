using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeRouteSkillPolicyTests
{
    [Fact]
    public void Resolve_ShouldUseGenericSkill_WhenGameTypeRoutingIsDisabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpgdemo26",
            gameName: "rpgdemo26",
            gameTypeSource: "勇者斗恶龙",
            repoPath: Path.GetTempPath());

        var context = PrototypeRouteSkillPolicy.Resolve(project);
        var prompt = PrototypeRouteSkillPolicy.BuildPromptBlock(project);

        context.RouteSkillId.Should().Be("prototype-7day-playable-godot-zh");
        context.SkillRelativePath.Should().Be(".agents/skills/prototype-7day-playable-godot-zh/SKILL.md");
        context.ContractRelativePath.Should().BeNull();
        prompt.Should().Contain("Downstream source boundary");
        prompt.Should().Contain("only the GDD route may read broad game-type sources");
        prompt.Should().Contain("do not read docs/game-type-guides");
        prompt.Should().NotContain("MandatorySkillEntry");
        prompt.Should().NotContain("MandatorySkillPath");
        prompt.Should().NotContain("RouteSkillContract");
        prompt.Should().Contain("GameTypeId: default");
        prompt.Should().Contain("ProfileId: godot-playable-default-v1");
        prompt.Should().Contain("RouteSetId: default-prototype-routes-v1");
        prompt.Should().Contain("PromptProtocolId: default-prompt-protocol-v1");
        prompt.Should().Contain("ILlmRouteEngine");
        prompt.Should().Contain("CodexHostedProcessCommandFactory");
        prompt.Should().Contain("do not use AGENTS.md as hosted project memory");
        prompt.Should().Contain("Player-visible text rule");
        prompt.Should().Contain("must default to Chinese");
        prompt.Should().Contain("Do not rename platform-validated fixed nodes");
    }

    [Fact]
    public void ResolveProfile_ShouldExposeRpgRouteProtocol_ForRpgProject()
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
    public void ResolveProfile_ShouldExposeSurvivorsLikeRouteProtocol_ForSurvivorsLikeProject()
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
        prompt.Should().Contain("Downstream source boundary");
        prompt.Should().Contain("do not read docs/game-type-guides");
        prompt.Should().NotContain("MandatorySkillEntry");
        prompt.Should().Contain("GameTypeId: survivorslike");
        prompt.Should().Contain("Player-visible text rule");
    }

    [Fact]
    public void ResolveProfile_ShouldExposeDeckbuilderRouteProtocol_ForDeckbuilderProject()
    {
        var project = Project(
            name: "deck-demo",
            gameName: "Deck Demo",
            gameTypeSource: "Roguelike Deckbuilder",
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var prompt = PrototypeRouteSkillPolicy.BuildPromptBlock(project);

        profile.GameTypeId.Should().Be("deckbuilder");
        profile.ProfileId.Should().Be("godot-deckbuilder-v1");
        profile.RouteSetId.Should().Be("deckbuilder-prototype-routes-v1");
        profile.PlannerId.Should().Be("deckbuilder-iteration-planner-v1");
        profile.EvaluatorId.Should().Be("deckbuilder-plan-evaluator-v1");
        profile.ExecutorId.Should().Be("deckbuilder-goal-executor-v1");
        profile.NeedsFixId.Should().Be("deckbuilder-needs-fix-v1");
        profile.FinalAcceptanceId.Should().Be("deckbuilder-final-acceptance-v1");
        profile.RouteSkill.RouteSkillId.Should().Be("prototype-deckbuilder-godot-zh");
        profile.RouteSkill.ContractRelativePath.Should().Be(".agents/skills/prototype-deckbuilder-godot-zh/references/deckbuilder-prototype-contract.md");
        prompt.Should().Contain("Downstream source boundary");
        prompt.Should().Contain("do not read docs/game-type-guides");
        prompt.Should().NotContain("MandatorySkillEntry");
        prompt.Should().Contain("GameTypeId: deckbuilder");
        prompt.Should().Contain("Player-visible text rule");
    }

    [Theory]
    [InlineData("deckbuilder")]
    [InlineData("deckbuilding")]
    [InlineData("deck-building")]
    [InlineData("deck-building roguelike")]
    [InlineData("card battler")]
    [InlineData("card roguelike")]
    [InlineData("Slay the Spire")]
    [InlineData("Monster Train")]
    [InlineData("Inscryption")]
    [InlineData("Balatro")]
    [InlineData("Wildfrost")]
    [InlineData("Griftlands")]
    [InlineData("Across the Obelisk")]
    [InlineData("Vault of the Void")]
    [InlineData("Roguebook")]
    [InlineData("Cobalt Core")]
    [InlineData("Dicey Dungeons")]
    [InlineData("\u5361\u724c\u6784\u7b51")]
    [InlineData("\u724c\u7ec4\u6784\u5efa\u5f0f\u7c7bRogue")]
    [InlineData("\u8089\u9e3d\u5361\u724c")]
    [InlineData("\u5361\u724c\u8089\u9e3d")]
    [InlineData("\u6740\u622e\u5c16\u5854")]
    [InlineData("\u602a\u7269\u706b\u8f66")]
    [InlineData("\u90aa\u6076\u51a5\u523b")]
    [InlineData("\u5c0f\u4e11\u724c")]
    [InlineData("\u6708\u5706\u4e4b\u591c")]
    public void ResolveProfile_ShouldUseDeckbuilderRoute_ForDeckbuilderAliases(string gameTypeSource)
    {
        var project = Project(
            name: "deck-demo",
            gameName: "Deck Demo",
            gameTypeSource: gameTypeSource,
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);

        profile.GameTypeId.Should().Be("deckbuilder");
    }

    [Fact]
    public void ResolveProfile_ShouldNotTreatGenericCardGameAsDeckbuilder()
    {
        var project = Project(
            name: "card-demo",
            gameName: "Card Demo",
            gameTypeSource: "card-game",
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);

        profile.GameTypeId.Should().Be("default");
    }

    [Theory]
    [InlineData("Trading Card Game")]
    [InlineData("Collectible Card Game")]
    [InlineData("TCG")]
    [InlineData("CCG")]
    [InlineData("Hearthstone-like card duel")]
    [InlineData("\u96c6\u6362\u5f0f\u5361\u724c")]
    [InlineData("\u6536\u85cf\u5f0f\u5361\u724c")]
    [InlineData("\u5361\u724c\u5bf9\u6218")]
    public void ResolveProfile_ShouldNotTreatNonDeckbuildingCardGamesAsDeckbuilder(string gameTypeSource)
    {
        var project = Project(
            name: "card-duel-demo",
            gameName: "Card Duel Demo",
            gameTypeSource: gameTypeSource,
            repoPath: Path.GetTempPath());

        var profile = PrototypeRouteSkillPolicy.ResolveProfile(project);

        profile.GameTypeId.Should().Be("default");
    }

    [Fact]
    public void ResolveProfile_ShouldPreferSurvivorsLikeRoute_WhenProjectNameContainsRpgAndSurvivorsLike()
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
    public void ResolveProfile_ShouldUseSurvivorsLikeRoute_ForSurvivorsLikeAliases(string gameTypeSource)
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
        Write(temp.Path, ".agents/skills/prototype-survivorslike-godot-zh/references/survivorslike-prototype-contract.md", "# Contract\n");
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
    public void CheckAvailable_ShouldPass_WhenDeckbuilderSkillAndContractExist()
    {
        using var temp = TempDirectory.Create();
        Write(temp.Path, ".agents/skills/prototype-deckbuilder-godot-zh/SKILL.md", "name: prototype-deckbuilder-godot-zh\n");
        Write(temp.Path, ".agents/skills/prototype-deckbuilder-godot-zh/references/deckbuilder-prototype-contract.md", "# Contract\n");
        var project = Project(
            name: "deck-demo",
            gameName: "Deck Demo",
            gameTypeSource: "\u5361\u724c\u6784\u7b51",
            repoPath: temp.Path);

        var availability = PrototypeRouteSkillPolicy.CheckAvailable(project);

        availability.IsAvailable.Should().BeTrue();
        availability.FailureCode.Should().BeEmpty();
    }

    [Fact]
    public void EnsureAvailable_ShouldSeedSurvivorsLikeSkillFromHostRepository_ForSurvivorsLikeProject()
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
    public void GoalAcceptancePromptBuilder_ShouldNotExposeSurvivorsLikeHardAcceptance_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
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

        prompt.Should().NotContain("Platform hard acceptance for Vampire Survivors-like core weapon");
        prompt.Should().NotContain("STATUS: needs_fix");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldNotExposeDeckbuilderHardAcceptance_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "deck-demo",
            gameName: "Deck Demo",
            gameTypeSource: "Roguelike Deckbuilder",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "Deckbuilder First Loop: card play resolution feedback",
            "Validate playing at least one readable card.",
            "Pass only when card play produces immediate feedback.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var prompt = PrototypeGoalAcceptancePromptBuilder.Build(project, goal);

        prompt.Should().NotContain("Platform hard acceptance for deckbuilder card play resolution");
        prompt.Should().NotContain("STATUS: needs_fix");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldNotExposeRpgSceneSwitchingAcceptance_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
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

        prompt.Should().NotContain("Platform hard acceptance for RPG scene switching");
        prompt.Should().NotContain("Platform hard acceptance for RPG Step 4");
        prompt.Should().NotContain("ShowRewardScene");
        prompt.Should().NotContain("RewardOptions.Count");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldNotExposeJrpgFieldNavigationAcceptance_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
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

        prompt.Should().NotContain("Platform hard acceptance for JRPG field navigation");
        prompt.Should().NotContain("Add RpgEnemyAsset only when");
        prompt.Should().NotContain("RpgPlayerAsset, RpgEnemyAsset nodes");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldNotExposeRpgRewardPrompt_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
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

        prompt.Should().NotContain("Platform hard acceptance for RPG Step 4");
        prompt.Should().NotContain("RewardOptions.Count");
    }

    [Fact]
    public void GoalAcceptancePromptBuilder_ShouldExposeDefaultRpgHardAcceptance_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpgdemo",
            gameName: "rpgdemo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            2,
            "Goal 2: map movement and objective clarity",
            "Start Adventure opens a visible map and stable movement.",
            "Pass when map entry and movement evidence are visible.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var prompt = PrototypeGoalAcceptancePromptBuilder.Build(project, goal);

        prompt.Should().Contain("Platform hard acceptance for default RPG map movement");
        prompt.Should().Contain("Start Adventure or the project entry must open a visible playable map");
        prompt.Should().NotContain("Platform hard acceptance for JRPG field navigation");
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
    public void GodotSmokePolicy_ShouldValidateDeckbuilderFirstLoopGoals()
    {
        var project = Project(
            name: "deck-demo",
            gameName: "Deck Demo",
            gameTypeSource: "Roguelike Deckbuilder",
            repoPath: Path.GetTempPath());
        var finalGoal = Goal(10, "Deckbuilder First Loop: final deckbuilder first-loop acceptance");
        var routeGoal = Goal(11, "Deckbuilder First Loop: final deckbuilder first-loop acceptance");
        var earlyGoal = Goal(1, "Deckbuilder First Loop: run context and objective");

        PrototypeGodotSmokeService.ShouldValidateGoal(project, finalGoal).Should().BeTrue();
        PrototypeGodotSmokeService.ShouldValidateGoal(project, routeGoal).Should().BeTrue();
        PrototypeGodotSmokeService.ShouldValidateGoal(project, earlyGoal).Should().BeTrue();
    }

    [Fact]
    public void GodotSmokePolicy_ShouldValidateDefaultNonSpecializedGoals()
    {
        var project = Project(
            name: "action-demo",
            gameName: "Action Demo",
            gameTypeSource: "Action",
            repoPath: Path.GetTempPath());
        var goal = Goal(10, "最终任务：完整可玩原型验收");

        PrototypeGodotSmokeService.ShouldValidateGoal(project, goal).Should().BeTrue();
    }

    [Fact]
    public void RouteStrategy_ShouldUseDefaultRpgFinalAcceptanceContract_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
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
        contract!.Kind.Should().Be("default-rpg-final-first-loop-acceptance");
        contract.MainSceneHostUiHiddenAcceptance.Should().BeTrue();
    }

    [Fact]
    public void RouteStrategy_ShouldNotUseRpgAssetUsageContract_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
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

        contract.Should().BeNull();
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
    public void DefaultRouteStrategy_ShouldRequireMovementMarker_ForRpgMapMovementFallback()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            1,
            "Goal 1: stabilize map movement",
            "Start Adventure opens a visible map and stable movement.",
            "Pass when the map is visible and movement is stable.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-map-movement-entry");
        contract.RequiredMarkers.Should().Contain("MoveOnMap");
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldRequireBattleAcceptance_ForRpgBattleChallengeFallback()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "Module 5: battle or challenge resolution with movement readability",
            "Resolve the first challenge and keep movement feedback readable during the battle.",
            "Pass when battle or challenge resolution settles victory or failure.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-battle-or-challenge-resolution");
        contract.BattleSceneAcceptance.Should().BeTrue();
        contract.RequiredMarkers.Should().Contain("ResolveAttackTurn");
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldPreferBattleFallback_WhenGoalAlsoMentionsObjective()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "Module 5: battle or challenge resolution objective",
            "Resolve the first battle and keep the player objective readable.",
            "Pass when battle or challenge resolution settles victory or failure.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-battle-or-challenge-resolution");
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldPreferBattleChallengeFallback_WhenGoalAlsoMentionsMovement()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "Module 5: battle or challenge resolution with map movement readability",
            "Resolve the first battle and keep stable movement feedback readable.",
            "Pass when battle or challenge resolution settles victory or failure.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-battle-or-challenge-resolution");
        contract.MapEntryAcceptance.Should().BeFalse();
        contract.BattleSceneAcceptance.Should().BeTrue();
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldPreferRpgMapMovementFallback_WhenLoopTextAlsoAppears()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            1,
            "Goal 1: first loop stable movement",
            "Start Adventure opens a visible map, then the first loop continues with stable movement.",
            "Pass when the map is visible and movement is stable.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-map-movement-entry");
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldRequireMainSceneHostAcceptance_ForRpgFinalFallback()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            6,
            "JRPG First Loop: final first-loop acceptance",
            "Validate final acceptance for the playable first loop.",
            "Pass when final first-loop acceptance is ready.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-final-first-loop-acceptance");
        contract.MainSceneHostUiHiddenAcceptance.Should().BeTrue();
        contract.MapEntryAcceptance.Should().BeTrue();
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldUseFullFinalContract_WhenRpgFinalMentionsBattleAndReward()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            6,
            "JRPG First Loop: final first-loop acceptance",
            "Validate the full playable final acceptance with battle settlement and reward choice.",
            "Pass when final first-loop acceptance covers map, battle, reward, assets, and host UI.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-final-first-loop-acceptance");
        contract.FinalAcceptance.Should().BeTrue();
        contract.AssetUsageAcceptance.Should().BeTrue();
        contract.MapEntryAcceptance.Should().BeTrue();
        contract.BattleSceneAcceptance.Should().BeTrue();
        contract.RewardFlowAcceptance.Should().BeTrue();
        contract.MainSceneHostUiHiddenAcceptance.Should().BeTrue();
        contract.RequiredMarkers.Should().Contain("MoveOnMap");
        contract.RequiredMarkers.Should().Contain("ResolveAttackTurn");
        contract.RequiredMarkers.Should().Contain("RewardOptions.Count");
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldPreferFinalFallback_WhenGoalAlsoMentionsObjective()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            6,
            "JRPG First Loop: final first-loop acceptance with objective",
            "Validate final acceptance while preserving the current player objective.",
            "Pass when final first-loop acceptance covers map, battle, reward, assets, and host UI.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-rpg-final-first-loop-acceptance");
        contract.FinalAcceptance.Should().BeTrue();
    }

    [Fact]
    public void RpgRouteStrategy_ShouldPreferBattleResolution_WhenChallengeGoalMentionsMovement()
    {
        using var routeProfile = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(false);
        var project = Project(
            name: "rpg-demo",
            gameName: "RPG Demo",
            gameTypeSource: "RPG",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "Module 5: battle or challenge resolution with movement readability",
            "Resolve the first challenge and keep movement feedback readable during the battle.",
            "Pass when battle or challenge resolution settles victory or failure.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("jrpg-battle-or-challenge-resolution");
        contract.MapEntryAcceptance.Should().BeFalse();
    }

    [Fact]
    public void DefaultRouteStrategy_ShouldResolveProductionFeedbackContract_ForGenericCraftingGoal()
    {
        var project = Project(
            name: "shop-demo",
            gameName: "Shop Demo",
            gameTypeSource: "Simulation",
            repoPath: Path.GetTempPath());
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            2,
            "Goal 2: production feedback",
            "\u8865\u901a\u5236\u4f5c\u53cd\u9988\uff0c\u8ba9\u73a9\u5bb6\u770b\u5230\u5236\u4f5c\u540e\u7684\u72b6\u6001\u53d8\u5316\u3002",
            "\u73a9\u5bb6\u70b9\u51fb\u5236\u4f5c\u540e\u80fd\u770b\u5230\u7ed3\u679c\u53cd\u9988\uff0c\u5e76\u53ef\u4ee5\u7ee7\u7eed\u5faa\u73af\u3002",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);

        contract.Should().NotBeNull();
        contract!.Kind.Should().Be("default-production-feedback");
        contract.StaticAcceptanceOnly.Should().BeTrue();
        contract.RequiredMarkers.Should().Contain(marker => marker.Contains("Craft", StringComparison.Ordinal));
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
        Write(temp.Path, ".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md", "# Contract\n");
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
    public void MutationGuard_ShouldNotRunSpecializedGuard_WhenGenericRoutingIsEnabled()
    {
        using var genericMode = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
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

        result.Status.Should().Be("not_required");
        result.Reason.Should().Be("not_specialized_prototype_project");
        result.AllowsProgress.Should().BeTrue();
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
            MetaPath: Path.Combine(repoPath, ".phasea"),
            GameTypeMatchJson: BuildGameTypeMatchJson(name, gameName, gameTypeSource));
    }

    private static string BuildGameTypeMatchJson(string name, string gameName, string gameTypeSource)
    {
        var text = string.Join(" ", name, gameName, gameTypeSource).ToLowerInvariant();
        string matched;
        string[] tags;
        if (ContainsAny(text, "survivors", "survivor", "vampire", "arena survival", "horde survival", "\u5e78\u5b58\u8005", "\u5272\u8349"))
        {
            matched = "survivorslike";
            tags = ["survivorslike", "vampire-survivors", "bullet-heaven", "arena-survival"];
        }
        else if (ContainsAny(text, "ccg", "tcg", "collectible", "trading card", "hearthstone", "duel", "card game", "\u96c6\u6362", "\u6536\u85cf", "\u5361\u724c\u5bf9\u6218"))
        {
            matched = "card-game";
            tags = ["card", "card-game"];
        }
        else if (ContainsAny(text, "deck", "card battler", "card roguelike", "slay the spire", "monster train", "inscryption", "balatro", "wildfrost", "griftlands", "obelisk", "roguebook", "cobalt core", "dicey dungeons", "night of full moon", "\u5361\u724c\u6784\u7b51", "\u5361\u724c\u6784\u5efa", "\u8089\u9e3d\u5361\u724c", "\u5361\u724c\u8089\u9e3d", "\u6740\u622e\u5c16\u5854", "\u602a\u7269\u706b\u8f66", "\u5c0f\u4e11\u724c", "\u6708\u5706\u4e4b\u591c", "\u90aa\u6076\u51a5\u523b"))
        {
            matched = "card-game";
            tags = ["card", "deck-building", "deckbuilder", "roguelike"];
        }
        else if (ContainsAny(text, "rpg", "dragon quest", "\u89d2\u8272\u626e\u6f14", "\u52c7\u8005\u6597\u6076\u9f99"))
        {
            matched = "rpg";
            tags = ["rpg", "role-playing", "jrpg"];
        }
        else
        {
            matched = "";
            tags = [];
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        return new ProjectGameTypeMatchEvidence(
            1,
            string.IsNullOrWhiteSpace(matched) ? "no_match" : "matched",
            string.IsNullOrWhiteSpace(matched) ? "test_no_match" : "matched_by_test_genre_tags",
            "steam",
            gameTypeSource,
            "1",
            "Test App",
            tags,
            [],
            tags,
            tags,
            matched,
            string.IsNullOrWhiteSpace(matched) ? "" : $"docs/game-type-guides/{matched}.md",
            string.IsNullOrWhiteSpace(matched) ? 0 : 20,
            [],
            "",
            "test",
            now,
            now).ToJson();
    }

    private static bool ContainsAny(string text, params string[] needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.Ordinal));
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
