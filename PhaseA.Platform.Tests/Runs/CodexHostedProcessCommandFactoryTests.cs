using FluentAssertions;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class CodexHostedProcessCommandFactoryTests
{
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
}
