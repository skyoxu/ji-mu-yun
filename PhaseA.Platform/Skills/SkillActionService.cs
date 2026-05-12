using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Skills;

public sealed class SkillActionService
{
    private const string RunType = "skill-action";
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly SkillActionCatalog _catalog;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;

    public SkillActionService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        SkillActionCatalog catalog,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder)
    {
        _metadataStore = metadataStore;
        _options = options;
        _catalog = catalog;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
    }

    public IReadOnlyList<SkillActionDefinition> ListAllowed(string role)
    {
        return _catalog.ListAllowed(role);
    }

    public async Task<SkillActionRunResult> RunAsync(
        string projectId,
        string actionId,
        SkillActionRunRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(actionId);
        ArgumentNullException.ThrowIfNull(request);

        var action = _catalog.Find(actionId);
        if (action is null)
        {
            return new SkillActionRunResult("", "skill_action_not_allowed", 404, actionId, "", "", [], "skill_action_not_allowed");
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        var relativeDir = ToSlash(Path.Combine("logs", "phase-a-skills", project.ProjectId, runId));
        var outputRelativePath = ToSlash(Path.Combine(relativeDir, "skill-output.md"));
        var requestRelativePath = ToSlash(Path.Combine(relativeDir, "skill-request.json"));
        var outputAbsolutePath = Path.Combine(project.RepoPath, outputRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var requestAbsolutePath = Path.Combine(project.RepoPath, requestRelativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(outputAbsolutePath)!);

        await File.WriteAllTextAsync(
            requestAbsolutePath,
            JsonSerializer.Serialize(new
            {
                action.ActionId,
                action.SkillName,
                request.Input,
                project.ProjectId,
                project.Name,
                project.GameName,
                project.GameTypeSource
            }, new JsonSerializerOptions { WriteIndented = true }),
            Encoding.UTF8,
            cancellationToken);

        var prompt = BuildPrompt(action, project, request);
        var process = await _processRunner.RunAsync(BuildCodexReadOnlyCommand(project.RepoPath, outputAbsolutePath, prompt), cancellationToken);
        var output = File.Exists(outputAbsolutePath)
            ? await File.ReadAllTextAsync(outputAbsolutePath, Encoding.UTF8, cancellationToken)
            : FirstNonEmpty(process.Stdout, process.Stderr, "");
        var status = process.ExitCode == 0 ? "succeeded" : "failed";

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "skill-action-request",
            requestRelativePath,
            "Skill action request payload"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "skill-action-output",
            outputRelativePath,
            "Skill action output"), cancellationToken);

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            action_id = action.ActionId,
            skill_name = action.SkillName,
            execution_mode = action.ExecutionMode,
            request = requestRelativePath,
            output = outputRelativePath
        });
        await _metadataStore.CompleteRunAsync(runId, status, process.ExitCode, process.Stdout, process.Stderr, evidenceJson, cancellationToken);

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
        return new SkillActionRunResult(runId, status, process.ExitCode, action.ActionId, action.SkillName, output.Trim(), artifacts);
    }

    private HostedProcessCommand BuildCodexReadOnlyCommand(string repositoryRoot, string outputPath, string prompt)
    {
        var arguments = new List<string>
        {
            "exec",
            "--sandbox",
            "read-only",
            "-m",
            "gpt-5.4",
            "-c",
            "approval_policy=\"never\"",
            "-c",
            "model_reasoning_effort=\"high\"",
            "--cd",
            repositoryRoot,
            "-o",
            outputPath,
            prompt
        };

        return new HostedProcessCommand(
            ResolveCodexCommand(),
            arguments,
            repositoryRoot,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["PHASEA_CODEX_DEFAULT_MODEL"] = "gpt-5.4",
                ["PHASEA_CODEX_REASONING_EFFORT"] = "high"
            });
    }

    private static string BuildPrompt(SkillActionDefinition action, ProjectSnapshot project, SkillActionRunRequest request)
    {
        return $"""
            请使用 ${action.SkillName} 这个白名单 skill。
            你正在积木云 Phase A 的项目级 workspace 中运行，只允许只读分析和输出建议，不要修改文件，不要执行破坏性操作。

            项目信息：
            - ProjectId: {project.ProjectId}
            - ProjectName: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}

            用户输入：
            {request.Input?.Trim() ?? "请基于当前项目状态输出下一步建议。"}

            输出要求：
            - 用中文回答。
            - 明确说明调用的 skill 名称。
            - 给出可执行建议、风险和下一步。
            - 不要声称已经修改代码。
            """;
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
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "npm", "codex.cmd"),
            @"C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\codex.cmd",
            @"C:\Users\Administrator\AppData\Roaming\npm\codex.cmd"
        };

        return candidates.FirstOrDefault(File.Exists) ?? "codex";
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Length > 6000 ? value[^6000..] : value;
            }
        }

        return "";
    }

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }
}
