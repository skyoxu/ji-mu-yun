namespace PhaseA.Platform.Data;

public sealed record MigrationEvidence(
    string OperationId,
    string AccountId,
    string ProjectId,
    string Status,
    string CorrelationId,
    IReadOnlyDictionary<string, string> Fields)
{
    public MigrationEvidence Redacted()
    {
        var safe = Fields
            .Where(item => !item.Key.Contains("secret", StringComparison.OrdinalIgnoreCase)
                && !item.Key.Contains("token", StringComparison.OrdinalIgnoreCase)
                && !item.Key.Contains("password", StringComparison.OrdinalIgnoreCase))
            .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
        return this with { Fields = safe };
    }
}
