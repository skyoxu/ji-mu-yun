using System.Diagnostics;
using System.Text;

namespace PhaseA.Platform.Runs;

public sealed class HostedProcessRunner : IHostedProcessRunner
{
    private readonly RunCancellationService _runCancellation;

    public HostedProcessRunner(RunCancellationService? runCancellation = null)
    {
        _runCancellation = runCancellation ?? new RunCancellationService();
    }

    public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(command);
        using var linkedCancellation = string.IsNullOrWhiteSpace(command.RunId)
            ? null
            : _runCancellation.CreateLinkedTokenSource(command.RunId, cancellationToken);
        var effectiveCancellationToken = linkedCancellation?.Token ?? cancellationToken;

        var startInfo = new ProcessStartInfo
        {
            FileName = command.FileName,
            WorkingDirectory = command.WorkingDirectory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = command.StandardInput is not null,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        if (command.StandardInput is not null)
        {
            startInfo.StandardInputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        }

        foreach (var argument in command.Arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        foreach (var variable in command.Environment)
        {
            startInfo.Environment[variable.Key] = variable.Value;
        }

        using var process = new Process { StartInfo = startInfo };
        var stdout = new StringBuilder();
        var stderr = new StringBuilder();

        process.OutputDataReceived += (_, args) =>
        {
            if (args.Data is not null)
            {
                stdout.AppendLine(args.Data);
            }
        };
        process.ErrorDataReceived += (_, args) =>
        {
            if (args.Data is not null)
            {
                stderr.AppendLine(args.Data);
            }
        };

        try
        {
            process.Start();
            if (command.StandardInput is not null)
            {
                await process.StandardInput.WriteAsync(command.StandardInput);
                await process.StandardInput.FlushAsync(effectiveCancellationToken);
                process.StandardInput.Close();
            }

            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            await process.WaitForExitAsync(effectiveCancellationToken);
        }
        catch (OperationCanceledException)
        {
            try
            {
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                    await process.WaitForExitAsync(CancellationToken.None);
                }
            }
            catch (InvalidOperationException)
            {
            }

            throw;
        }
        finally
        {
            if (!string.IsNullOrWhiteSpace(command.RunId))
            {
                _runCancellation.Unregister(command.RunId);
            }
        }

        return new HostedProcessResult(process.ExitCode, stdout.ToString(), stderr.ToString());
    }
}
