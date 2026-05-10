using FluentAssertions;
using PhaseA.Platform.Projects;
using Xunit;

namespace PhaseA.Platform.Tests.Projects;

public sealed class ProjectRuleCatalogTests
{
    [Fact]
    public void DefaultRule_AllowsOnlyPhaseAPrototypeWorkflows()
    {
        var catalog = new ProjectRuleCatalog();

        var rule = catalog.Find(ProjectRuleCatalog.DefaultRuleId);

        rule.Should().NotBeNull();
        rule!.Id.Should().Be("godot-prototype-default");
        rule.LlmBindingRequired.Should().BeTrue();
        rule.AllowsWorkflow("chapter2-bootstrap").Should().BeTrue();
        rule.AllowsWorkflow("prototype-7day-playable").Should().BeTrue();
        rule.AllowsWorkflow("prototype-tdd").Should().BeTrue();
        rule.AllowsWorkflow("prototype-scene").Should().BeTrue();
        rule.AllowsWorkflow("chapter3").Should().BeFalse();
        rule.AllowsWorkflow("chapter4").Should().BeFalse();
        rule.AllowsWorkflow("chapter5").Should().BeFalse();
        rule.AllowsWorkflow("chapter6").Should().BeFalse();
        rule.AllowsWorkflow("chapter7").Should().BeFalse();
    }
}
