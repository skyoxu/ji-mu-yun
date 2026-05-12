namespace PhaseA.Platform.Projects;

public sealed record ProjectDeletionRequest(
    string? ConfirmOne,
    string? ConfirmTwo);
