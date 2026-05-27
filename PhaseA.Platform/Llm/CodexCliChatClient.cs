using System.Diagnostics;
using System.Text;

namespace PhaseA.Platform.Llm;

public sealed class CodexCliChatClient : ICodexChatClient
{
    private const int TimeoutSeconds = 300;
    private readonly IAiCodeMirrorBillingClient _billingClient;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;

    public CodexCliChatClient()
        : this(new DisabledAiCodeMirrorBillingClient(), null)
    {
    }

    public CodexCliChatClient(
        IAiCodeMirrorBillingClient billingClient,
        AiCodeMirrorKeyPoolService? keyPoolService = null)
    {
        _billingClient = billingClient;
        _keyPoolService = keyPoolService;
    }

    public async Task<CodexChatClientResult> CompleteAsync(
        string projectRoot,
        string model,
        string prompt,
        CodexChatClientOptions? options = null,
        string? billingApiKeyName = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(model);
        ArgumentException.ThrowIfNullOrWhiteSpace(prompt);

        Directory.CreateDirectory(Path.Combine(projectRoot, "logs", "phase-a-chat"));
        var outputPath = Path.Combine(projectRoot, "logs", "phase-a-chat", $"codex-{Guid.NewGuid():N}.txt");
        var runtimeCredential = await ResolveRuntimeCredentialAsync(billingApiKeyName, cancellationToken);
        if (!runtimeCredential.Ready)
        {
            return new CodexChatClientResult(false, null, runtimeCredential.FailureCode, 1, "", "", CodexUsageExtractor.Extract("", ""), null);
        }

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
        startInfo.ArgumentList.Add("--json");
        startInfo.ArgumentList.Add("--sandbox");
        startInfo.ArgumentList.Add("read-only");
        startInfo.ArgumentList.Add("-m");
        startInfo.ArgumentList.Add(model);
        startInfo.ArgumentList.Add("-c");
        startInfo.ArgumentList.Add("approval_policy=\"never\"");
        if (!string.IsNullOrWhiteSpace(options?.ReasoningEffort))
        {
            startInfo.ArgumentList.Add("-c");
            startInfo.ArgumentList.Add($"model_reasoning_effort=\"{options.ReasoningEffort}\"");
        }
        if (options?.IgnoreRules == true)
        {
            startInfo.ArgumentList.Add("--ignore-rules");
        }
        startInfo.ArgumentList.Add("--cd");
        startInfo.ArgumentList.Add(projectRoot);
        if (!string.IsNullOrWhiteSpace(options?.OutputSchemaPath))
        {
            startInfo.ArgumentList.Add("--output-schema");
            startInfo.ArgumentList.Add(options.OutputSchemaPath);
        }
        startInfo.ArgumentList.Add("-o");
        startInfo.ArgumentList.Add(outputPath);
        startInfo.ArgumentList.Add(prompt);
        if (!string.IsNullOrWhiteSpace(runtimeCredential.CodexHomePath))
        {
            startInfo.Environment["CODEX_HOME"] = runtimeCredential.CodexHomePath;
        }

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(TimeoutSeconds));
        using var process = new Process { StartInfo = startInfo };
        var stdout = new StringBuilder();
        var stderr = new StringBuilder();
        var resolvedBillingKeyName = runtimeCredential.BillingKeyName ?? billingApiKeyName;
        var billingBefore = await _billingClient.CaptureAsync(resolvedBillingKeyName, cancellationToken);

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
            var timeoutStdout = stdout.ToString();
            var timeoutStderr = stderr.ToString();
            return new CodexChatClientResult(false, null, "codex_timeout", 124, timeoutStdout, timeoutStderr, CodexUsageExtractor.Extract(timeoutStdout, timeoutStderr), await CaptureBillingAfterAsync(billingBefore, resolvedBillingKeyName));
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            var failedStdout = stdout.ToString();
            var failedStderr = ex.Message;
            return new CodexChatClientResult(false, null, "codex_not_available", 127, failedStdout, failedStderr, CodexUsageExtractor.Extract(failedStdout, failedStderr), await CaptureBillingAfterAsync(billingBefore, resolvedBillingKeyName));
        }

        var finalStdout = stdout.ToString();
        var finalStderr = stderr.ToString();
        var tokenUsage = CodexUsageExtractor.Extract(finalStdout, finalStderr);
        var providerBilling = await CaptureBillingAfterAsync(billingBefore, resolvedBillingKeyName);
        var finalMessage = File.Exists(outputPath)
            ? await File.ReadAllTextAsync(outputPath, Encoding.UTF8, cancellationToken)
            : null;

        if (process.ExitCode != 0)
        {
            return new CodexChatClientResult(false, finalMessage, "codex_failed", process.ExitCode, finalStdout, finalStderr, tokenUsage, providerBilling);
        }

        if (string.IsNullOrWhiteSpace(finalMessage))
        {
            return new CodexChatClientResult(false, null, "codex_empty_response", process.ExitCode, finalStdout, finalStderr, tokenUsage, providerBilling);
        }

        return new CodexChatClientResult(true, finalMessage.Trim(), null, process.ExitCode, finalStdout, finalStderr, tokenUsage, providerBilling);
    }

    private async Task<AiCodeMirrorBillingDelta> CaptureBillingAfterAsync(AiCodeMirrorBillingSnapshot before, string? billingApiKeyName)
    {
        var after = await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None);
        return new AiCodeMirrorBillingDelta(before, after);
    }

    private async Task<string?> ResolveBillingApiKeyNameAsync(string? accountIdOrApiKeyName, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(accountIdOrApiKeyName) || _keyPoolService is null)
        {
            return accountIdOrApiKeyName;
        }

        return await _keyPoolService.ResolveKeyNameForAccountAsync(accountIdOrApiKeyName, cancellationToken)
               ?? accountIdOrApiKeyName;
    }

    private async Task<AiCodeMirrorRuntimeCredential> ResolveRuntimeCredentialAsync(
        string? accountIdOrApiKeyName,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(accountIdOrApiKeyName) || _keyPoolService is null)
        {
            return new AiCodeMirrorRuntimeCredential(accountIdOrApiKeyName, null, null);
        }

        return await _keyPoolService.ResolveRuntimeCredentialForAccountAsync(accountIdOrApiKeyName, cancellationToken);
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
