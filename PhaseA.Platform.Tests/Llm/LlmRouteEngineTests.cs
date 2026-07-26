using FluentAssertions;
using PhaseA.Platform.Llm;
using System.Text.Json;
using Xunit;

namespace PhaseA.Platform.Tests.Llm;

public sealed class LlmRouteEngineTests
{
    [Fact]
    public void HostedContextGate_ShouldRejectMissingManifestInEnforceMode()
    {
        var result = HostedContextGate.Evaluate(
            HostedContextGateMode.Enforce,
            envelope: null);

        result.Allowed.Should().BeFalse();
        result.FailureCode.Should().Be("context_manifest_required");
    }

    [Fact]
    public void HostedContextGate_ShouldKeepLegacyCompatibility()
    {
        var result = HostedContextGate.Evaluate(
            HostedContextGateMode.Legacy,
            envelope: null);

        result.Allowed.Should().BeTrue();
        result.FailureCode.Should().BeNull();
    }

    [Fact]
    public void HostedContextGate_ShouldRecordWouldBlockInObserveMode()
    {
        var result = HostedContextGate.Evaluate(HostedContextGateMode.Observe, envelope: null);

        result.Allowed.Should().BeTrue();
        result.WouldBlockFailureCode.Should().Be("context_manifest_required");
    }

    [Fact]
    public void HostedContextGatePolicy_ShouldKeepUnknownOperationInLegacyMode()
    {
        var policy = new HostedContextGatePolicy();

        policy.Resolve("llm:unregistered-operation").Should().Be(HostedContextGateMode.Legacy);
    }

    [Fact]
    public void HostedContextGatePolicy_CreateWithOverrides_ShouldPreserveDefaults()
    {
        var policy = HostedContextGatePolicy.CreateWithOverrides(new Dictionary<string, HostedContextGateMode>
        {
            ["llm:gdd-question-form"] = HostedContextGateMode.Enforce
        });

        policy.Resolve("llm:gdd-question-form").Should().Be(HostedContextGateMode.Enforce);
        policy.Resolve("llm:project-chat").Should().Be(HostedContextGateMode.Observe);
        policy.Resolve("llm:unregistered-operation").Should().Be(HostedContextGateMode.Legacy);
    }

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
                RequireJsonObject: true,
                OperationKey: "llm:draft-analysis"));

            result.Succeeded.Should().BeFalse();
            result.FailureCode.Should().Be("llm_json_parse_failed");
            result.FailureCategory.Should().Be("invalid_json");
            result.ContextGateWouldBlockCode.Should().Be("context_manifest_required");
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
            metrics.RootElement.GetProperty("contextGateWouldBlockCode").GetString().Should().Be("context_manifest_required");
        }
        finally
        {
            if (Directory.Exists(workspace))
            {
                Directory.Delete(workspace, recursive: true);
            }
        }
    }

    [Fact]
    public async Task CompleteAsync_EnforceMode_ShouldRequirePersistedManifestValidation()
    {
        var validator = new FakeManifestValidator();
        var engine = new LlmRouteEngine(
            new FakeCodexClient("accepted"),
            new HostedContextGatePolicy(new Dictionary<string, HostedContextGateMode>
            {
                ["llm:unit-enforce"] = HostedContextGateMode.Enforce
            }),
            validator);
        var workspace = Path.Combine(Path.GetTempPath(), $"phase-a-llm-route-{Guid.NewGuid():N}");
        var envelope = new HostedContextEnvelope(
            "manifest-1", "snapshot-1", "policy-1", "signature-1",
            AccountId: "account-1", ProjectId: "project-1", OperationKey: "llm:unit-enforce", Nonce: "nonce-1");

        try
        {
            var first = await engine.CompleteAsync(new LlmRouteRequest(workspace, "unit-enforce", "gpt-5.4", "Accept.", OperationKey: "llm:unit-enforce", ContextEnvelope: envelope));
            var replay = await engine.CompleteAsync(new LlmRouteRequest(workspace, "unit-enforce", "gpt-5.4", "Accept.", OperationKey: "llm:unit-enforce", ContextEnvelope: envelope));

            first.Succeeded.Should().BeTrue();
            replay.Succeeded.Should().BeFalse();
            replay.FailureCode.Should().Be("context_manifest_invalid");
            validator.Calls.Should().Be(2);
        }
        finally
        {
            if (Directory.Exists(workspace))
            {
                Directory.Delete(workspace, recursive: true);
            }
        }
    }

    [Fact]
    public async Task CompleteAsync_ConcurrentFailuresUseUniqueEvidenceNamesAndRedactPersistedOutputs()
    {
        var client = new FakeCodexClient(
            "not json Authorization: Bearer abc.def.ghi C:\\host\\private\\output.json",
            "OPENAI_API_KEY=sk-abcdefghijklmnop C:\\host\\private\\stdout.txt",
            "PHASEA_ADMIN_TOKEN=topsecret C:\\host\\private\\stderr.txt");
        var engine = new LlmRouteEngine(client);
        var workspace = Path.Combine(Path.GetTempPath(), $"phase-a-llm-route-{Guid.NewGuid():N}");

        try
        {
            var tasks = Enumerable.Range(0, 8)
                .Select(_ => engine.CompleteAsync(new LlmRouteRequest(
                    workspace,
                    "concurrent-redaction-test",
                    "gpt-5.4",
                    "Return JSON.",
                    RequireJsonObject: true)))
                .ToArray();

            var results = await Task.WhenAll(tasks);
            results.Should().OnlyContain(result => !result.Succeeded && result.FailureCode == "llm_json_parse_failed");
            var evidenceDir = Path.Combine(workspace, "logs", "phase-a-chat");
            var failures = Directory.EnumerateFiles(evidenceDir, "*.failure.json").ToArray();
            var outputs = Directory.EnumerateFiles(evidenceDir, "*.output.txt").ToArray();
            failures.Should().HaveCount(8);
            failures.Select(Path.GetFileName).Distinct(StringComparer.Ordinal).Should().HaveCount(8);
            outputs.Should().HaveCount(8);
            foreach (var path in Directory.EnumerateFiles(evidenceDir, "*.txt"))
            {
                var persisted = File.ReadAllText(path);
                persisted.Should().NotContain("abc.def.ghi");
                persisted.Should().NotContain("sk-abcdefghijklmnop");
                persisted.Should().NotContain("topsecret");
                persisted.Should().NotContain("C:\\host\\private");
            }
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
        private readonly string _stdout;
        private readonly string _stderr;

        public FakeCodexClient(string reply, string stdout = "", string stderr = "")
        {
            _reply = reply;
            _stdout = stdout;
            _stderr = stderr;
        }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new CodexChatClientResult(true, _reply, null, 0, _stdout, _stderr));
        }
    }

    private sealed class FakeManifestValidator : IHostedContextManifestValidator
    {
        private bool _consumed;

        public int Calls { get; private set; }

        public Task<bool> ValidateAndConsumeAsync(HostedContextEnvelope envelope, string operationKey, CancellationToken cancellationToken = default)
        {
            Calls++;
            var allowed = !_consumed && envelope.Nonce == "nonce-1" && operationKey == "llm:unit-enforce";
            _consumed = _consumed || allowed;
            return Task.FromResult(allowed);
        }
    }
}
