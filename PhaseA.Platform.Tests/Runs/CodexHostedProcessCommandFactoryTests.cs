using FluentAssertions;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class CodexHostedProcessCommandFactoryTests
{
    [Fact]
    public void Build_ShouldRejectMissingManifestWhenServerPolicyEnforcesContext()
    {
        var policy = new HostedContextGatePolicy(new Dictionary<string, HostedContextGateMode>
        {
            ["test-enforce"] = HostedContextGateMode.Enforce
        });

        var action = () => CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            @"C:\repo",
            @"C:\repo\logs\codex-output.txt",
            "prompt body",
            "gpt-5.4",
            "low",
            OperationKey: "test-enforce"), policy);

        action.Should().Throw<InvalidOperationException>().WithMessage("context_manifest_required");
    }

    [Fact]
    public void Build_ShouldCreateWorkspaceWriteCommandWithStdinPrompt()
    {
        var command = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            @"C:\repo",
            @"C:\repo\logs\codex-output.txt",
            "prompt body",
            "gpt-5.4",
            "low"));

        command.Arguments.Should().ContainInOrder([
            "exec",
            "--json",
            "--sandbox",
            "workspace-write",
            "-m",
            "gpt-5.4",
            "-c",
            "approval_policy=\"never\"",
            "-c",
            "model_reasoning_effort=\"low\"",
            "--cd",
            @"C:\repo",
            "-o",
            @"C:\repo\logs\codex-output.txt",
            "-"
        ]);
        command.StandardInput.Should().Be("prompt body");
        command.Environment["PHASEA_CODEX_DEFAULT_MODEL"].Should().Be("gpt-5.4");
        command.Environment["PHASEA_CODEX_REASONING_EFFORT"].Should().Be("low");
    }

    [Fact]
    public async Task BuildAsync_ShouldValidateAndConsumeManifestBeforeReturningCommand_WhenServerPolicyEnforcesContext()
    {
        var policy = new HostedContextGatePolicy(new Dictionary<string, HostedContextGateMode>
        {
            ["test-enforce"] = HostedContextGateMode.Enforce
        });
        var validator = new CapturingManifestValidator();
        var envelope = new HostedContextEnvelope("manifest-1", "snapshot-1", "policy-1", "signature-1", Nonce: "nonce-1");

        var command = await CodexHostedProcessCommandFactory.BuildAsync(
            new CodexHostedProcessRequest(
                @"C:\repo",
                @"C:\repo\logs\codex-output.txt",
                "prompt body",
                "gpt-5.4",
                "low",
                OperationKey: "test-enforce",
                ContextEnvelope: envelope),
            policy,
            validator);

        command.StandardInput.Should().Be("prompt body");
        validator.Envelope.Should().Be(envelope);
        validator.OperationKey.Should().Be("test-enforce");
    }

    [Fact]
    public void Build_ShouldCreateReadOnlyCommand_WhenRequested()
    {
        var command = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            @"C:\repo",
            @"C:\repo\logs\codex-output.txt",
            "prompt body",
            "gpt-5.4",
            "high",
            Sandbox: "read-only"));

        command.Arguments.Should().ContainInOrder(["--sandbox", "read-only"]);
        command.Arguments.Last().Should().Be("-");
        command.StandardInput.Should().Be("prompt body");
    }

    private sealed class CapturingManifestValidator : IHostedContextManifestValidator
    {
        public HostedContextEnvelope? Envelope { get; private set; }
        public string? OperationKey { get; private set; }

        public Task<bool> ValidateAndConsumeAsync(
            HostedContextEnvelope envelope,
            string operationKey,
            CancellationToken cancellationToken = default)
        {
            Envelope = envelope;
            OperationKey = operationKey;
            return Task.FromResult(true);
        }
    }
}
