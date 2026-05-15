using PhaseA.Platform.Data;

namespace PhaseA.Platform.Projects;

public sealed class ProjectInitializationRecoveryService : BackgroundService
{
    private static readonly TimeSpan InitialDelay = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan Interval = TimeSpan.FromMinutes(1);
    private static readonly TimeSpan DefaultRunTimeout = TimeSpan.FromMinutes(30);
    private static readonly TimeSpan PrototypeWorkflowTimeout = TimeSpan.FromHours(2);
    private static readonly TimeSpan PrototypeFeedbackTimeout = TimeSpan.FromHours(1);

    private readonly ProjectInitializationService _initializationService;
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly ILogger<ProjectInitializationRecoveryService> _logger;

    public ProjectInitializationRecoveryService(
        ProjectInitializationService initializationService,
        PhaseAMetadataStore metadataStore,
        ILogger<ProjectInitializationRecoveryService> logger)
    {
        _initializationService = initializationService;
        _metadataStore = metadataStore;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            await Task.Delay(InitialDelay, stoppingToken);
        }
        catch (OperationCanceledException)
        {
            return;
        }

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await _initializationService.ReconcileStaleInitializationsAsync(stoppingToken);
                await _metadataStore.ReconcileAbandonedRunsAsync(
                    SelectTimeout,
                    BuildFailureMessage,
                    stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                return;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Project initialization recovery scan failed.");
            }

            try
            {
                await Task.Delay(Interval, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                return;
            }
        }
    }

    private static TimeSpan? SelectTimeout(InterruptedRunSnapshot run)
    {
        return run.RunType switch
        {
            "chapter2-bootstrap" => null,
            "prototype-7day-playable" => PrototypeWorkflowTimeout,
            "prototype-feedback-iteration" => PrototypeFeedbackTimeout,
            _ => DefaultRunTimeout
        };
    }

    private static string BuildFailureMessage(InterruptedRunSnapshot run)
    {
        return $"Run was recovered after exceeding the inactivity timeout for {run.RunType}.";
    }
}
