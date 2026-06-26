using System.Diagnostics;
using System.Text;
using System.Threading;

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
        var startedAt = DateTimeOffset.UtcNow;
        var lastActivityAt = startedAt;
        string? timeoutReason = null;

        process.OutputDataReceived += (_, args) =>
        {
            if (args.Data is not null)
            {
                lastActivityAt = DateTimeOffset.UtcNow;
                stdout.AppendLine(args.Data);
            }
        };
        process.ErrorDataReceived += (_, args) =>
        {
            if (args.Data is not null)
            {
                lastActivityAt = DateTimeOffset.UtcNow;
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
            using var timeoutMonitorCancellation = new CancellationTokenSource();
            var waitTask = process.WaitForExitAsync(effectiveCancellationToken);
            var timeoutTask = MonitorTimeoutsAsync(
                process,
                command,
                () => startedAt,
                () => lastActivityAt,
                value => lastActivityAt = value,
                reason => timeoutReason = reason,
                timeoutMonitorCancellation.Token);
            await waitTask;
            await timeoutMonitorCancellation.CancelAsync();
            await timeoutTask;
            if (!string.IsNullOrWhiteSpace(timeoutReason))
            {
                return new HostedProcessResult(408, stdout.ToString(), timeoutReason);
            }
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

            if (!string.IsNullOrWhiteSpace(timeoutReason) && !cancellationToken.IsCancellationRequested)
            {
                return new HostedProcessResult(408, stdout.ToString(), timeoutReason);
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

    private static async Task MonitorTimeoutsAsync(
        Process process,
        HostedProcessCommand command,
        Func<DateTimeOffset> startedAt,
        Func<DateTimeOffset> lastActivityAt,
        Action<DateTimeOffset> setLastActivityAt,
        Action<string> setTimeoutReason,
        CancellationToken cancellationToken)
    {
        if (command.TotalTimeout is null && command.InactivityTimeout is null)
        {
            return;
        }

        var lastWatchedSnapshot = GetWatchedActivitySnapshot(command);
        while (!process.HasExited)
        {
            var now = DateTimeOffset.UtcNow;
            var watchedSnapshot = GetWatchedActivitySnapshot(command);
            if (watchedSnapshot != lastWatchedSnapshot)
            {
                setLastActivityAt(now);
                lastWatchedSnapshot = watchedSnapshot;
            }
            else if (watchedSnapshot?.NewestWrite is { } watchedWrite && watchedWrite > lastActivityAt())
            {
                setLastActivityAt(watchedWrite);
            }

            if (command.TotalTimeout is { } totalTimeout && now - startedAt() > totalTimeout)
            {
                setTimeoutReason($"Process exceeded total timeout of {FormatTimeout(totalTimeout)}.");
                KillProcessTree(process);
                return;
            }

            if (command.InactivityTimeout is { } inactivityTimeout && now - lastActivityAt() > inactivityTimeout)
            {
                setTimeoutReason($"Process had no stdout, stderr, or watched file activity for {FormatTimeout(inactivityTimeout)}.");
                KillProcessTree(process);
                return;
            }

            try
            {
                await Task.Delay(command.ActivityWatchPollInterval ?? TimeSpan.FromSeconds(1), cancellationToken);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return;
            }
        }
    }

    private static WatchedActivitySnapshot? GetWatchedActivitySnapshot(HostedProcessCommand command)
    {
        if (command.ActivityWatchPaths is null || command.ActivityWatchPaths.Count == 0)
        {
            return null;
        }

        DateTimeOffset? newest = null;
        var fileCount = 0;
        long totalBytes = 0;
        foreach (var configuredPath in command.ActivityWatchPaths)
        {
            if (string.IsNullOrWhiteSpace(configuredPath))
            {
                continue;
            }

            var path = Path.IsPathRooted(configuredPath)
                ? configuredPath
                : Path.Combine(command.WorkingDirectory, configuredPath);

            try
            {
                if (File.Exists(path))
                {
                    AddFile(path, ref fileCount, ref totalBytes, ref newest);
                }
                else if (Directory.Exists(path))
                {
                    foreach (var file in Directory.EnumerateFiles(path, "*", SearchOption.AllDirectories))
                    {
                        AddFile(file, ref fileCount, ref totalBytes, ref newest);
                    }
                }
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        return fileCount == 0
            ? null
            : new WatchedActivitySnapshot(fileCount, totalBytes, newest);
    }

    private static void AddFile(string path, ref int fileCount, ref long totalBytes, ref DateTimeOffset? newest)
    {
        var info = new FileInfo(path);
        fileCount++;
        totalBytes += info.Length;
        newest = Max(newest, info.LastWriteTimeUtc);
    }

    private static DateTimeOffset Max(DateTimeOffset? current, DateTimeOffset candidate)
    {
        return current is null || candidate > current.Value ? candidate : current.Value;
    }

    private static void KillProcessTree(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
        }
    }

    private static string FormatTimeout(TimeSpan timeout)
    {
        return timeout.TotalMinutes >= 1
            ? $"{timeout.TotalMinutes:0.##} minute(s)"
            : $"{timeout.TotalSeconds:0.##} second(s)";
    }

    private sealed record WatchedActivitySnapshot(int FileCount, long TotalBytes, DateTimeOffset? NewestWrite);
}
