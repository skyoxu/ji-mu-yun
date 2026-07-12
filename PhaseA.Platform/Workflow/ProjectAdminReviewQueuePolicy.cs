using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Workflow;

public static class ProjectAdminReviewQueuePolicy
{
    public static readonly IReadOnlySet<string> InputStatuses = new HashSet<string>(
        ["open"],
        StringComparer.Ordinal);

    public static readonly IReadOnlySet<string> DecisionStatuses = new HashSet<string>(
        ["approved", "deferred", "rejected", "backlog", "resolved"],
        StringComparer.Ordinal);

    public static readonly IReadOnlySet<string> PersistedStatuses = new HashSet<string>(
        ["open", "approved", "deferred", "rejected", "backlog", "resolved", "superseded"],
        StringComparer.Ordinal);

    public static bool IsBlocking(string status)
    {
        return status is "open" or "rejected" or "backlog";
    }

    public static bool IsBlocking(ProjectAdminReviewQueueEntry entry, DateTimeOffset? now = null)
    {
        if (IsBlocking(entry.Status))
        {
            return true;
        }

        return entry.Status == "deferred" && !HasActiveDeferredWindow(entry.DecisionMetadataJson, entry.RouteId, now ?? DateTimeOffset.UtcNow);
    }

    public static bool IsCleared(string status)
    {
        return status is "approved" or "deferred" or "resolved";
    }

    public static bool IsCleared(ProjectAdminReviewQueueEntry entry, DateTimeOffset? now = null)
    {
        return IsCleared(entry.Status) && !IsBlocking(entry, now);
    }

    private static bool HasActiveDeferredWindow(string metadataJson, string routeId, DateTimeOffset now)
    {
        try
        {
            using var document = JsonDocument.Parse(metadataJson);
            var root = document.RootElement;
            if (!root.TryGetProperty("deferred_until_utc", out var untilElement) ||
                untilElement.ValueKind != JsonValueKind.String ||
                !DateTimeOffset.TryParse(untilElement.GetString(), out var until) ||
                until <= now ||
                !root.TryGetProperty("affected_routes", out var routes) ||
                routes.ValueKind != JsonValueKind.Array)
            {
                return false;
            }

            return routes.EnumerateArray().Any(item =>
                item.ValueKind == JsonValueKind.String &&
                string.Equals(item.GetString()?.Trim(), routeId, StringComparison.Ordinal));
        }
        catch (JsonException)
        {
            return false;
        }
    }
}
