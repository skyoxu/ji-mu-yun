namespace PhaseA.Platform.Projects;

public sealed record ProjectCreationRule(
    string Id,
    bool LlmBindingRequired,
    IReadOnlyList<string> AllowedWorkflows)
{
    public bool AllowsWorkflow(string workflowId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workflowId);
        return AllowedWorkflows.Contains(workflowId, StringComparer.OrdinalIgnoreCase);
    }
}
