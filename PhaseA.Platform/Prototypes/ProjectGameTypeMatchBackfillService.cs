using System.Text.Json;
using Microsoft.Extensions.Logging;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;

namespace PhaseA.Platform.Prototypes;

public sealed class ProjectGameTypeMatchBackfillService
{
    private static readonly HashSet<string> RetryableStatusReasons = new(StringComparer.Ordinal)
    {
        "not_resolved",
        "invalid_match_json",
        "game_type_match_failed",
        "game_type_match_cancelled",
        "multiple_game_types_have_close_scores",
        "steam_app_not_found",
        "steam_lookup_timeout",
        "steam_lookup_http_failed",
        "steam_lookup_json_invalid",
        "steam_unavailable",
        "steam_provider_not_configured"
    };

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly IProjectGameTypeMatchService _gameTypeMatchService;
    private readonly ILogger<ProjectGameTypeMatchBackfillService>? _logger;

    public ProjectGameTypeMatchBackfillService(
        PhaseAMetadataStore metadataStore,
        IProjectGameTypeMatchService gameTypeMatchService,
        ILogger<ProjectGameTypeMatchBackfillService>? logger = null)
    {
        _metadataStore = metadataStore;
        _gameTypeMatchService = gameTypeMatchService;
        _logger = logger;
    }

    public async Task<ProjectSnapshot> EnsureResolvedAsync(
        ProjectSnapshot project,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(project);

        var current = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        if (!ShouldBackfill(project.GameTypeMatchJson, current))
        {
            return project;
        }

        ProjectGameTypeMatchEvidence evidence;
        try
        {
            evidence = await _gameTypeMatchService.ResolveAsync(project.GameTypeSource, cancellationToken);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            evidence = ProjectGameTypeMatchEvidence.Empty("game_type_match_backfill_cancelled");
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Game type match backfill failed for project {ProjectId}.", project.ProjectId);
            evidence = ProjectGameTypeMatchEvidence.Empty("game_type_match_backfill_failed");
        }

        var json = evidence.ToJson();
        await _metadataStore.UpdateProjectGameTypeMatchAsync(project.ProjectId, json, cancellationToken);
        if (!evidence.IsMatched)
        {
            await RecordFailureBestEffortAsync(project, evidence, cancellationToken);
        }

        return project with { GameTypeMatchJson = json };
    }

    internal static bool ShouldBackfill(string? rawJson, ProjectGameTypeMatchEvidence evidence)
    {
        if (string.IsNullOrWhiteSpace(rawJson) || string.Equals(rawJson.Trim(), "{}", StringComparison.Ordinal))
        {
            return true;
        }

        if (evidence.IsMatched)
        {
            return false;
        }

        if (string.IsNullOrWhiteSpace(evidence.ReferenceQuery) ||
            string.IsNullOrWhiteSpace(evidence.EvidenceSource) ||
            string.Equals(evidence.Status, "unresolved", StringComparison.Ordinal))
        {
            return true;
        }

        return RetryableStatusReasons.Contains(evidence.StatusReason);
    }

    private async Task RecordFailureBestEffortAsync(
        ProjectSnapshot project,
        ProjectGameTypeMatchEvidence evidence,
        CancellationToken cancellationToken)
    {
        try
        {
            await _metadataStore.RecordProjectGameTypeMatchFailureAsync(new ProjectGameTypeMatchFailureCommand(
                project.AccountId,
                project.ProjectId,
                project.Name,
                project.GameName,
                project.GameTypeSource,
                evidence.Status,
                evidence.StatusReason,
                evidence.ReferenceQuery,
                JsonSerializer.Serialize(evidence.NormalizedGenreTags, ProjectGameTypeMatchEvidence.JsonOptions),
                JsonSerializer.Serialize(evidence.CandidateScores, ProjectGameTypeMatchEvidence.JsonOptions),
                evidence.MissingGuidePath,
                evidence.MatchedGameTypeId,
                evidence.MatchedGuidePath,
                evidence.SteamAppId,
                evidence.SteamName,
                evidence.SteamResolvedQuery,
                JsonSerializer.Serialize(evidence.SteamAttemptedQueries, ProjectGameTypeMatchEvidence.JsonOptions)), cancellationToken);
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Failed to record game type match backfill failure for project {ProjectId}.", project.ProjectId);
        }
    }
}
