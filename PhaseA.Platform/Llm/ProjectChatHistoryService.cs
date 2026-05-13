using PhaseA.Platform.Data;

namespace PhaseA.Platform.Llm;

public sealed class ProjectChatHistoryService
{
    public const int DefaultLimit = 50;

    private readonly PhaseAMetadataStore _metadataStore;

    public ProjectChatHistoryService(PhaseAMetadataStore metadataStore)
    {
        _metadataStore = metadataStore;
    }

    public async Task<ProjectChatHistoryResult?> ListAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var messages = await _metadataStore.ListProjectChatMessagesAsync(accountId, projectId, DefaultLimit, cancellationToken);
        return new ProjectChatHistoryResult(
            projectId,
            messages.Select(message => new ProjectChatHistoryItem(
                message.Role,
                PublicChatSanitizer.Sanitize(message.Content),
                message.Kind,
                message.CreatedUtc)).ToArray());
    }

    public async Task AppendAsync(
        string accountId,
        string projectId,
        string role,
        string? content,
        string? kind = null,
        CancellationToken cancellationToken = default)
    {
        var sanitized = PublicChatSanitizer.Sanitize(content);
        if (string.IsNullOrWhiteSpace(sanitized))
        {
            return;
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return;
        }

        await _metadataStore.AddProjectChatMessageAsync(
            accountId,
            projectId,
            role,
            sanitized,
            kind,
            DefaultLimit,
            cancellationToken);
    }
}

public sealed record ProjectChatHistoryResult(
    string ProjectId,
    IReadOnlyList<ProjectChatHistoryItem> Messages);

public sealed record ProjectChatHistoryItem(
    string Role,
    string Content,
    string? Kind,
    string CreatedUtc);
