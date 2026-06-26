using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeRouteStateSelection
{
    public static string SelectCurrentNeedsFixState(
        string needsFixState,
        string executeNextGoalState,
        string sessionId,
        ProjectIterationGoalSnapshot goal)
    {
        if (string.IsNullOrWhiteSpace(needsFixState))
        {
            return "";
        }

        var match = RouteStateMatchesCurrentGoal(needsFixState, sessionId, goal);
        if (match == RouteStateGoalMatch.Current)
        {
            return needsFixState;
        }

        if (match is RouteStateGoalMatch.Stale or RouteStateGoalMatch.Invalid or RouteStateGoalMatch.Legacy)
        {
            return "";
        }

        if (string.IsNullOrWhiteSpace(executeNextGoalState))
        {
            return needsFixState;
        }

        var executeNextMatch = RouteStateMatchesCurrentGoal(executeNextGoalState, sessionId, goal);
        return executeNextMatch == RouteStateGoalMatch.Current ? "" : needsFixState;
    }

    public static string SelectCurrentExecuteNextGoalState(
        string executeNextGoalState,
        string sessionId,
        ProjectIterationGoalSnapshot goal)
    {
        if (string.IsNullOrWhiteSpace(executeNextGoalState))
        {
            return "";
        }

        var match = RouteStateMatchesCurrentGoal(executeNextGoalState, sessionId, goal);
        return match == RouteStateGoalMatch.Current ? executeNextGoalState : "";
    }

    public static IReadOnlyList<string> SelectCurrentRouteStates(
        string needsFixState,
        string executeNextGoalState,
        string sessionId,
        ProjectIterationGoalSnapshot goal)
    {
        var selectedNeedsFixState = SelectCurrentNeedsFixState(needsFixState, executeNextGoalState, sessionId, goal);
        var selectedExecuteNextGoalState = SelectCurrentExecuteNextGoalState(executeNextGoalState, sessionId, goal);
        return new[] { selectedNeedsFixState, selectedExecuteNextGoalState }
            .Where(static state => !string.IsNullOrWhiteSpace(state))
            .Distinct(StringComparer.Ordinal)
            .ToArray();
    }

    private static RouteStateGoalMatch RouteStateMatchesCurrentGoal(
        string routeState,
        string sessionId,
        ProjectIterationGoalSnapshot goal)
    {
        try
        {
            using var document = JsonDocument.Parse(routeState);
            var root = document.RootElement;
            var stateSessionId = ReadString(root, "session_id");
            var stateGoalId = ReadString(root, "goal_id");
            var stateGoalIndex = ReadInt(root, "goal_index");
            var hasStrongIdentity = !string.IsNullOrWhiteSpace(stateSessionId) ||
                                    !string.IsNullOrWhiteSpace(stateGoalId);
            if (!hasStrongIdentity)
            {
                return RouteStateGoalMatch.Legacy;
            }

            if (!string.IsNullOrWhiteSpace(stateSessionId) &&
                !string.Equals(stateSessionId, sessionId, StringComparison.Ordinal))
            {
                return RouteStateGoalMatch.Stale;
            }

            if (!string.IsNullOrWhiteSpace(stateGoalId) &&
                !string.Equals(stateGoalId, goal.GoalId, StringComparison.Ordinal))
            {
                return RouteStateGoalMatch.Stale;
            }

            if (stateGoalIndex.HasValue && stateGoalIndex.Value != goal.GoalIndex)
            {
                return RouteStateGoalMatch.Stale;
            }

            return RouteStateGoalMatch.Current;
        }
        catch (JsonException)
        {
            return RouteStateGoalMatch.Invalid;
        }
    }

    private static string? ReadString(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static int? ReadInt(JsonElement root, string propertyName)
    {
        if (root.ValueKind != JsonValueKind.Object ||
            !root.TryGetProperty(propertyName, out var value))
        {
            return null;
        }

        if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var number))
        {
            return number;
        }

        if (value.ValueKind == JsonValueKind.String &&
            int.TryParse(value.GetString(), out var parsed))
        {
            return parsed;
        }

        return null;
    }

    private enum RouteStateGoalMatch
    {
        Current,
        Stale,
        Legacy,
        Invalid
    }
}
