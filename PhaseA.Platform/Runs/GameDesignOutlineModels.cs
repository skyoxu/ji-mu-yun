namespace PhaseA.Platform.Runs;

public sealed record GameDesignOutlineReadResult(
    string ProjectId,
    string Title,
    string Summary,
    string RelativePath,
    string LastUpdatedUtc,
    IReadOnlyList<GameDesignOutlineSection> Sections);

public sealed record GameDesignOutlineSection(
    string Id,
    string Title,
    string Skeleton,
    string Content);

public sealed record GameDesignOutlineSectionRequest(
    string? SectionId,
    string? Message,
    string? Model = null);

public sealed record GameDesignOutlineSectionSaveRequest(
    string? SectionId,
    string? Skeleton,
    string? Content);

public sealed record GameDesignOutlineSectionSaveResult(
    string ProjectId,
    string Status,
    string SectionId,
    string Summary);

public sealed record GameDesignOutlineCompleteAllRequest(
    string? Message,
    string? Model = null);

public sealed record GameDesignOutlineCompleteAllSectionResult(
    string SectionId,
    string Title,
    string Status,
    string? RunId,
    string? FailureCode,
    string? Summary);

public sealed record GameDesignOutlineCompleteAllResult(
    string ProjectId,
    string Status,
    int RequestedCount,
    int CompletedCount,
    IReadOnlyList<GameDesignOutlineCompleteAllSectionResult> Sections,
    string Summary,
    string? RunId = null);

public sealed record GameDesignOutlineDeleteResult(
    string ProjectId,
    string Status,
    IReadOnlyList<string> DeletedPaths);

public sealed record GameDesignOutlineDocument(
    string Title,
    string Summary,
    IReadOnlyList<GameDesignOutlineSection> Sections);
