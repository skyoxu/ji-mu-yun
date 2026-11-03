using System.Collections.Frozen;
using Microsoft.Extensions.Hosting;
using PhaseA.Platform.Prototypes;

namespace PhaseA.Platform.Configuration;

public sealed record HostedContextSigningKeyRing(
    string ActiveKeyId,
    IReadOnlyDictionary<string, string> Keys);

public sealed record PhaseAPlatformOptions(
    string HostedWorkspaceRoot,
    int HostedProjectLimit,
    string HttpsTermination,
    string AppBindUrl,
    string PublicBaseUrl,
    string LlmGatewayProvider,
    string LlmGatewayBaseUrl,
    string LlmGatewayTokenMode,
    string LlmGatewayBindingMode,
    decimal LlmCostStopLossPerRunCny,
    decimal LlmCostStopLossDailyAccountCny,
    string MetadataDatabasePath,
    string RepositoryRoot,
    string PythonCommand,
    string? GodotBin,
    string DeliveryProfile,
    string AdminUsername,
    string? AdminPasswordHash,
    string? AdminTokenHash,
    string? TicketSigningSecret,
    string? WebPreviewSigningSecret,
    HostedContextSigningKeyRing? HostedContextSigningKeyRing,
    int MaxConcurrentChats,
    int MaxConcurrentChatsPerAccount,
    int MaxConcurrentQuestionForms,
    int MaxConcurrentQuestionFormsPerAccount,
    int MaxConcurrentProjectCreations,
    int MaxConcurrentProjectCreationsPerAccount,
    int MaxConcurrentOtherRuns,
    int MaxConcurrentPrototypeCreations,
    int MaxConcurrentAssetGenerations,
    int MaxConcurrentWebPreviews,
    int MaxConcurrentWebPreviewsPerAccount,
    int Godot3WebPreviewExportTimeoutSeconds,
    int Godot3WebPreviewExportInactivityTimeoutSeconds,
    int MaxConcurrentAssetGenerationsPerAccount,
    bool AiCodeMirrorBillingEnabled,
    string AiCodeMirrorBaseUrl,
    string? AiCodeMirrorCookie,
    string? AiCodeMirrorApiKeyName,
    string AiCodeMirrorCodexHomeRoot,
    IReadOnlyList<string> AssetAllowedUrlPrefixes)
{
    public string PhaseServiceState { get; init; } = PhaseServiceStates.Development;

    // ADR-0061 AD15/AD20: immutable startup responsibilities, never phase-state defaults.
    public string? NodeId { get; init; }
    public string? NodeScope { get; init; }
    public string? NodeTopology { get; init; }
    public bool? AcceptNewAccounts { get; init; }
    public IReadOnlySet<string> EnabledRoles { get; init; } = Array.Empty<string>().ToFrozenSet(StringComparer.Ordinal);
    public bool EntryRoleEnabled => EnabledRoles.Contains("entry");
    public bool ProductionRoleEnabled => EnabledRoles.Contains("production");

    // ADR-0061: only the composition root binds the immutable host lifetime.
    private IHostApplicationLifetime? _nodeLifetime;
    internal void BindNodeLifetime(IHostApplicationLifetime lifetime)
    {
        ArgumentNullException.ThrowIfNull(lifetime);
        var previous = Interlocked.CompareExchange(ref _nodeLifetime, lifetime, null);
        if (previous is not null && !ReferenceEquals(previous, lifetime))
            throw new InvalidOperationException("node_lifetime_already_bound");
    }

    internal bool NodeProductionStopping => _nodeLifetime is { } lifetime &&
        (lifetime.ApplicationStopping.IsCancellationRequested || lifetime.ApplicationStopped.IsCancellationRequested);

    public void ValidateServiceIdentity()
    {
        if (EnabledRoles.Count == 0)
            throw new PhaseAPlatformConfigException("PHASEA_ENABLED_ROLES must explicitly contain entry and/or production.");
        if (string.IsNullOrWhiteSpace(NodeId))
            throw new PhaseAPlatformConfigException("PHASEA_NODE_ID must be explicitly configured.");
        if (NodeScope != "single_node_test")
            throw new PhaseAPlatformConfigException("PHASEA_NODE_SCOPE must be single_node_test; formal production is not enabled.");
        if (AcceptNewAccounts is null)
            throw new PhaseAPlatformConfigException("PHASEA_ACCEPT_NEW_ACCOUNTS must explicitly be true or false.");
        if (NodeTopology != "single_service")
            throw new PhaseAPlatformConfigException("PHASEA_NODE_TOPOLOGY must be single_service; independent schedulers are unsupported.");
    }

    // AD22: observation only. These facts never authorize placement or replace queue budgets.
    internal LocalNodeCapacityReadback ReadLocalNodeCapacity(IHostApplicationLifetime? lifetime)
    {
        ValidateServiceIdentity();
        var online = lifetime is not null && lifetime.ApplicationStarted.IsCancellationRequested &&
            !lifetime.ApplicationStopping.IsCancellationRequested && !lifetime.ApplicationStopped.IsCancellationRequested;
        // S2-03A alone supplies a real measurement; current S2-06 has no measurement provider.
        return new LocalNodeCapacityReadback(NodeId!, online, AcceptNewAccounts!.Value, false, null, null);
    }

    // Authority reduction occurs in the trusted configuration owner; no reverse conversion exists.
    public static implicit operator NodeExecutionOptions(PhaseAPlatformOptions source) => new(source);
    public static implicit operator NodeTicketSigner(PhaseAPlatformOptions source) => new(source.TicketSigningSecret);
    public static implicit operator NodePreviewRuntime(PhaseAPlatformOptions source) => new((NodeExecutionOptions)source, new NodeTicketSigner(source.WebPreviewSigningSecret));

    public bool GovernanceChecksEnabled =>
        PhaseServiceStates.GovernanceChecksEnabled(PhaseServiceState);
}

public static class PhaseServiceStates
{
    public const string Development = "development";
    public const string Test = "test";
    public const string Production = "production";

    public static bool GovernanceChecksEnabled(string state) =>
        state == Test || state == Production;
}

public sealed record LocalNodeCapacityReadback(
    string NodeId,
    bool Online,
    bool AcceptNewAccounts,
    bool MeasurementValid,
    string? CapacityRef,
    string? ReadinessRef);

// ADR-0061 AD14: immutable nonsecret execution data, never the protected configuration object.
public sealed class NodeExecutionOptions
{
    internal NodeExecutionOptions(PhaseAPlatformOptions source)
    {
        ArgumentNullException.ThrowIfNull(source);
        HostedWorkspaceRoot=source.HostedWorkspaceRoot; RepositoryRoot=source.RepositoryRoot;
        // These existing catalogs retain only loaded public data, never the supplied options.
        GameTypeGuides=new GameTypeGuideCatalog(source);
        GameTypeTemplates=new GameTypeTemplateCatalog(source);
        PythonCommand=source.PythonCommand; GodotBin=source.GodotBin; DeliveryProfile=source.DeliveryProfile;
        LlmGatewayProvider=source.LlmGatewayProvider;
        LlmCostStopLossPerRunCny=source.LlmCostStopLossPerRunCny;
        LlmCostStopLossDailyAccountCny=source.LlmCostStopLossDailyAccountCny;
        MaxConcurrentPrototypeCreations=source.MaxConcurrentPrototypeCreations;
        MaxConcurrentAssetGenerations=source.MaxConcurrentAssetGenerations;
        MaxConcurrentAssetGenerationsPerAccount=source.MaxConcurrentAssetGenerationsPerAccount;
        MaxConcurrentWebPreviews=source.MaxConcurrentWebPreviews;
        MaxConcurrentWebPreviewsPerAccount=source.MaxConcurrentWebPreviewsPerAccount;
        Godot3WebPreviewExportTimeoutSeconds=source.Godot3WebPreviewExportTimeoutSeconds;
        Godot3WebPreviewExportInactivityTimeoutSeconds=source.Godot3WebPreviewExportInactivityTimeoutSeconds;
        AssetAllowedUrlPrefixes=Array.AsReadOnly(source.AssetAllowedUrlPrefixes.ToArray());
        NodeId=source.NodeId; NodeScope=source.NodeScope; NodeTopology=source.NodeTopology;
        AcceptNewAccounts=source.AcceptNewAccounts;
        EnabledRoles=source.EnabledRoles.ToFrozenSet(StringComparer.Ordinal);
    }
    public GameTypeGuideCatalog GameTypeGuides { get; }
    public GameTypeTemplateCatalog GameTypeTemplates { get; }
    public static ProjectGameTypeContractSnapshot GameTypeContract(NodeExecutionOptions? options,
        ProjectGameTypeMatchEvidence evidence, bool refresh = false)
    {
        if(options is null || string.IsNullOrWhiteSpace(evidence.MatchedGameTypeId))
            return ProjectGameTypeContractSnapshot.Empty();
        var entry=new BmadGameTypeDesignCatalog(options.RepositoryRoot).Find(evidence.MatchedGameTypeId);
        var value=entry is null ? ProjectGameTypeContractSnapshot.Empty() : ProjectGameTypeContractSnapshot.FromEntry(entry);
        if(!refresh || !value.HasContract) return value;
        var current=ProjectGameTypeContractSnapshot.Normalize(evidence.ContractSnapshot);
        return value with { CreatedUtc=current.HasContract ? current.CreatedUtc : value.CreatedUtc };
    }
    public string HostedWorkspaceRoot { get; }
    public string RepositoryRoot { get; }
    public string DeliveryProfile { get; }
    public string PythonCommand { get; }
    public string? GodotBin { get; }
    public string LlmGatewayProvider { get; }
    public decimal LlmCostStopLossPerRunCny { get; }
    public decimal LlmCostStopLossDailyAccountCny { get; }
    public int MaxConcurrentPrototypeCreations { get; }
    public int MaxConcurrentAssetGenerations { get; }
    public int MaxConcurrentAssetGenerationsPerAccount { get; }
    public int MaxConcurrentWebPreviews { get; }
    public int MaxConcurrentWebPreviewsPerAccount { get; }
    public int Godot3WebPreviewExportTimeoutSeconds { get; }
    public int Godot3WebPreviewExportInactivityTimeoutSeconds { get; }
    public IReadOnlyList<string> AssetAllowedUrlPrefixes { get; }
    public string? NodeId { get; }
    public string? NodeScope { get; }
    public string? NodeTopology { get; }
    public bool? AcceptNewAccounts { get; }
    public IReadOnlySet<string> EnabledRoles { get; }
    public bool ProductionRoleEnabled => EnabledRoles.Contains("production");
    public bool EntryRoleEnabled => EnabledRoles.Contains("entry");
    public LocalNodeCapacityReadback ReadLocalNodeCapacity(IHostApplicationLifetime? lifetime)
    {
        if(string.IsNullOrWhiteSpace(NodeId) || NodeScope!="single_node_test" || NodeTopology!="single_service" || AcceptNewAccounts is null || EnabledRoles.Count==0)
            throw new InvalidOperationException("node_configuration_unavailable");
        var online=lifetime is not null && lifetime.ApplicationStarted.IsCancellationRequested &&
            !lifetime.ApplicationStopping.IsCancellationRequested && !lifetime.ApplicationStopped.IsCancellationRequested;
        return new(NodeId,online,AcceptNewAccounts.Value,false,null,null);
    }
}

// Purpose-only cryptographic backing; public consumers cannot obtain raw key/configuration or sign arbitrary data.
public sealed class NodeTicketSigner
{
    private readonly byte[]? _key;
    internal NodeTicketSigner(string? secret) => _key=string.IsNullOrWhiteSpace(secret) ? null : System.Text.Encoding.UTF8.GetBytes(secret);
    internal bool IsConfigured => _key is not null;
    internal byte[]? TrySign(string payload)
    {
        if(_key is null) return null;
        using var hmac=new System.Security.Cryptography.HMACSHA256(_key);
        return hmac.ComputeHash(System.Text.Encoding.UTF8.GetBytes(payload));
    }
}

// ADR-0061 AD14: preview-only central backing; neither signing keys nor runtime credentials are returned.
public sealed class NodePreviewRuntime
{
    private readonly NodeTicketSigner _signer;
    private readonly PhaseA.Platform.Llm.AiCodeMirrorKeyPoolService? _keyPool;
    internal NodePreviewRuntime(NodeExecutionOptions settings, NodeTicketSigner signer,
        PhaseA.Platform.Llm.AiCodeMirrorKeyPoolService? keyPool=null)
    { Settings=settings; _signer=signer; _keyPool=keyPool; }
    public NodeExecutionOptions Settings { get; }
    internal bool SigningConfigured => _signer.IsConfigured;
    internal byte[] Sign(string payload) => _signer.TrySign(payload) ??
        throw new InvalidOperationException("A web preview signing secret is not configured.");
    internal static NodePreviewRuntime ExecutionOnly(NodeExecutionOptions settings,
        PhaseA.Platform.Llm.AiCodeMirrorKeyPoolService? pool) => new(settings,new NodeTicketSigner(null),pool);
    internal async Task<PhaseA.Platform.Runs.HostedProcessResult> ExecuteAsync(
        PhaseA.Platform.Runs.HostedProcessCommand command, PhaseA.Platform.Runs.IHostedProcessRunner runner,
        string accountId, string runId, TimeSpan total, TimeSpan inactivity, CancellationToken cancellationToken)
    {
        var credential = _keyPool is null
            ? new PhaseA.Platform.Llm.AiCodeMirrorRuntimeCredential(accountId,null,null)
            : await _keyPool.ResolveRuntimeCredentialForAccountAsync(accountId,cancellationToken);
        return await runner.RunAsync(PhaseA.Platform.Runs.CodexHostedProcessCommandFactory.ApplyRuntime(command,credential)
            .WithRunId(runId).WithTimeouts(total,inactivity),cancellationToken);
    }
}
