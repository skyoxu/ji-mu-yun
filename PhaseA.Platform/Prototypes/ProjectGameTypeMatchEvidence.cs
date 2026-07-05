using System.Text.Json;
using System.Text.Json.Serialization;

namespace PhaseA.Platform.Prototypes;

public sealed record ProjectGameTypeMatchEvidence(
    int SchemaVersion,
    string Status,
    string StatusReason,
    string EvidenceSource,
    string ReferenceQuery,
    string SteamAppId,
    string SteamName,
    IReadOnlyList<string> SteamTags,
    IReadOnlyList<string> SteamCategories,
    IReadOnlyList<string> SteamGenres,
    IReadOnlyList<string> NormalizedGenreTags,
    string MatchedGameTypeId,
    string MatchedGuidePath,
    int MatchScore,
    IReadOnlyList<GameTypeGuideCandidate> CandidateScores,
    string MissingGuidePath,
    string CatalogHash,
    string CreatedUtc,
    string UpdatedUtc)
{
    public bool IsMatched => string.Equals(Status, "matched", StringComparison.Ordinal);

    public static ProjectGameTypeMatchEvidence Empty(string statusReason = "not_resolved")
    {
        var now = DateTimeOffset.UtcNow.ToString("O");
        return new ProjectGameTypeMatchEvidence(
            1,
            "unresolved",
            statusReason,
            "",
            "",
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
            "",
            now,
            now);
    }

    public static ProjectGameTypeMatchEvidence FromJson(string? json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return Empty();
        }

        try
        {
            return Normalize(JsonSerializer.Deserialize<ProjectGameTypeMatchEvidence>(json, JsonOptions));
        }
        catch (JsonException)
        {
            return Empty("invalid_match_json");
        }
    }

    public string ToJson()
    {
        return JsonSerializer.Serialize(this, JsonOptions);
    }

    private static ProjectGameTypeMatchEvidence Normalize(ProjectGameTypeMatchEvidence? evidence)
    {
        if (evidence is null)
        {
            return Empty("invalid_match_json");
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        return evidence with
        {
            SchemaVersion = evidence.SchemaVersion <= 0 ? 1 : evidence.SchemaVersion,
            Status = evidence.Status ?? "unresolved",
            StatusReason = evidence.StatusReason ?? "not_resolved",
            EvidenceSource = evidence.EvidenceSource ?? "",
            ReferenceQuery = evidence.ReferenceQuery ?? "",
            SteamAppId = evidence.SteamAppId ?? "",
            SteamName = evidence.SteamName ?? "",
            SteamTags = evidence.SteamTags ?? [],
            SteamCategories = evidence.SteamCategories ?? [],
            SteamGenres = evidence.SteamGenres ?? [],
            NormalizedGenreTags = evidence.NormalizedGenreTags ?? [],
            MatchedGameTypeId = evidence.MatchedGameTypeId ?? "",
            MatchedGuidePath = evidence.MatchedGuidePath ?? "",
            CandidateScores = evidence.CandidateScores ?? [],
            MissingGuidePath = evidence.MissingGuidePath ?? "",
            CatalogHash = evidence.CatalogHash ?? "",
            CreatedUtc = string.IsNullOrWhiteSpace(evidence.CreatedUtc) ? now : evidence.CreatedUtc,
            UpdatedUtc = string.IsNullOrWhiteSpace(evidence.UpdatedUtc) ? now : evidence.UpdatedUtc
        };
    }

    public static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        WriteIndented = false
    };
}
