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
        int count = 1,
        string? referenceImagePath = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(prompt);
        ArgumentException.ThrowIfNullOrWhiteSpace(outputAbsoluteDirectory);
        ArgumentException.ThrowIfNullOrWhiteSpace(outputRelativeDirectory);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileStem);

        Directory.CreateDirectory(outputAbsoluteDirectory);
        count = Math.Clamp(count, 1, 4);
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
                "--background",
                "transparent",
                "--n",
                count.ToString(System.Globalization.CultureInfo.InvariantCulture),
                "--timeout",
                "120"
            ]);
        if (!string.IsNullOrWhiteSpace(referenceImagePath))
        {
            arguments.Add("--reference-image");
            arguments.Add(referenceImagePath);
        }

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

        var generatedImagePaths = Directory.EnumerateFiles(outputAbsoluteDirectory, "*", SearchOption.TopDirectoryOnly)
            .Where(path =>
            {
                var extension = Path.GetExtension(path);
                return extension.Equals(".png", StringComparison.OrdinalIgnoreCase) ||
                       extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
                       extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase) ||
                       extension.Equals(".webp", StringComparison.OrdinalIgnoreCase);
            })
            .Select(Path.GetFullPath)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var generated = process.ExitCode == 0 && generatedImagePaths.Length > 0;
        var status = process.ExitCode == 0 ? "succeeded" : "failed";
        var assistantMessage = generated
            ? $"\u5df2\u901a\u8fc7\u8f7b\u91cf\u56fe\u7247\u751f\u6210\u94fe\u8def\u521b\u5efa {generatedImagePaths.Length} \u4e2a\u7d20\u6750\uff0c\u8017\u65f6 {stopwatch.Elapsed.TotalSeconds:0.0} \u79d2\u3002"
            : process.ExitCode == 0
                ? $"\u8f7b\u91cf\u56fe\u7247\u751f\u6210\u94fe\u8def\u5df2\u7ed3\u675f\uff0c\u4f46\u6ca1\u6709\u4ea7\u51fa\u53ef\u7528\u56fe\u7247\uff0c\u8017\u65f6 {stopwatch.Elapsed.TotalSeconds:0.0} \u79d2\u3002"
                : $"\u8f7b\u91cf\u56fe\u7247\u751f\u6210\u5931\u8d25\uff0c\u8017\u65f6 {stopwatch.Elapsed.TotalSeconds:0.0} \u79d2\u3002";

        var sidecar = new
        {
            run_id = runId,
            route = "project-asset-image-direct",
            status,
            elapsed_seconds = Math.Round(stopwatch.Elapsed.TotalSeconds, 3),
            image = generated ? ToSlash(Path.GetRelativePath(project.RepoPath, generatedImagePaths[0])) : null,
            images = generatedImagePaths.Select(path => ToSlash(Path.GetRelativePath(project.RepoPath, path))).ToArray(),
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
        artifacts.AddRange(generatedImagePaths.Select(path => ToSlash(Path.GetRelativePath(project.RepoPath, path))));

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
