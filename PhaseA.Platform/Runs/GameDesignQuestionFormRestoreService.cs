using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class GameDesignQuestionFormRestoreService
{
    private const string GddRunType = "game-design-gdd";
    private const int MaxAnswers = 12;
    private static readonly Regex AnswerHeaderRegex = new(
        @"^\s*(\d+)\.\s*(.*?):\s*(.*)\s*$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;

    public GameDesignQuestionFormRestoreService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options)
    {
        _metadataStore = metadataStore;
        _options = options;
    }

    public async Task<GameDesignQuestionFormRestoreResult?> ReadLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        foreach (var run in runs
                     .Where(run => string.Equals(run.RunType, GddRunType, StringComparison.Ordinal))
                     .OrderByDescending(RunSortTimeUtc))
        {
            var promptPath = Path.GetFullPath(Path.Combine(
                projectRoot,
                "logs",
                "phase-a-gdd",
                project.ProjectId,
                run.RunId,
                "gdd-prompt.md"));
            if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, promptPath) || !File.Exists(promptPath))
            {
                continue;
            }

            var text = await File.ReadAllTextAsync(promptPath, cancellationToken);
            var answers = ParseQuestionFormAnswers(text);
            if (answers.Count > 0)
            {
                return new GameDesignQuestionFormRestoreResult(
                    "ready",
                    project.ProjectId,
                    run.RunId,
                    answers);
            }
        }

        return new GameDesignQuestionFormRestoreResult(
            "not_found",
            project.ProjectId,
            "",
            [],
            "gdd_question_form_restore_not_found");
    }

    internal static IReadOnlyList<GameDesignQuestionFormRestoreAnswer> ParseQuestionFormAnswers(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return [];
        }

        var start = text.IndexOf("Question-form answers:", StringComparison.Ordinal);
        if (start < 0)
        {
            return [];
        }

        var answers = new List<GameDesignQuestionFormRestoreAnswer>();
        int? currentIndex = null;
        string currentLabel = "";
        var currentAnswer = new List<string>();

        void Flush()
        {
            if (currentIndex is null || string.IsNullOrWhiteSpace(currentLabel))
            {
                return;
            }

            var answer = string.Join("\n", currentAnswer)
                .Trim();
            if (string.IsNullOrWhiteSpace(answer))
            {
                return;
            }

            answers.Add(new GameDesignQuestionFormRestoreAnswer(
                currentIndex.Value,
                Trim(currentLabel, 120),
                Trim(answer, 1200)));
        }

        var body = text[(start + "Question-form answers:".Length)..];
        using var reader = new StringReader(body);
        while (answers.Count < MaxAnswers && reader.ReadLine() is { } line)
        {
            var trimmed = line.Trim();
            if (trimmed.Length == 0)
            {
                continue;
            }

            if (trimmed.StartsWith("Use these answers ", StringComparison.Ordinal) ||
                trimmed.StartsWith("User-confirmed scene route", StringComparison.Ordinal) ||
                trimmed.StartsWith("Current uploaded TXT references", StringComparison.Ordinal))
            {
                break;
            }

            var match = AnswerHeaderRegex.Match(line);
            if (match.Success)
            {
                Flush();
                currentIndex = int.Parse(match.Groups[1].Value);
                currentLabel = match.Groups[2].Value.Trim();
                currentAnswer.Clear();
                currentAnswer.Add(match.Groups[3].Value.Trim());
                continue;
            }

            if (currentIndex is not null)
            {
                currentAnswer.Add(trimmed);
            }
        }

        Flush();
        return answers
            .OrderBy(answer => answer.Index)
            .Take(MaxAnswers)
            .ToArray();
    }

    private static DateTimeOffset RunSortTimeUtc(RunSnapshot run)
    {
        return ParseUtc(run.FinishedUtc) ??
            ParseUtc(run.ProgressUpdatedUtc) ??
            ParseUtc(run.StartedUtc) ??
            ParseUtc(run.CreatedUtc) ??
            DateTimeOffset.MinValue;
    }

    private static DateTimeOffset? ParseUtc(string? value)
    {
        return DateTimeOffset.TryParse(value, out var parsed) ? parsed.ToUniversalTime() : null;
    }

    private static string Trim(string value, int maxLength)
    {
        value = value.Trim();
        return value.Length <= maxLength ? value : value[..maxLength];
    }
}
