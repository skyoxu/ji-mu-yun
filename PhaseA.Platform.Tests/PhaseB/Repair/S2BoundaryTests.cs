using PhaseA.Platform.Runs;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S2BoundaryTests
{
    private readonly ITestOutputHelper _output;
    public S2BoundaryTests(ITestOutputHelper output) => _output = output;
    [Fact]
    public async Task O_26DE8E588B36()
    {
        var root = Path.Combine(Path.GetTempPath(), "s2-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var output = Path.Combine(root, "output.txt");
        try
        {
            var request = new CodexHostedProcessRequest(root, output, "", "test-model", "low");
            var command = CodexHostedProcessCommandFactory.Build(request with { Prompt = "write harmless marker" });
            var runner = new HostedProcessRunner();
            var result = await runner.RunAsync(command with { FileName = "cmd.exe", Arguments = ["/c", "echo", "s2-ok", ">", output] });
            Assert.Equal(0, result.ExitCode);
            Assert.True(File.Exists(output));
            Assert.Contains("s2-ok", await File.ReadAllTextAsync(output));
            _output.WriteLine("S2_OBSERVATION:0,true,true");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
}
