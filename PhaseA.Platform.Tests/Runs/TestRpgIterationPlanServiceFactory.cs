using System.Text.Json;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;

namespace PhaseA.Platform.Tests.Runs;

internal static class TestRpgIterationPlanServiceFactory
{
    public static PrototypeIterationPlanService Create(
        PhaseAMetadataStore store,
        PrototypeRouteStateWriter? routeStateWriter = null)
    {
        return new PrototypeIterationPlanService(
            store,
            routeStateWriter ?? new PrototypeRouteStateWriter(),
            null,
            new SuccessfulRpgPlanCodexClient());
    }

    private sealed class SuccessfulRpgPlanCodexClient : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            var schema = options?.OutputSchemaPath ?? "";
            if (schema.Contains("planning-analysis", StringComparison.OrdinalIgnoreCase))
            {
                const string analysis = """
                {
                  "analysisSummary": "Test planning analysis succeeded.",
                  "fieldCoverage": [
                    { "field": "hypothesis", "status": "partial", "evidence": "test", "missingReason": null },
                    { "field": "minimum_playable_loop", "status": "partial", "evidence": "movement, encounter, battle, reward, return to map", "missingReason": null },
                    { "field": "core_gameplay_loop", "status": "partial", "evidence": "movement-driven encounter, BattleScene, reward loop, return to map", "missingReason": null },
                    { "field": "reward_loop", "status": "partial", "evidence": "reward 3-choice and return to map", "missingReason": null },
                    { "field": "win_fail_conditions", "status": "partial", "evidence": "battle victory and game over rules", "missingReason": null }
                  ]
                }
                """;
                return Task.FromResult(new CodexChatClientResult(true, analysis, null, 0, "", ""));
            }

            if (schema.Contains("goal-plan", StringComparison.OrdinalIgnoreCase))
            {
                return Task.FromResult(new CodexChatClientResult(true, BuildGoalPlan(prompt), null, 0, "", ""));
            }

            if (schema.Contains("evaluation", StringComparison.OrdinalIgnoreCase))
            {
                const string evaluation = """
                {
                  "decision": "ready_to_execute",
                  "summary": "Test evaluation succeeded.",
                  "reason": "The test plan is ready.",
                  "suggestedAction": "Execute the next goal.",
                  "suggestedPromptForRegeneration": null
                }
                """;
                return Task.FromResult(new CodexChatClientResult(true, evaluation, null, 0, "", ""));
            }

            return Task.FromResult(new CodexChatClientResult(false, null, "unexpected_test_schema", 1, "", ""));
        }

        private static string BuildGoalPlan(string prompt)
        {
            var scaffold = ExtractScaffoldGoals(prompt);
            var goals = scaffold.Select(goal => new
            {
                title = goal.Title,
                description = string.IsNullOrWhiteSpace(goal.Description)
                    ? "Test-refined RPG goal description."
                    : goal.Description,
                acceptanceHint = string.IsNullOrWhiteSpace(goal.AcceptanceHint)
                    ? "Test-refined RPG acceptance."
                    : goal.AcceptanceHint
            });
            return JsonSerializer.Serialize(new { goals });
        }

        private static IReadOnlyList<ScaffoldGoal> ExtractScaffoldGoals(string prompt)
        {
            var marker = "Goal scaffold that must be preserved:";
            var markerIndex = prompt.IndexOf(marker, StringComparison.Ordinal);
            if (markerIndex < 0)
            {
                return [];
            }

            var jsonStart = prompt.IndexOf('[', markerIndex);
            if (jsonStart < 0)
            {
                return [];
            }

            var json = ExtractJsonArray(prompt[jsonStart..]);
            if (string.IsNullOrWhiteSpace(json))
            {
                return [];
            }

            try
            {
                using var document = JsonDocument.Parse(json);
                return document.RootElement.EnumerateArray()
                    .Select(item => new ScaffoldGoal(
                        ReadString(item, "Title") ?? ReadString(item, "title") ?? "RPG Test Goal",
                        ReadString(item, "Description") ?? ReadString(item, "description") ?? "Test description.",
                        ReadString(item, "AcceptanceHint") ?? ReadString(item, "acceptanceHint") ?? "Test acceptance."))
                    .ToArray();
            }
            catch (JsonException)
            {
                return [];
            }
        }

        private static string? ExtractJsonArray(string text)
        {
            var depth = 0;
            var inString = false;
            var escaped = false;
            for (var index = 0; index < text.Length; index++)
            {
                var current = text[index];
                if (inString)
                {
                    if (escaped)
                    {
                        escaped = false;
                    }
                    else if (current == '\\')
                    {
                        escaped = true;
                    }
                    else if (current == '"')
                    {
                        inString = false;
                    }

                    continue;
                }

                if (current == '"')
                {
                    inString = true;
                    continue;
                }

                if (current == '[')
                {
                    depth++;
                }
                else if (current == ']')
                {
                    depth--;
                    if (depth == 0)
                    {
                        return text[..(index + 1)];
                    }
                }
            }

            return null;
        }

        private static string? ReadString(JsonElement element, string propertyName)
        {
            return element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
                ? property.GetString()
                : null;
        }

        private sealed record ScaffoldGoal(string Title, string Description, string AcceptanceHint);
    }
}
