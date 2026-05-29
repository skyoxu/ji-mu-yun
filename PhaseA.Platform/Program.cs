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
builder.Services.AddSingleton<ProjectCreationService>();
builder.Services.AddSingleton<ProjectDraftImportService>();
builder.Services.AddSingleton<ProjectInitializationService>();
builder.Services.AddHostedService<ProjectInitializationRecoveryService>();
builder.Services.AddSingleton<IHostedProcessRunner, HostedProcessRunner>();
builder.Services.AddSingleton<Chapter2BootstrapCommandBuilder>();
builder.Services.AddSingleton<ProjectHealthArtifactIndexer>();
builder.Services.AddSingleton<Chapter2BootstrapService>();
builder.Services.AddSingleton<HeavyRunnerQueueService>();
builder.Services.AddSingleton<PrototypeRecordWriter>();
builder.Services.AddSingleton<PrototypeWorkflowCommandBuilder>();
builder.Services.AddSingleton<PrototypeArtifactIndexer>();
builder.Services.AddSingleton<PrototypeRouteStateWriter>();
builder.Services.AddSingleton<PrototypeWorkflowService>();
builder.Services.AddSingleton<PrototypeFeedbackIterationService>();
builder.Services.AddSingleton<PrototypeQuickFixService>();
builder.Services.AddSingleton<PrototypeNeedsFixRouteService>();
builder.Services.AddSingleton<PrototypeIterationPlanService>();
builder.Services.AddSingleton<PrototypeIterationGoalService>();
builder.Services.AddSingleton<PrototypeRepairPlanService>();
builder.Services.AddSingleton<PrototypeCommandBuilder>();
builder.Services.AddSingleton<PrototypeTddArtifactIndexer>();
builder.Services.AddSingleton<PrototypeCommandService>();
builder.Services.AddSingleton<SkillActionCatalog>();
builder.Services.AddSingleton<SkillActionService>();
builder.Services.AddSingleton<ArtifactReadbackService>();
builder.Services.AddSingleton<ProjectPackageService>();
builder.Services.AddSingleton<ProjectAssetInventoryService>();
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
builder.Services.AddTransient<ChatService>();
builder.Services.AddSingleton<ProjectChatHistoryService>();
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
if (interruptedRunCount > 0)
{
    app.Logger.LogWarning("Recovered {InterruptedRunCount} interrupted runs during startup.", interruptedRunCount);
}

app.Use(async (context, next) =>
{
    if (context.Request.Path == "/healthz" ||
        context.Request.Path == "/" ||
        context.Request.Path == "/ui" ||
        context.Request.Path == "/downloads" ||
        context.Request.Path == "/assets" ||
        context.Request.Path == "/admin/llm-usage" ||
        (context.Request.Path.StartsWithSegments("/projects") &&
         context.Request.Path.Value?.Contains("/asset-preview", StringComparison.Ordinal) == true &&
         context.Request.Query.ContainsKey("ticket")) ||
        (context.Request.Path.StartsWithSegments("/projects") &&
         context.Request.Path.Value?.Contains("/packages/", StringComparison.Ordinal) == true &&
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
    await next(context);
});

app.MapGet("/healthz", () => Results.Ok(new
{
    status = "ok",
    service = "phase-a-platform"
}));

app.MapGet("/", (
    [FromServices] BrowserUiRenderer ui) =>
{
    return Results.Content(ui.RenderShell(), "text/html; charset=utf-8");
});

app.MapGet("/ui", (
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

app.MapGet("/api/projects/{projectId}/runs", async (
    string projectId,
    HttpContext context,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var result = await readback.GetProjectRunsForAccountAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/packages", async (
    string projectId,
    HttpContext context,
    [FromServices] ProjectPackageService packages,
    CancellationToken cancellationToken) =>
{
    var result = await packages.CreatePackageAsync(CurrentAccountId(context), projectId, cancellationToken);
    return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
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

app.MapGet("/api/projects/{projectId}/asset-inventory", async (
    string projectId,
    string? model,
    bool? judge,
    HttpContext context,
    [FromServices] ProjectAssetInventoryService assets,
    CancellationToken cancellationToken) =>
{
    var result = await assets.GetInventoryAsync(CurrentAccountId(context), projectId, judge == true, model, cancellationToken);
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
        previewUrl = $"/projects/{projectId}/asset-preview?resource={Uri.EscapeDataString(request.ResourcePath)}&ticket={Uri.EscapeDataString(tickets.CreateTicket(projectId, request.ResourcePath))}"
    });
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
    var ticket = request.Query["ticket"].FirstOrDefault();
    if (!tickets.IsValid(ticket, projectId, resource))
    {
        return Results.Unauthorized();
    }

    var project = await store.GetProjectSnapshotAsync(projectId, cancellationToken);
    if (project is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
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
    var ticket = request.Query["ticket"].FirstOrDefault();
    if (!tickets.IsValid(ticket, projectId, fileName))
    {
        return Results.Unauthorized();
    }

    var project = await store.GetProjectSnapshotAsync(projectId, cancellationToken);
    if (project is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
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

    return Results.Ok(new
    {
        downloadUrl = $"/projects/{projectId}/packages/{Uri.EscapeDataString(fileName)}?ticket={Uri.EscapeDataString(tickets.CreateTicket(projectId, fileName))}"
    });
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
            "missing_message" or "message_too_long" => Results.BadRequest(result),
            _ when result.FailureCode is "llm_run_stop_loss_exceeded" or "llm_daily_stop_loss_exceeded" => Results.Json(result, statusCode: StatusCodes.Status402PaymentRequired),
            _ => Results.BadRequest(result)
        };
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

app.MapPost("/api/projects/{projectId}/iteration-plan", async (
    string projectId,
    PrototypeIterationPlanRequest request,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await iterationPlans.CreateAsync(accountId, projectId, request, cancellationToken);
        if (result.Status == "ready")
        {
            await chatHistory.AppendAsync(accountId, projectId, "user", request.Message, "iteration-plan-request", cancellationToken);
            var goalSummary = result.Goals.Count == 0
                ? result.Summary
                : $"{result.Summary}\n\n本次目标拆分：\n{string.Join("\n", result.Goals.Select(goal => $"{goal.GoalIndex}. {goal.Title}"))}";
            await chatHistory.AppendAsync(accountId, projectId, "assistant", goalSummary, "iteration-plan-result", cancellationToken);
        }
        return result.Status == "ready" ? Results.Ok(result) : Results.BadRequest(result);
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

app.MapPost("/api/projects/{projectId}/iteration-plan/evaluate", async (
    string projectId,
    HttpContext context,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var progress = await prototypeWorkflow.GetProgressAsync(accountId, projectId, cancellationToken);
        var result = await iterationPlans.EvaluateAsync(accountId, projectId, progress, cancellationToken);
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
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await iterationGoals.ExecuteNextAsync(accountId, projectId, cancellationToken);
        if (result.Status is "completed" or "failed" or "needs_fix")
        {
            await chatHistory.AppendAsync(
                accountId,
                projectId,
                "assistant",
                result.Summary,
                result.Status == "completed" ? "iteration-goal-result" : "iteration-goal-failed",
                cancellationToken);
        }
        return result.Status == "completed" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-feedback-iterations", async (
    string projectId,
    PrototypeFeedbackRequest request,
    HttpContext context,
    [FromServices] PrototypeFeedbackIterationService feedbackIterations,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        await chatHistory.AppendAsync(accountId, projectId, "user", request.Feedback, "formal-feedback", cancellationToken);
        var result = await feedbackIterations.SubmitAsync(accountId, projectId, request, cancellationToken);
        if (result.Status == "completed" || result.Status == "failed")
        {
            await chatHistory.AppendAsync(
                accountId,
                projectId,
                "assistant",
                result.AssistantMessage,
                result.Status == "completed" ? "formal-feedback-result" : "formal-feedback-failed",
                cancellationToken);
        }

        return result.Status == "completed" ? Results.Ok(result) : Results.BadRequest(result);
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
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        if (!string.IsNullOrWhiteSpace(request.Feedback))
        {
            await chatHistory.AppendAsync(accountId, projectId, "user", request.Feedback, "needs-fix-route", cancellationToken);
        }

        var result = await needsFixRoute.RunAsync(accountId, projectId, request, cancellationToken);
        if (!string.IsNullOrWhiteSpace(result.Summary))
        {
            await chatHistory.AppendAsync(
                accountId,
                projectId,
                "assistant",
                result.Summary,
                result.Status == "completed" ? "needs-fix-route-result" : "needs-fix-route-failed",
                cancellationToken);
        }

        return result.Status == "completed" ? Results.Ok(result) : Results.BadRequest(result);
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
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await repairPlans.CreateAsync(accountId, projectId, cancellationToken);
        if (result.Status is "ready")
        {
            var goalSummary = $"{result.Summary}\n\n修复步骤：\n{string.Join("\n", result.Goals.Select(goal => $"{goal.GoalIndex}. {goal.Title}"))}";
            await chatHistory.AppendAsync(accountId, projectId, "assistant", goalSummary, "repair-plan-result", cancellationToken);
        }

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
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var accountId = CurrentAccountId(context);
        var result = await repairPlans.ExecuteNextAsync(accountId, projectId, request, cancellationToken);
        if (!string.IsNullOrWhiteSpace(result.Summary))
        {
            await chatHistory.AppendAsync(accountId, projectId, "assistant", result.Summary, "repair-step-result", cancellationToken);
        }

        return result.Status == "completed" ? Results.Ok(result) : Results.BadRequest(result);
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

    var result = await projects.CreateProjectAsync(CurrentAccountId(context), request, cancellationToken);
    if (!result.Succeeded)
    {
        return result.FailureCode == "project_initialization_in_progress"
            ? Results.Json(result, statusCode: StatusCodes.Status409Conflict)
            : Results.BadRequest(result);
    }

    initialization.StartChapter2Bootstrap(result.ProjectId!);
    return Results.Ok(result);
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

        return result.Status == "queued" ? Results.Json(result, statusCode: StatusCodes.Status202Accepted) : Results.BadRequest(result);
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
            _ => Results.BadRequest(result)
        };
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

    if (role == PhaseAAuth.UserRole)
    {
        return new AccountIdentity(adminAccountId, "legacy-user", PhaseAAuth.UserRole);
    }

    return null;
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
