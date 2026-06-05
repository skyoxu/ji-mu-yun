using FluentAssertions;
using PhaseA.Platform.Llm;
using System.Text.Json;
using Xunit;

namespace PhaseA.Platform.Tests.Llm;

public sealed class LlmRouteEngineTests
{
    [Fact]
    public void ExtractFirstJsonObject_ShouldHandleWrappedJsonAndBracesInsideStrings()
    {
        var text = "prefix {\"message\":\"keep {this} text\",\"items\":[{\"id\":1}]} suffix";

        var json = LlmRouteEngine.ExtractFirstJsonObject(text);

        json.Should().Be("{\"message\":\"keep {this} text\",\"items\":[{\"id\":1}]}");
    }

    [Fact]
    public async Task CompleteAsync_ShouldReturnJsonParseFailure_WhenJsonIsRequiredButMissing()
    {
        var client = new FakeCodexClient("not json");
        var engine = new LlmRouteEngine(client);
        var workspace = Path.Combine(Path.GetTempPath(), $"phase-a-llm-route-{Guid.NewGuid():N}");

        try
        {
            var result = await engine.CompleteAsync(new LlmRouteRequest(
                workspace,
                "unit-test",
                "gpt-5.4",
                "Return JSON.",
                RequireJsonObject: true));

            result.Succeeded.Should().BeFalse();
            result.FailureCode.Should().Be("llm_json_parse_failed");
            result.FailureCategory.Should().Be("invalid_json");
            result.PromptLength.Should().Be("Return JSON.".Length);
            result.EstimatedPromptTokens.Should().BeGreaterThan(0);
            Directory.EnumerateFiles(Path.Combine(workspace, "logs", "phase-a-chat"), "*.failure.json")
                .Should()
                .ContainSingle();
            var metricsFiles = Directory.EnumerateFiles(Path.Combine(workspace, "logs", "phase-a-chat"), "*.metrics.json").ToArray();
            metricsFiles.Should().ContainSingle();
            var metricsPath = metricsFiles.Single();
            using var metrics = JsonDocument.Parse(File.ReadAllText(metricsPath));
            metrics.RootElement.GetProperty("failureCategory").GetString().Should().Be("invalid_json");
            metrics.RootElement.GetProperty("durationMs").GetInt64().Should().BeGreaterThanOrEqualTo(0);
            metrics.RootElement.GetProperty("estimatedPromptTokens").GetInt32().Should().BeGreaterThan(0);
        }
        finally
        {
            if (Directory.Exists(workspace))
            {
                Directory.Delete(workspace, recursive: true);
            }
        }
    }

    private sealed class FakeCodexClient : ICodexChatClient
    {
        private readonly string _reply;

        public FakeCodexClient(string reply)
        {
            _reply = reply;
        }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new CodexChatClientResult(true, _reply, null, 0, "", ""));
        }
    }
}
