using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeWorkflowService
{
    private const string RunType = "prototype-7day-playable";

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly PrototypeRecordWriter _recordWriter;
    private readonly PrototypeWorkflowCommandBuilder _commandBuilder;
    private readonly PrototypeArtifactIndexer _artifactIndexer;
    private readonly LlmBindingService _llmBindingService;
    private readonly LlmStopLossService _llmStopLossService;

    public PrototypeWorkflowService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        PrototypeRecordWriter recordWriter,
        PrototypeWorkflowCommandBuilder commandBuilder,
        PrototypeArtifactIndexer artifactIndexer,
        LlmBindingService llmBindingService,
        LlmStopLossService llmStopLossService)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _recordWriter = recordWriter;
        _commandBuilder = commandBuilder;
        _artifactIndexer = artifactIndexer;
        _llmBindingService = llmBindingService;
        _llmStopLossService = llmStopLossService;
    }

    public async Task<PrototypeWorkflowResult> RunAsync(string projectId, PrototypeWorkflowRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var missing = PrototypeWorkflowValidation.MissingRequiredFields(request);
        if (missing.Count > 0)
        {
            return new PrototypeWorkflowResult("", "missing_required_fields", 2, "", "", "", [], missing);
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        var usesLlm = IsLlmScoring(request.ScoreEngine);
        LlmCostEstimate? llmEstimate = null;
        LlmStopLossDecision? stopLoss = null;
        if (usesLlm)
        {
            var binding = await _llmBindingService.GetAsync(project.AccountId, cancellationToken);
            if (binding is null)
            {
                return new PrototypeWorkflowResult("", "llm_binding_required", 402, "", "", "new-api binding is required", [], []);
            }

            llmEstimate = new LlmCostEstimate(0.50m, Model: request.ScoreEngine, RequestId: null);
            stopLoss = await _llmStopLossService.CheckAsync(project.AccountId, llmEstimate, cancellationToken);
            if (!stopLoss.Allowed)
            {
                return new PrototypeWorkflowResult("", stopLoss.FailureCode!, 402, "", "", "LLM stop-loss blocked the operation", [], []);
            }
        }

        var prototypeRecordPath = _recordWriter.Write(request);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        var process = await _processRunner.RunAsync(_commandBuilder.Build(request, prototypeRecordPath), cancellationToken);
        var status = process.ExitCode == 0 ? "succeeded" : "failed";
        var slug = PrototypeRecordWriter.SanitizeSlug(request.Slug!);
        var discoveredArtifacts = _artifactIndexer.Discover(_options.RepositoryRoot, runId, project.ProjectId, slug, prototypeRecordPath);

        foreach (var artifact in discoveredArtifacts)
        {
            await _metadataStore.AddArtifactAsync(artifact, cancellationToken);
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            prototype_record = prototypeRecordPath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray()
        });
        await _metadataStore.CompleteRunAsync(runId, status, process.ExitCode, process.Stdout, process.Stderr, evidenceJson, cancellationToken);
        if (usesLlm && llmEstimate is not null && stopLoss is not null)
        {
            await _metadataStore.RecordRunLlmAuditAsync(
                runId,
                _options.LlmGatewayProvider,
                llmEstimate.RequestId,
                llmEstimate.Model,
                LlmStopLossService.BuildCostJson(llmEstimate, stopLoss),
                cancellationToken);
        }

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);

        return new PrototypeWorkflowResult(runId, status, process.ExitCode, prototypeRecordPath, process.Stdout, process.Stderr, artifacts, []);
    }

    private static bool IsLlmScoring(string? scoreEngine)
    {
        return string.Equals(scoreEngine, "codex", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(scoreEngine, "hybrid", StringComparison.OrdinalIgnoreCase);
    }
}
