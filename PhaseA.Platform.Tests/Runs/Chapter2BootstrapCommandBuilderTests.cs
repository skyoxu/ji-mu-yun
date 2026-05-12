using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class Chapter2BootstrapCommandBuilderTests
{
    [Fact]
    public void BuildLocalHardChecksCommand_DelegatesToRepositoryNativeChapter2Entrypoint()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["PHASEA_PYTHON_COMMAND"] = "py",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe",
            ["DELIVERY_PROFILE"] = "fast-ship"
        });
        var builder = new Chapter2BootstrapCommandBuilder(options);

        var command = builder.BuildLocalHardChecksCommand(@"C:\project-repo");

        command.FileName.Should().Be("py");
        command.WorkingDirectory.Should().Be(@"C:\project-repo");
        command.Arguments.Should().ContainInOrder(
            "-3",
            "scripts/python/dev_cli.py",
            "run-local-hard-checks",
            "--delivery-profile",
            "fast-ship",
            "--godot-bin",
            @"C:\Godot\Godot.exe");
        command.Environment["GODOT_BIN"].Should().Be(@"C:\Godot\Godot.exe");
    }

}
