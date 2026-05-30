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

    private static readonly PrototypeInputFieldDefinition[] InputFieldDefinitions =
    [
        new("slug", "Prototype identifier and current prototype folder/name anchor.", "Prototype folder, prototype scene name, route state, artifacts."),
        new("game_name", "Player-facing game name.", "Prototype title, menu copy, visible UI labels when useful."),
        new("game_type", "Normalized type route selected by the platform.", "Route skill, type kit, default scene/asset rules."),
        new("game_type_source", "Original game type source supplied by the project/user.", "Type-specific skill selection and ambiguity handling."),
        new("hypothesis", "What the prototype must validate.", "Scenario framing, final report, acceptance focus."),
        new("core_player_fantasy", "What the player should feel or do.", "Primary verbs, UI feedback, scene presentation."),
        new("minimum_playable_loop", "Smallest complete playable loop.", "Scene flow, state transitions, smoke/acceptance target."),
        new("success_criteria", "User-visible pass criteria.", "Iteration goals, final validation checklist, needs-fix blockers."),
        new("game_feature", "Concrete feature set to implement.", "Gameplay mechanics, scene objects, scripts, tests."),
        new("core_gameplay_loop", "Repeated gameplay sequence.", "Map/battle/reward/control flow and loop continuity."),
        new("win_fail_conditions", "Victory and failure conditions.", "Settlement UI, game-over/retry, battle/map outcome logic.")
    ];

    public PrototypeContractSnapshot WriteFromRequest(
        ProjectSnapshot project,
        PrototypeWorkflowRequest request,
        string prototypeRecordPath,
        string slug)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(request);

        var routeSkill = PrototypeRouteSkillPolicy.Resolve(project);
        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var payload = new
        {
            schema_version = 1,
            route = "prototype-contract",
            project_id = project.ProjectId,
            game_name = FirstNonEmpty(request.GameName, project.GameName),
            game_type = FirstNonEmpty(request.GameType, request.GameTypeSource, project.GameTypeSource),
            game_type_source = FirstNonEmpty(request.GameTypeSource, project.GameTypeSource),
            route_skill = routeSkill,
            game_type_profile = routeProfile,
            slug,
            prototype_record = prototypeRecordPath,
            hard_rules = new[]
            {
                "Treat this contract as the project-specific source of truth for prototype, iteration-plan, execute-next-goal, and needs-fix.",
                "User form fields override type templates, examples, generic RPG defaults, and fallback kit defaults.",
                "Do not replace concrete values from the user form with template defaults unless the field is empty or explicitly ambiguous.",
                "When the form is ambiguous, preserve the ambiguity in the result and mark the related goal as needs_fix instead of silently guessing.",
                "Every route must verify the current work against this contract before reporting succeeded.",
                "Every non-empty input field must be traceable to gameplay, UI, scene flow, asset choice, test coverage, or an explicit needs_fix blocker.",
                "If a field cannot be implemented in the current route, keep it in the traceability notes and produce a concrete follow-up or needs_fix reason."
            },
            form_fields = new
            {
                slug,
                game_name = FirstNonEmpty(request.GameName, project.GameName),
                game_type = FirstNonEmpty(request.GameType, request.GameTypeSource, project.GameTypeSource),
                game_type_source = FirstNonEmpty(request.GameTypeSource, project.GameTypeSource),
                hypothesis = request.Hypothesis?.Trim() ?? "",
                core_player_fantasy = request.CorePlayerFantasy?.Trim() ?? "",
                minimum_playable_loop = request.MinimumPlayableLoop?.Trim() ?? "",
                success_criteria = request.SuccessCriteria?.Where(item => !string.IsNullOrWhiteSpace(item)).Select(item => item.Trim()).ToArray() ?? [],
                game_feature = request.GameFeature?.Trim() ?? "",
                core_gameplay_loop = request.CoreGameplayLoop?.Trim() ?? "",
                win_fail_conditions = request.WinFailConditions?.Trim() ?? ""
            },
            input_traceability = BuildTraceability(request, project, slug),
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
            - Mandatory: consume form_fields and input_traceability before planning, coding, validating, or repairing.
            - Mandatory: verify the current route output against this contract before reporting succeeded.
            - Mandatory: if any non-empty field is not reflected in gameplay, UI, scene flow, tests, or final acceptance, report needs_fix instead of succeeded.
            {TrimForPrompt(CompactForPrompt(contract.Json))}
            """;
    }

    private static object[] BuildTraceability(PrototypeWorkflowRequest request, ProjectSnapshot project, string slug)
    {
        var values = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
        {
            ["slug"] = slug,
            ["game_name"] = FirstNonEmpty(request.GameName, project.GameName),
            ["game_type"] = FirstNonEmpty(request.GameType, request.GameTypeSource, project.GameTypeSource),
            ["game_type_source"] = FirstNonEmpty(request.GameTypeSource, project.GameTypeSource),
            ["hypothesis"] = request.Hypothesis?.Trim() ?? "",
            ["core_player_fantasy"] = request.CorePlayerFantasy?.Trim() ?? "",
            ["minimum_playable_loop"] = request.MinimumPlayableLoop?.Trim() ?? "",
            ["success_criteria"] = request.SuccessCriteria?.Where(item => !string.IsNullOrWhiteSpace(item)).Select(item => item.Trim()).ToArray() ?? [],
            ["game_feature"] = request.GameFeature?.Trim() ?? "",
            ["core_gameplay_loop"] = request.CoreGameplayLoop?.Trim() ?? "",
            ["win_fail_conditions"] = request.WinFailConditions?.Trim() ?? ""
        };

        return InputFieldDefinitions
            .Select(definition =>
            {
                var rawValue = values.TryGetValue(definition.Key, out var value) ? value : null;
                var hasValue = rawValue switch
                {
                    string text => !string.IsNullOrWhiteSpace(text),
                    string[] items => items.Length > 0,
                    IReadOnlyCollection<string> items => items.Count > 0,
                    _ => rawValue is not null
                };
                return new
                {
                    field = definition.Key,
                    value = rawValue,
                    required = hasValue,
                    semantic_role = definition.SemanticRole,
                    must_reflect_in = definition.MustReflectIn,
                    route_rule = hasValue
                        ? "Implement or explicitly preserve this field as a needs_fix blocker; do not silently drop it."
                        : "Empty field; templates may provide fallback context."
                };
            })
            .Cast<object>()
            .ToArray();
    }

    private static string ContractRelativePath()
    {
        return Path.Combine("routes", "prototype-contract", "latest.json").Replace('\\', '/');
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        return values.Select(value => value?.Trim()).FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    }

    private static string CompactForPrompt(string value)
    {
        try
        {
            using var document = JsonDocument.Parse(value);
            var root = document.RootElement;
            var compact = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
            foreach (var propertyName in new[] { "form_fields", "input_traceability", "route_skill", "game_type_profile" })
            {
                if (root.TryGetProperty(propertyName, out var property))
                {
                    compact[propertyName] = property.Clone();
                }
            }

            return compact.Count == 0
                ? value
                : JsonSerializer.Serialize(compact, JsonOptions);
        }
        catch (JsonException)
        {
            return value;
        }
    }

    private static string TrimForPrompt(string value)
    {
        var trimmed = value.Trim();
        return trimmed.Length <= 3500 ? trimmed : trimmed[..3500];
    }
}

public sealed record PrototypeContractSnapshot(string RelativePath, string Json);

internal sealed record PrototypeInputFieldDefinition(string Key, string SemanticRole, string MustReflectIn);
