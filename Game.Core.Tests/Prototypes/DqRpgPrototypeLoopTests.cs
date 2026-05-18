using Game.Core.Prototypes;
using Xunit;

namespace Game.Core.Tests.Prototypes;

public class DqRpgPrototypeLoopTests
{
    [Fact]
    public void ShouldDescribePlayableLoop_WhenPrototypeImplementationIsReady()
    {
        var loop = new DqRpgPrototypeLoop();
        var summary = loop.DescribePlayableLoop();

        Assert.False(string.IsNullOrWhiteSpace(summary));
        Assert.DoesNotContain("TODO", summary);
    }

    [Fact]
    public void ShouldReachRewardPhase_AfterWinningTheFirstEncounter()
    {
        var loop = new DqRpgPrototypeLoop();
        var state = loop.CreateInitialState();

        state = loop.MoveOnMap(state, 1, 0);
        state = loop.MoveOnMap(state, 1, 0);
        state = loop.MoveOnMap(state, 1, 0);
        state = loop.MoveOnMap(state, 0, 1);
        state = loop.ResolveAttackTurn(state);
        state = loop.ResolveAttackTurn(state);

        Assert.Equal("reward", state.Phase);
        Assert.Equal(1, state.BattlesWon);
        Assert.Equal(3, state.RewardOptions.Count);
    }

    [Fact]
    public void ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward()
    {
        var loop = new DqRpgPrototypeLoop();
        var state = loop.CreateInitialState();

        state = loop.StartEncounter(state);
        state = loop.ResolveAttackTurn(state);
        state = loop.ResolveAttackTurn(state);
        state = loop.ApplyReward(state, 0);

        Assert.Equal("map", state.Phase);
        Assert.Equal(4, state.PlayerAttack);
        Assert.Equal(1, state.BattlesWon);
        Assert.Contains("Reward chosen", state.StatusText);
    }
}
