namespace PhaseA.Platform.Runs;

public sealed record GameDesignQuestionFormRequest(string? Model = null);

public sealed record GameDesignQuestionFormField(
    string Id,
    string Label,
    string Placeholder,
    string InputType = "textarea",
    int Rows = 3,
    int MaxLength = 500,
    bool Required = true);

public sealed record GameDesignQuestionFormResult(
    string Status,
    string ProjectId,
    string SchemaVersion,
    string Title,
    string GameType,
    IReadOnlyList<GameDesignQuestionFormField> Fields,
    string Source,
    string? FailureCode = null);
