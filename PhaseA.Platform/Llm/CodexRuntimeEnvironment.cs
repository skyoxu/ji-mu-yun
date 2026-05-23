namespace PhaseA.Platform.Llm;

public static class CodexRuntimeEnvironment
{
    public const string CredentialNotReadyFailureCode = "aicodemirror_codex_credential_not_imported";

    public static void ApplyTo(IDictionary<string, string> environment, AiCodeMirrorRuntimeCredential credential)
    {
        ArgumentNullException.ThrowIfNull(environment);
        ArgumentNullException.ThrowIfNull(credential);

        if (!credential.Ready)
        {
            throw new InvalidOperationException(credential.FailureCode ?? CredentialNotReadyFailureCode);
        }

        if (!string.IsNullOrWhiteSpace(credential.CodexHomePath))
        {
            environment["CODEX_HOME"] = credential.CodexHomePath;
        }
    }

    public static IReadOnlyDictionary<string, string> Merge(
        IReadOnlyDictionary<string, string> environment,
        AiCodeMirrorRuntimeCredential credential)
    {
        ArgumentNullException.ThrowIfNull(environment);
        var merged = new Dictionary<string, string>(environment, StringComparer.OrdinalIgnoreCase);
        ApplyTo(merged, credential);
        return merged;
    }
}
