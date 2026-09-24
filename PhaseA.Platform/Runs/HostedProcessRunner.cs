using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using PhaseA.Platform.Security;

namespace PhaseA.Platform.Runs;

public sealed class HostedProcessRunner : IHostedProcessRunner
{
    private readonly RunCancellationService _runCancellation;
    private int _cleanupFailureObserved;

    public HostedProcessRunner(RunCancellationService? runCancellation = null)
    {
        _runCancellation = runCancellation ?? new RunCancellationService();
    }

    public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(command);
        if (Volatile.Read(ref _cleanupFailureObserved) != 0)
        {
            return new HostedProcessResult(409, string.Empty, "runner dispatch is blocked after a prior cleanup failure");
        }
        using var linkedCancellation = string.IsNullOrWhiteSpace(command.RunId)
            ? null
            : _runCancellation.CreateLinkedTokenSource(command.RunId, cancellationToken);
        var effectiveCancellationToken = linkedCancellation?.Token ?? cancellationToken;
        RunnerIsolationDescriptor? isolationDescriptor = null;
        var hasIsolation = OperatingSystem.IsWindows()
            && RunnerIsolationPolicy.TryGetWorkspaceDescriptor(command.WorkingDirectory, out isolationDescriptor);

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
        if (hasIsolation)
        {
            var credential = RunnerCredentialStore.Read(RunnerIsolationPolicy.CredentialTarget(isolationDescriptor!));
            var logonIdentity = RunnerLogonIdentity.Parse(credential.UserName);
            startInfo.UserName = logonIdentity.UserName;
            startInfo.Domain = logonIdentity.Domain;
            startInfo.PasswordInClearText = credential.Password;
            startInfo.LoadUserProfile = true;
        }
        if (command.StandardInput is not null)
        {
            startInfo.StandardInputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        }

        startInfo.Environment.Clear();
        if (OperatingSystem.IsWindows() && Environment.GetEnvironmentVariable("SystemRoot") is { Length: > 0 } systemRoot)
        {
            var systemDirectory = Path.Combine(systemRoot, "System32");
            startInfo.Environment["SystemRoot"] = systemRoot;
            startInfo.Environment["Path"] = string.Join(Path.PathSeparator, systemDirectory, Path.Combine(systemDirectory, "WindowsPowerShell", "v1.0"), systemRoot);
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
        using var processIsolation = hasIsolation ? RunnerIsolationPolicy.CreateProcessIsolation(isolationDescriptor!) : null;
        if (hasIsolation && !RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(isolationDescriptor!))
        {
            return new HostedProcessResult(403, string.Empty, "runner workspace security drift detected");
        }
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
            startedAt = DateTimeOffset.UtcNow;
            startInfo.PasswordInClearText = null;
            processIsolation?.AttachProcess(process);
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
            process.WaitForExit();
            await timeoutMonitorCancellation.CancelAsync();
            await timeoutTask;
            if (!string.IsNullOrWhiteSpace(timeoutReason))
            {
                Interlocked.Exchange(ref _cleanupFailureObserved, 1);
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
                Interlocked.Exchange(ref _cleanupFailureObserved, 1);
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

        var result = new HostedProcessResult(process.ExitCode, stdout.ToString(), stderr.ToString());
        if (result.ExitCode != 0)
        {
            Interlocked.Exchange(ref _cleanupFailureObserved, 1);
        }
        return result;
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

internal sealed record RunnerCredential(string UserName, string Password);

internal sealed record RunnerLogonIdentity(string UserName, string Domain)
{
    public static RunnerLogonIdentity Parse(string userName)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(userName);
        var separator = userName.IndexOf('\\');
        if (separator < 0)
        {
            return new RunnerLogonIdentity(userName, ".");
        }

        var domain = userName[..separator];
        var account = userName[(separator + 1)..];
        if (string.IsNullOrWhiteSpace(account) || account.Contains('\\'))
        {
            throw new InvalidOperationException("managed runner credential has an invalid user name");
        }

        return new RunnerLogonIdentity(account, string.IsNullOrWhiteSpace(domain) ? "." : domain);
    }
}

internal static class RunnerCredentialStore
{
    private const uint CredTypeGeneric = 1;

    public static RunnerCredential Read(string target)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(target);
        if (!OperatingSystem.IsWindows() || !CredRead(target, CredTypeGeneric, 0, out var pointer))
        {
            throw new InvalidOperationException("managed runner credential is unavailable");
        }

        try
        {
            var credential = Marshal.PtrToStructure<NativeCredential>(pointer);
            if (credential.CredentialBlob == nint.Zero || credential.CredentialBlobSize == 0 || string.IsNullOrWhiteSpace(credential.UserName))
            {
                throw new InvalidOperationException("managed runner credential is incomplete");
            }

            var password = Marshal.PtrToStringUni(credential.CredentialBlob, checked((int)credential.CredentialBlobSize / sizeof(char)));
            if (string.IsNullOrEmpty(password))
            {
                throw new InvalidOperationException("managed runner credential is incomplete");
            }

            return new RunnerCredential(credential.UserName, password);
        }
        finally
        {
            CredFree(pointer);
        }
    }

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CredRead(string target, uint type, uint flags, out nint credential);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern void CredFree(nint buffer);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NativeCredential
    {
        public uint Flags;
        public uint Type;
        public nint TargetName;
        public nint Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public nint CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public nint Attributes;
        public nint TargetAlias;
        [MarshalAs(UnmanagedType.LPWStr)] public string? UserName;
    }
}
