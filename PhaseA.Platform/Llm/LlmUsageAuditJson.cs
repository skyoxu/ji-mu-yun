using System.Text.Json;

namespace PhaseA.Platform.Llm;

public static class LlmUsageAuditJson
{
    public static string BuildCodexUsageJson(
        string operation,
        string model,
        string? runType = null,
        string? projectId = null,
        string? skillActionId = null,
        string? skillName = null,
        string? route = null,
        string? failureCode = null,
        int? exitCode = null,
        string usageStatus = "unknown",
        decimal? estimatedCostCny = 0m,
        decimal? actualCostCny = null,
        int? inputTokens = null,
        int? outputTokens = null,
        int? cachedInputTokens = null,
        string? requestId = null,
        string billingSource = "codex-cli",
        AiCodeMirrorBillingDelta? providerBilling = null)
    {
        return JsonSerializer.Serialize(new
        {
            billing_source = billingSource,
            usage_status = usageStatus,
            provider_billing_status = providerBilling?.Status,
            provider_billing_source = providerBilling is null ? null : "aicodemirror",
            provider_api_key_name = providerBilling?.After.ApiKeyName,
            provider_api_key_total_consumed_cny_before = providerBilling?.Before.ApiKeyTotalConsumedCny,
            provider_api_key_total_consumed_cny_after = providerBilling?.After.ApiKeyTotalConsumedCny,
            provider_api_key_consumed_delta_cny = providerBilling?.ApiKeyConsumedDeltaCny,
            provider_wallet_balance_cny_after = providerBilling?.After.WalletBalanceCny,
            provider_wallet_bonus_balance_cny_after = providerBilling?.After.WalletBonusBalanceCny,
            provider_failure_code = providerBilling?.After.FailureCode ?? providerBilling?.Before.FailureCode,
            operation,
            route,
            run_type = runType,
            project_id = projectId,
            skill_action_id = skillActionId,
            skill_name = skillName,
            model,
            request_id = requestId,
            exit_code = exitCode,
            failure_code = failureCode,
            estimated_cost_cny = estimatedCostCny,
            actual_cost_cny = actualCostCny ?? providerBilling?.ApiKeyConsumedDeltaCny,
            input_tokens = inputTokens,
            output_tokens = outputTokens,
            cached_input_tokens = cachedInputTokens
        });
    }

    public static string BuildCodexUsageJson(
        string operation,
        string model,
        CodexTokenUsage tokenUsage,
        string? runType = null,
        string? projectId = null,
        string? skillActionId = null,
        string? skillName = null,
        string? route = null,
        string? failureCode = null,
        int? exitCode = null,
        AiCodeMirrorBillingDelta? providerBilling = null)
    {
        return BuildCodexUsageJson(
            operation: operation,
            model: model,
            runType: runType,
            projectId: projectId,
            skillActionId: skillActionId,
            skillName: skillName,
            route: route,
            failureCode: failureCode,
            exitCode: exitCode,
            usageStatus: tokenUsage.HasAny ? "captured" : "unknown",
            inputTokens: tokenUsage.InputTokens,
            outputTokens: tokenUsage.OutputTokens,
            cachedInputTokens: tokenUsage.CachedInputTokens,
            providerBilling: providerBilling);
    }

    public static decimal SumEstimatedCostCny(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return 0m;
        }

        try
        {
            using var document = JsonDocument.Parse(json);
            return SumEstimatedCostCny(document.RootElement);
        }
        catch (JsonException)
        {
            return 0m;
        }
    }

    private static decimal SumEstimatedCostCny(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.Array => element.EnumerateArray().Sum(SumEstimatedCostCny),
            JsonValueKind.Object => SumEstimatedCostCnyFromObject(element),
            _ => 0m
        };
    }

    private static decimal SumEstimatedCostCnyFromObject(JsonElement element)
    {
        if (TryReadDecimal(element, "actual_cost_cny", out var actual))
        {
            return actual;
        }

        if (TryReadDecimal(element, "provider_api_key_consumed_delta_cny", out var providerDelta))
        {
            return providerDelta;
        }

        if (TryReadDecimal(element, "estimated_cost_cny", out var direct))
        {
            return direct;
        }

        if (element.TryGetProperty("calls", out var calls) && calls.ValueKind == JsonValueKind.Array)
        {
            return calls.EnumerateArray().Sum(SumEstimatedCostCny);
        }

        if (TryReadDecimal(element, "cost_cny", out var legacy))
        {
            return legacy;
        }

        return 0m;
    }

    private static bool TryReadDecimal(JsonElement element, string propertyName, out decimal value)
    {
        value = 0m;
        return element.TryGetProperty(propertyName, out var property) &&
               property.ValueKind == JsonValueKind.Number &&
               property.TryGetDecimal(out value);
    }
}
