using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

internal static class ProjectAdminReviewQueueSidecarWriter
{
    private static readonly UTF8Encoding Utf8NoBom = new(false);

    public static async Task WriteAsync(
        ProjectSnapshot project,
        IReadOnlyList<ProjectAdminReviewQueueEntry> entries,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(entries);

        var path = Path.Combine(project.RepoPath, "meta", "routes", "admin-review-queue", "latest.json");
        var hasBlockingEntry = entries.Any(entry => ProjectAdminReviewQueuePolicy.IsBlocking(entry));
        var hasDeferredEntry = entries.Any(entry => string.Equals(entry.Status, "deferred", StringComparison.Ordinal));
        var payload = JsonSerializer.Serialize(new
        {
            schema_version = "project-admin-review-queue.v1",
            route = "admin-review-queue",
            status = hasBlockingEntry ? "blocked" : hasDeferredEntry ? "unknown" : "ready",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            entry_status_dimension = RouteStatusVocabulary.AdminReviewQueue,
            entry_status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.AdminReviewQueue),
            status_authority = "metadata_db_live",
            live_recheck_required = hasDeferredEntry,
            updated_utc = DateTimeOffset.UtcNow.ToString("O"),
            entries = entries.Select(entry => new
            {
                route_id = entry.RouteId,
                requirement_id = entry.RequirementId,
                severity = entry.Severity,
                status = entry.Status,
                is_blocking = string.Equals(entry.Status, "deferred", StringComparison.Ordinal)
                    ? (bool?)null
                    : ProjectAdminReviewQueuePolicy.IsBlocking(entry),
                user_safe_summary = string.Equals(entry.Status, "deferred", StringComparison.Ordinal)
                    ? "Deferred review status requires a live metadata recheck."
                    : ProjectAdminReviewQueuePolicy.IsBlocking(entry)
                    ? "Administrative review is required before this route can continue."
                    : "Administrative review is not currently blocking this route."
            }).ToArray()
        }, new JsonSerializerOptions { WriteIndented = true });

        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var tempPath = Path.Combine(Path.GetDirectoryName(path)!, $".{Path.GetFileName(path)}.{Guid.NewGuid():N}.tmp");
        try
        {
            await File.WriteAllTextAsync(tempPath, payload, Utf8NoBom, cancellationToken);
            File.Move(tempPath, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(tempPath))
            {
                File.Delete(tempPath);
            }
        }
    }
}
