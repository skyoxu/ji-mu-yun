using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class RouteActionDescriptorsTests
{
    [Fact]
    public void Phase2_ShouldActivateOnlyIterationPlanCreation()
    {
        RouteActionDescriptors.Get("create_iteration_plan").DefaultPhaseEligibility.Should().Be("active");
        RouteActionDescriptors.Get("create_prototype").DefaultPhaseEligibility.Should().Be("not_active");
        RouteActionDescriptors.Get("execute_next_goal").DefaultPhaseEligibility.Should().Be("not_active");
        RouteActionDescriptors.Get("run_needs_fix").DefaultPhaseEligibility.Should().Be("not_active");
        RouteActionDescriptors.Get("run_ui_closure").DefaultPhaseEligibility.Should().Be("not_active");
        RouteActionDescriptors.Get("preview_package").DefaultPhaseEligibility.Should().Be("not_active");
    }

    [Theory]
    [InlineData("generate_requirement_map", "/api/projects/{projectId}/gdd/requirements-map", "/api/projects/{projectId}/gdd/requirements-map/latest")]
    [InlineData("freeze_contract", "/api/projects/{projectId}/prototype-contract/freeze", "/api/projects/{projectId}/prototype-contract/status")]
    [InlineData("refresh_contract", "/api/projects/{projectId}/prototype-contract/freeze", "/api/projects/{projectId}/prototype-contract/status")]
    public void MutationActions_ShouldDeclareRunSemanticsAndRealEndpoints(
        string actionId,
        string apiRoute,
        string readbackRoute)
    {
        var descriptor = RouteActionDescriptors.Get(actionId);

        descriptor.OperationScope.Should().Be("run");
        descriptor.DuplicateRunPolicy.Should().Be("request_identity_or_active_run_reuse");
        descriptor.ApiRouteTemplate.Should().Be(apiRoute);
        descriptor.ReadbackUrlTemplate.Should().Be(readbackRoute);
    }

    [Fact]
    public void Fixture_ShouldMatchRuntimeDescriptors()
    {
        using var document = ReadFixture("route-action-descriptors.v1.json");
        var root = document.RootElement;

        root.GetProperty("descriptorId").GetString().Should().Be(RouteActionDescriptors.DescriptorId);
        root.GetProperty("descriptorVersion").GetString().Should().Be(RouteActionDescriptors.DescriptorVersion);
        root.GetProperty("descriptorHash").GetString().Should().Be(RouteActionDescriptors.DescriptorHash);
        root.GetProperty("disabledDomainCodes").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(RouteActionDescriptors.DisabledDomainCodes);

        var fixtureActions = root.GetProperty("actions").EnumerateArray().ToArray();
        fixtureActions.Select(action => action.GetProperty("actionId").GetString())
            .Should()
            .BeEquivalentTo(RouteActionDescriptors.CanonicalActionIds);

        foreach (var runtime in RouteActionDescriptors.All)
        {
            var fixture = fixtureActions.Single(action => action.GetProperty("actionId").GetString() == runtime.ActionId);
            fixture.GetProperty("exposureClass").GetString().Should().Be(runtime.ExposureClass);
            fixture.GetProperty("defaultPhaseEligibility").GetString().Should().Be(runtime.DefaultPhaseEligibility);
            fixture.GetProperty("apiRouteTemplate").GetString().Should().Be(runtime.ApiRouteTemplate);
            fixture.GetProperty("browserActionId").GetString().Should().Be(runtime.BrowserActionId);
            fixture.GetProperty("displayLabelKey").GetString().Should().Be(runtime.DisplayLabelKey);
            fixture.GetProperty("operationScope").GetString().Should().Be(runtime.OperationScope);
            fixture.GetProperty("readbackUrlTemplate").GetString().Should().Be(runtime.ReadbackUrlTemplate);
            fixture.GetProperty("requiredPhase").GetString().Should().Be(runtime.RequiredPhase);
            fixture.GetProperty("accountBoundary").GetString().Should().Be(runtime.AccountBoundary);
            fixture.GetProperty("authBoundary").GetString().Should().Be(runtime.AuthBoundary);
            fixture.GetProperty("duplicateRunPolicy").GetString().Should().Be(runtime.DuplicateRunPolicy);
        }
    }

    [Fact]
    public void Descriptors_ShouldDeclareAccountAuthAndDuplicateRunContracts()
    {
        RouteActionDescriptors.All.Should().OnlyContain(action =>
            !string.IsNullOrWhiteSpace(action.AccountBoundary) &&
            !string.IsNullOrWhiteSpace(action.AuthBoundary) &&
            !string.IsNullOrWhiteSpace(action.DuplicateRunPolicy));
        RouteActionDescriptors.Get("analyze_game_type").AuthBoundary.Should().Be("admin_only");
    }

    [Fact]
    public void Recommendation_ShouldNotReactivateInactiveRecommendedAction()
    {
        using var fixture = RouteStateFixture.Create();
        var artifacts = fixture.Service.Read(fixture.Project);

        var recommendation = fixture.Service.BuildRecommendation(
            fixture.Project,
            artifacts,
            new ProjectWorkflowNextAction("create-prototype", "Create", "Create", "Create", "create-prototype", true));

        recommendation.AllowedActions.Should().NotContain(action => action.ActionId == "create_prototype");
        recommendation.ForbiddenActions.Should().Contain(action =>
            action.ActionId == "create_prototype" &&
            action.DisabledDomainCode == "route_contract_not_active");
    }

    [Fact]
    public void Recommendation_ShouldUseDescriptorRegistryForEveryAction()
    {
        using var fixture = RouteStateFixture.Create();
        var artifacts = fixture.Service.Read(fixture.Project);

        var recommendation = fixture.Service.BuildRecommendation(
            fixture.Project,
            artifacts,
            new ProjectWorkflowNextAction("create-prototype", "Create", "Create", "Create", "create-prototype", true));

        recommendation.ActionDescriptorRef.DescriptorHash.Should().Be(RouteActionDescriptors.DescriptorHash);
        recommendation.AllowedActions.Concat(recommendation.ForbiddenActions)
            .Select(action => action.ActionId)
            .Should()
            .BeEquivalentTo(RouteActionDescriptors.CanonicalActionIds);

        foreach (var action in recommendation.AllowedActions.Concat(recommendation.ForbiddenActions))
        {
            var descriptor = RouteActionDescriptors.Get(action.ActionId);
            action.DescriptorHash.Should().Be(RouteActionDescriptors.DescriptorHash);
            action.ExposureClass.Should().Be(descriptor.ExposureClass);
            action.ApiRoute.Should().Be(RouteActionDescriptors.ResolveTemplate(descriptor.ApiRouteTemplate, fixture.Project.ProjectId));
            action.BrowserActionId.Should().Be(descriptor.BrowserActionId);
            action.DisplayLabelKey.Should().Be(descriptor.DisplayLabelKey);
            action.OperationScope.Should().Be(descriptor.OperationScope);
            action.ReadbackUrl.Should().Be(RouteActionDescriptors.ResolveTemplate(descriptor.ReadbackUrlTemplate, fixture.Project.ProjectId));
        }
    }

    private static JsonDocument ReadFixture(string name)
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Fixtures", name);
        return JsonDocument.Parse(File.ReadAllText(path));
    }

    private sealed class RouteStateFixture : IDisposable
    {
        private readonly string _root;

        private RouteStateFixture(string root)
        {
            _root = root;
            Project = new ProjectSnapshot(
                "project-1",
                "owner-1",
                "Workflow Game",
                "Game",
                "RPG",
                "default",
                false,
                "[]",
                "succeeded",
                null,
                "workspace-1",
                root,
                Path.Combine(root, "repo"),
                Path.Combine(root, "runtime"),
                Path.Combine(root, "meta"),
                "{}");
            Directory.CreateDirectory(Project.RepoPath);
            Directory.CreateDirectory(Project.MetaPath);
            Service = new ProjectRouteStateArtifactService();
        }

        public ProjectSnapshot Project { get; }

        public ProjectRouteStateArtifactService Service { get; }

        public static RouteStateFixture Create()
        {
            var root = Path.Combine(Path.GetTempPath(), "phasea-route-action-tests", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            return new RouteStateFixture(root);
        }

        public void Dispose()
        {
            if (Directory.Exists(_root))
            {
                Directory.Delete(_root, recursive: true);
            }
        }
    }
}
