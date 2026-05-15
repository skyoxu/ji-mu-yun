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
}
