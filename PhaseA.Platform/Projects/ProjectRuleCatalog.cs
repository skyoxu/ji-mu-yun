namespace PhaseA.Platform.Projects;

public sealed class ProjectRuleCatalog
{
    public const string DefaultRuleId = "godot-prototype-default";

    private readonly Dictionary<string, ProjectCreationRule> _rules;

    public ProjectRuleCatalog()
    {
        var defaultRule = new ProjectCreationRule(
            DefaultRuleId,
            LlmBindingRequired: true,
            AllowedWorkflows:
            [
                "chapter2-bootstrap",
                "prototype-7day-playable",
                "prototype-tdd",
                "prototype-scene"
            ]);

        _rules = new Dictionary<string, ProjectCreationRule>(StringComparer.OrdinalIgnoreCase)
        {
            [defaultRule.Id] = defaultRule
        };
    }

    public ProjectCreationRule? Find(string? ruleId)
    {
        var effectiveRuleId = string.IsNullOrWhiteSpace(ruleId) ? DefaultRuleId : ruleId.Trim();
        return _rules.TryGetValue(effectiveRuleId, out var rule) ? rule : null;
    }
}
