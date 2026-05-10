using FluentAssertions;
using PhaseA.Platform.Browser;
using Xunit;

namespace PhaseA.Platform.Tests.Browser;

public sealed class BrowserUiRendererTests
{
    [Fact]
    public void RenderShell_IncludesPrototypeLaneControls()
    {
        var html = new BrowserUiRenderer().RenderShell();

        html.Should().Contain("Phase A Prototype Console");
        html.Should().Contain("Admin token");
        html.Should().Contain("Create project");
        html.Should().Contain("Run Chapter 2 Bootstrap");
        html.Should().Contain("Run Prototype Route");
        html.Should().Contain("TDD Red");
        html.Should().Contain("Create Prototype Scene");
        html.Should().Contain("/api/projects");
        html.Should().Contain("prototype-7day-playable");
        html.Should().Contain("prototype-tdd");
    }
}
