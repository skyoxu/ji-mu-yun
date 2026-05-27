using System.Text.Json;
using System.Text.Json.Nodes;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeIterationPlanningAnalysisUpdater
{
    private static readonly string[] CoreContractFields =
    [
        "hypothesis",
        "core_player_fantasy",
        "minimum_playable_loop",
        "success_criteria",
        "game_feature",
        "core_gameplay_loop",
        "win_fail_conditions"
    ];

    private static readonly string[] FinalAcceptanceFields =
    [
        "hypothesis",
        "core_player_fantasy",
        "minimum_playable_loop",
        "success_criteria",
        "game_feature",
        "core_gameplay_loop",
        "win_fail_conditions",
        "reward_loop"
    ];

    public static void Refresh(
        PrototypeRouteStateWriter stateWriter,
        ProjectSnapshot project,
        string iterationPlanState,
        ProjectIterationGoalSnapshot goal,
        string goalStatus,
        string publicSummary,
        string updatedUtc,
        string sessionSummary)
    {
        if (string.IsNullOrWhiteSpace(iterationPlanState))
        {
            return;
        }

        try
        {
            var root = JsonNode.Parse(iterationPlanState) as JsonObject;
            if (root is null)
            {
                return;
            }

            var analysis = root["planning_analysis"] as JsonObject;
            if (analysis is null)
            {
                return;
            }

            var fieldCoverage = analysis["fieldCoverage"] as JsonArray;
            if (fieldCoverage is not null)
            {
                foreach (var field in ResolveAffectedPlanningFields(goal))
                {
                    UpsertPlanningField(fieldCoverage, field, goalStatus, publicSummary);
                }
            }

            var previousSummary = analysis["analysisSummary"]?.GetValue<string>() ?? "";
            analysis["analysisSummary"] = BuildUpdatedPlanningSummary(previousSummary, goal, goalStatus, sessionSummary);
            root["planning_analysis"] = analysis;
            stateWriter.WriteIterationPlanState(project, root);
            stateWriter.WriteIterationPlanAnalysisState(project, new
            {
                route = "iteration-plan",
                goal_index = goal.GoalIndex,
                planning_analysis = analysis.Deserialize<object>(),
                updated_utc = updatedUtc
            });
        }
        catch (Exception)
        {
        }
    }

    private static IReadOnlyList<string> ResolveAffectedPlanningFields(ProjectIterationGoalSnapshot goal)
    {
        var text = string.Join(" ", goal.Title ?? "", goal.Description ?? "", goal.AcceptanceHint ?? "").ToLowerInvariant();
        var fields = new List<string>();

        if (ContainsAny(text, "contract", "合同", "traceability", "需求表单", "漂移"))
        {
            fields.AddRange(CoreContractFields);
        }

        if (ContainsAny(text, "地图", "map", "start adventure", "遇敌", "encounter"))
        {
            fields.Add("minimum_playable_loop");
            fields.Add("core_gameplay_loop");
        }

        if (ContainsAny(text, "战斗", "battle", "结算"))
        {
            fields.Add("core_gameplay_loop");
            fields.Add("success_criteria");
        }

        if (ContainsAny(text, "奖励", "reward", "3 选 1", "三选一"))
        {
            fields.Add("reward_loop");
            fields.Add("success_criteria");
        }

        if (ContainsAny(text, "胜负", "game over", "victory", "失败条件"))
        {
            fields.Add("win_fail_conditions");
            fields.Add("success_criteria");
        }

        if (ContainsAny(text, "可读性", "乱码", "readability", "中文产物"))
        {
            fields.Add("success_criteria");
        }

        if (ContainsAny(text, "final acceptance", "最终验收", "全量验收"))
        {
            fields.AddRange(FinalAcceptanceFields);
        }

        return fields.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
    }

    private static void UpsertPlanningField(JsonArray fieldCoverage, string field, string goalStatus, string publicSummary)
    {
        JsonObject? target = null;
        foreach (var node in fieldCoverage)
        {
            if (node is not JsonObject obj)
            {
                continue;
            }

            var name = obj["field"]?.GetValue<string>() ?? "";
            if (string.Equals(name, field, StringComparison.OrdinalIgnoreCase))
            {
                target = obj;
                break;
            }
        }

        target ??= new JsonObject { ["field"] = field };
        target["status"] = string.Equals(goalStatus, "succeeded", StringComparison.OrdinalIgnoreCase) ? "completed" : "partial";
        target["evidence"] = TrimForState(publicSummary, 120);
        target["missingReason"] = string.Equals(goalStatus, "succeeded", StringComparison.OrdinalIgnoreCase)
            ? null
            : "当前目标执行后仍需补充或修复。";

        if (!fieldCoverage.Contains(target))
        {
            fieldCoverage.Add(target);
        }
    }

    private static string BuildUpdatedPlanningSummary(string previousSummary, ProjectIterationGoalSnapshot goal, string goalStatus, string sessionSummary)
    {
        var action = string.Equals(goalStatus, "succeeded", StringComparison.OrdinalIgnoreCase) ? "已收敛" : "已部分收敛";
        var current = $"{goal.Title} {action}。{sessionSummary}";
        if (string.IsNullOrWhiteSpace(previousSummary))
        {
            return current;
        }

        return TrimForState($"{previousSummary} {current}", 240);
    }

    private static string TrimForState(string value, int maxLength)
    {
        var trimmed = (value ?? "").Trim();
        return trimmed.Length <= maxLength ? trimmed : $"{trimmed[..maxLength]}...";
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.OrdinalIgnoreCase));
    }
}
