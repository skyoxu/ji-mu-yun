using System.Diagnostics;
using System.Text;

namespace PhaseA.Platform.Llm;

public sealed class CodexCliChatClient : ICodexChatClient
{
    private const int TimeoutSeconds = 300;

    public async Task<CodexChatClientResult> CompleteAsync(
        string projectRoot,
        string model,
        string prompt,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(model);
        ArgumentException.ThrowIfNullOrWhiteSpace(prompt);

        Directory.CreateDirectory(Path.Combine(projectRoot, "logs", "phase-a-chat"));
        var outputPath = Path.Combine(projectRoot, "logs", "phase-a-chat", $"codex-{Guid.NewGuid():N}.txt");
        var startInfo = new ProcessStartInfo
        {
            FileName = ResolveCodexCommand(),
            WorkingDirectory = projectRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };

        startInfo.ArgumentList.Add("exec");
        startInfo.ArgumentList.Add("--sandbox");
        startInfo.ArgumentList.Add("read-only");
        startInfo.ArgumentList.Add("-m");
        startInfo.ArgumentList.Add(model);
        startInfo.ArgumentList.Add("-c");
        startInfo.ArgumentList.Add("approval_policy=\"never\"");
        startInfo.ArgumentList.Add("--cd");
        startInfo.ArgumentList.Add(projectRoot);
        startInfo.ArgumentList.Add("-o");
        startInfo.ArgumentList.Add(outputPath);
        startInfo.ArgumentList.Add(prompt);

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(TimeoutSeconds));
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
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            TryKill(process);
            return new CodexChatClientResult(false, null, "codex_timeout", 124, stdout.ToString(), stderr.ToString());
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return new CodexChatClientResult(false, null, "codex_not_available", 127, stdout.ToString(), ex.Message);
        }

        var finalMessage = File.Exists(outputPath)
            ? await File.ReadAllTextAsync(outputPath, Encoding.UTF8, cancellationToken)
            : null;

        if (process.ExitCode != 0)
        {
            return new CodexChatClientResult(false, finalMessage, "codex_failed", process.ExitCode, stdout.ToString(), stderr.ToString());
        }

        if (string.IsNullOrWhiteSpace(finalMessage))
        {
            return new CodexChatClientResult(false, null, "codex_empty_response", process.ExitCode, stdout.ToString(), stderr.ToString());
        }

        return new CodexChatClientResult(true, finalMessage.Trim(), null, process.ExitCode, stdout.ToString(), stderr.ToString());
    }

    private static void TryKill(Process process)
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

    private static string ResolveCodexCommand()
    {
        var configured = Environment.GetEnvironmentVariable("PHASEA_CODEX_COMMAND");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        var candidates = new[]
        {
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "npm",
                "codex.cmd"),
            @"C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\codex.cmd",
            @"C:\Users\Administrator\AppData\Roaming\npm\codex.cmd"
        };

        return candidates.FirstOrDefault(File.Exists) ?? "codex";
    }
}
