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

    public static bool HasDeferredRecheckTrigger(ProjectAdminReviewQueueEntry entry)
    {
        if (entry.Status != "deferred")
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(entry.DecisionMetadataJson);
            return HasNonEmptyString(document.RootElement, "recheck_trigger");
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool HasActiveDeferredWindow(string metadataJson, string routeId, DateTimeOffset now)
    {
        try
        {
            using var document = JsonDocument.Parse(metadataJson);
            var root = document.RootElement;
            var hasExpiry = root.TryGetProperty("deferred_until_utc", out var untilElement) &&
                            untilElement.ValueKind == JsonValueKind.String &&
                            !string.IsNullOrWhiteSpace(untilElement.GetString());
            var hasValidFutureExpiry = hasExpiry &&
                                       DateTimeOffset.TryParse(untilElement.GetString(), out var until) &&
                                       until > now;
            if (!HasNonEmptyString(root, "deferred_owner") ||
                (hasExpiry && !hasValidFutureExpiry) ||
                (!hasValidFutureExpiry && !HasNonEmptyString(root, "recheck_trigger")) ||
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

    private static bool HasNonEmptyString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String &&
               !string.IsNullOrWhiteSpace(value.GetString());
    }
}
