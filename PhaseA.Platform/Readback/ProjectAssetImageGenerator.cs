using System.Diagnostics;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;

namespace PhaseA.Platform.Readback;

public sealed class ProjectAssetImageGenerator
{
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;

    public ProjectAssetImageGenerator(PhaseAPlatformOptions options, IHostedProcessRunner processRunner)
    {
        _options = options;
        _processRunner = processRunner;
    }

    public async Task<ProjectAssetImageGenerationResult> GenerateAsync(
        ProjectSnapshot project,
        string runId,
        string prompt,
        string outputAbsoluteDirectory,
        string outputRelativeDirectory,
        string fileStem,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(prompt);
        ArgumentException.ThrowIfNullOrWhiteSpace(outputAbsoluteDirectory);
        ArgumentException.ThrowIfNullOrWhiteSpace(outputRelativeDirectory);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileStem);

        Directory.CreateDirectory(outputAbsoluteDirectory);
        var promptRelativePath = ToSlash(Path.Combine(outputRelativeDirectory, "generation-prompt.txt"));
        var manifestRelativePath = ToSlash(Path.Combine(outputRelativeDirectory, "image-generation-manifest.json"));
        var imageRelativePath = ToSlash(Path.Combine(outputRelativeDirectory, $"{fileStem}.png"));
        var promptPath = Path.Combine(project.RepoPath, promptRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var manifestPath = Path.Combine(project.RepoPath, manifestRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var imagePath = Path.Combine(project.RepoPath, imageRelativePath.Replace('/', Path.DirectorySeparatorChar));
        await File.WriteAllTextAsync(promptPath, prompt, Encoding.UTF8, cancellationToken);

        var scriptPath = Path.Combine(_options.RepositoryRoot, "scripts", "python", "aiartmirror_image_cli.py");
        var arguments = new List<string>();
        if (Path.GetFileNameWithoutExtension(_options.PythonCommand).Equals("py", StringComparison.OrdinalIgnoreCase))
        {
            arguments.Add("-3");
        }

        arguments.AddRange(
            [
                scriptPath,
                "--prompt-file",
                promptPath,
                "--out",
                imagePath,
                "--manifest-out",
                manifestPath,
                "--size",
                "1024x1024",
                "--quality",
                "low",
                "--timeout",
                "120"
            ]);

        var command = new HostedProcessCommand(
            _options.PythonCommand,
            arguments,
            project.RepoPath,
            new Dictionary<string, string>
            {
                ["PHASEA_ASSET_GENERATION_RUN_ID"] = runId
            });

        var stopwatch = Stopwatch.StartNew();
        var process = await _processRunner.RunAsync(command, cancellationToken);
        stopwatch.Stop();

        var generated = process.ExitCode == 0 && File.Exists(imagePath);
        var status = process.ExitCode == 0 ? "succeeded" : "failed";
        var assistantMessage = generated
            ? $"已通过轻量图片生成链路创建素材：{imageRelativePath}，耗时 {stopwatch.Elapsed.TotalSeconds:0.0} 秒。"
            : process.ExitCode == 0
                ? $"轻量图片生成链路已结束，但没有产出可用图片，耗时 {stopwatch.Elapsed.TotalSeconds:0.0} 秒。"
                : $"轻量图片生成失败，耗时 {stopwatch.Elapsed.TotalSeconds:0.0} 秒。";

        var sidecar = new
        {
            run_id = runId,
            route = "project-asset-image-direct",
            status,
            elapsed_seconds = Math.Round(stopwatch.Elapsed.TotalSeconds, 3),
            image = generated ? imageRelativePath : null,
            prompt = promptRelativePath,
            manifest = File.Exists(manifestPath) ? manifestRelativePath : null,
            exit_code = process.ExitCode,
            stdout_tail = Tail(process.Stdout),
            stderr_tail = Tail(process.Stderr)
        };
        var sidecarRelativePath = ToSlash(Path.Combine(outputRelativeDirectory, "direct-generation-result.json"));
        var sidecarPath = Path.Combine(project.RepoPath, sidecarRelativePath.Replace('/', Path.DirectorySeparatorChar));
        await File.WriteAllTextAsync(sidecarPath, JsonSerializer.Serialize(sidecar, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8, cancellationToken);

        var artifacts = new List<string> { promptRelativePath, sidecarRelativePath };
        if (File.Exists(manifestPath))
        {
            artifacts.Add(manifestRelativePath);
        }
        if (generated)
        {
            artifacts.Add(imageRelativePath);
        }

        return new ProjectAssetImageGenerationResult(
            runId,
            status,
            process.ExitCode,
            process.Stdout,
            process.Stderr,
            assistantMessage,
            artifacts,
            stopwatch.Elapsed);
    }

    private static string Tail(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        return value.Length > 4000 ? value[^4000..] : value;
    }

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }
}

public sealed record ProjectAssetImageGenerationResult(
    string RunId,
    string Status,
    int ExitCode,
    string Stdout,
    string Stderr,
    string AssistantMessage,
    IReadOnlyList<string> ArtifactPaths,
    TimeSpan Elapsed);
