namespace PhaseA.Platform.Data;

// ADR-0044: callers cannot select whether Hosted route aggregate evidence applies.
public static class HostedContextRouteContractPolicy
{
    public const string Revision = "hosted-route-applicability.v1";
    public const string NoAggregateReason = "no_pre_dispatch_hosted_route_aggregate";

    public static IReadOnlyCollection<string> EnforcedOperations { get; } = new HashSet<string>(StringComparer.Ordinal)
    {
        "llm:gdd-question-form",
        "llm:gdd-question-form-cache-decision",
        "llm:project-workflow-route-intent",
        "llm:gdd-scene-route-draft",
        "llm:gdd-requirement-map",
        "llm:draft-analysis",
        "llm:draft-coverage",
        "llm:draft-coverage-retry",
        "llm:project-chat",
        "llm:project-asset-library-skill-selection",
        "llm:repair-plan",
        "llm:planning-analysis",
        "llm:goal-plan",
        "llm:prototype-skeleton-regeneration-guard",
        "llm:plan-evaluation",
        "llm:gdd-next-step-review",
        "llm:asset-inventory-judgement",
        "codex:prototype-iteration-goal",
        "codex:prototype-quick-fix",
        "codex:prototype-post-validation-repair",
        "codex:prototype-ui-optimization",
        "codex:gdd-document-generation",
        "codex:web-preview-dedicated-adapter",
        "codex:web-preview-semantic-adapter",
        "codex:skill-action",
        "llm:skill-action"
    };

    public static HostedContextRouteContractDisposition Resolve(string operation)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        if (!EnforcedOperations.Contains(operation, StringComparer.Ordinal))
        {
            throw new InvalidOperationException("Hosted Context route applicability is not registered.");
        }
        return new HostedContextRouteContractDisposition("not_applicable", Revision, NoAggregateReason);
    }
}

public sealed record HostedContextRouteContractDisposition(string Mode, string PolicyRevision, string ReasonCode);
