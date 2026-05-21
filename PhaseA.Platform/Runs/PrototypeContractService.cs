using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeContractService
{
    private static readonly Encoding Utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true
    };

    public PrototypeContractSnapshot WriteFromRequest(
        ProjectSnapshot project,
        PrototypeWorkflowRequest request,
        string prototypeRecordPath,
        string slug)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(request);

        var routeSkill = PrototypeRouteSkillPolicy.Resolve(project);
        var payload = new
        {
            schema_version = 1,
            route = "prototype-contract",
            project_id = project.ProjectId,
            game_name = FirstNonEmpty(request.GameName, project.GameName),
            game_type = FirstNonEmpty(request.GameType, request.GameTypeSource, project.GameTypeSource),
            game_type_source = FirstNonEmpty(request.GameTypeSource, project.GameTypeSource),
            route_skill = routeSkill,
            slug,
            prototype_record = prototypeRecordPath,
            hard_rules = new[]
            {
                "Treat this contract as the project-specific source of truth for prototype, iteration-plan, execute-next-goal, and needs-fix.",
                "User form fields override type templates, examples, generic RPG defaults, and fallback kit defaults.",
                "Do not replace concrete values from the user form with template defaults unless the field is empty or explicitly ambiguous.",
                "When the form is ambiguous, preserve the ambiguity in the result and mark the related goal as needs_fix instead of silently guessing.",
                "Every route must verify the current work against this contract before reporting succeeded."
            },
            form_fields = new
            {
                hypothesis = request.Hypothesis?.Trim() ?? "",
                core_player_fantasy = request.CorePlayerFantasy?.Trim() ?? "",
                minimum_playable_loop = request.MinimumPlayableLoop?.Trim() ?? "",
                success_criteria = request.SuccessCriteria?.Where(item => !string.IsNullOrWhiteSpace(item)).Select(item => item.Trim()).ToArray() ?? [],
                game_feature = request.GameFeature?.Trim() ?? "",
                core_gameplay_loop = request.CoreGameplayLoop?.Trim() ?? "",
                win_fail_conditions = request.WinFailConditions?.Trim() ?? ""
            },
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        };

        var relativePath = ContractRelativePath();
        var absolutePath = Path.Combine(project.MetaPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(absolutePath)!);
        File.WriteAllText(absolutePath, JsonSerializer.Serialize(payload, JsonOptions), Utf8NoBom);
        return new PrototypeContractSnapshot(relativePath, File.ReadAllText(absolutePath, Encoding.UTF8));
    }

    public PrototypeContractSnapshot Read(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);

        var relativePath = ContractRelativePath();
        var absolutePath = Path.Combine(project.MetaPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
        return File.Exists(absolutePath)
            ? new PrototypeContractSnapshot(relativePath, File.ReadAllText(absolutePath, Encoding.UTF8))
            : new PrototypeContractSnapshot(relativePath, "");
    }

    public static string BuildPromptBlock(PrototypeContractSnapshot contract)
    {
        if (string.IsNullOrWhiteSpace(contract.Json))
        {
            return """
                Project prototype contract:
                - Status: missing
                - Rule: If this route requires prototype-specific implementation, report the missing contract as a blocker instead of inventing defaults.
                """;
        }

        return $"""
            Project prototype contract:
            - Status: present
            - ContractPath: {contract.RelativePath}
            - Mandatory: the JSON below is the per-project hard contract. User form values override templates and generic type defaults.
            - Mandatory: verify the current route output against this contract before reporting succeeded.
            {TrimForPrompt(contract.Json)}
            """;
    }

    private static string ContractRelativePath()
    {
        return Path.Combine("routes", "prototype-contract", "latest.json").Replace('\\', '/');
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        return values.Select(value => value?.Trim()).FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    }

    private static string TrimForPrompt(string value)
    {
        var trimmed = value.Trim();
        return trimmed.Length <= 8000 ? trimmed : trimmed[..8000];
    }
}

public sealed record PrototypeContractSnapshot(string RelativePath, string Json);
