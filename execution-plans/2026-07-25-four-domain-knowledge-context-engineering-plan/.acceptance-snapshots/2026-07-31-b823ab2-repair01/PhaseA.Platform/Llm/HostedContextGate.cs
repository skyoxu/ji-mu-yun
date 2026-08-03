namespace PhaseA.Platform.Llm;

public enum HostedContextGateMode
{
    Legacy,
    Observe,
    Enforce
}

public sealed record HostedContextEnvelope(
    string ManifestId,
    string SnapshotId,
    string PolicyRevision,
    string Signature,
    string? SignatureKeyId = null,
    string? AccountId = null,
    string? ProjectId = null,
    string? OperationKey = null,
    bool SnapshotCurrent = true,
    bool PolicyMatches = true,
    bool WithinBudget = true,
    string? Nonce = null,
    string? ExpiresUtc = null,
    string? CreatedUtc = null);

public interface IHostedContextManifestValidator
{
    Task<bool> ValidateAndConsumeAsync(
        HostedContextEnvelope envelope,
        string operationKey,
        CancellationToken cancellationToken = default);
}

public sealed record HostedContextGateResult(bool Allowed, string? FailureCode, string? WouldBlockFailureCode = null);

public sealed class HostedContextGatePolicy
{
    private static readonly IReadOnlyDictionary<string, HostedContextGateMode> DefaultModes = new Dictionary<string, HostedContextGateMode>(StringComparer.Ordinal)
    {
        ["llm:draft-analysis"] = HostedContextGateMode.Observe,
        ["llm:draft-coverage"] = HostedContextGateMode.Observe,
        ["llm:draft-coverage-retry"] = HostedContextGateMode.Observe,
        ["llm:skill-action"] = HostedContextGateMode.Observe,
        ["llm:project-chat"] = HostedContextGateMode.Observe,
        ["llm:gdd-next-step-review"] = HostedContextGateMode.Observe,
        ["llm:gdd-scene-route-draft"] = HostedContextGateMode.Observe,
        ["llm:gdd-requirement-map"] = HostedContextGateMode.Observe,
        ["llm:gdd-question-form"] = HostedContextGateMode.Observe,
        ["llm:gdd-question-form-cache-decision"] = HostedContextGateMode.Observe,
        ["llm:repair-plan"] = HostedContextGateMode.Observe,
        ["llm:planning-analysis"] = HostedContextGateMode.Observe,
        ["llm:goal-plan"] = HostedContextGateMode.Observe,
        ["llm:prototype-skeleton-regeneration-guard"] = HostedContextGateMode.Observe,
        ["llm:plan-evaluation"] = HostedContextGateMode.Observe,
        ["llm:project-workflow-route-intent"] = HostedContextGateMode.Observe,
        ["llm:project-asset-library-skill-selection"] = HostedContextGateMode.Observe,
        ["llm:asset-inventory-judgement"] = HostedContextGateMode.Observe
    };
    private readonly IReadOnlyDictionary<string, HostedContextGateMode> _modes;

    public HostedContextGatePolicy(IReadOnlyDictionary<string, HostedContextGateMode>? modes = null)
    {
        _modes = modes ?? DefaultModes;
    }

    public static HostedContextGatePolicy CreateWithOverrides(
        IReadOnlyDictionary<string, HostedContextGateMode> overrides)
    {
        ArgumentNullException.ThrowIfNull(overrides);
        var modes = new Dictionary<string, HostedContextGateMode>(DefaultModes, StringComparer.Ordinal);
        foreach (var pair in overrides)
        {
            modes[pair.Key] = pair.Value;
        }

        return new HostedContextGatePolicy(modes);
    }

    public HostedContextGateMode Resolve(string? operationKey)
    {
        return !string.IsNullOrWhiteSpace(operationKey) && _modes.TryGetValue(operationKey, out var mode)
            ? mode
            : HostedContextGateMode.Legacy;
    }

}

public static class HostedContextGate
{
    public static HostedContextGateResult Evaluate(HostedContextGateMode mode, HostedContextEnvelope? envelope)
    {
        if (mode == HostedContextGateMode.Legacy)
        {
            return new HostedContextGateResult(true, null);
        }

        string? failureCode = null;
        if (envelope is null)
        {
            failureCode = "context_manifest_required";
        }
        else if (string.IsNullOrWhiteSpace(envelope.ManifestId) || string.IsNullOrWhiteSpace(envelope.Signature))
        {
            failureCode = "context_manifest_invalid";
        }
        else if (!envelope.SnapshotCurrent)
        {
            failureCode = "context_snapshot_stale";
        }
        else if (!envelope.PolicyMatches)
        {
            failureCode = "context_policy_mismatch";
        }
        else if (!envelope.WithinBudget)
        {
            failureCode = "context_budget_exceeded";
        }

        return mode == HostedContextGateMode.Observe
            ? new HostedContextGateResult(true, null, failureCode)
            : new HostedContextGateResult(string.IsNullOrWhiteSpace(failureCode), failureCode);
    }
}
