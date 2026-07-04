using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypePhysicsRequirementPolicyTests
{
    [Fact]
    public void Evaluate_Requires3DPhysics_ForThirdPersonActionRoguelike()
    {
        var project = Project("Towerdemo", "third person action roguelike with KayKit GLTF assets");

        var result = PrototypePhysicsRequirementPolicy.Evaluate(project, "WASD movement, mouse facing, combo attacks, roll, enemy chase, collision and hitbox validation.");

        result.RequiresPhysics.Should().BeTrue();
        result.Dimension.Should().Be("3d");
        result.RecommendedEngine.Should().Be("GodotPhysics3D");
        result.NodeContract.Should().Contain("CharacterBody3D");
        result.MatchedTerms.Should().Contain(term => term.Contains("third", StringComparison.OrdinalIgnoreCase) || term.Contains("第三", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void BuildPromptBlock_DoesNotForcePhysics_WhenNoVocabularyMatches()
    {
        var project = Project("Carddemo", "visual novel");

        var prompt = PrototypePhysicsRequirementPolicy.BuildPromptBlock(project, "Dialogue choices and relationship flags.");

        prompt.Should().Contain("RequiresPhysics: false");
        prompt.Should().Contain("re-evaluate");
    }

    [Fact]
    public void Evaluate_RequiresPhysics_ForSteamActionTagVocabulary()
    {
        var project = Project("DungeonDemo", "Action RPG, Souls-like, Hack and Slash, Dungeon Crawler");

        var result = PrototypePhysicsRequirementPolicy.Evaluate(project, "Close-range combat, dodging, enemy pressure, and room traversal.");

        result.RequiresPhysics.Should().BeTrue();
        result.MatchedTerms.Should().Contain(term => term.Contains("souls", StringComparison.OrdinalIgnoreCase));
        result.MatchedTerms.Should().Contain(term => term.Contains("hack", StringComparison.OrdinalIgnoreCase));
        result.RecommendedEngine.Should().Contain("GodotPhysics");
    }

    [Fact]
    public void Evaluate_Requires2DPhysics_ForExtractionShooterVocabulary()
    {
        var project = Project("SDC", "逃离鸭科夫");

        var result = PrototypePhysicsRequirementPolicy.Evaluate(project, "俯视角搜打撤：WASD 移动、鼠标瞄准射击、搜刮箱子、敌人追击、撤离点胜利。");

        result.RequiresPhysics.Should().BeTrue();
        result.Dimension.Should().Be("2d");
        result.RecommendedEngine.Should().Be("GodotPhysics2D");
        result.NodeContract.Should().Contain("CharacterBody2D");
        result.MatchedTerms.Should().Contain(term => term.Contains("搜打撤", StringComparison.OrdinalIgnoreCase) || term.Contains("逃离鸭科夫", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void BuildPromptBlock_ForPhysicsRequired_ShouldRejectUiOnlyStateMachineCompletion()
    {
        var project = Project("SDC", "extraction shooter");

        var prompt = PrototypePhysicsRequirementPolicy.BuildPromptBlock(project, "top-down shooter with loot extraction and enemy chase.");

        prompt.Should().Contain("StateMachineGuard");
        prompt.Should().Contain("must not be completed mainly by button panels");
        prompt.Should().Contain("continuous input");
        prompt.Should().Contain("loot or interaction contact");
    }

    private static ProjectSnapshot Project(string gameName, string gameType)
    {
        var root = Path.Combine(Path.GetTempPath(), $"phase-a-physics-{Guid.NewGuid():N}");
        return new ProjectSnapshot(
            ProjectId: "project-1",
            AccountId: "account-1",
            Name: gameName,
            GameName: gameName,
            GameTypeSource: gameType,
            TemplateRuleId: "godot-prototype-default",
            LlmBindingRequired: false,
            AllowedWorkflowsJson: "[]",
            BootstrapStatus: "succeeded",
            BootstrapError: null,
            WorkspaceId: "workspace-1",
            WorkspaceRootPath: root,
            RepoPath: root,
            RuntimePath: root,
            MetaPath: Path.Combine(root, "meta"));
    }
}
