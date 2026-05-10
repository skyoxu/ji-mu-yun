namespace PhaseA.Platform.Runs;

public interface IHostedProcessRunner
{
    Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default);
}
