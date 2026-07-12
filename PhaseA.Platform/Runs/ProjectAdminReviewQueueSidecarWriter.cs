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
        var payload = JsonSerializer.Serialize(new
        {
            schema_version = "project-admin-review-queue.v1",
            route = "admin-review-queue",
            status = entries.Any(entry => ProjectAdminReviewQueuePolicy.IsBlocking(entry)) ? "blocked" : "ready",
            status_dimension = "admin_review_queue",
            status_allowed_values = new[] { "open", "approved", "deferred", "rejected", "backlog", "superseded", "resolved" },
            updated_utc = DateTimeOffset.UtcNow.ToString("O"),
            entries = entries.Select(entry => new
            {
                entry_id = entry.Id,
                route_id = entry.RouteId,
                requirement_id = entry.RequirementId,
                severity = entry.Severity,
                blocking_reason = entry.BlockingReason,
                source_artifact_path = entry.SourceArtifactPath,
                evidence_refs = JsonNodeOrString(entry.EvidenceRefsJson),
                status = entry.Status,
                decision_status = entry.DecisionStatus,
                decision_by = entry.DecisionActorAccountId,
                decision_reason = entry.DecisionReason,
                decision_metadata = JsonNodeOrString(entry.DecisionMetadataJson),
                decision_version = entry.DecisionVersion,
                decided_utc = entry.DecidedUtc,
                project_deleted_utc = entry.ProjectDeletedUtc,
                supersedes_entry_id = entry.SupersedesEntryId,
                superseded_by_entry_id = entry.SupersededByEntryId
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

    private static object JsonNodeOrString(string value)
    {
        try
        {
            return JsonSerializer.Deserialize<JsonElement>(value);
        }
        catch (JsonException)
        {
            return value;
        }
    }
}
