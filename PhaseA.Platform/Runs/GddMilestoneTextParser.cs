using System.Text.RegularExpressions;

namespace PhaseA.Platform.Runs;

internal static class GddMilestoneTextParser
{
    private static readonly Regex MarkdownHeadingRegex = new(
        @"^\s*#{1,6}\s+(?<title>.+?)\s*$",
        RegexOptions.Compiled);

    private static readonly Regex MilestoneLineRegex = new(
        @"^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(?:\d+[.)、]\s*)?(?:\*\*[^*]+\*\*\s*[:：]\s*)?(?<id>M\d+(?:[-.]\d+)?)(?:(?:\s*[:：\-–—]\s*)|\s+)(?<body>.+?)\s*$",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    internal static List<GddMilestoneTextStep> ExtractExplicitSteps(string gddText)
    {
        var lines = Regex.Split(gddText.Replace("\r\n", "\n"), "\n");
        var searchRanges = BuildSearchRanges(lines);
        var collected = new List<GddMilestoneTextStep>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var range in searchRanges)
        {
            var candidates = ExtractCandidates(lines, range.Start, range.End);
            var steps = BuildSteps(lines, candidates);
            foreach (var step in steps)
            {
                if (seen.Add(step.StepId))
                {
                    collected.Add(step);
                }
            }
        }

        return collected
            .OrderBy(step => StepSortKey(step.StepId))
            .ThenBy(step => step.StepIndex)
            .Select((step, index) => step with { StepIndex = index + 1 })
            .ToList();
    }

    internal static bool ContainsMilestoneGroup(string text)
    {
        var lines = Regex.Split(text.Replace("\r\n", "\n"), "\n");
        return lines
            .Select(line => MilestoneLineRegex.Match(line))
            .Where(match => match.Success)
            .Select(match => NormalizeStepId(match.Groups["id"].Value))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(2)
            .Count() >= 2;
    }

    internal static string RemoveMilestoneListLines(string text)
    {
        var lines = Regex.Split(text.Replace("\r\n", "\n"), "\n");
        var kept = new List<string>();
        var removingMilestoneBlock = false;
        foreach (var line in lines)
        {
            if (MilestoneLineRegex.IsMatch(line))
            {
                removingMilestoneBlock = true;
                continue;
            }

            if (removingMilestoneBlock)
            {
                if (string.IsNullOrWhiteSpace(line))
                {
                    removingMilestoneBlock = false;
                    continue;
                }

                if (IsMilestoneContinuationLine(line))
                {
                    continue;
                }

                removingMilestoneBlock = false;
            }

            kept.Add(line);
        }

        return string.Join("\n", kept).Trim();
    }

    private static bool IsMilestoneContinuationLine(string line)
    {
        var text = CleanMilestoneText(Regex.Replace(line.Trim(), @"^\s*(?:[-*]\s*)?(?:\d+[.)、]\s*)?", ""));
        return ContainsAny(
            text,
            "目标",
            "范围",
            "验收",
            "验证",
            "玩家",
            "切片",
            "打包",
            "场景",
            "输入",
            "反馈",
            "Scope",
            "Goal",
            "Acceptance",
            "Validation",
            "Verification",
            "Godot",
            "C#",
            "Scene",
            "Control",
            "Input",
            "Reward");
    }

    private static List<(int Start, int End)> BuildSearchRanges(IReadOnlyList<string> lines)
    {
        var strongRanges = new List<(int Start, int End)>();
        var weakRanges = new List<(int Start, int End)>();
        for (var index = 0; index < lines.Count; index++)
        {
            var match = MarkdownHeadingRegex.Match(lines[index]);
            if (!match.Success)
            {
                continue;
            }

            var title = match.Groups["title"].Value;
            var strength = MilestoneHeadingStrength(title);
            if (strength == 0)
            {
                continue;
            }

            var end = lines.Count;
            for (var next = index + 1; next < lines.Count; next++)
            {
                if (MarkdownHeadingRegex.IsMatch(lines[next]))
                {
                    end = next;
                    break;
                }
            }

            if (strength == 2)
            {
                strongRanges.Add((index + 1, end));
            }
            else
            {
                weakRanges.Add((index + 1, end));
            }
        }

        if (strongRanges.Count > 0)
        {
            return strongRanges;
        }

        if (weakRanges.Count > 0)
        {
            return weakRanges;
        }

        return [(0, lines.Count)];
    }

    private static int MilestoneHeadingStrength(string value)
    {
        var text = value.Trim();
        if (ContainsAny(text, "里程碑", "实现步骤", "实施步骤", "模块步骤", "游戏模块", "开发模块", "开发步骤", "Milestone", "Module", "Modules", "Step Plan", "Implementation Steps"))
        {
            return 2;
        }

        return ContainsAny(text, "原型验收", "Prototype Plan") ? 1 : 0;
    }

    private static List<Candidate> ExtractCandidates(IReadOnlyList<string> lines, int start, int end)
    {
        var candidates = new List<Candidate>();
        for (var index = start; index < end; index++)
        {
            var match = MilestoneLineRegex.Match(lines[index]);
            if (!match.Success)
            {
                continue;
            }

            var body = CleanMilestoneText(match.Groups["body"].Value);
            var title = ExtractTitle(body);
            if (string.IsNullOrWhiteSpace(title))
            {
                continue;
            }

            candidates.Add(new Candidate(index, NormalizeStepId(match.Groups["id"].Value), title, body));
        }

        return candidates
            .GroupBy(candidate => candidate.StepId, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .OrderBy(candidate => StepSortKey(candidate.StepId))
            .ThenBy(candidate => candidate.LineIndex)
            .Take(20)
            .ToList();
    }

    private static List<GddMilestoneTextStep> BuildSteps(IReadOnlyList<string> lines, IReadOnlyList<Candidate> candidates)
    {
        var result = new List<GddMilestoneTextStep>();
        foreach (var candidate in candidates)
        {
            var nextLineIndex = candidates
                .Where(item => item.LineIndex > candidate.LineIndex)
                .Select(item => item.LineIndex)
                .DefaultIfEmpty(lines.Count)
                .Min();
            var body = ExtractBody(lines, candidate.LineIndex + 1, nextLineIndex);
            var description = Trim(FirstNonEmpty(Compact($"{candidate.FullBody} {body}"), candidate.FullBody, candidate.Title), 420);
            result.Add(new GddMilestoneTextStep(
                candidate.StepId,
                result.Count + 1,
                $"{candidate.StepId}：{Trim(candidate.Title, 80)}",
                description));
        }

        return result;
    }

    private static string ExtractBody(IReadOnlyList<string> lines, int start, int end)
    {
        var chunks = new List<string>();
        for (var index = start; index < end; index++)
        {
            var line = lines[index].Trim();
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            if (line.StartsWith("#", StringComparison.Ordinal))
            {
                break;
            }

            chunks.Add(CleanMilestoneText(line));
            if (Compact(string.Join(" ", chunks)).Length >= 600)
            {
                break;
            }
        }

        return Compact(string.Join(" ", chunks));
    }

    private static string ExtractTitle(string body)
    {
        var text = CleanMilestoneText(body);
        var delimiters = new[]
        {
            "：目标", ": Goal", ": goal", "：Goal", "：goal", "；Scope", "; Scope", "；范围", "；验收", "；验证"
        };
        foreach (var delimiter in delimiters)
        {
            var index = text.IndexOf(delimiter, StringComparison.OrdinalIgnoreCase);
            if (index > 0)
            {
                text = text[..index];
                break;
            }
        }

        return CleanMilestoneText(text);
    }

    private static string CleanMilestoneText(string value)
    {
        var cleaned = Regex.Replace(value.Trim(), @"^\s*(?:[-*]\s*)?", "");
        cleaned = Regex.Replace(cleaned, @"\s+", " ");
        return cleaned.Trim().TrimEnd(':', '：', '-', '–', '—').Trim();
    }

    private static int StepSortKey(string stepId)
    {
        var match = Regex.Match(stepId, @"^M(?<major>\d+)(?:-(?<minor>\d+))?$", RegexOptions.IgnoreCase);
        if (!match.Success)
        {
            return int.MaxValue;
        }

        var major = int.Parse(match.Groups["major"].Value);
        var minor = match.Groups["minor"].Success ? int.Parse(match.Groups["minor"].Value) : 0;
        return major * 1000 + minor;
    }

    private static bool ContainsAny(string value, params string[] needles)
        => needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));

    private static string NormalizeStepId(string value)
        => value.Trim().ToUpperInvariant().Replace('.', '-');

    private static string Compact(string? value)
        => string.IsNullOrWhiteSpace(value) ? "" : Regex.Replace(value.Trim(), @"\s+", " ");

    private static string FirstNonEmpty(params string?[] values)
        => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value))?.Trim() ?? "";

    private static string Trim(string value, int maxLength)
    {
        var compact = Compact(value);
        return compact.Length <= maxLength ? compact : compact[..maxLength].TrimEnd() + "...";
    }

    private sealed record Candidate(int LineIndex, string StepId, string Title, string FullBody);
}

internal sealed record GddMilestoneTextStep(
    string StepId,
    int StepIndex,
    string Title,
    string Description);
