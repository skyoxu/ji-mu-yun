using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace PhaseA.Platform.Data;

// ADR-0044: this is the complete canonical payload signed for E2 dispatch.
public sealed class HostedContextSignedPayloadV1
{
    public const string Schema = "jimuyun.hosted-context-manifest.v1";
    public const string GlobalPolicyRevision = "hosted-context-global.v1";
    public const string VisibilityPolicyRevision = "hosted-context-visibility.v1";
    public const string ScopeProfileRevision = "hosted-context-project-scope.v1";
    public const string BudgetProfileRevision = "hosted-context-budget.default.v1";
    public const string SandboxPolicyRevision = "hosted-context-sandbox.v1";
    public const string NetworkPolicyRevision = "hosted-context-network.provider-only.v1";
    public const string ToolPolicyRevision = "hosted-context-tools.v1";
    public const string RouteApplicabilityPolicyRevision = HostedContextRouteContractPolicy.Revision;

    private static readonly string[] RequiredProperties =
    [
        "schema_version", "manifest_id", "identity_mode", "service_principal_id", "primary_domain",
        "allowed_dependency_domains", "visibility", "visibility_policy_revision", "lifecycle", "enforcement_level",
        "gate_mode", "route_id", "skill_id", "operation", "account_id", "project_id", "workspace_id",
        "workspace_generation", "run_id", "attempt_id", "dispatch_id", "global_policy_revision",
        "route_policy_revision", "skill_policy_revision", "account_policy_revision", "project_restrictions_sha256",
        "scope_profile_revision", "effective_capabilities", "repository_snapshot_id", "template_snapshot_id",
        "project_snapshot_id", "allowed_read_artifact_manifest_ref", "allowed_read_artifact_manifest_sha256",
        "allowed_read_artifacts", "allowed_write_paths", "output_targets", "context_assembly_result_ref",
        "context_assembly_result_sha256", "context_assembly", "context_budget_profile_revision", "sandbox_policy",
        "network_policy", "tool_execution_policy", "hosted_route_contracts", "execution_prompt_hash",
        "persisted_prompt_hash", "issued_at_utc", "not_before_utc", "expires_at_utc", "nonce", "max_uses"
    ];

    private HostedContextSignedPayloadV1(string canonicalJson)
    {
        CanonicalJson = canonicalJson;
        using var document = JsonDocument.Parse(canonicalJson);
        var root = document.RootElement;
        ManifestId = RequiredString(root, "manifest_id");
        AccountId = RequiredString(root, "account_id");
        ProjectId = RequiredString(root, "project_id");
        WorkspaceId = RequiredString(root, "workspace_id");
        WorkspaceGeneration = RequiredString(root, "workspace_generation");
        RunId = RequiredString(root, "run_id");
        Operation = RequiredString(root, "operation");
        ProjectSnapshotId = RequiredString(root, "project_snapshot_id");
        RoutePolicyRevision = RequiredString(root, "route_policy_revision");
        Nonce = RequiredString(root, "nonce");
        ExpiresAtUtc = RequiredString(root, "expires_at_utc");
        IssuedAtUtc = RequiredString(root, "issued_at_utc");
        NotBeforeUtc = RequiredString(root, "not_before_utc");
    }

    public string CanonicalJson { get; }
    public string ManifestId { get; }
    public string AccountId { get; }
    public string ProjectId { get; }
    public string WorkspaceId { get; }
    public string WorkspaceGeneration { get; }
    public string RunId { get; }
    public string Operation { get; }
    public string ProjectSnapshotId { get; }
    public string RoutePolicyRevision { get; }
    public string Nonce { get; }
    public string ExpiresAtUtc { get; }
    public string IssuedAtUtc { get; }
    public string NotBeforeUtc { get; }

    public static HostedContextSignedPayloadV1 Parse(string json)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(json);
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
        {
            throw new ArgumentException("Hosted Context signed payload must be an object.", nameof(json));
        }
        var names = root.EnumerateObject().Select(property => property.Name).ToArray();
        if (names.Length != RequiredProperties.Length || RequiredProperties.Any(name => !names.Contains(name, StringComparer.Ordinal)))
        {
            throw new ArgumentException("Hosted Context signed payload properties do not match v1.", nameof(json));
        }
        if (RequiredString(root, "schema_version") != Schema ||
            RequiredString(root, "identity_mode") != "project-bound" ||
            RequiredString(root, "lifecycle") != "run-artifact-view" ||
            RequiredString(root, "enforcement_level") != "E2" ||
            RequiredString(root, "gate_mode") != "enforce" ||
            root.GetProperty("max_uses").GetInt32() != 1)
        {
            throw new ArgumentException("Hosted Context signed payload is not an enforceable E2 payload.", nameof(json));
        }
        foreach (var property in new[]
        {
            "manifest_id", "account_id", "project_id", "workspace_id", "workspace_generation", "run_id", "attempt_id",
            "dispatch_id", "operation", "route_id", "global_policy_revision", "route_policy_revision",
            "visibility_policy_revision", "scope_profile_revision", "context_budget_profile_revision", "nonce"
        })
        {
            _ = RequiredString(root, property);
        }
        foreach (var property in new[]
        {
            "project_restrictions_sha256", "project_snapshot_id", "allowed_read_artifact_manifest_sha256",
            "context_assembly_result_sha256", "execution_prompt_hash"
        })
        {
            RequireSha256(root, property);
        }
        if (root.GetProperty("persisted_prompt_hash").ValueKind != JsonValueKind.Null)
        {
            RequireSha256(root, "persisted_prompt_hash");
        }
        ValidateProjectPaths(root.GetProperty("allowed_write_paths"));
        ValidateProjectPaths(root.GetProperty("output_targets"));
        ValidateHostedRouteContracts(root.GetProperty("hosted_route_contracts"));
        ValidateInlineBindings(root);
        return new HostedContextSignedPayloadV1(Canonicalize(root));
    }

    public static HostedContextSignedPayloadV1 CreateServerDerived(
        string manifestId,
        ProjectSnapshot project,
        string operation,
        string projectSnapshotId,
        string routePolicyRevision,
        string nonce,
        string issuedAtUtc,
        string expiresAtUtc,
        string executionPrompt,
        string? persistedPrompt = null,
        string? requestedRunId = null,
        string sandbox = "read-only",
        IReadOnlyList<string>? allowedWritePaths = null,
        IReadOnlyList<string>? outputTargets = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(executionPrompt);
        if (!IsSha256(projectSnapshotId))
        {
            throw new ArgumentException("Project snapshot ID must be a SHA-256 value.", nameof(projectSnapshotId));
        }
        if (sandbox is not ("read-only" or "workspace-write"))
        {
            throw new ArgumentException("Unsupported Hosted Context sandbox mode.", nameof(sandbox));
        }
        var runId = string.IsNullOrWhiteSpace(requestedRunId) ? $"context-run-{Guid.NewGuid():N}" : requestedRunId;
        var attemptId = $"attempt-{Guid.NewGuid():N}";
        var dispatchId = $"dispatch-{Guid.NewGuid():N}";
        var promptHash = Sha256(executionPrompt);
        var persistedPromptHash = string.IsNullOrEmpty(persistedPrompt) ? null : Sha256(persistedPrompt);
        var workspaceGeneration = Sha256(string.Join("\n", project.WorkspaceId, project.WorkspaceRootPath, project.RepoPath));
        var projectRestrictionsHash = Sha256(string.Join("\n", project.AllowedWorkflowsJson, project.GameTypeMatchJson, project.LlmBindingRequired));
        var readArtifacts = new JsonArray(
            new JsonObject { ["artifact_ref"] = "prompt://execution", ["sha256"] = promptHash },
            new JsonObject { ["artifact_ref"] = $"phase://projects/{project.ProjectId}/snapshot", ["sha256"] = projectSnapshotId });
        var readArtifactsHash = Sha256(Canonicalize(JsonSerializer.SerializeToElement(readArtifacts)));
        var contextAssembly = new JsonObject
        {
            ["execution_prompt_sha256"] = promptHash,
            ["input_manifest_sha256"] = readArtifactsHash,
            ["project_snapshot_id"] = projectSnapshotId
        };
        var contextAssemblyHash = Sha256(Canonicalize(JsonSerializer.SerializeToElement(contextAssembly)));
        var writes = NormalizeProjectPaths(project.RepoPath, allowedWritePaths ?? []);
        var outputs = NormalizeProjectPaths(project.RepoPath, outputTargets ?? []);
        var capabilities = new List<string> { "model_execute", "project_read" };
        if (sandbox == "workspace-write") capabilities.Add("project_write");
        var allowedTools = operation.StartsWith("codex:", StringComparison.Ordinal) ? new[] { "codex-exec" } : [];
        var commandPolicyHash = Sha256(JsonSerializer.Serialize(new { allowedTools, sandbox }));
        var routeContractDisposition = HostedContextRouteContractPolicy.Resolve(operation);
        var payload = new JsonObject
        {
            ["schema_version"] = Schema,
            ["manifest_id"] = manifestId,
            ["identity_mode"] = "project-bound",
            ["service_principal_id"] = null,
            ["primary_domain"] = "workspace",
            ["allowed_dependency_domains"] = new JsonArray("phase", "toolchain"),
            ["visibility"] = new JsonObject { ["toolchain"] = "dependency", ["phase"] = "dependency", ["workspace"] = "active", ["marketplace"] = "excluded" },
            ["visibility_policy_revision"] = VisibilityPolicyRevision,
            ["lifecycle"] = "run-artifact-view",
            ["enforcement_level"] = "E2",
            ["gate_mode"] = "enforce",
            ["route_id"] = operation,
            ["skill_id"] = null,
            ["operation"] = operation,
            ["account_id"] = project.AccountId,
            ["project_id"] = project.ProjectId,
            ["workspace_id"] = project.WorkspaceId,
            ["workspace_generation"] = workspaceGeneration,
            ["run_id"] = runId,
            ["attempt_id"] = attemptId,
            ["dispatch_id"] = dispatchId,
            ["global_policy_revision"] = GlobalPolicyRevision,
            ["route_policy_revision"] = routePolicyRevision,
            ["skill_policy_revision"] = null,
            ["account_policy_revision"] = null,
            ["project_restrictions_sha256"] = projectRestrictionsHash,
            ["scope_profile_revision"] = ScopeProfileRevision,
            ["effective_capabilities"] = new JsonArray(capabilities.Select(value => (JsonNode?)JsonValue.Create(value)).ToArray()),
            ["repository_snapshot_id"] = null,
            ["template_snapshot_id"] = null,
            ["project_snapshot_id"] = projectSnapshotId,
            ["allowed_read_artifact_manifest_ref"] = "signed-payload://allowed_read_artifacts",
            ["allowed_read_artifact_manifest_sha256"] = readArtifactsHash,
            ["allowed_read_artifacts"] = readArtifacts,
            ["allowed_write_paths"] = new JsonArray(writes.Select(value => (JsonNode?)JsonValue.Create(value)).ToArray()),
            ["output_targets"] = new JsonArray(outputs.Select(value => (JsonNode?)JsonValue.Create(value)).ToArray()),
            ["context_assembly_result_ref"] = "signed-payload://context_assembly",
            ["context_assembly_result_sha256"] = contextAssemblyHash,
            ["context_assembly"] = contextAssembly,
            ["context_budget_profile_revision"] = BudgetProfileRevision,
            ["sandbox_policy"] = new JsonObject { ["revision"] = SandboxPolicyRevision, ["mode"] = sandbox },
            ["network_policy"] = new JsonObject { ["revision"] = NetworkPolicyRevision, ["mode"] = "provider-only", ["allowlist_sha256"] = null },
            ["tool_execution_policy"] = new JsonObject
            {
                ["revision"] = ToolPolicyRevision,
                ["allowed_tools"] = new JsonArray(allowedTools.Select(value => (JsonNode?)JsonValue.Create(value)).ToArray()),
                ["command_policy_sha256"] = commandPolicyHash
            },
            ["hosted_route_contracts"] = new JsonObject
            {
                ["mode"] = routeContractDisposition.Mode,
                ["applicability_policy_revision"] = routeContractDisposition.PolicyRevision,
                ["reason_code"] = routeContractDisposition.ReasonCode
            },
            ["execution_prompt_hash"] = promptHash,
            ["persisted_prompt_hash"] = persistedPromptHash,
            ["issued_at_utc"] = issuedAtUtc,
            ["not_before_utc"] = issuedAtUtc,
            ["expires_at_utc"] = expiresAtUtc,
            ["nonce"] = nonce,
            ["max_uses"] = 1
        };
        return Parse(payload.ToJsonString());
    }

    internal static string Canonicalize(JsonElement element)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping }))
        {
            WriteCanonical(writer, element);
        }
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    internal static string Sha256(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();

    private static void ValidateHostedRouteContracts(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.Object || value.EnumerateObject().Count() != 3 ||
            RequiredString(value, "mode") != "not_applicable" ||
            RequiredString(value, "applicability_policy_revision") != RouteApplicabilityPolicyRevision ||
            RequiredString(value, "reason_code") != HostedContextRouteContractPolicy.NoAggregateReason)
        {
            throw new ArgumentException("Hosted route contract disposition is invalid.");
        }
    }

    private static void ValidateInlineBindings(JsonElement root)
    {
        if (RequiredString(root, "allowed_read_artifact_manifest_ref") != "signed-payload://allowed_read_artifacts" ||
            RequiredString(root, "context_assembly_result_ref") != "signed-payload://context_assembly")
        {
            throw new ArgumentException("Hosted Context inline binding references are invalid.");
        }
        var artifacts = root.GetProperty("allowed_read_artifacts");
        if (artifacts.ValueKind != JsonValueKind.Array || artifacts.GetArrayLength() < 2)
        {
            throw new ArgumentException("Hosted Context allowed-read artifacts are incomplete.");
        }
        foreach (var artifact in artifacts.EnumerateArray())
        {
            _ = RequiredString(artifact, "artifact_ref");
            RequireSha256(artifact, "sha256");
        }
        var artifactsHash = Sha256(Canonicalize(artifacts));
        if (artifactsHash != RequiredString(root, "allowed_read_artifact_manifest_sha256"))
        {
            throw new ArgumentException("Hosted Context allowed-read manifest hash is invalid.");
        }
        var assembly = root.GetProperty("context_assembly");
        RequireSha256(assembly, "execution_prompt_sha256");
        RequireSha256(assembly, "input_manifest_sha256");
        RequireSha256(assembly, "project_snapshot_id");
        if (RequiredString(assembly, "execution_prompt_sha256") != RequiredString(root, "execution_prompt_hash") ||
            RequiredString(assembly, "input_manifest_sha256") != artifactsHash ||
            RequiredString(assembly, "project_snapshot_id") != RequiredString(root, "project_snapshot_id") ||
            Sha256(Canonicalize(assembly)) != RequiredString(root, "context_assembly_result_sha256"))
        {
            throw new ArgumentException("Hosted Context assembly binding is invalid.");
        }
    }

    private static string[] NormalizeProjectPaths(string projectRoot, IReadOnlyList<string> paths)
    {
        var root = Path.GetFullPath(projectRoot);
        var normalized = new List<string>();
        foreach (var value in paths)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(value);
            var absolute = Path.GetFullPath(Path.IsPathRooted(value) ? value : Path.Combine(root, value));
            var relative = Path.GetRelativePath(root, absolute).Replace('\\', '/');
            if (relative == ".." || relative.StartsWith("../", StringComparison.Ordinal) || Path.IsPathRooted(relative))
            {
                throw new ArgumentException("Hosted Context project path escapes the project root.", nameof(paths));
            }
            normalized.Add(relative == "." ? "project://" : $"project://{relative}");
        }
        return normalized.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
    }

    private static void ValidateProjectPaths(JsonElement paths)
    {
        if (paths.ValueKind != JsonValueKind.Array)
        {
            throw new ArgumentException("Hosted Context project paths must be arrays.");
        }
        var values = paths.EnumerateArray().Select(item => item.GetString()).ToArray();
        if (values.Any(value => string.IsNullOrWhiteSpace(value) || !value.StartsWith("project://", StringComparison.Ordinal) || value.Contains("..", StringComparison.Ordinal)) ||
            values.Distinct(StringComparer.Ordinal).Count() != values.Length)
        {
            throw new ArgumentException("Hosted Context project paths are invalid.");
        }
    }

    private static string RequiredString(JsonElement value, string property)
    {
        if (!value.TryGetProperty(property, out var item) || item.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(item.GetString()))
        {
            throw new ArgumentException($"Hosted Context signed payload field {property} is invalid.");
        }
        return item.GetString()!;
    }

    private static void RequireSha256(JsonElement value, string property)
    {
        if (!IsSha256(RequiredString(value, property)))
        {
            throw new ArgumentException($"Hosted Context signed payload field {property} is not SHA-256.");
        }
    }

    private static bool IsSha256(string value) => value.Length == 64 && value.All(character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static void WriteCanonical(Utf8JsonWriter writer, JsonElement element)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in element.EnumerateObject().OrderBy(item => item.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteCanonical(writer, property.Value);
                }
                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in element.EnumerateArray()) WriteCanonical(writer, item);
                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(element.GetString());
                break;
            case JsonValueKind.Number:
                writer.WriteRawValue(element.GetRawText(), skipInputValidation: false);
                break;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                break;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                break;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;
            default:
                throw new JsonException("Unsupported JSON value in Hosted Context payload.");
        }
    }
}
