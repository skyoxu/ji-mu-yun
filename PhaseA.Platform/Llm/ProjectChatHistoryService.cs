using PhaseA.Platform.Data;
using System.Text.RegularExpressions;

namespace PhaseA.Platform.Llm;

public sealed class ProjectChatHistoryService
{
    public const int DefaultLimit = 50;
    private static readonly Regex NextStepRegex = new(
        @"下一步建议[：:]\s*([\s\S]{1,800}?)(?:\r?\n\s*\r?\n(?:如果你同意|如你同意|若你同意)|$)",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

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
        var items = messages.Select(message => new ProjectChatHistoryItem(
            message.Role,
            PublicChatSanitizer.Sanitize(message.Content),
            message.Kind,
            message.CreatedUtc,
            GetSuggestedFeedback(message.Role, message.Content),
            false)).ToList();

        var latestActionableAssistantIndex = -1;
        for (var index = 0; index < items.Count; index++)
        {
            var item = items[index];
            if (string.Equals(item.Role, "assistant", StringComparison.Ordinal) &&
                !string.IsNullOrWhiteSpace(item.SuggestedFeedback))
            {
                latestActionableAssistantIndex = index;
                continue;
            }

            if (string.Equals(item.Role, "user", StringComparison.Ordinal) &&
                string.Equals(item.Kind, "formal-feedback", StringComparison.Ordinal) &&
                latestActionableAssistantIndex >= 0)
            {
                items[latestActionableAssistantIndex] = items[latestActionableAssistantIndex] with
                {
                    ContinueConsumed = true
                };
            }
        }

        return new ProjectChatHistoryResult(
            projectId,
            items.ToArray());
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

    private static string? GetSuggestedFeedback(string role, string? content)
    {
        if (!string.Equals(role, "assistant", StringComparison.Ordinal))
        {
            return null;
        }

        var sanitized = PublicChatSanitizer.Sanitize(content);
        if (string.IsNullOrWhiteSpace(sanitized))
        {
            return null;
        }

        var match = NextStepRegex.Match(sanitized);
        return match.Success
            ? match.Groups[1].Value.Trim()
            : null;
    }
}

public sealed record ProjectChatHistoryResult(
    string ProjectId,
    IReadOnlyList<ProjectChatHistoryItem> Messages);

public sealed record ProjectChatHistoryItem(
    string Role,
    string Content,
    string? Kind,
    string CreatedUtc,
    string? SuggestedFeedback,
    bool ContinueConsumed);
