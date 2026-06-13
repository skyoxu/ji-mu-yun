using System.Text.Json;

namespace PhaseA.Platform.Runs;

internal sealed class PrototypeNeedsFixRepairLedger
{
    public int StepIndex { get; set; }

    public string CurrentStatus { get; set; } = "unknown";

    public List<PrototypeNeedsFixRepairLedgerBlocker> OpenBlockers { get; set; } = [];

    public List<PrototypeNeedsFixRepairLedgerBlocker> ResolvedBlockers { get; set; } = [];

    public List<PrototypeNeedsFixRepairLedgerBlocker> NewBlockersThisRun { get; set; } = [];

    public PrototypeNeedsFixRepairLedgerRun? LastRun { get; set; }

    public string UpdatedUtc { get; set; } = "";

    public static PrototypeNeedsFixRepairLedger ReadOrCreate(string json, int stepIndex)
    {
        if (!string.IsNullOrWhiteSpace(json))
        {
            try
            {
                var ledger = JsonSerializer.Deserialize<PrototypeNeedsFixRepairLedger>(json, JsonOptions());
                if (ledger is not null)
                {
                    ledger.StepIndex = stepIndex;
                    ledger.OpenBlockers ??= [];
                    ledger.ResolvedBlockers ??= [];
                    ledger.NewBlockersThisRun ??= [];
                    ledger.OpenBlockers = NormalizeLegacyBlockers(ledger.OpenBlockers);
                    ledger.ResolvedBlockers = NormalizeLegacyBlockers(ledger.ResolvedBlockers);
                    ledger.NewBlockersThisRun = NormalizeLegacyBlockers(ledger.NewBlockersThisRun);
                    return ledger;
                }
            }
            catch (JsonException)
            {
                // Keep the route usable even if an old ledger was partially written.
            }
        }

        return new PrototypeNeedsFixRepairLedger
        {
            StepIndex = stepIndex,
            CurrentStatus = "unknown",
            UpdatedUtc = DateTimeOffset.UtcNow.ToString("O")
        };
    }

    public static object UpdateFromRun(
        string existingJson,
        int stepIndex,
        string runId,
        string? assistantClaimedStatus,
        string routeStatus,
        string? iterationGoalStatus,
        string? evidenceJson)
    {
        var ledger = ReadOrCreate(existingJson, stepIndex);
        var now = DateTimeOffset.UtcNow.ToString("O");
        var platformStatus = NormalizeStatus(iterationGoalStatus, routeStatus);
        var currentBlockers = ExtractBlockers(evidenceJson, runId, now).ToList();
        var currentIds = currentBlockers.Select(blocker => blocker.Id).ToHashSet(StringComparer.Ordinal);
        var previousOpen = ledger.OpenBlockers.ToDictionary(blocker => blocker.Id, StringComparer.Ordinal);

        for (var index = 0; index < currentBlockers.Count; index++)
        {
            var blocker = currentBlockers[index];
            if (previousOpen.TryGetValue(blocker.Id, out var existing))
            {
                currentBlockers[index] = blocker with
                {
                    FirstSeenRunId = string.IsNullOrWhiteSpace(existing.FirstSeenRunId) ? blocker.FirstSeenRunId : existing.FirstSeenRunId,
                    FirstSeenUtc = string.IsNullOrWhiteSpace(existing.FirstSeenUtc) ? blocker.FirstSeenUtc : existing.FirstSeenUtc
                };
            }
        }

        var resolvedThisRun = ledger.OpenBlockers
            .Where(blocker => !currentIds.Contains(blocker.Id))
            .Select(blocker => blocker with
            {
                ResolvedRunId = runId,
                ResolvedUtc = now
            })
            .ToList();
        var resolvedIds = ledger.ResolvedBlockers.Select(blocker => blocker.Id).ToHashSet(StringComparer.Ordinal);
        foreach (var blocker in resolvedThisRun)
        {
            if (!resolvedIds.Contains(blocker.Id))
            {
                ledger.ResolvedBlockers.Add(blocker);
            }
        }

        ledger.NewBlockersThisRun = currentBlockers
            .Where(blocker => !previousOpen.ContainsKey(blocker.Id))
            .ToList();
        ledger.OpenBlockers = currentBlockers;
        ledger.CurrentStatus = platformStatus;
        ledger.LastRun = new PrototypeNeedsFixRepairLedgerRun(
            runId,
            assistantClaimedStatus ?? "unknown",
            platformStatus,
            string.Equals(platformStatus, "succeeded", StringComparison.Ordinal));
        ledger.UpdatedUtc = now;
        return ledger;
    }

    public static string BuildPromptBlock(string ledgerJson)
    {
        if (string.IsNullOrWhiteSpace(ledgerJson))
        {
            return "- Status: none";
        }

        var ledger = ReadOrCreate(ledgerJson, 0);
        var open = ledger.OpenBlockers.Count == 0
            ? "- none"
            : string.Join(Environment.NewLine, ledger.OpenBlockers.Take(5).Select(blocker =>
                $"- [{blocker.Priority}] {blocker.Id}; source={blocker.Source}; reason={blocker.Reason}; last_run={blocker.LastSeenRunId}; details={Trim(blocker.Details, 550)}; suggested_fix={Trim(blocker.SuggestedFix, 350)}"));
        var resolved = ledger.ResolvedBlockers.Count == 0
            ? "- none"
            : string.Join(Environment.NewLine, ledger.ResolvedBlockers.TakeLast(3).Select(blocker =>
                $"- {blocker.Id}; resolved_run={blocker.ResolvedRunId ?? "unknown"}"));
        var lastRun = ledger.LastRun is null
            ? "- LastRun: none"
            : $"- LastRun: {ledger.LastRun.RunId}; assistant_claimed_status={ledger.LastRun.AssistantClaimedStatus}; platform_status={ledger.LastRun.PlatformStatus}; accepted_by_platform={ledger.LastRun.AcceptedByPlatform}";

        return $"""
            - Status: {ledger.CurrentStatus}
            {lastRun}
            - Rule: This ledger is continuity memory only. Current platform acceptance diagnosis overrides the ledger when they differ.
            - OpenBlockers:
            {open}
            - RecentlyResolvedBlockers:
            {resolved}
            """;
    }

    private static IReadOnlyList<PrototypeNeedsFixRepairLedgerBlocker> ExtractBlockers(string? evidenceJson, string runId, string now)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return [];
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            var root = document.RootElement;
            var blockers = new List<PrototypeNeedsFixRepairLedgerBlocker>();
            AddAcceptanceBlocker(blockers, root, runId, now);
            AddMutationGuardBlocker(blockers, root, runId, now);
            AddValidationBlocker(blockers, root, "godot_smoke_validation", "godot_smoke", runId, now);
            AddValidationBlocker(blockers, root, "rpg_gdunit_validation", "rpg_gdunit", runId, now);
            return blockers
                .GroupBy(blocker => blocker.Id, StringComparer.Ordinal)
                .Select(group => group.OrderBy(blocker => blocker.Priority).First())
                .OrderBy(blocker => blocker.Priority)
                .ToList();
        }
        catch (JsonException)
        {
            return
            [
                NewBlocker(
                    "evidence:unreadable",
                    "evidence",
                    "evidence_json_unreadable",
                    "The latest run evidence_json could not be parsed.",
                    runId,
                    now,
                    1,
                    "Inspect the latest run logs and repair the concrete validation blocker before reporting completion.")
            ];
        }
    }

    private static void AddAcceptanceBlocker(List<PrototypeNeedsFixRepairLedgerBlocker> blockers, JsonElement root, string runId, string now)
    {
        var status = ReadString(root, "acceptance_validation_status");
        if (string.Equals(status, "passed", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(status, "not_required", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        var reason = ReadString(root, "acceptance_validation_reason");
        var details = ReadString(root, "acceptance_validation_details");
        if (string.IsNullOrWhiteSpace(reason) && string.IsNullOrWhiteSpace(details))
        {
            return;
        }

        blockers.Add(NewBlocker(
            BuildAcceptanceId(reason, details),
            "platform_acceptance",
            reason ?? "unknown",
            details ?? "none",
            runId,
            now,
            1,
            BuildSuggestedFix(reason, details)));
    }

    private static void AddMutationGuardBlocker(List<PrototypeNeedsFixRepairLedgerBlocker> blockers, JsonElement root, string runId, string now)
    {
        if (!root.TryGetProperty("mutation_guard", out var guard) || guard.ValueKind != JsonValueKind.Object)
        {
            return;
        }

        var reason = ReadString(guard, "reason") ?? "unknown";
        var status = ReadString(guard, "status");
        if (string.Equals(status, "passed", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(status, "not_required", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(reason, "not_specialized_prototype_project", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(reason, "not_goal_repair", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        blockers.Add(NewBlocker(
            $"mutation_guard:{NormalizeToken(reason)}",
            "mutation_guard",
            reason,
            BuildViolationDetails(guard),
            runId,
            now,
            2,
            "Undo unrelated files or move the repair back inside the current step scope."));
    }

    private static void AddValidationBlocker(List<PrototypeNeedsFixRepairLedgerBlocker> blockers, JsonElement root, string propertyName, string source, string runId, string now)
    {
        if (!root.TryGetProperty(propertyName, out var validation) || validation.ValueKind != JsonValueKind.Object)
        {
            return;
        }

        var required = ReadBool(validation, "required");
        var passed = ReadBool(validation, "passed");
        if (required == false || passed == true)
        {
            return;
        }

        var reason = ReadValidationReason(validation);
        var scene = ReadValidationScene(validation);
        var suggestedFix = source == "godot_smoke"
            ? BuildGodotSmokeSuggestedFix(reason, scene)
            : "Fix the RPG acceptance test mismatch named by the validation evidence.";
        blockers.Add(NewBlocker(
            $"{source}:{NormalizeToken(reason)}",
            source,
            reason,
            validation.ToString(),
            runId,
            now,
            source == "godot_smoke" ? 3 : 4,
            suggestedFix));
    }

    private static PrototypeNeedsFixRepairLedgerBlocker NewBlocker(
        string id,
        string source,
        string reason,
        string details,
        string runId,
        string now,
        int priority,
        string suggestedFix)
    {
        return new PrototypeNeedsFixRepairLedgerBlocker(
            id,
            source,
            reason,
            Trim(details, 2400),
            runId,
            runId,
            now,
            now,
            priority,
            suggestedFix,
            null,
            null);
    }

    private static List<PrototypeNeedsFixRepairLedgerBlocker> NormalizeLegacyBlockers(IEnumerable<PrototypeNeedsFixRepairLedgerBlocker> blockers)
    {
        return blockers.Select(NormalizeLegacyBlocker).ToList();
    }

    private static PrototypeNeedsFixRepairLedgerBlocker NormalizeLegacyBlocker(PrototypeNeedsFixRepairLedgerBlocker blocker)
    {
        if (!string.Equals(blocker.Source, "godot_smoke", StringComparison.Ordinal) ||
            !string.Equals(blocker.Reason, "unknown", StringComparison.OrdinalIgnoreCase))
        {
            return blocker;
        }

        var reason = TryReadReasonFromDetails(blocker.Details);
        if (string.IsNullOrWhiteSpace(reason))
        {
            return blocker;
        }

        var scene = TryReadSceneFromDetails(blocker.Details);
        return blocker with
        {
            Id = $"godot_smoke:{NormalizeToken(reason)}",
            Reason = reason,
            SuggestedFix = BuildGodotSmokeSuggestedFix(reason, scene)
        };
    }

    private static string BuildAcceptanceId(string? reason, string? details)
    {
        var text = details ?? "";
        if (string.Equals(reason, "core_tests_failed", StringComparison.OrdinalIgnoreCase) &&
            text.Contains("CS0246", StringComparison.OrdinalIgnoreCase) &&
            (text.Contains("Xunit", StringComparison.OrdinalIgnoreCase) ||
             text.Contains("FluentAssertions", StringComparison.OrdinalIgnoreCase)))
        {
            return "platform_acceptance:core_tests_failed:cs0246-test-packages";
        }

        return $"platform_acceptance:{NormalizeToken(reason ?? "unknown")}";
    }

    private static string BuildSuggestedFix(string? reason, string? details)
    {
        var text = details ?? "";
        if (string.Equals(reason, "core_tests_failed", StringComparison.OrdinalIgnoreCase) &&
            text.Contains("CS0246", StringComparison.OrdinalIgnoreCase) &&
            (text.Contains("Xunit", StringComparison.OrdinalIgnoreCase) ||
             text.Contains("FluentAssertions", StringComparison.OrdinalIgnoreCase)))
        {
            return "Fix Game.Core.Tests/Game.Core.Tests.csproj PackageReference entries for xunit, xunit.runner.visualstudio, FluentAssertions, Microsoft.NET.Test.Sdk, and related test packages before changing gameplay/UI.";
        }

        if (string.Equals(reason, "core_tests_failed", StringComparison.OrdinalIgnoreCase) &&
            text.Contains("CS", StringComparison.OrdinalIgnoreCase))
        {
            return "Fix the exact C# compile errors named in acceptance_validation_details first. Keep the repair scoped to the listed files, missing symbols, and error codes; do not continue gameplay/UI/content polish while these compile errors remain open.";
        }

        if (StartsWithReason(reason, "missing_rpg_map_entry_contract"))
        {
            return "Repair the full RPG/JRPG map-entry contract group, not only the first missing_file. Ensure Game.Godot/Prototypes/dq-rpg/MapScene.tscn and Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs exist together, MapScene.tscn has MapScene/TrackLayer/RpgMapAsset/Grid/Overlay/RpgPlayerAsset, and MapScene.cs exposes grid-position mapping, player visibility restore, and stable movement handling. Add RpgEnemyAsset or encounter trigger wiring only when the selected route or latest failure explicitly requires encounter, conflict, or battle.";
        }

        if (StartsWithReason(reason, "missing_rpg_battle_scene_contract"))
        {
            return "Repair the full RPG/JRPG battle-scene contract, not only the first missing token. Ensure Game.Godot/Prototypes/dq-rpg/BattleScene.tscn and Game.Godot/Prototypes/dq-rpg/Scripts/BattleScene.cs exist together, BattleScene.tscn exposes BattleScene, AttackButton, and file-backed Texture2D nodes named RpgPlayerAsset and RpgEnemyAsset, and BattleScene.cs exposes BattleFinished plus ResolveBattle or ResolveAttackTurn battle settlement wiring instead of leaving the battle loop only inside DqRpgPrototype.cs.";
        }

        if (StartsWithReason(reason, "missing_rpg_reward_flow_contract"))
        {
            return "Repair the full RPG/JRPG reward-flow contract. Ensure victory or consequence exposes exactly three understandable reward choices, selecting one calls ApplyReward, closes the reward panel, visibly updates stats or consequence text, returns or refreshes the map, and restores player visibility. A DqRpgPrototype.cs-owned reward panel is valid if it keeps the reward entry, selection, ApplyReward, visible feedback, and map-return contract together.";
        }

        if (StartsWithReason(reason, "missing_required_core_markers"))
        {
            return "Add or restore the exact required markers named in acceptance_validation_reason or acceptance_validation_details. Keep the repair scoped to the current goal capability and represent each missing_marker in runtime code, tests, visible UI text, or a validation-facing contract marker before reporting completion.";
        }

        return reason switch
        {
            "core_tests_failed" => "Fix the concrete core test compile or assertion failure named in acceptance_validation_details.",
            "godot_project_build_failed" => "Fix the concrete Godot build error named in acceptance_validation_details.",
            _ => "Fix the concrete platform acceptance failure named in acceptance_validation_details."
        };
    }

    private static bool StartsWithReason(string? actual, string expected)
    {
        return !string.IsNullOrWhiteSpace(actual) &&
               actual.Trim().StartsWith(expected, StringComparison.OrdinalIgnoreCase);
    }

    private static string BuildGodotSmokeSuggestedFix(string reason, string? scene)
    {
        if (string.Equals(reason, "prototype_main_menu_navigation_failed", StringComparison.OrdinalIgnoreCase))
        {
            return $"Static/platform acceptance already passed; repair only the Godot smoke main-menu navigation failure for {scene ?? "the prototype scene"}. Do not revisit unrelated gameplay or test package work.";
        }

        return "Fix the concrete Godot smoke/runtime validation error named by the validation evidence.";
    }

    private static string? TryReadReasonFromDetails(string? details)
    {
        if (string.IsNullOrWhiteSpace(details))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(details);
            return ReadValidationReason(document.RootElement);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string? TryReadSceneFromDetails(string? details)
    {
        if (string.IsNullOrWhiteSpace(details))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(details);
            return ReadValidationScene(document.RootElement);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string BuildViolationDetails(JsonElement guard)
    {
        if (guard.TryGetProperty("violations", out var violations) && violations.ValueKind == JsonValueKind.Array)
        {
            return violations.ToString();
        }

        return ReadString(guard, "reason") ?? "mutation guard failed";
    }

    private static string NormalizeStatus(string? iterationGoalStatus, string routeStatus)
    {
        if (!string.IsNullOrWhiteSpace(iterationGoalStatus))
        {
            return iterationGoalStatus;
        }

        return string.IsNullOrWhiteSpace(routeStatus) ? "unknown" : routeStatus;
    }

    private static string NormalizeToken(string value)
    {
        var chars = value
            .Trim()
            .ToLowerInvariant()
            .Select(ch => char.IsLetterOrDigit(ch) ? ch : '-')
            .ToArray();
        var compact = new string(chars);
        while (compact.Contains("--", StringComparison.Ordinal))
        {
            compact = compact.Replace("--", "-", StringComparison.Ordinal);
        }

        return compact.Trim('-');
    }

    private static string? ReadString(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static string ReadValidationReason(JsonElement validation)
    {
        var topLevelReason = ReadString(validation, "reason");
        if (!string.IsNullOrWhiteSpace(topLevelReason))
        {
            return topLevelReason;
        }

        if (validation.ValueKind == JsonValueKind.Object &&
            validation.TryGetProperty("smoke", out var smoke) &&
            smoke.ValueKind == JsonValueKind.Object)
        {
            var smokeReason = ReadString(smoke, "reason");
            if (!string.IsNullOrWhiteSpace(smokeReason))
            {
                return smokeReason;
            }
        }

        return "unknown";
    }

    private static string? ReadValidationScene(JsonElement validation)
    {
        var topLevelScene = ReadString(validation, "scene");
        if (!string.IsNullOrWhiteSpace(topLevelScene))
        {
            return topLevelScene;
        }

        if (validation.ValueKind == JsonValueKind.Object &&
            validation.TryGetProperty("smoke", out var smoke) &&
            smoke.ValueKind == JsonValueKind.Object)
        {
            return ReadString(smoke, "scene");
        }

        return null;
    }

    private static bool? ReadBool(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               (value.ValueKind == JsonValueKind.True || value.ValueKind == JsonValueKind.False)
            ? value.GetBoolean()
            : null;
    }

    private static string Trim(string? value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "none";
        }

        var trimmed = value.Trim();
        return trimmed.Length <= maxLength ? trimmed : trimmed[..maxLength];
    }

    private static JsonSerializerOptions JsonOptions()
    {
        return new JsonSerializerOptions(JsonSerializerDefaults.Web)
        {
            WriteIndented = true
        };
    }
}

internal sealed record PrototypeNeedsFixRepairLedgerBlocker(
    string Id,
    string Source,
    string Reason,
    string Details,
    string FirstSeenRunId,
    string LastSeenRunId,
    string FirstSeenUtc,
    string LastSeenUtc,
    int Priority,
    string SuggestedFix,
    string? ResolvedRunId,
    string? ResolvedUtc);

internal sealed record PrototypeNeedsFixRepairLedgerRun(
    string RunId,
    string AssistantClaimedStatus,
    string PlatformStatus,
    bool AcceptedByPlatform);
