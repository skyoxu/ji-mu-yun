namespace PhaseA.Platform.Data;

public sealed record AiCodeMirrorKeyPoolEntry(
    string KeyId,
    string KeyName,
    string? AccountId,
    string Status,
    string? Notes,
    int? ValidDays,
    string? ExpiresUtc,
    bool CredentialImported,
    string ImportedUtc,
    string? AssignedUtc,
    string UpdatedUtc);

public sealed record AiCodeMirrorKeyImportCommand(
    string KeyName,
    string? Notes = null,
    int? ValidDays = null,
    bool CredentialImported = false);

public sealed record AiCodeMirrorKeyImportCsvRow(
    string KeyName,
    string? ApiKey,
    string? Notes,
    int? ValidDays);

public sealed record AiCodeMirrorKeyImportCsvResult(
    int Imported,
    IReadOnlyList<string> Errors);

public sealed record AiCodeMirrorKeyAssignmentResult(
    bool Succeeded,
    string? FailureCode,
    AiCodeMirrorKeyPoolEntry? Entry)
{
    public static AiCodeMirrorKeyAssignmentResult Ok(AiCodeMirrorKeyPoolEntry entry) => new(true, null, entry);
    public static AiCodeMirrorKeyAssignmentResult Failure(string failureCode) => new(false, failureCode, null);
}
