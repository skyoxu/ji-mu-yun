using PhaseA.Platform.Data;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Projects;

public sealed class ProjectInitializationRecoveryService : BackgroundService
{
    private static readonly TimeSpan InitialDelay = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan Interval = TimeSpan.FromMinutes(1);
    private static readonly TimeSpan DefaultRunTimeout = TimeSpan.FromMinutes(30);
    private static readonly TimeSpan PrototypeWorkflowTimeout = TimeSpan.FromHours(2);
    private static readonly TimeSpan PrototypeFeedbackTimeout = TimeSpan.FromHours(1);
    private static readonly TimeSpan PrototypeQuickFixTimeout = TimeSpan.FromMinutes(15);
    private static readonly TimeSpan WebPreviewDefaultExportTimeout = TimeSpan.FromMinutes(3);
    private static readonly TimeSpan WebPreviewRecoveryGrace = TimeSpan.FromMinutes(2);
    private static readonly TimeSpan WebPreviewQueuedTimeout = TimeSpan.FromMinutes(30);

    private readonly ProjectInitializationService _initializationService;
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly ProjectWorkspaceMaintenanceService _workspaceMaintenanceService;
    private readonly PhaseAPlatformOptions _options;
    private readonly ILogger<ProjectInitializationRecoveryService> _logger;
    private readonly DateTimeOffset _processStartedUtc;

    public ProjectInitializationRecoveryService(
        ProjectInitializationService initializationService,
        PhaseAMetadataStore metadataStore,
        ProjectWorkspaceMaintenanceService workspaceMaintenanceService,
        PhaseAPlatformOptions options,
        ILogger<ProjectInitializationRecoveryService> logger)
    {
        _initializationService = initializationService;
        _metadataStore = metadataStore;
        _workspaceMaintenanceService = workspaceMaintenanceService;
        _options = options;
        _logger = logger;
        _processStartedUtc = DateTimeOffset.UtcNow;
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
                await _workspaceMaintenanceService.EnsureAllWorkspacesSeededAsync(stoppingToken);
                await _initializationService.ReconcileStaleInitializationsAsync(stoppingToken);
                await _metadataStore.ReconcileAbandonedRunsAsync(
                    run => SelectTimeout(run, _options, _processStartedUtc),
                    run => BuildFailureMessage(run, _processStartedUtc),
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

    private static TimeSpan? SelectTimeout(
        InterruptedRunSnapshot run,
        PhaseAPlatformOptions? options = null,
        DateTimeOffset? processStartedUtc = null)
    {
        return run.RunType switch
        {
            "chapter2-bootstrap" => null,
            "prototype-7day-playable" => PrototypeWorkflowTimeout,
            "prototype-feedback-iteration" => PrototypeFeedbackTimeout,
            "prototype-quick-fix" => PrototypeQuickFixTimeout,
            "project-web-preview" => SelectWebPreviewTimeout(run, options, processStartedUtc),
            _ => DefaultRunTimeout
        };
    }

    public static TimeSpan? SelectTimeoutForTesting(
        InterruptedRunSnapshot run,
        PhaseAPlatformOptions? options = null,
        DateTimeOffset? processStartedUtc = null)
    {
        return SelectTimeout(run, options, processStartedUtc);
    }

    public static string BuildFailureMessageForTesting(InterruptedRunSnapshot run, DateTimeOffset? processStartedUtc = null)
    {
        return BuildFailureMessage(run, processStartedUtc);
    }

    private static TimeSpan SelectWebPreviewTimeout(
        InterruptedRunSnapshot run,
        PhaseAPlatformOptions? options,
        DateTimeOffset? processStartedUtc)
    {
        if (IsQueuedWebPreview(run))
        {
            if (IsOrphanedQueuedWebPreview(run, processStartedUtc))
            {
                return TimeSpan.Zero;
            }

            return WebPreviewQueuedTimeout;
        }

        var exportTimeout = options is not null && options.Godot3WebPreviewExportTimeoutSeconds > 0
            ? TimeSpan.FromSeconds(options.Godot3WebPreviewExportTimeoutSeconds)
            : WebPreviewDefaultExportTimeout;
        return exportTimeout + WebPreviewRecoveryGrace;
    }

    private static string BuildFailureMessage(InterruptedRunSnapshot run, DateTimeOffset? processStartedUtc)
    {
        if (IsOrphanedQueuedWebPreview(run, processStartedUtc))
        {
            return "Queued web preview was recovered after the server restarted before its background worker picked it up.";
        }

        return $"Run was recovered after exceeding the inactivity timeout for {run.RunType}.";
    }

    private static bool IsQueuedWebPreview(InterruptedRunSnapshot run)
    {
        return string.Equals(run.RunType, "project-web-preview", StringComparison.Ordinal) &&
               string.Equals(run.Status, "queued", StringComparison.Ordinal);
    }

    private static bool IsOrphanedQueuedWebPreview(
        InterruptedRunSnapshot run,
        DateTimeOffset? processStartedUtc)
    {
        return IsQueuedWebPreview(run) &&
               processStartedUtc is not null &&
               DateTimeOffset.TryParse(run.CreatedUtc, out var createdUtc) &&
               createdUtc < processStartedUtc.Value;
    }
}
