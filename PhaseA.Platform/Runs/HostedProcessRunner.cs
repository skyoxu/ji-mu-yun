using System.Diagnostics;
using System.ComponentModel;
using Microsoft.Win32.SafeHandles;
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
        if (command.RequireIsolation && OperatingSystem.IsWindows() && !hasIsolation)
        {
            return new HostedProcessResult(403, string.Empty, "runner isolation registration is required");
        }

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

        using var processIsolation = hasIsolation ? RunnerIsolationPolicy.CreateProcessIsolation(isolationDescriptor!) : null;
        if (hasIsolation && !RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(isolationDescriptor!))
        {
            return new HostedProcessResult(403, string.Empty, "runner workspace security drift detected");
        }
        using var nativeProcess = hasIsolation
            ? WindowsIsolatedProcess.Start(command, isolationDescriptor!, RunnerCredentialStore.Read(RunnerIsolationPolicy.CredentialTarget(isolationDescriptor!)), startInfo.Environment)
            : null;
        using var process = nativeProcess?.Process ?? new Process { StartInfo = startInfo };
        var stdout = new StringBuilder();
        var stderr = new StringBuilder();
        var startedAt = DateTimeOffset.UtcNow;
        var lastActivityAt = startedAt;
        string? timeoutReason = null;

        Task? nativeStdoutPump = null;
        Task? nativeStderrPump = null;
        if (nativeProcess is null)
        {
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
        }
        else
        {
            nativeStdoutPump = PumpLinesAsync(nativeProcess.StandardOutput, stdout, () => lastActivityAt = DateTimeOffset.UtcNow);
            nativeStderrPump = PumpLinesAsync(nativeProcess.StandardError, stderr, () => lastActivityAt = DateTimeOffset.UtcNow);
        }

        try
        {
            if (nativeProcess is null)
            {
                process.Start();
            }
            startedAt = DateTimeOffset.UtcNow;
            startInfo.PasswordInClearText = null;
            try
            {
                processIsolation?.AttachProcess(process);
                nativeProcess?.Resume();
            }
            catch
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
            if (command.StandardInput is not null)
            {
                if (nativeProcess is not null)
                {
                    await nativeProcess.StandardInput.WriteAsync(command.StandardInput);
                    await nativeProcess.StandardInput.FlushAsync(effectiveCancellationToken);
                    nativeProcess.StandardInput.Close();
                }
                else
                {
                    await process.StandardInput.WriteAsync(command.StandardInput);
                    await process.StandardInput.FlushAsync(effectiveCancellationToken);
                    process.StandardInput.Close();
                }
            }

            if (nativeProcess is null)
            {
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
            }
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
            if (nativeStdoutPump is not null) await nativeStdoutPump;
            if (nativeStderrPump is not null) await nativeStderrPump;
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

    private static async Task PumpLinesAsync(StreamReader reader, StringBuilder output, Action onActivity)
    {
        while (await reader.ReadLineAsync() is { } line)
        {
            onActivity();
            output.AppendLine(line);
        }
    }
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

internal sealed class WindowsIsolatedProcess : IDisposable
{
    private const uint LogonWithProfile = 1;
    private const uint CreateUnicodeEnvironment = 0x00000400;
    private const uint CreateBreakawayFromJob = 0x01000000;
    private const uint CreateNoWindow = 0x08000000;
    private const uint CreateSuspended = 0x00000004;
    private const uint StartfUseStdHandles = 0x00000100;
    private const uint HandleFlagInherit = 1;

    private readonly IntPtr _thread;

    private WindowsIsolatedProcess(Process process, IntPtr thread, StreamWriter standardInput, StreamReader standardOutput, StreamReader standardError)
    {
        Process = process;
        _thread = thread;
        StandardInput = standardInput;
        StandardOutput = standardOutput;
        StandardError = standardError;
    }

    public Process Process { get; }
    public StreamWriter StandardInput { get; }
    public StreamReader StandardOutput { get; }
    public StreamReader StandardError { get; }

    public void Resume()
    {
        if (ResumeThread(_thread) == uint.MaxValue)
            throw new Win32Exception(Marshal.GetLastWin32Error(), "isolated runner process could not be resumed after Job Object attachment");
    }

    public static WindowsIsolatedProcess Start(
        HostedProcessCommand command,
        RunnerIsolationDescriptor descriptor,
        RunnerCredential credential,
        IEnumerable<KeyValuePair<string, string?>> environment)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("Windows isolated process launch is only supported on Windows.");

        var identity = RunnerLogonIdentity.Parse(credential.UserName);
        var security = new SecurityAttributes { Length = Marshal.SizeOf<SecurityAttributes>(), InheritHandle = true };
        IntPtr childStdout = IntPtr.Zero;
        IntPtr parentStdout = IntPtr.Zero;
        IntPtr childStderr = IntPtr.Zero;
        IntPtr parentStderr = IntPtr.Zero;
        IntPtr childStdin = IntPtr.Zero;
        IntPtr parentStdin = IntPtr.Zero;
        IntPtr environmentBlock = IntPtr.Zero;
        Process? process = null;

        try
        {
            DemandPipe(CreatePipe(out parentStdout, out childStdout, ref security, 0), "stdout");
            DemandPipe(SetHandleInformation(parentStdout, HandleFlagInherit, 0), "stdout parent");
            DemandPipe(CreatePipe(out parentStderr, out childStderr, ref security, 0), "stderr");
            DemandPipe(SetHandleInformation(parentStderr, HandleFlagInherit, 0), "stderr parent");
            DemandPipe(CreatePipe(out childStdin, out parentStdin, ref security, 0), "stdin");
            DemandPipe(SetHandleInformation(parentStdin, HandleFlagInherit, 0), "stdin parent");

            environmentBlock = BuildEnvironmentBlock(environment);
            var startup = new StartupInfo
            {
                Size = Marshal.SizeOf<StartupInfo>(),
                Flags = StartfUseStdHandles,
                StandardInput = childStdin,
                StandardOutput = childStdout,
                StandardError = childStderr
            };
            var commandLine = new StringBuilder(BuildCommandLine(command.FileName, command.Arguments));
            var flags = CreateUnicodeEnvironment | CreateBreakawayFromJob | CreateNoWindow | CreateSuspended;
            if (!CreateProcessWithLogonW(
                    identity.UserName,
                    identity.Domain,
                    credential.Password,
                    LogonWithProfile,
                    null,
                    commandLine,
                    flags,
                    environmentBlock,
                    command.WorkingDirectory,
                    ref startup,
                    out var processInformation))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "isolated runner process could not be started with breakaway job semantics");
            }

            CloseHandle(childStdin);
            childStdin = IntPtr.Zero;
            CloseHandle(childStdout);
            childStdout = IntPtr.Zero;
            CloseHandle(childStderr);
            childStderr = IntPtr.Zero;
            process = Process.GetProcessById(processInformation.ProcessId);
            CloseHandle(processInformation.Process);
            var output = new StreamReader(new FileStream(new SafeFileHandle(parentStdout, ownsHandle: true), FileAccess.Read, 4096, isAsync: false), Encoding.UTF8);
            parentStdout = IntPtr.Zero;
            var error = new StreamReader(new FileStream(new SafeFileHandle(parentStderr, ownsHandle: true), FileAccess.Read, 4096, isAsync: false), Encoding.UTF8);
            parentStderr = IntPtr.Zero;
            var input = new StreamWriter(new FileStream(new SafeFileHandle(parentStdin, ownsHandle: true), FileAccess.Write, 4096, isAsync: false), new UTF8Encoding(false))
            {
                AutoFlush = false,
                NewLine = Environment.NewLine
            };
            parentStdin = IntPtr.Zero;
            return new WindowsIsolatedProcess(process, processInformation.Thread, input, output, error);
        }
        catch
        {
            try
            {
                if (process is not null && !process.HasExited)
                    process.Kill(entireProcessTree: true);
            }
            catch (InvalidOperationException)
            {
            }
            CloseHandle(childStdin);
            CloseHandle(parentStdin);
            CloseHandle(childStdout);
            CloseHandle(parentStdout);
            CloseHandle(childStderr);
            CloseHandle(parentStderr);
            throw;
        }
        finally
        {
            if (environmentBlock != IntPtr.Zero)
                Marshal.FreeCoTaskMem(environmentBlock);
        }
    }

    public void Dispose()
    {
        CloseHandle(_thread);
        StandardInput.Dispose();
        StandardOutput.Dispose();
        StandardError.Dispose();
    }

    private static void DemandPipe(bool success, string pipe)
    {
        if (!success)
            throw new Win32Exception(Marshal.GetLastWin32Error(), $"isolated runner {pipe} pipe could not be created");
    }

    private static string BuildCommandLine(string fileName, IReadOnlyList<string> arguments)
    {
        var executable = fileName.EndsWith(".cmd", StringComparison.OrdinalIgnoreCase) || fileName.EndsWith(".bat", StringComparison.OrdinalIgnoreCase)
            ? Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe"
            : fileName;
        var command = string.Join(" ", new[] { Quote(executable) }.Concat(arguments.Select(Quote)));
        return executable.Equals(fileName, StringComparison.OrdinalIgnoreCase)
            ? command
            : $"{Quote(executable)} /d /s /c {Quote(command)}";
    }

    private static string Quote(string value)
    {
        if (value.Length == 0) return "\"\"";
        if (!value.Any(char.IsWhiteSpace) && !value.Contains('"')) return value;
        var builder = new StringBuilder("\"");
        var slashes = 0;
        foreach (var character in value)
        {
            if (character == '\\') { slashes++; continue; }
            if (character == '"') builder.Append('\\', slashes * 2 + 1);
            else builder.Append('\\', slashes);
            slashes = 0;
            builder.Append(character);
        }
        builder.Append('\\', slashes * 2).Append('"');
        return builder.ToString();
    }

    private static IntPtr BuildEnvironmentBlock(IEnumerable<KeyValuePair<string, string?>> environment)
    {
        var block = string.Join("\0", environment
            .Where(pair => pair.Key.Length > 0)
            .OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase)
            .Select(pair => $"{pair.Key}={pair.Value ?? string.Empty}")) + "\0\0";
        return Marshal.StringToCoTaskMemUni(block);
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SecurityAttributes
    {
        public int Length;
        public IntPtr Descriptor;
        [MarshalAs(UnmanagedType.Bool)] public bool InheritHandle;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct StartupInfo
    {
        public int Size;
        public string? Reserved;
        public string? Desktop;
        public string? Title;
        public int X;
        public int Y;
        public int XSize;
        public int YSize;
        public int XCountChars;
        public int YCountChars;
        public int FillAttribute;
        public uint Flags;
        public short ShowWindow;
        public short Reserved2;
        public IntPtr Reserved2Pointer;
        public IntPtr StandardInput;
        public IntPtr StandardOutput;
        public IntPtr StandardError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        public IntPtr Process;
        public IntPtr Thread;
        public int ProcessId;
        public int ThreadId;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreatePipe(out IntPtr readPipe, out IntPtr writePipe, ref SecurityAttributes attributes, int size);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetHandleInformation(IntPtr handle, uint mask, uint flags);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateProcessWithLogonW(
        string userName,
        string domain,
        string password,
        uint logonFlags,
        string? applicationName,
        StringBuilder commandLine,
        uint creationFlags,
        IntPtr environment,
        string currentDirectory,
        ref StartupInfo startupInfo,
        out ProcessInformation processInformation);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint ResumeThread(IntPtr thread);
}
