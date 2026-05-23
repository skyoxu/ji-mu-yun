using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Llm;

public sealed record AiCodeMirrorKeyImportRequest(string? KeyName, string? ApiKey = null, string? Notes = null, int? ValidDays = null);
public sealed record AiCodeMirrorKeyAssignRequest(string? AccountId, string? KeyName);
public sealed record AiCodeMirrorRuntimeCredential(
    string? BillingKeyName,
    string? CodexHomePath,
    string? FailureCode)
{
    public bool Ready => string.IsNullOrWhiteSpace(FailureCode);
}

public sealed class AiCodeMirrorKeyPoolService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;

    public AiCodeMirrorKeyPoolService(PhaseAMetadataStore metadataStore, PhaseAPlatformOptions options)
    {
        _metadataStore = metadataStore;
        _options = options;
    }

    public async Task<AiCodeMirrorKeyPoolEntry?> ImportAsync(
        AiCodeMirrorKeyImportRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        if (string.IsNullOrWhiteSpace(request.KeyName))
        {
            return null;
        }

        var validDays = request.ValidDays is > 0 ? request.ValidDays : null;
        var entry = await _metadataStore.UpsertAiCodeMirrorKeyAsync(
            new AiCodeMirrorKeyImportCommand(
                request.KeyName.Trim(),
                request.Notes?.Trim(),
                validDays,
                !string.IsNullOrWhiteSpace(request.ApiKey)),
            cancellationToken);

        if (!string.IsNullOrWhiteSpace(request.ApiKey))
        {
            WriteCodexHome(entry, request.ApiKey.Trim());
        }

        return entry;
    }

    public async Task<AiCodeMirrorKeyAssignmentResult> AssignAsync(
        AiCodeMirrorKeyAssignRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        if (string.IsNullOrWhiteSpace(request.AccountId))
        {
            return AiCodeMirrorKeyAssignmentResult.Failure("account_id_required");
        }

        if (string.IsNullOrWhiteSpace(request.KeyName))
        {
            return AiCodeMirrorKeyAssignmentResult.Failure("key_name_required");
        }

        return await _metadataStore.AssignAiCodeMirrorKeyToAccountAsync(
            request.KeyName.Trim(),
            request.AccountId.Trim(),
            cancellationToken);
    }

    public Task<IReadOnlyList<AiCodeMirrorKeyPoolEntry>> ListAsync(CancellationToken cancellationToken = default)
    {
        return _metadataStore.ListAiCodeMirrorKeysAsync(cancellationToken);
    }

    public async Task<AiCodeMirrorKeyImportCsvResult> ImportCsvAsync(
        string csv,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(csv))
        {
            return new AiCodeMirrorKeyImportCsvResult(0, ["csv_empty"]);
        }

        var errors = new List<string>();
        var imported = 0;
        var lines = csv.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
        var start = lines.Length > 0 && lines[0].Contains("key_name", StringComparison.OrdinalIgnoreCase) ? 1 : 0;
        for (var index = start; index < lines.Length; index++)
        {
            var line = lines[index].Trim();
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var cells = SplitCsvLine(line);
            var keyName = Cell(cells, 0);
            var apiKey = Cell(cells, 1);
            var notes = Cell(cells, 2);
            var validDaysRaw = Cell(cells, 3);
            if (string.IsNullOrWhiteSpace(keyName))
            {
                errors.Add($"line_{index + 1}:key_name_required");
                continue;
            }

            int? validDays = null;
            if (!string.IsNullOrWhiteSpace(validDaysRaw))
            {
                if (!int.TryParse(validDaysRaw, System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out var parsed) || parsed < 1)
                {
                    errors.Add($"line_{index + 1}:invalid_valid_days");
                    continue;
                }

                validDays = parsed;
            }

            var result = await ImportAsync(new AiCodeMirrorKeyImportRequest(keyName, apiKey, notes, validDays), cancellationToken);
            if (result is null)
            {
                errors.Add($"line_{index + 1}:key_name_required");
                continue;
            }

            imported++;
        }

        return new AiCodeMirrorKeyImportCsvResult(imported, errors);
    }

    public async Task<string?> ResolveKeyNameForAccountAsync(string accountId, CancellationToken cancellationToken = default)
    {
        var entry = await _metadataStore.GetAiCodeMirrorKeyForAccountAsync(accountId, cancellationToken);
        return entry?.KeyName;
    }

    public async Task<AiCodeMirrorRuntimeCredential> ResolveRuntimeCredentialForAccountAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(accountId))
        {
            return new AiCodeMirrorRuntimeCredential(null, null, null);
        }

        var entry = await _metadataStore.GetAiCodeMirrorKeyForAccountAsync(accountId, cancellationToken);
        if (entry is null)
        {
            return new AiCodeMirrorRuntimeCredential(null, null, null);
        }

        var codexHome = GetCodexHomePath(entry);
        if (!File.Exists(Path.Combine(codexHome, "auth.json")) ||
            !File.Exists(Path.Combine(codexHome, "config.toml")))
        {
            return new AiCodeMirrorRuntimeCredential(entry.KeyName, null, "aicodemirror_codex_credential_not_imported");
        }

        return new AiCodeMirrorRuntimeCredential(entry.KeyName, codexHome, null);
    }

    private string GetCodexHomePath(AiCodeMirrorKeyPoolEntry entry)
    {
        return Path.Combine(_options.AiCodeMirrorCodexHomeRoot, SanitizePathSegment(entry.KeyId));
    }

    private static string Cell(IReadOnlyList<string> cells, int index)
    {
        return index < cells.Count ? cells[index].Trim() : "";
    }

    private static IReadOnlyList<string> SplitCsvLine(string line)
    {
        var cells = new List<string>();
        var builder = new StringBuilder();
        var inQuotes = false;
        for (var i = 0; i < line.Length; i++)
        {
            var ch = line[i];
            if (ch == '"')
            {
                if (inQuotes && i + 1 < line.Length && line[i + 1] == '"')
                {
                    builder.Append('"');
                    i++;
                    continue;
                }

                inQuotes = !inQuotes;
                continue;
            }

            if (ch == ',' && !inQuotes)
            {
                cells.Add(builder.ToString());
                builder.Clear();
                continue;
            }

            builder.Append(ch);
        }

        cells.Add(builder.ToString());
        return cells;
    }

    private void WriteCodexHome(AiCodeMirrorKeyPoolEntry entry, string apiKey)
    {
        var codexHome = GetCodexHomePath(entry);
        Directory.CreateDirectory(codexHome);
        File.WriteAllText(
            Path.Combine(codexHome, "auth.json"),
            JsonSerializer.Serialize(new Dictionary<string, string> { ["OPENAI_API_KEY"] = apiKey }),
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        File.WriteAllText(
            Path.Combine(codexHome, "config.toml"),
            BuildCodexConfigToml(),
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
    }

    private static string BuildCodexConfigToml()
    {
        return """
            model_provider = "aicodemirror"
            model = "gpt-5.4"
            model_reasoning_effort = "high"
            disable_response_storage = true
            preferred_auth_method = "apikey"
            approvals_reviewer = "user"

            [model_providers.aicodemirror]
            name = "aicodemirror"
            base_url = "https://api.aicodemirror.com/api/codex/backend-api/codex"
            wire_api = "responses"

            [windows]
            sandbox = "unelevated"

            [notice]
            hide_full_access_warning = true
            """;
    }

    private static string SanitizePathSegment(string value)
    {
        var invalid = Path.GetInvalidFileNameChars();
        var builder = new StringBuilder(value.Length);
        foreach (var ch in value)
        {
            builder.Append(invalid.Contains(ch) ? '_' : ch);
        }

        return builder.ToString();
    }
}
