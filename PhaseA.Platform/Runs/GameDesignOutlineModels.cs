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

public sealed record GameDesignOutlineDocument(
    string Title,
    string Summary,
    IReadOnlyList<GameDesignOutlineSection> Sections);
