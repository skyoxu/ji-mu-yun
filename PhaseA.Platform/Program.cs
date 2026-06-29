using PhaseA.Platform.Browser;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;
using Microsoft.Data.Sqlite;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.FileProviders;
using System.Text;
using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);
var options = PhaseAPlatformOptionsLoader.FromEnvironment();
var metadataDirectory = Path.GetDirectoryName(options.MetadataDatabasePath);
if (!string.IsNullOrWhiteSpace(metadataDirectory))
{
    Directory.CreateDirectory(metadataDirectory);
}
var connectionString = new SqliteConnectionStringBuilder
{
    DataSource = options.MetadataDatabasePath
}.ToString();

await SqliteMetadataSchema.InitializeAsync(connectionString);

builder.Services.AddSingleton(options);
builder.Services.AddSingleton(new PhaseAMetadataStore(connectionString, options));
builder.Services.AddSingleton<ProjectRuleCatalog>();
builder.Services.AddSingleton<GameTypeTemplateCatalog>();
builder.Services.AddSingleton<IProjectWorkspaceSeeder, ProjectWorkspaceSeeder>();
builder.Services.AddSingleton<ProjectWorkspaceMaintenanceService>();
builder.Services.AddSingleton(new ProjectCreationConcurrencyLimiter(
    options.MaxConcurrentProjectCreations,
    options.MaxConcurrentProjectCreationsPerAccount));
builder.Services.AddSingleton<ProjectCreationService>();
builder.Services.AddSingleton<ProjectDraftImportService>();
builder.Services.AddSingleton<ProjectInitializationService>();
builder.Services.AddHostedService<ProjectInitializationRecoveryService>();
builder.Services.AddSingleton<RunCancellationService>();
builder.Services.AddSingleton<IHostedProcessRunner, HostedProcessRunner>();
builder.Services.AddSingleton<Chapter2BootstrapCommandBuilder>();
builder.Services.AddSingleton<ProjectHealthArtifactIndexer>();
builder.Services.AddSingleton<Chapter2BootstrapService>();
builder.Services.AddSingleton(new ProjectCreationRunnerQueue(new HeavyRunnerQueueService(
    TimeSpan.FromMinutes(8),
    options.MaxConcurrentProjectCreations)));
builder.Services.AddSingleton(new HeavyRunnerQueueService(
    TimeSpan.FromMinutes(8),
    options.MaxConcurrentOtherRuns));
builder.Services.AddKeyedSingleton("prototype-creation", new HeavyRunnerQueueService(
    TimeSpan.FromMinutes(25),
    options.MaxConcurrentPrototypeCreations));
builder.Services.AddKeyedSingleton("asset-generation", new HeavyRunnerQueueService(
    TimeSpan.FromMinutes(4),
    options.MaxConcurrentAssetGenerations));
builder.Services.AddKeyedSingleton("web-preview", new HeavyRunnerQueueService(
    TimeSpan.FromMinutes(3),
    options.MaxConcurrentWebPreviews));
builder.Services.AddSingleton(new ProjectWebPreviewConcurrencyLimiter(
    options.MaxConcurrentWebPreviewsPerAccount));
builder.Services.AddSingleton<ProjectWebPreviewSemanticAdapterService>();
builder.Services.AddSingleton<ProjectWebPreviewDedicatedAdapterService>();
builder.Services.AddSingleton(new AssetGenerationConcurrencyLimiter(
    options.MaxConcurrentAssetGenerationsPerAccount));
builder.Services.AddSingleton<PrototypeRecordWriter>();
builder.Services.AddSingleton<IGameTypeRouteEngine, GameTypeRouteEngine>();
builder.Services.AddSingleton<PrototypeWorkflowCommandBuilder>();
builder.Services.AddSingleton<PrototypeArtifactIndexer>();
builder.Services.AddSingleton<PrototypeRouteStateWriter>();
builder.Services.AddSingleton<PrototypeEngineeringClosureService>();
builder.Services.AddSingleton<PrototypeWorkflowService>();
builder.Services.AddSingleton<IPrototypeFromGddWorkflow>(sp => sp.GetRequiredService<PrototypeWorkflowService>());
builder.Services.AddSingleton<IPrototypeLightweightValidationService, PrototypeLightweightValidationService>();
builder.Services.AddSingleton<PrototypeFeedbackIterationService>();
builder.Services.AddSingleton<PrototypeQuickFixService>();
builder.Services.AddSingleton<PrototypeNeedsFixRouteService>();
builder.Services.AddSingleton<PrototypeIterationPlanService>();
builder.Services.AddSingleton<PrototypeIterationGoalService>();
builder.Services.AddSingleton<PrototypeRepairPlanService>();
builder.Services.AddSingleton<PrototypeUiOptimizationService>();
builder.Services.AddSingleton<GddMilestoneStepService>();
builder.Services.AddSingleton<GameDesignDocumentService>();
builder.Services.AddSingleton(new QuestionFormConcurrencyLimiter(
    options.MaxConcurrentQuestionForms,
    options.MaxConcurrentQuestionFormsPerAccount));
builder.Services.AddSingleton<GameDesignQuestionFormService>();
builder.Services.AddSingleton<PrototypeCommandBuilder>();
builder.Services.AddSingleton<PrototypeTddArtifactIndexer>();
builder.Services.AddSingleton<PrototypeCommandService>();
builder.Services.AddSingleton<SkillActionCatalog>();
builder.Services.AddSingleton<SkillActionService>();
builder.Services.AddSingleton<ArtifactReadbackService>();
builder.Services.AddSingleton<ProjectWebPreviewService>();
builder.Services.AddSingleton<ProjectPackageService>();
builder.Services.AddSingleton<ProjectAssetInventoryService>();
builder.Services.AddSingleton<ProjectAssetImageGenerator>();
builder.Services.AddHttpClient<ProjectAssetLibraryService>()
    .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
    {
        AllowAutoRedirect = false
    });
builder.Services.AddSingleton<ProjectPackageDownloadTicketService>();
builder.Services.AddSingleton<ProjectAssetPreviewTicketService>();
builder.Services.AddSingleton<LlmBindingService>();
builder.Services.AddSingleton<LlmStopLossService>();
builder.Services.AddSingleton<AiCodeMirrorKeyPoolService>();
builder.Services.AddHttpClient<IAiCodeMirrorBillingClient, AiCodeMirrorBillingClient>();
builder.Services.AddHttpClient<INewApiChatClient, NewApiChatClient>();
builder.Services.AddHttpClient<IAiCodeMirrorResponsesClient, AiCodeMirrorResponsesClient>();
builder.Services.AddSingleton<ICodexChatClient, CodexCliChatClient>();
builder.Services.AddSingleton<ILlmRouteEngine, LlmRouteEngine>();
builder.Services.AddSingleton(new ChatConcurrencyLimiter(
    options.MaxConcurrentChats,
    options.MaxConcurrentChatsPerAccount));
builder.Services.AddTransient<ChatService>();
builder.Services.AddSingleton<ProjectChatHistoryService>();
builder.Services.AddSingleton<ProjectWorkflowRouteService>();
builder.Services.AddSingleton<BrowserUiRenderer>();

var app = builder.Build();
var metadataStore = app.Services.GetRequiredService<PhaseAMetadataStore>();
var adminAccountId = await metadataStore.EnsureSingleAdminAsync();
var initializationService = app.Services.GetRequiredService<ProjectInitializationService>();
await initializationService.ReconcileInterruptedInitializationsAsync();
var interruptedRunCount = await metadataStore.ReconcileInterruptedRunsAsync(
    "Run was interrupted because the service restarted before completion.");
await metadataStore.ReconcileProjectBootstrapStatusAsync();
await initializationService.ReconcileStaleInitializationsAsync();
var workspaceMaintenance = app.Services.GetRequiredService<ProjectWorkspaceMaintenanceService>();
await workspaceMaintenance.EnsureAllWorkspacesSeededAsync();
_ = Task.Run(async () =>
{
    try
    {
        var health = await app.Services.GetRequiredService<ProjectWebPreviewService>().GetGodot3HealthAsync(CancellationToken.None);
        if (string.Equals(health.Status, "healthy", StringComparison.Ordinal))
        {
            app.Logger.LogInformation(
                "Godot3 web preview health preheat completed. SmokeStatus={SmokeStatus}",
                health.SmokeStatus);
        }
        else
        {
            app.Logger.LogWarning(
                "Godot3 web preview health preheat reported unhealthy status. SmokeStatus={SmokeStatus} Error={SmokeError}",
                health.SmokeStatus,
                health.SmokeError);
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogWarning(ex, "Godot3 web preview health preheat failed.");
    }
}, CancellationToken.None);
if (interruptedRunCount > 0)
{
    app.Logger.LogWarning("Recovered {InterruptedRunCount} interrupted runs during startup.", interruptedRunCount);
}

app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new PhysicalFileProvider(ResolveStaticWebRoot(builder.Environment.ContentRootPath)),
    RequestPath = ""
});

app.Use(async (context, next) =>
{
    if (context.Request.Path == "/healthz" ||
        context.Request.Path == "/favicon.ico" ||
        context.Request.Path == "/" ||
        context.Request.Path == "/ui" ||
        context.Request.Path == "/ui-v2" ||
        context.Request.Path == "/backup" ||
        context.Request.Path == "/gdd-outline" ||
        context.Request.Path.StartsWithSegments("/ui-v2/icons") ||
        context.Request.Path == "/downloads" ||
        context.Request.Path == "/assets" ||
        context.Request.Path == "/admin/llm-usage" ||
        context.Request.Path == "/admin/run-duration-metrics" ||
        context.Request.Path == "/admin/chat-average-metrics" ||
        (context.Request.Path.StartsWithSegments("/projects") &&
         context.Request.Path.Value?.Contains("/asset-preview", StringComparison.Ordinal) == true &&
         context.Request.Query.ContainsKey("ticket")) ||
        (context.Request.Path.StartsWithSegments("/projects") &&
         context.Request.Path.Value?.Contains("/packages/", StringComparison.Ordinal) == true &&
         context.Request.Query.ContainsKey("ticket")) ||
        (context.Request.Path.StartsWithSegments("/projects") &&
         context.Request.Path.Value?.Contains("/web-previews/", StringComparison.Ordinal) == true) ||
        (context.Request.Path.StartsWithSegments("/projects") &&
         context.Request.Path.Value?.Contains("/gdd/GDD.md", StringComparison.Ordinal) == true &&
         context.Request.Query.ContainsKey("ticket")))
    {
        await next(context);
        return;
    }

    var identity = await ResolveIdentityAsync(context, adminAccountId);
    if (identity is null)
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        await context.Response.WriteAsJsonAsync(new { error = PhaseAAuth.AuthFailureCode });
        return;
    }

    if (TryReadApiProjectId(context.Request.Path, out var projectId) &&
        !await metadataStore.ProjectBelongsToAccountAsync(identity.AccountId, projectId, context.RequestAborted))
    {
        context.Response.StatusCode = StatusCodes.Status404NotFound;
        await context.Response.WriteAsJsonAsync(new { error = "project_not_found" });
        return;
    }

    context.Items["phasea.identity"] = identity;
    context.Items["phasea.role"] = identity.Role;
    context.Items["phasea.accountId"] = identity.AccountId;
    context.Items["phasea.username"] = identity.Username;
    PersistAccessTokenCookie(context);
    await next(context);
});

app.MapGet("/healthz", () => Results.Ok(new
{
    status = "ok",
    service = "phase-a-platform"
}));

app.MapGet("/favicon.ico", () => Results.NoContent());

app.MapGet("/", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderShellV2(), "text/html; charset=utf-8");
});

app.MapGet("/ui", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderShellV2(), "text/html; charset=utf-8");
});

app.MapGet("/ui-v2", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderShellV2(), "text/html; charset=utf-8");
});

app.MapGet("/gdd-outline", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderGddOutline(), "text/html; charset=utf-8");
});

app.MapGet("/backup", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderShell(), "text/html; charset=utf-8");
});

app.MapGet("/api/projects", async (
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    return Results.Ok(await readback.ListProjectsAsync(CurrentAccountId(context), cancellationToken));
});

app.MapGet("/api/project-creation-failures/latest", async (
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var failure = await readback.GetLatestProjectCreationFailureAsync(CurrentAccountId(context), cancellationToken);
    return failure is null ? Results.NotFound(new { error = "project_creation_failure_not_found" }) : Results.Ok(failure);
});

app.MapGet("/api/session", (HttpContext context) => Results.Ok(new
{
    authenticated = true,
    accountId = CurrentIdentity(context).AccountId,
    username = CurrentIdentity(context).Username,
    role = CurrentIdentity(context).Role
}));

app.MapGet("/api/account/active-run", async (
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    return Results.Ok(await readback.GetActiveRunAsync(CurrentAccountId(context), cancellationToken));
});

app.MapPost("/api/runs/{runId}/cancel", async (
    string runId,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    [FromServices] ArtifactReadbackService readback,
    [FromServices] RunCancellationService runCancellation,
    [FromServices] HeavyRunnerQueueService heavyRunnerQueue,
    [FromKeyedServices("prototype-creation")] HeavyRunnerQueueService prototypeCreationQueue,
    [FromKeyedServices("asset-generation")] HeavyRunnerQueueService assetRunnerQueue,
    [FromKeyedServices("web-preview")] HeavyRunnerQueueService webPreviewQueue,
    CancellationToken cancellationToken) =>
{
    var accountId = CurrentAccountId(context);
    var run = await readback.GetRunForAccountAsync(accountId, runId, cancellationToken);
    if (run is null)
    {
        return Results.NotFound(new { error = "run_not_found" });
    }

    if (RunCancellationPolicy.IsCancellationBlocked(run.RunType))
    {
        return Results.Conflict(new { error = "run_cancel_not_allowed" });
    }

    var result = await store.CancelRunAsync(accountId, runId, cancellationToken);
    if (result == RunCancelResult.NotFound)
    {
        return Results.NotFound(new { error = "run_not_found" });
    }

    if (result == RunCancelResult.NotActive)
    {
        return Results.Conflict(new { error = "run_not_active" });
    }

    runCancellation.Cancel(runId);
    heavyRunnerQueue.CancelRun(runId);
    prototypeCreationQueue.CancelRun(runId);
    assetRunnerQueue.CancelRun(runId);
    webPreviewQueue.CancelRun(runId);
    return Results.Ok(new { runId, status = "cancel" });
});

app.MapGet("/api/heavy-runner/queue", (
    HttpContext context,
    [FromServices] ArtifactReadbackService readback) =>
{
    return Results.Ok(readback.GetHeavyRunnerQueue(CurrentAccountId(context), CurrentIdentity(context).IsAdmin));
});

app.MapGet("/api/account/llm-usage", async (
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    return Results.Ok(await readback.GetAccountLlmUsageAsync(CurrentAccountId(context), cancellationToken));
});

app.MapGet("/api/admin/llm-usage", async (
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    return Results.Ok(await readback.GetAdminLlmUsageAsync(cancellationToken));
});

app.MapGet("/api/admin/llm-usage/aggregate", async (
    string? grain,
    string? split,
    string? fromUtc,
    string? toUtc,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    try
    {
        return Results.Ok(await readback.GetAdminLlmUsageAggregateAsync(grain, split, fromUtc, toUtc, cancellationToken));
    }
    catch (ArgumentOutOfRangeException ex)
    {
        return Results.BadRequest(new { error = "invalid_llm_usage_query", detail = ex.Message });
    }
});

app.MapGet("/api/admin/llm-usage.csv", async (
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var usage = await readback.GetAdminLlmUsageAsync(cancellationToken);
    var csv = ArtifactReadbackService.ExportAdminLlmUsageCsv(usage);
    return Results.Text(
        csv,
        "text/csv; charset=utf-8",
        Encoding.UTF8,
        StatusCodes.Status200OK);
});

app.MapGet("/api/admin/llm-runs", async (
    int? limit,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    return Results.Ok(await readback.GetAdminLlmRunAuditAsync(limit ?? 100, cancellationToken));
});

app.MapGet("/api/admin/run-metrics", async (
    string? accountId,
    string? runType,
    int? limit,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    return Results.Ok(await readback.GetAdminRunMetricsAsync(accountId, runType, limit ?? 500, cancellationToken));
});

app.MapGet("/api/projects/{projectId}/runs", async (
    string projectId,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var result = await readback.GetProjectRunsForAccountAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapGet("/api/projects/{projectId}/ui-state", async (
    string projectId,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    var snapshot = await store.GetProjectUiStateAsync(CurrentAccountId(context), projectId, cancellationToken);
    return snapshot is null ? Results.NotFound(new { error = "project_ui_state_not_found" }) : Results.Ok(new
    {
        snapshot.AccountId,
        snapshot.ProjectId,
        stateJson = snapshot.StateJson,
        snapshot.UpdatedUtc
    });
});

app.MapPost("/api/projects/{projectId}/ui-state", async (
    string projectId,
    JsonElement payload,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    await store.UpsertProjectUiStateAsync(CurrentAccountId(context), projectId, payload.GetRawText(), cancellationToken);
    return Results.Ok(new { projectId, updated = true });
});

app.MapPost("/api/projects/{projectId}/packages", async (
    string projectId,
    HttpContext context,
    [FromServices] ProjectPackageService packages,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await packages.CreatePackageAsync(CurrentAccountId(context), projectId, cancellationToken);
        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
});

app.MapGet("/api/projects/{projectId}/packages", async (
    string projectId,
    HttpContext context,
    [FromServices] ProjectPackageService packages,
    CancellationToken cancellationToken) =>
{
    var result = await packages.ListPackagesAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/gdd", async (
    string projectId,
    GameDesignDocumentRequest request,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    [FromServices] ProjectChatHistoryService chatHistory,
    [FromServices] ProjectPackageDownloadTicketService tickets,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await gdd.CreateAsync(accountId, projectId, request, cancellationToken);
        if (result.Status == "succeeded")
        {
            var outlineUrl = $"/gdd-outline?projectId={Uri.EscapeDataString(projectId)}";
            var chatSummary = $"{result.Summary}\n\n\u67e5\u9605\u7b56\u5212\u5927\u7eb2\uff1a{outlineUrl}";
            await chatHistory.AppendAsync(accountId, projectId, "user", request.Message, "gdd-request", cancellationToken);
            await chatHistory.AppendAsync(accountId, projectId, "assistant", chatSummary, "gdd-result", cancellationToken);
            return Results.Ok(new
            {
                result.ProjectId,
                result.RunId,
                result.Status,
                result.RelativePath,
                DownloadUrl = outlineUrl,
                result.Artifacts,
                result.FailureCode,
                result.Summary
            });
        }

        if (result.FailureCode == "gdd_already_exists")
        {
            return Results.Conflict(result);
        }

        var failureSummary = string.IsNullOrWhiteSpace(result.Summary)
            ? "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u5931\u8d25\u3002"
            : result.Summary;
        await chatHistory.AppendAsync(accountId, projectId, "user", request.Message, "gdd-request", cancellationToken);
        await chatHistory.AppendAsync(accountId, projectId, "assistant", failureSummary, "gdd-result", cancellationToken);
        return Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/gdd/question-form", async (
    string projectId,
    GameDesignQuestionFormRequest request,
    HttpContext context,
    [FromServices] GameDesignQuestionFormService questionForms,
    CancellationToken cancellationToken) =>
{
    var result = await questionForms.CreateAsync(CurrentAccountId(context), projectId, request, cancellationToken);
    if (result is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    return result.Status == "rate_limited"
        ? Results.Json(result, statusCode: StatusCodes.Status429TooManyRequests)
        : Results.Ok(result);
});

app.MapGet("/api/projects/{projectId}/gdd", async (
    string projectId,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    var result = await gdd.ReadAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "gdd_not_found" })
        : Results.Ok(new
        {
            fileName = result.FileName,
            relativePath = result.RelativePath,
            sizeBytes = result.SizeBytes,
            lastUpdatedUtc = result.LastUpdatedUtc,
            downloadUrl = $"/api/projects/{projectId}/gdd/download"
        });
});

app.MapGet("/api/projects/{projectId}/gdd/outline", async (
    string projectId,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    var result = await gdd.ReadOutlineAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "gdd_outline_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/gdd/outline/export", async (
    string projectId,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    var result = await gdd.ExportOutlineMarkdownAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "gdd_outline_not_found" })
        : Results.Ok(new
        {
            result.FileName,
            result.RelativePath,
            result.SizeBytes,
            result.LastUpdatedUtc,
            downloadPageUrl = $"/downloads?projectId={Uri.EscapeDataString(projectId)}"
        });
});

app.MapDelete("/api/projects/{projectId}/gdd/outline", async (
    string projectId,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    var result = await gdd.DeleteOutlineAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "project_not_found" })
        : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/gdd/outline/sections/complete-missing", async (
    string projectId,
    GameDesignOutlineCompleteAllRequest request,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await gdd.CompleteMissingSectionsAsync(
            CurrentAccountId(context),
            projectId,
            request,
            cancellationToken);
        return result.Status is "queued" ? Results.Accepted($"/runs?projectId={Uri.EscapeDataString(projectId)}", result)
            : result.Status is "succeeded" or "already_complete" ? Results.Ok(result)
            : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/gdd/outline/sections/add", async (
    string projectId,
    GameDesignOutlineAddSectionRequest request,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await gdd.AddSectionAsync(
            CurrentAccountId(context),
            projectId,
            request,
            cancellationToken);
        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/gdd/outline/sections/{sectionId}", async (
    string projectId,
    string sectionId,
    GameDesignOutlineSectionRequest request,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await gdd.GenerateSectionAsync(
            CurrentAccountId(context),
            projectId,
            request with { SectionId = sectionId },
            cancellationToken);
        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPatch("/api/projects/{projectId}/gdd/outline/sections/{sectionId}", async (
    string projectId,
    string sectionId,
    GameDesignOutlineSectionSaveRequest request,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await gdd.SaveSectionAsync(
            CurrentAccountId(context),
            projectId,
            request with { SectionId = sectionId },
            cancellationToken);
        return result is null ? Results.NotFound(new { error = "gdd_outline_section_not_found" }) : Results.Ok(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/projects/{projectId}/gdd/download", async (
    string projectId,
    HttpContext context,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    var result = await gdd.ReadAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "gdd_not_found" })
        : Results.File(result.Content, result.ContentType, result.FileName);
});

app.MapPost("/api/projects/{projectId}/gdd/download-ticket", async (
    string projectId,
    HttpContext context,
    [FromServices] ProjectPackageDownloadTicketService tickets,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!await store.ProjectBelongsToAccountAsync(CurrentAccountId(context), projectId, cancellationToken))
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    var accountId = CurrentAccountId(context);
    return Results.Ok(new
    {
        downloadUrl = $"/projects/{projectId}/gdd/GDD.md?ticket={Uri.EscapeDataString(tickets.CreateTicket(accountId, projectId, "GDD.md"))}"
    });
});

app.MapGet("/projects/{projectId}/gdd/GDD.md", async (
    string projectId,
    HttpRequest request,
    [FromServices] ProjectPackageDownloadTicketService tickets,
    [FromServices] PhaseAMetadataStore store,
    [FromServices] GameDesignDocumentService gdd,
    CancellationToken cancellationToken) =>
{
    var project = await store.GetProjectSnapshotAsync(projectId, cancellationToken);
    if (project is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    var ticket = request.Query["ticket"].FirstOrDefault();
    if (!tickets.IsValid(ticket, project.AccountId, projectId, "GDD.md"))
    {
        return Results.Unauthorized();
    }

    var result = await gdd.ReadAsync(project.AccountId, projectId, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "gdd_not_found" })
        : Results.File(result.Content, result.ContentType, result.FileName);
});

app.MapGet("/api/projects/{projectId}/asset-inventory", async (
    string projectId,
    string? model,
    bool? judge,
    bool? force,
    HttpContext context,
    [FromServices] ProjectAssetInventoryService assets,
    CancellationToken cancellationToken) =>
{
    var result = await assets.GetInventoryAsync(CurrentAccountId(context), projectId, judge == true, model, force == true, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapGet("/api/projects/{projectId}/asset-preview", async (
    string projectId,
    string resource,
    HttpContext context,
    [FromServices] ProjectAssetInventoryService assets,
    CancellationToken cancellationToken) =>
{
    var result = await assets.ReadPreviewAsync(CurrentAccountId(context), projectId, resource, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "asset_preview_not_found" })
        : Results.File(result.Content, result.ContentType, result.FileName);
});

app.MapPost("/api/projects/{projectId}/asset-preview-ticket", async (
    string projectId,
    AssetPreviewTicketRequest request,
    HttpContext context,
    [FromServices] ProjectAssetPreviewTicketService tickets,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (string.IsNullOrWhiteSpace(request.ResourcePath))
    {
        return Results.BadRequest(new { error = "resource_path_required" });
    }

    if (!await store.ProjectBelongsToAccountAsync(CurrentAccountId(context), projectId, cancellationToken))
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    return Results.Ok(new
    {
        previewUrl = $"/projects/{projectId}/asset-preview?resource={Uri.EscapeDataString(request.ResourcePath)}&ticket={Uri.EscapeDataString(tickets.CreateTicket(CurrentAccountId(context), projectId, request.ResourcePath))}"
    });
});

app.MapGet("/api/projects/{projectId}/prototype-evidence", async (
    string projectId,
    string path,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (string.IsNullOrWhiteSpace(path))
    {
        return Results.BadRequest(new { error = "evidence_path_required" });
    }

    if (!path.Replace('\\', '/').StartsWith("logs/prototype-evidence/", StringComparison.Ordinal))
    {
        return Results.BadRequest(new { error = "evidence_path_not_allowed" });
    }

    var project = await store.GetProjectSnapshotAsync(projectId, cancellationToken);
    if (project is null || !string.Equals(project.AccountId, CurrentAccountId(context), StringComparison.Ordinal))
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    var evidenceRoot = Path.GetFullPath(Path.Combine(project.RepoPath, "logs", "prototype-evidence"));
    var absolutePath = Path.GetFullPath(Path.Combine(project.RepoPath, path.Replace('/', Path.DirectorySeparatorChar)));
    if (!WorkspacePathPolicy.IsUnderRoot(project.RepoPath, absolutePath) ||
        !WorkspacePathPolicy.IsUnderRoot(evidenceRoot, absolutePath) ||
        !absolutePath.EndsWith($"{Path.DirectorySeparatorChar}evidence.json", StringComparison.OrdinalIgnoreCase) ||
        !File.Exists(absolutePath))
    {
        return Results.NotFound(new { error = "prototype_evidence_not_found" });
    }

    await using var stream = File.OpenRead(absolutePath);
    using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
    return Results.Json(document.RootElement.Clone());
});

app.MapGet("/api/projects/{projectId}/asset-library", async (
    string projectId,
    HttpContext context,
    [FromServices] ProjectAssetLibraryService library,
    CancellationToken cancellationToken) =>
{
    var result = await library.ReadAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/asset-library/generate", async (
    string projectId,
    ProjectAssetGenerationRunRequest request,
    HttpContext context,
    [FromServices] ProjectAssetLibraryService library,
    CancellationToken cancellationToken) =>
{
    if (request.Unit is null)
    {
        return Results.BadRequest(new { error = "asset_unit_required" });
    }

    try
    {
        var result = await library.GenerateAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (AssetGenerationConcurrencyLimitException ex)
    {
        return Results.Json(new { error = ex.FailureCode }, statusCode: StatusCodes.Status429TooManyRequests);
    }
    catch (InvalidOperationException ex) when (string.Equals(ex.Message, "Project runner is busy.", StringComparison.Ordinal))
    {
        return Results.Json(new { error = "project_busy" }, statusCode: StatusCodes.Status423Locked);
    }
});

app.MapPost("/api/projects/{projectId}/asset-library/import", async (
    string projectId,
    ProjectAssetImportRequest request,
    HttpContext context,
    [FromServices] ProjectAssetLibraryService library,
    CancellationToken cancellationToken) =>
{
    if (request.Unit is null)
    {
        return Results.BadRequest(new { error = "asset_unit_required" });
    }

    if (string.IsNullOrWhiteSpace(request.QueryOrUrl))
    {
        return Results.BadRequest(new { error = "asset_keyword_or_url_required" });
    }

    try
    {
        var result = await library.ImportAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (ArgumentException ex)
    {
        return Results.BadRequest(new { error = ex.Message });
    }
    catch (InvalidOperationException ex) when (string.Equals(ex.Message, "Project runner is busy.", StringComparison.Ordinal))
    {
        return Results.Json(new { error = "project_busy" }, statusCode: StatusCodes.Status423Locked);
    }
});

app.MapPost("/api/projects/{projectId}/asset-library/select", async (
    string projectId,
    ProjectAssetSelectionRequest request,
    HttpContext context,
    [FromServices] ProjectAssetLibraryService library,
    CancellationToken cancellationToken) =>
{
    if (string.IsNullOrWhiteSpace(request.UnitKey) || string.IsNullOrWhiteSpace(request.EntryId))
    {
        return Results.BadRequest(new { error = "asset_selection_required" });
    }

    try
    {
        var result = await library.SelectAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex) when (string.Equals(ex.Message, "Project runner is busy.", StringComparison.Ordinal))
    {
        return Results.Json(new { error = "project_busy" }, statusCode: StatusCodes.Status423Locked);
    }
});

app.MapGet("/projects/{projectId}/asset-preview", async (
    string projectId,
    string resource,
    HttpRequest request,
    [FromServices] ProjectAssetInventoryService assets,
    [FromServices] PhaseAMetadataStore store,
    [FromServices] ProjectAssetPreviewTicketService tickets,
    CancellationToken cancellationToken) =>
{
    var project = await store.GetProjectSnapshotAsync(projectId, cancellationToken);
    if (project is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    var ticket = request.Query["ticket"].FirstOrDefault();
    if (!tickets.IsValid(ticket, project.AccountId, projectId, resource))
    {
        return Results.Unauthorized();
    }

    var result = await assets.ReadPreviewAsync(project.AccountId, projectId, resource, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "asset_preview_not_found" })
        : Results.File(result.Content, result.ContentType, result.FileName);
});

app.MapGet("/projects/{projectId}/packages/{fileName}", async (
    string projectId,
    string fileName,
    HttpRequest request,
    [FromServices] ProjectPackageService packages,
    [FromServices] PhaseAMetadataStore store,
    [FromServices] ProjectPackageDownloadTicketService tickets,
    CancellationToken cancellationToken) =>
{
    var project = await store.GetProjectSnapshotAsync(projectId, cancellationToken);
    if (project is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    var ticket = request.Query["ticket"].FirstOrDefault();
    if (!tickets.IsValid(ticket, project.AccountId, projectId, fileName))
    {
        return Results.Unauthorized();
    }

    var result = await packages.ReadPackageAsync(project.AccountId, projectId, fileName, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "project_package_not_found" })
        : Results.File(result.Content, result.ContentType, result.FileName);
});

app.MapPost("/api/projects/{projectId}/packages/{fileName}/download-ticket", async (
    string projectId,
    string fileName,
    HttpContext context,
    [FromServices] ProjectPackageDownloadTicketService tickets,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!await store.ProjectBelongsToAccountAsync(CurrentAccountId(context), projectId, cancellationToken))
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    var accountId = CurrentAccountId(context);
    return Results.Ok(new
    {
        downloadUrl = $"/projects/{projectId}/packages/{Uri.EscapeDataString(fileName)}?ticket={Uri.EscapeDataString(tickets.CreateTicket(accountId, projectId, fileName))}"
    });
});

app.MapPost("/api/projects/{projectId}/packages/{fileName}/web-preview", async (
    string projectId,
    string fileName,
    HttpContext context,
    [FromServices] ProjectWebPreviewService previews,
    CancellationToken cancellationToken) =>
{
    var accountId = CurrentAccountId(context);
    var queued = await previews.QueuePreviewAsync(accountId, projectId, fileName, cancellationToken);
    if (!string.Equals(queued.Status, "queued", StringComparison.Ordinal))
    {
        var statusCode = queued.FailureCode switch
        {
            "project_not_found" or "package_not_found" => StatusCodes.Status404NotFound,
            "project_busy" => StatusCodes.Status423Locked,
            "user_web_preview_concurrency_limit_exceeded" => StatusCodes.Status429TooManyRequests,
            _ => StatusCodes.Status400BadRequest
        };
        return Results.Json(new
        {
            status = "failed",
            failureCode = queued.FailureCode
        }, statusCode: statusCode);
    }

    _ = Task.Run(async () =>
    {
        try
        {
            await previews.GenerateQueuedPreviewAsync(accountId, projectId, fileName, queued.RunId, CancellationToken.None);
        }
        catch (OperationCanceledException)
        {
            app.Logger.LogInformation(
                "Web preview generation was cancelled. RunId={RunId} ProjectId={ProjectId} FileName={FileName}",
                queued.RunId,
                projectId,
                fileName);
        }
        catch (Exception ex)
        {
            app.Logger.LogError(
                ex,
                "Web preview generation failed unexpectedly. RunId={RunId} ProjectId={ProjectId} FileName={FileName}",
                queued.RunId,
                projectId,
                fileName);
            await previews.RecordUnexpectedPreviewFailureAsync(queued.RunId, fileName, ex, CancellationToken.None);
        }
    }, CancellationToken.None);

    await Task.CompletedTask;
    return Results.Accepted($"/api/projects/{projectId}/packages", new
    {
        status = "queued",
        runId = queued.RunId,
        projectId,
        fileName
    });
});

app.MapGet("/api/system/godot3-web-preview-health", async (
    [FromServices] ProjectWebPreviewService previews,
    CancellationToken cancellationToken) =>
{
    var health = await previews.GetGodot3HealthAsync(cancellationToken);
    return health.Status == "healthy" ? Results.Ok(health) : Results.Problem(
        title: "Godot3 web preview environment is not healthy.",
        statusCode: StatusCodes.Status503ServiceUnavailable,
        extensions: new Dictionary<string, object?>
        {
            ["health"] = health
        });
});

app.MapMethods("/projects/{projectId}/web-previews/{previewId}", ["GET", "HEAD"], async (
    string projectId,
    string previewId,
    HttpContext context,
    [FromServices] ProjectWebPreviewService previews,
    CancellationToken cancellationToken) =>
{
    var result = await previews.ReadPreviewAsync(projectId, previewId, "index.html", cancellationToken);
    ApplyWebPreviewCachePolicy(context, result);
    return result is null
        ? WebPreviewNotFound(context)
        : Results.File(result.FilePath, result.ContentType, enableRangeProcessing: true);
});

app.MapMethods("/projects/{projectId}/web-previews/{previewId}/{**previewPath}", ["GET", "HEAD"], async (
    string projectId,
    string previewId,
    string? previewPath,
    HttpContext context,
    [FromServices] ProjectWebPreviewService previews,
    CancellationToken cancellationToken) =>
{
    var result = await previews.ReadPreviewAsync(projectId, previewId, previewPath, cancellationToken);
    ApplyWebPreviewCachePolicy(context, result);
    return result is null
        ? WebPreviewNotFound(context)
        : Results.File(result.FilePath, result.ContentType, enableRangeProcessing: true);
});

app.MapGet("/downloads", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderDownloads(), "text/html; charset=utf-8");
});

app.MapGet("/assets", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderAssets(), "text/html; charset=utf-8");
});

app.MapGet("/admin/llm-usage", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderAdminLlmUsage(), "text/html; charset=utf-8");
});

app.MapGet("/admin/run-duration-metrics", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderAdminRunDurationMetrics(), "text/html; charset=utf-8");
});

app.MapGet("/admin/chat-average-metrics", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderAdminChatAverageMetrics(), "text/html; charset=utf-8");
});

app.MapGet("/projects/{projectId}", async (
    string projectId,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    [FromServices] BrowserUiRenderer ui,
    CancellationToken cancellationToken) =>
{
    var result = await readback.GetProjectRunsForAccountAsync(CurrentAccountId(context), projectId, cancellationToken);
    if (result is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    return Results.Content(ui.RenderProject(result.Project, result.Runs), "text/html; charset=utf-8");
});

app.MapGet("/api/runs/{runId}", async (
    string runId,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var run = await readback.GetRunForAccountAsync(CurrentAccountId(context), runId, cancellationToken);
    if (run is null)
    {
        return Results.NotFound(new { error = "run_not_found" });
    }

    var artifacts = await readback.ListArtifactsForRunAsync(runId, cancellationToken);
    return Results.Ok(new { run, artifacts });
});

app.MapGet("/runs/{runId}", async (
    string runId,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    [FromServices] BrowserUiRenderer ui,
    CancellationToken cancellationToken) =>
{
    var run = await readback.GetRunForAccountAsync(CurrentAccountId(context), runId, cancellationToken);
    if (run is null)
    {
        return Results.NotFound(new { error = "run_not_found" });
    }

    var artifacts = await readback.ListArtifactsForRunAsync(runId, cancellationToken);
    return Results.Content(ui.RenderRun(run, artifacts), "text/html; charset=utf-8");
});

app.MapGet("/api/artifacts/{artifactId}", async (
    string artifactId,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var artifact = await readback.ReadArtifactForAccountAsync(CurrentAccountId(context), artifactId, cancellationToken);
    return artifact is null ? Results.NotFound(new { error = "artifact_not_found" }) : Results.Ok(artifact);
});

app.MapGet("/artifacts/{artifactId}", async (
    string artifactId,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var artifact = await readback.ReadArtifactForAccountAsync(CurrentAccountId(context), artifactId, cancellationToken);
    if (artifact is null)
    {
        return Results.NotFound(new { error = "artifact_not_found" });
    }

    return Results.Content(artifact.Content, artifact.ContentType);
});

app.MapGet("/project-health/latest.html", (
    [FromServices] ArtifactReadbackService readback) =>
{
    var artifact = readback.ReadProjectHealth("logs/ci/project-health/latest.html");
    return artifact is null ? Results.NotFound(new { error = "project_health_not_found" }) : Results.Content(artifact.Content, artifact.ContentType);
});

app.MapGet("/project-health/latest.json", (
    [FromServices] ArtifactReadbackService readback) =>
{
    var artifact = readback.ReadProjectHealth("logs/ci/project-health/latest.json");
    return artifact is null ? Results.NotFound(new { error = "project_health_not_found" }) : Results.Content(artifact.Content, "application/json; charset=utf-8");
});

app.MapGet("/api/admin/llm-binding", async (
    HttpContext context,
    [FromServices] LlmBindingService llmBinding,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var binding = await llmBinding.GetAsync(adminAccountId, cancellationToken);
    return binding is null ? Results.NotFound(new { error = "llm_binding_not_found" }) : Results.Ok(binding);
});

app.MapGet("/api/account/llm-binding", async (
    HttpContext context,
    [FromServices] LlmBindingService llmBinding,
    CancellationToken cancellationToken) =>
{
    var binding = await llmBinding.GetAsync(CurrentAccountId(context), cancellationToken);
    return binding is null ? Results.NotFound(new { error = "llm_binding_not_found" }) : Results.Ok(binding);
});

app.MapPost("/api/admin/llm-binding", async (
    LlmBindingRequest request,
    HttpContext context,
    [FromServices] LlmBindingService llmBinding,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var result = await llmBinding.BindAsync(adminAccountId, request, cancellationToken);
    return result.Succeeded ? Results.Ok(result.Binding) : Results.BadRequest(result);
});

app.MapPost("/api/account/llm-binding", async (
    LlmBindingRequest request,
    HttpContext context,
    [FromServices] LlmBindingService llmBinding,
    CancellationToken cancellationToken) =>
{
    var result = await llmBinding.BindAsync(CurrentAccountId(context), request, cancellationToken);
    return result.Succeeded ? Results.Ok(result.Binding) : Results.BadRequest(result);
});

app.MapGet("/api/admin/aicodemirror-keys", async (
    HttpContext context,
    [FromServices] AiCodeMirrorKeyPoolService keyPool,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    return Results.Ok(new { keys = await keyPool.ListAsync(cancellationToken) });
});

app.MapGet("/api/admin/aicodemirror-keys/template.csv", (
    HttpContext context) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var csv = "key_name,api_key,description,valid_days\r\nuser-key-001,sk-your-aicodemirror-key,optional description,30\r\nuser-key-002,sk-your-aicodemirror-key-2,,\r\n";
    return Results.File(Encoding.UTF8.GetBytes(csv), "text/csv; charset=utf-8", "aicodemirror-key-template.csv");
});

app.MapPost("/api/admin/aicodemirror-keys", async (
    AiCodeMirrorKeyImportRequest request,
    HttpContext context,
    [FromServices] AiCodeMirrorKeyPoolService keyPool,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var result = await keyPool.ImportAsync(request, cancellationToken);
    return result is null ? Results.BadRequest(new { error = "key_name_required" }) : Results.Ok(result);
});

app.MapPost("/api/admin/aicodemirror-keys/import-csv", async (
    HttpRequest request,
    HttpContext context,
    [FromServices] AiCodeMirrorKeyPoolService keyPool,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    using var reader = new StreamReader(request.Body, Encoding.UTF8, detectEncodingFromByteOrderMarks: true, leaveOpen: false);
    var csv = await reader.ReadToEndAsync(cancellationToken);
    var result = await keyPool.ImportCsvAsync(csv, cancellationToken);
    return result.Errors.Count == 0 ? Results.Ok(result) : Results.Json(result, statusCode: StatusCodes.Status207MultiStatus);
});

app.MapPost("/api/admin/aicodemirror-keys/assign", async (
    AiCodeMirrorKeyAssignRequest request,
    HttpContext context,
    [FromServices] AiCodeMirrorKeyPoolService keyPool,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var result = await keyPool.AssignAsync(request, cancellationToken);
    return result.Succeeded ? Results.Ok(result) : Results.BadRequest(result);
});

app.MapPost("/api/admin/users", async (
    AdminCreateUserRequest request,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    [FromServices] PhaseAPlatformOptions platformOptions,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    if (string.IsNullOrWhiteSpace(request.Username))
    {
        return Results.BadRequest(new { error = "username_required" });
    }

    var projectLimit = request.ProjectLimit ?? platformOptions.HostedProjectLimit;
    if (projectLimit < 1)
    {
        return Results.BadRequest(new { error = "invalid_project_limit" });
    }

    try
    {
        var result = await store.CreateUserAccountAsync(request.Username, projectLimit, request.ValidDays, request.SpendLimitCny, requireAiCodeMirrorKey: true, cancellationToken);
        await store.RecordAdminAccountAuditEventAsync(
            CurrentAccountId(context),
            "user_created",
            result.AccountId,
            new
            {
                username = result.Username,
                project_limit = result.ProjectLimit,
                valid_until_utc = result.ValidUntilUtc,
                spend_limit_cny = result.SpendLimitCny,
                aicodemirror_key_name = result.AiCodeMirrorKeyName
            },
            cancellationToken);
        return Results.Ok(result);
    }
    catch (InvalidOperationException ex) when (ex.Message == "aicodemirror_key_pool_exhausted")
    {
        return Results.Conflict(new { error = "aicodemirror_key_pool_exhausted" });
    }
    catch (SqliteException ex) when (ex.SqliteErrorCode == 19)
    {
        return Results.Conflict(new { error = "username_already_exists" });
    }
});

app.MapPost("/api/admin/users/{accountId}/limits", async (
    string accountId,
    AdminUpdateUserLimitsRequest request,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    if (string.Equals(accountId, CurrentAccountId(context), StringComparison.Ordinal))
    {
        return Results.BadRequest(new { error = "cannot_modify_current_admin" });
    }

    if (request.ValidDays is < 0)
    {
        return Results.BadRequest(new { error = "invalid_valid_days" });
    }

    if (request.SpendLimitCny is < 0)
    {
        return Results.BadRequest(new { error = "invalid_spend_limit_cny" });
    }

    var updated = await store.UpdateUserLimitsAsync(accountId, request.ValidDays, request.SpendLimitCny, cancellationToken);
    if (updated)
    {
        await store.RecordAdminAccountAuditEventAsync(
            CurrentAccountId(context),
            "user_limits_updated",
            accountId,
            new { valid_days = request.ValidDays, spend_limit_cny = request.SpendLimitCny },
            cancellationToken);
    }

    return updated ? Results.Ok(new { accountId, validDays = request.ValidDays, spendLimitCny = request.SpendLimitCny }) : Results.NotFound(new { error = "user_not_found" });
});

app.MapGet("/api/admin/users", async (
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    return Results.Ok(new { users = await store.ListAccountsAsync(cancellationToken) });
});

app.MapPost("/api/admin/users/{accountId}/status", async (
    string accountId,
    AdminUpdateUserStatusRequest request,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    if (string.Equals(accountId, CurrentAccountId(context), StringComparison.Ordinal))
    {
        return Results.BadRequest(new { error = "cannot_modify_current_admin" });
    }

    var updated = await store.SetUserDisabledAsync(accountId, request.Disabled, cancellationToken);
    if (updated)
    {
        await store.RecordAdminAccountAuditEventAsync(
            CurrentAccountId(context),
            request.Disabled ? "user_disabled" : "user_enabled",
            accountId,
            new { disabled = request.Disabled },
            cancellationToken);
    }
    return updated ? Results.Ok(new { accountId, disabled = request.Disabled }) : Results.NotFound(new { error = "user_not_found" });
});

app.MapPost("/api/admin/users/{accountId}/rotate-token", async (
    string accountId,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    if (string.Equals(accountId, CurrentAccountId(context), StringComparison.Ordinal))
    {
        return Results.BadRequest(new { error = "cannot_rotate_current_admin" });
    }

    var result = await store.RotateUserTokenAsync(accountId, cancellationToken);
    if (result is not null)
    {
        await store.RecordAdminAccountAuditEventAsync(
            CurrentAccountId(context),
            "user_token_rotated",
            accountId,
            new { username = result.Username },
            cancellationToken);
    }
    return result is null ? Results.NotFound(new { error = "user_not_found" }) : Results.Ok(result);
});

app.MapGet("/api/admin/account-audit", async (
    int? limit,
    int? offset,
    string? action,
    string? targetAccountId,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var query = new AdminAccountAuditQuery(
        Math.Clamp(limit ?? 100, 1, 200),
        Math.Max(0, offset ?? 0),
        action,
        targetAccountId);
    return Results.Ok(new { events = await store.ListAdminAccountAuditEventsAsync(query, cancellationToken) });
});

app.MapGet("/api/admin/account-audit.csv", async (
    int? limit,
    int? offset,
    string? action,
    string? targetAccountId,
    HttpContext context,
    [FromServices] PhaseAMetadataStore store,
    CancellationToken cancellationToken) =>
{
    if (!CurrentIdentity(context).IsAdmin)
    {
        return AdminForbidden();
    }

    var query = new AdminAccountAuditQuery(
        Math.Clamp(limit ?? 500, 1, 500),
        Math.Max(0, offset ?? 0),
        action,
        targetAccountId);
    var events = await store.ListAdminAccountAuditEventsAsync(query, cancellationToken);
    var csv = ArtifactReadbackService.ExportAdminAccountAuditCsv(events);
    return Results.Text(
        csv,
        "text/csv; charset=utf-8",
        Encoding.UTF8,
        StatusCodes.Status200OK);
});

app.MapPost("/api/projects/{projectId}/chat", async (
    string projectId,
    ChatRequest request,
    HttpContext context,
    [FromServices] ChatService chat,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await chat.SendAsync(accountId, projectId, request, cancellationToken);
        if (result.Status == "succeeded")
        {
            await chatHistory.AppendAsync(accountId, projectId, "user", request.Message, null, cancellationToken);
            await chatHistory.AppendAsync(accountId, projectId, "assistant", result.AssistantMessage, null, cancellationToken);
        }

        return result.Status switch
        {
            "succeeded" => Results.Ok(result),
            "llm_binding_required" => Results.Json(result, statusCode: StatusCodes.Status402PaymentRequired),
            "llm_token_unresolved" => Results.Json(result, statusCode: StatusCodes.Status424FailedDependency),
            "cancel" => Results.Json(result, statusCode: 499),
            "chat_concurrency_limit_exceeded" or "user_chat_concurrency_limit_exceeded" => Results.Json(result, statusCode: StatusCodes.Status429TooManyRequests),
            "missing_message" or "message_too_long" => Results.BadRequest(result),
            _ when result.FailureCode is "llm_run_stop_loss_exceeded" or "llm_daily_stop_loss_exceeded" => Results.Json(result, statusCode: StatusCodes.Status402PaymentRequired),
            _ => Results.BadRequest(result)
        };
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/projects/{projectId}/chat-history", async (
    string projectId,
    HttpContext context,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    var result = await chatHistory.ListAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapGet("/api/projects/{projectId}/workflow-route", async (
    string projectId,
    string? playtestFeedback,
    HttpContext context,
    [FromServices] ProjectWorkflowRouteService workflowRoute,
    [FromServices] ILoggerFactory loggerFactory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await workflowRoute.QueryAsync(CurrentAccountId(context), projectId, playtestFeedback, cancellationToken);
        return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (Exception ex)
    {
        loggerFactory.CreateLogger("PhaseA.ProjectWorkflowRoute")
            .LogError(ex, "Unhandled project workflow route failure for {ProjectId}", projectId);
        return Results.Json(
            new
            {
                error = "workflow_route_failed",
                failureCode = "workflow_route_failed"
            },
            statusCode: StatusCodes.Status500InternalServerError);
    }
});

app.MapPost("/api/projects/{projectId}/workflow-route/intent", async (
    string projectId,
    ProjectWorkflowIntentRequest request,
    HttpContext context,
    [FromServices] ProjectWorkflowRouteService workflowRoute,
    CancellationToken cancellationToken) =>
{
    var result = await workflowRoute.ClassifyIntentAsync(CurrentAccountId(context), projectId, request, cancellationToken);
    return result.Status == "project_not_found" ? Results.NotFound(result) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/iteration-plan", async (
    string projectId,
    PrototypeIterationPlanRequest request,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await iterationPlans.CreateAsync(accountId, projectId, request, cancellationToken);
        return result.Status is "ready" or "llm_failed" or "custom_route_required" or "prototype_recreation_required" or "iteration_plan_update_blocked" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/projects/{projectId}/iteration-plan/latest", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    CancellationToken cancellationToken) =>
{
    var result = await iterationPlans.GetLatestAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "iteration_plan_not_found" }) : Results.Ok(result);
});

app.MapGet("/api/projects/{projectId}/iteration-plans", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    CancellationToken cancellationToken) =>
{
    var result = await iterationPlans.ListAsync(CurrentAccountId(context), projectId, cancellationToken);
    return Results.Ok(new { rounds = result });
});

app.MapDelete("/api/projects/{projectId}/iteration-plan", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await iterationPlans.DeleteAsync(CurrentAccountId(context), projectId, cancellationToken);
        return result.Status == "blocked" ? Results.BadRequest(result) : Results.Ok(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapDelete("/api/projects/{projectId}/iteration-plans/{sessionId}", async (
    string projectId,
    string sessionId,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await iterationPlans.DeleteSessionAsync(CurrentAccountId(context), projectId, sessionId, cancellationToken);
        return result.Status == "blocked" ? Results.BadRequest(result) : Results.Ok(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/projects/{projectId}/gdd-milestone-steps/latest", async (
    string projectId,
    HttpContext context,
    [FromServices] GddMilestoneStepService milestoneSteps,
    CancellationToken cancellationToken) =>
{
    var result = await milestoneSteps.GetOrCreateLatestAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "project_not_found" })
        : result.Status == "gdd_not_found"
            ? Results.Json(result, statusCode: StatusCodes.Status404NotFound)
            : Results.Ok(result);
});

// Legacy compatibility: the browser now uses /current/execute, but older clients may still call this route.
app.MapPost("/api/projects/{projectId}/gdd-milestone-steps/current/iteration-plan", async (
    string projectId,
    JsonElement request,
    HttpContext context,
    [FromServices] GddMilestoneStepService milestoneSteps,
    CancellationToken cancellationToken) =>
{
    _ = request;
    var result = await milestoneSteps.ExecuteCurrentStepAsync(CurrentAccountId(context), projectId, cancellationToken);
    if (result is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    return result.Status is "ready" or "llm_failed" or "custom_route_required" or "prototype_recreation_required" or "iteration_plan_update_blocked"
        or "completed" or "succeeded" or "needs_fix" or "failed" or "project_busy" or "prototype_required"
        ? Results.Ok(result)
        : result.Status == "gdd_not_found"
            ? Results.Json(result, statusCode: StatusCodes.Status404NotFound)
            : Results.BadRequest(result);
});

app.MapPost("/api/projects/{projectId}/gdd-milestone-steps/current/execute", async (
    string projectId,
    JsonElement request,
    HttpContext context,
    [FromServices] GddMilestoneStepService milestoneSteps,
    CancellationToken cancellationToken) =>
{
    _ = request;
    var result = await milestoneSteps.ExecuteCurrentStepAsync(CurrentAccountId(context), projectId, cancellationToken);
    if (result is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    return result.Status is "completed" or "succeeded" or "needs_fix" or "failed" or "project_busy" or "prototype_required"
        ? Results.Ok(result)
        : result.Status == "gdd_not_found"
            ? Results.Json(result, statusCode: StatusCodes.Status404NotFound)
            : Results.BadRequest(result);
});

app.MapPost("/api/projects/{projectId}/gdd-milestone-steps/{stepId}/confirm", async (
    string projectId,
    string stepId,
    GddMilestoneStepConfirmRequest request,
    HttpContext context,
    [FromServices] GddMilestoneStepService milestoneSteps,
    CancellationToken cancellationToken) =>
{
    var result = await milestoneSteps.ConfirmAsync(CurrentAccountId(context), projectId, stepId, request, cancellationToken);
    if (result is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    return result.Status == "confirmed"
        ? Results.Ok(result)
        : result.Status == "gdd_not_found"
            ? Results.Json(result, statusCode: StatusCodes.Status404NotFound)
            : Results.BadRequest(result);
});

app.MapPost("/api/projects/{projectId}/gdd-milestone-steps/{stepId}/feedback-run", async (
    string projectId,
    string stepId,
    GddMilestoneStepFeedbackRequest request,
    HttpContext context,
    [FromServices] GddMilestoneStepService milestoneSteps,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await milestoneSteps.SubmitFeedbackAsync(CurrentAccountId(context), projectId, stepId, request, cancellationToken);
        if (result is null)
        {
            return Results.NotFound(new { error = "project_not_found" });
        }

        return result.Status is "completed" or "succeeded" or "needs_fix" or "failed" or "missing_feedback" or "prototype_not_ready" or "prototype_required"
            ? Results.Ok(result)
            : result.Status == "gdd_not_found"
                ? Results.Json(result, statusCode: StatusCodes.Status404NotFound)
                : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
});

app.MapPost("/api/projects/{projectId}/iteration-plan/evaluate", async (
    string projectId,
    PrototypeIterationPlanEvaluationRequest request,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var progress = await prototypeWorkflow.GetProgressAsync(accountId, projectId, cancellationToken);
        var result = await iterationPlans.EvaluateWithRunAsync(accountId, projectId, progress, request.Model, cancellationToken);
        return Results.Ok(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/iteration-plan/execute-next", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeIterationGoalService iterationGoals,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await iterationGoals.ExecuteNextAsync(accountId, projectId, cancellationToken);
        return result.Status == "completed" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/ui-optimization", async (
    string projectId,
    PrototypeUiOptimizationRequest? request,
    HttpContext context,
    [FromServices] PrototypeUiOptimizationService uiOptimization,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await uiOptimization.RunAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result.Status switch
        {
            "succeeded" => Results.Ok(result),
            "project_busy" or "iteration_plan_not_ready" or "iteration_plan_not_complete" or "prototype_skeleton_not_ready" => Results.Json(result, statusCode: StatusCodes.Status409Conflict),
            "project_not_found" => Results.NotFound(result),
            _ => Results.Json(result, statusCode: StatusCodes.Status500InternalServerError)
        };
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
});

app.MapPost("/api/projects/{projectId}/prototype-feedback-iterations", async (
    string projectId,
    PrototypeFeedbackRequest request,
    HttpContext context,
    [FromServices] PrototypeFeedbackIterationService feedbackIterations,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await feedbackIterations.SubmitAsync(accountId, projectId, request, cancellationToken);

        return result.Status == "completed" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-quick-fixes", (
    string projectId) =>
{
    return Results.Json(
        new { error = "quick_fix_direct_entry_disabled", message = "Quick fix is only available through the needs-fix route." },
        statusCode: StatusCodes.Status410Gone);
});

app.MapPost("/api/projects/{projectId}/needs-fix-route", async (
    string projectId,
    PrototypeNeedsFixRouteRequest request,
    HttpContext context,
    [FromServices] PrototypeNeedsFixRouteService needsFixRoute,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await needsFixRoute.RunAsync(accountId, projectId, request, cancellationToken);

        return result.Status is "completed" or "succeeded" or "needs_fix"
            ? Results.Ok(result)
            : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/repair-plan", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeRepairPlanService repairPlans,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await repairPlans.CreateAsync(accountId, projectId, cancellationToken);

        return result.Status == "ready" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/projects/{projectId}/repair-plan/latest", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeRepairPlanService repairPlans,
    CancellationToken cancellationToken) =>
{
    var result = await repairPlans.GetLatestAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "repair_plan_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/repair-plan/execute-next", async (
    string projectId,
    PrototypeRepairStepExecutionRequest request,
    HttpContext context,
    [FromServices] PrototypeRepairPlanService repairPlans,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await repairPlans.ExecuteNextAsync(accountId, projectId, request, cancellationToken);

        return result.Status == "completed" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/skill-actions", (
    HttpContext context,
    [FromServices] SkillActionService skillActions) =>
{
    var role = context.Items.TryGetValue("phasea.role", out var value) ? value?.ToString() ?? "user" : "user";
    return Results.Ok(new { actions = skillActions.ListAllowed(role) });
});

app.MapPost("/api/projects/{projectId}/skill-actions/{actionId}", async (
    string projectId,
    string actionId,
    SkillActionRunRequest request,
    HttpContext context,
    [FromServices] SkillActionService skillActions,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await skillActions.RunAsync(CurrentAccountId(context), projectId, actionId, request, cancellationToken);
        return result.Status switch
        {
            "succeeded" => Results.Ok(result),
            "skill_action_not_allowed" => Results.NotFound(result),
            _ => Results.BadRequest(result)
        };
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects", async (
    JsonElement payload,
    HttpContext context,
    [FromServices] ProjectCreationService projects,
    [FromServices] ProjectInitializationService initialization,
    [FromServices] ILoggerFactory loggerFactory,
    CancellationToken cancellationToken) =>
{
    if (ProjectCreationRequestJsonPolicy.ContainsForbiddenGitUrl(payload))
    {
        return Results.BadRequest(new { error = "git_url_not_allowed" });
    }

    var request = payload.Deserialize<ProjectCreationRequest>(new JsonSerializerOptions
    {
        PropertyNameCaseInsensitive = true
    });

    if (request is null)
    {
        return Results.BadRequest(new { error = "invalid_project_request" });
    }

    try
    {
        var result = await projects.CreateProjectAsync(CurrentAccountId(context), request, cancellationToken);
        if (!result.Succeeded)
        {
            return result.FailureCode switch
            {
                "project_initialization_in_progress" => Results.Json(result, statusCode: StatusCodes.Status409Conflict),
                "project_creation_concurrency_limit_exceeded" or "user_project_creation_concurrency_limit_exceeded" => Results.Json(result, statusCode: StatusCodes.Status429TooManyRequests),
                _ => Results.BadRequest(result)
            };
        }

        initialization.StartChapter2Bootstrap(result.ProjectId!);
        return Results.Ok(result);
    }
    catch (Exception ex)
    {
        loggerFactory.CreateLogger("PhaseA.ProjectCreation")
            .LogError(ex, "Unhandled project creation request failure.");
        return Results.Json(
            new
            {
                error = "project_creation_failed",
                failureCode = "project_creation_failed",
                detail = ex.Message
            },
            statusCode: StatusCodes.Status500InternalServerError);
    }
});

app.MapPost("/api/projects/{projectId}/prototype-drafts/analyze", async (
    string projectId,
    HttpRequest request,
    HttpContext context,
    [FromServices] ProjectDraftImportService draftImport,
    CancellationToken cancellationToken) =>
{
    if (!request.HasFormContentType)
    {
        return Results.BadRequest(new { error = "form_content_type_required" });
    }

    var form = await request.ReadFormAsync(cancellationToken);
    var file = form.Files.GetFile("draftFile");
    if (file is null)
    {
        return Results.BadRequest(new { error = "draft_file_required" });
    }

    await using var stream = file.OpenReadStream();
    using var memory = new MemoryStream();
    await stream.CopyToAsync(memory, cancellationToken);
    try
    {
        var result = await draftImport.AnalyzeAsync(CurrentAccountId(context), projectId, file.FileName, memory.ToArray(), form["model"].FirstOrDefault(), cancellationToken);
        return result.Status switch
        {
            "succeeded" => Results.Ok(result),
            "project_busy" => Results.Json(result, statusCode: StatusCodes.Status423Locked),
            _ => Results.BadRequest(result)
        };
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/projects/{projectId}/prototype-drafts/latest", async (
    string projectId,
    HttpContext context,
    [FromServices] ProjectDraftImportService draftImport,
    CancellationToken cancellationToken) =>
{
    var result = await draftImport.GetLatestAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "prototype_draft_not_found" }) : Results.Ok(result);
});

app.MapDelete("/api/projects/{projectId}", async (
    string projectId,
    [FromBody] ProjectDeletionRequest request,
    HttpContext context,
    [FromServices] ProjectCreationService projects,
    CancellationToken cancellationToken) =>
{
    var result = await projects.DeleteProjectAsync(CurrentAccountId(context), projectId, request, cancellationToken);
    return result.Succeeded
        ? Results.Ok(result)
        : result.FailureCode switch
        {
            "project_not_found" => Results.NotFound(result),
            "project_busy" => Results.Json(result, statusCode: StatusCodes.Status409Conflict),
            _ => Results.BadRequest(result)
        };
});

app.MapPost("/api/projects/{projectId}/chapter2-bootstrap", async (
    string projectId,
    HttpContext context,
    [FromServices] Chapter2BootstrapService chapter2,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await chapter2.RunAsync(CurrentAccountId(context), projectId, cancellationToken);
        return result.Status switch
        {
            "succeeded" or "already_succeeded" => Results.Ok(result),
            "blocked" => Results.Json(result, statusCode: StatusCodes.Status423Locked),
            _ => Results.BadRequest(result)
        };
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-7day-playable", async (
    string projectId,
    PrototypeWorkflowRequest request,
    HttpContext context,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeWorkflow.QueueAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        if (result.Status == "missing_required_fields")
        {
            return Results.BadRequest(result);
        }

        if (result.Status == "prototype_skeleton_locked")
        {
            return Results.Json(result, statusCode: StatusCodes.Status409Conflict);
        }

        return result.Status == "queued" ? Results.Json(result, statusCode: StatusCodes.Status202Accepted) : Results.BadRequest(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-7day-playable/from-gdd", async (
    string projectId,
    PrototypeFromGddRequest request,
    HttpContext context,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeWorkflow.QueueFromGddAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result.Status switch
        {
            "queued" => Results.Json(result, statusCode: StatusCodes.Status202Accepted),
            "gdd_not_found" => Results.Json(result, statusCode: StatusCodes.Status404NotFound),
            "gdd_empty" => Results.Json(result, statusCode: StatusCodes.Status409Conflict),
            "prototype_skeleton_locked" => Results.Json(result, statusCode: StatusCodes.Status409Conflict),
            _ => Results.BadRequest(result)
        };
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapGet("/api/projects/{projectId}/prototype-7day-playable/progress", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        return Results.Ok(await prototypeWorkflow.GetProgressAsync(CurrentAccountId(context), projectId, cancellationToken));
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-7day-playable/repair", async (
    string projectId,
    PrototypeRepairRequest request,
    HttpContext context,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeWorkflow.RepairAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result.Status == "queued" ? Results.Json(result, statusCode: StatusCodes.Status202Accepted) : Results.BadRequest(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-7day-playable/validate", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeWorkflow.ValidateAsync(CurrentAccountId(context), projectId, cancellationToken);
        return result.Status switch
        {
            "succeeded" or "failed" => Results.Ok(result),
            "project_busy" => Results.Json(result, statusCode: StatusCodes.Status423Locked),
            "prototype_validation_not_available" => Results.Json(result, statusCode: StatusCodes.Status404NotFound),
            "iteration_plan_not_complete" => Results.Json(result, statusCode: StatusCodes.Status409Conflict),
            _ => Results.BadRequest(result)
        };
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-7day-playable/validate-skeleton", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeWorkflow.ValidateSkeletonAsync(CurrentAccountId(context), projectId, cancellationToken);
        return result.Status switch
        {
            "succeeded" or "failed" => Results.Ok(result),
            "project_busy" => Results.Json(result, statusCode: StatusCodes.Status423Locked),
            "prototype_validation_not_available" => Results.Json(result, statusCode: StatusCodes.Status404NotFound),
            _ => Results.BadRequest(result)
        };
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-tdd", async (
    string projectId,
    PrototypeTddRequest request,
    HttpContext context,
    [FromServices] PrototypeCommandService prototypeCommands,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeCommands.RunTddAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-scene", async (
    string projectId,
    PrototypeSceneRequest request,
    HttpContext context,
    [FromServices] PrototypeCommandService prototypeCommands,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeCommands.CreateSceneAsync(CurrentAccountId(context), projectId, request, cancellationToken);
        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
    {
        return CancelledRunResult();
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.Run(options.AppBindUrl);

static async Task<AccountIdentity?> ResolveIdentityAsync(HttpContext context, string adminAccountId)
{
    var authOptions = context.RequestServices.GetRequiredService<PhaseAPlatformOptions>();
    var token = PhaseAAuth.ReadBearerOrHeaderToken(context.Request);
    if (string.IsNullOrWhiteSpace(token))
    {
        return null;
    }

    var role = PhaseAAuth.GetRole(context.Request, authOptions);
    if (role == PhaseAAuth.AdminRole)
    {
        return new AccountIdentity(adminAccountId, authOptions.AdminUsername, PhaseAAuth.AdminRole);
    }

    var store = context.RequestServices.GetRequiredService<PhaseAMetadataStore>();
    var account = await store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(token), context.RequestAborted);
    if (account is not null)
    {
        return new AccountIdentity(
            account.AccountId,
            account.Username,
            account.IsAdmin ? PhaseAAuth.AdminRole : PhaseAAuth.UserRole);
    }

    return null;
}

static void PersistAccessTokenCookie(HttpContext context)
{
    var token = PhaseAAuth.ReadBearerOrHeaderToken(context.Request);
    if (string.IsNullOrWhiteSpace(token))
    {
        return;
    }

    context.Response.Cookies.Append(
        PhaseAAuth.AccessTokenCookieName,
        token,
        new CookieOptions
        {
            HttpOnly = false,
            IsEssential = true,
            MaxAge = TimeSpan.FromDays(30),
            Path = "/",
            SameSite = SameSiteMode.Lax,
            Secure = context.Request.IsHttps
        });
}

static AccountIdentity CurrentIdentity(HttpContext context)
{
    return context.Items.TryGetValue("phasea.identity", out var value) && value is AccountIdentity identity
        ? identity
        : throw new InvalidOperationException("Authenticated account identity is missing.");
}

static string CurrentAccountId(HttpContext context)
{
    return CurrentIdentity(context).AccountId;
}

static IResult AdminForbidden()
{
    return Results.Json(new { error = "admin_required" }, statusCode: StatusCodes.Status403Forbidden);
}

static IResult CancelledRunResult()
{
    return Results.Json(
        new { status = "cancel", error = "run_cancelled" },
        statusCode: 499);
}

static void ApplyNoStore(HttpContext context)
{
    context.Response.Headers.CacheControl = "no-store, no-cache, must-revalidate";
    context.Response.Headers.Pragma = "no-cache";
    context.Response.Headers.Expires = "0";
}

static void ApplyWebPreviewCachePolicy(HttpContext context, ProjectWebPreviewReadResult? result)
{
    if (result is not null)
    {
        context.Response.Headers.AccessControlAllowOrigin = "*";
        context.Response.Headers.XContentTypeOptions = "nosniff";
        context.Response.Headers["Referrer-Policy"] = "no-referrer";
        context.Response.Headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()";
        if (string.Equals(result.FileName, "index.html", StringComparison.OrdinalIgnoreCase))
        {
            context.Response.Headers.ContentSecurityPolicy =
                "sandbox allow-scripts allow-pointer-lock; " +
                "default-src 'self' data: blob:; " +
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval'; " +
                "connect-src 'self'; " +
                "img-src 'self' data: blob:; " +
                "style-src 'self' 'unsafe-inline'; " +
                "font-src 'self' data:; " +
                "worker-src 'self' blob:; " +
                "object-src 'none'; base-uri 'none'; form-action 'none'";
        }
    }

    if (result is not null && ProjectWebPreviewService.IsImmutablePreviewAsset(result.FileName))
    {
        context.Response.Headers.CacheControl = "public, max-age=31536000, immutable";
        context.Response.Headers.Remove("Pragma");
        context.Response.Headers.Remove("Expires");
        return;
    }

    ApplyNoStore(context);
}

static IResult WebPreviewNotFound(HttpContext context)
{
    ApplyNoStore(context);
    context.Response.Headers.XContentTypeOptions = "nosniff";
    context.Response.Headers["Referrer-Policy"] = "no-referrer";
    if (HttpMethods.IsHead(context.Request.Method))
    {
        return Results.NotFound();
    }

    return Results.Content(
        """
        <!doctype html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>试玩链接已失效</title>
          <style>
            body { margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; background: #f7f4ee; color: #1f2933; }
            main { width: min(560px, calc(100vw - 32px)); border: 1px solid #d9d2c5; background: #fffaf2; padding: 28px; border-radius: 8px; box-shadow: 0 18px 45px rgba(31, 41, 51, 0.12); }
            h1 { margin: 0 0 12px; font-size: 24px; }
            p { margin: 0 0 16px; line-height: 1.7; color: #52606d; }
            a { color: #8a4b12; font-weight: 700; }
          </style>
        </head>
        <body>
          <main>
            <h1>试玩链接已失效</h1>
            <p>这个 Godot3 浏览器试玩链接不存在、已被清理，或不再匹配当前项目文件包。</p>
            <p>请回到项目打包下载页面，重新生成浏览器试玩地址。</p>
            <a href="/downloads">返回打包下载页面</a>
          </main>
        </body>
        </html>
        """,
        "text/html; charset=utf-8",
        statusCode: StatusCodes.Status404NotFound);
}

static string ResolveStaticWebRoot(string contentRootPath)
{
    var contentRootWwwroot = Path.Combine(contentRootPath, "wwwroot");
    if (Directory.Exists(contentRootWwwroot))
    {
        return contentRootWwwroot;
    }

    var repositoryWwwroot = Path.Combine(contentRootPath, "PhaseA.Platform", "wwwroot");
    if (Directory.Exists(repositoryWwwroot))
    {
        return repositoryWwwroot;
    }

    return contentRootWwwroot;
}

static bool TryReadApiProjectId(PathString path, out string projectId)
{
    projectId = "";
    var value = path.Value;
    if (string.IsNullOrWhiteSpace(value))
    {
        return false;
    }

    var prefix = "/api/projects/";
    if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    var remainder = value[prefix.Length..];
    var slashIndex = remainder.IndexOf('/');
    projectId = slashIndex < 0 ? remainder : remainder[..slashIndex];
    return !string.IsNullOrWhiteSpace(projectId);
}

public partial class Program;
