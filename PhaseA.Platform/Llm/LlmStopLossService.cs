using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Llm;

public sealed class LlmStopLossService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;

    public LlmStopLossService(PhaseAMetadataStore metadataStore, PhaseAPlatformOptions options)
    {
        _metadataStore = metadataStore;
        _options = options;
    }

    public async Task<LlmStopLossDecision> CheckAsync(
        string accountId,
        LlmCostEstimate estimate,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentNullException.ThrowIfNull(estimate);

        if (estimate.EstimatedCostCny > _options.LlmCostStopLossPerRunCny)
        {
            return new LlmStopLossDecision(false, "llm_run_stop_loss_exceeded", estimate.EstimatedCostCny, estimate.EstimatedCostCny);
        }

        var currentCosts = await _metadataStore.ListAccountLlmCostJsonForUtcDayAsync(accountId, DateOnly.FromDateTime(DateTime.UtcNow), cancellationToken);
        var currentTotal = currentCosts.Sum(ParseCostCny);
        var after = currentTotal + estimate.EstimatedCostCny;
        if (after > _options.LlmCostStopLossDailyAccountCny)
        {
            return new LlmStopLossDecision(false, "llm_daily_stop_loss_exceeded", estimate.EstimatedCostCny, after);
        }

        return new LlmStopLossDecision(true, null, estimate.EstimatedCostCny, after);
    }

    public static string BuildCostJson(LlmCostEstimate estimate, LlmStopLossDecision decision)
    {
        return JsonSerializer.Serialize(new
        {
            estimated_cost_cny = estimate.EstimatedCostCny,
            model = estimate.Model,
            request_id = estimate.RequestId,
            daily_total_after_cny = decision.DailyTotalAfterCny
        });
    }

    private static decimal ParseCostCny(string costJson)
    {
        try
        {
            using var document = JsonDocument.Parse(costJson);
            if (document.RootElement.TryGetProperty("estimated_cost_cny", out var estimated) && estimated.TryGetDecimal(out var value))
            {
                return value;
            }

            if (document.RootElement.TryGetProperty("cost_cny", out var cost) && cost.TryGetDecimal(out var legacyValue))
            {
                return legacyValue;
            }
        }
        catch (JsonException)
        {
            return 0m;
        }

        return 0m;
    }
}
