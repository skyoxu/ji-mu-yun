using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Prototypes;

public interface IProjectGameTypeMatchService
{
    Task<ProjectGameTypeMatchEvidence> ResolveAsync(string gameTypeSource, CancellationToken cancellationToken);
}

public sealed class ProjectGameTypeMatchService : IProjectGameTypeMatchService
{
    private readonly GameTypeGuideCatalog _catalog;
    private readonly ISteamGameTypeMetadataProvider? _steamProvider;
    private readonly NodeExecutionOptions? _options;

    public ProjectGameTypeMatchService(NodeExecutionOptions options, ISteamGameTypeMetadataProvider steamProvider)
        : this(options.GameTypeGuides, steamProvider, options)
    {
    }

    private ProjectGameTypeMatchService(
        GameTypeGuideCatalog catalog,
        ISteamGameTypeMetadataProvider? steamProvider,
        NodeExecutionOptions? options)
    {
        _catalog = catalog;
        _steamProvider = steamProvider;
        _options = options;
    }

    public static IProjectGameTypeMatchService Offline(NodeExecutionOptions options)
    {
        return new ProjectGameTypeMatchService(options.GameTypeGuides, null, options);
    }

    public async Task<ProjectGameTypeMatchEvidence> ResolveAsync(string gameTypeSource, CancellationToken cancellationToken)
    {
        var now = DateTimeOffset.UtcNow.ToString("O");
        if (_steamProvider is null)
        {
            return new ProjectGameTypeMatchEvidence(
                1,
                "steam_unavailable",
                "steam_provider_not_configured",
                "steam",
                gameTypeSource.Trim(),
                "",
                "",
                [],
                [],
                [],
                [],
                "",
                "",
                0,
                [],
                "",
                _catalog.CatalogHash,
                now,
                now)
            {
                SteamAttemptedQueries = string.IsNullOrWhiteSpace(gameTypeSource) ? [] : [gameTypeSource.Trim()]
            };
        }

        var steam = await _steamProvider.ResolveAsync(gameTypeSource, cancellationToken);
        if (!string.Equals(steam.Status, "resolved", StringComparison.Ordinal))
        {
            return new ProjectGameTypeMatchEvidence(
                1,
                SteamFailureStatus(steam.StatusReason),
                steam.StatusReason,
                "steam",
                gameTypeSource.Trim(),
                steam.SteamAppId,
                steam.SteamName,
                steam.Tags,
                steam.Categories,
                steam.Genres,
                [],
                "",
                "",
                0,
                [],
                "",
                _catalog.CatalogHash,
                now,
                now)
            {
                SteamResolvedQuery = steam.ResolvedQuery,
                SteamAttemptedQueries = steam.AttemptedQueries
            };
        }

        var normalizedTags = GameTypeGuideCatalog.NormalizeTags(steam.Tags.Concat(steam.Categories).Concat(steam.Genres).ToArray());
        var match = _catalog.MatchByGenreTags(normalizedTags);
        var evidence = new ProjectGameTypeMatchEvidence(
            1,
            match.Status,
            match.StatusReason,
            "steam",
            gameTypeSource.Trim(),
            steam.SteamAppId,
            steam.SteamName,
            steam.Tags,
            steam.Categories,
            steam.Genres,
            match.NormalizedGenreTags,
            match.MatchedGameTypeId,
            match.MatchedGuidePath,
            match.MatchScore,
            match.CandidateScores,
            match.MissingGuidePath,
            _catalog.CatalogHash,
            now,
            now)
        {
            SteamResolvedQuery = steam.ResolvedQuery,
            SteamAttemptedQueries = steam.AttemptedQueries
        };
        return evidence with
        {
            ContractSnapshot = NodeExecutionOptions.GameTypeContract(_options, evidence)
        };
    }

    private static string SteamFailureStatus(string statusReason)
    {
        return statusReason switch
        {
            "steam_app_not_found" => "steam_not_found",
            "steam_query_empty" => "steam_not_found",
            _ => "steam_unavailable"
        };
    }
}
