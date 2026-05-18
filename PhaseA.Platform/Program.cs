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
builder.Services.AddSingleton<PrototypeRecordWriter>();
builder.Services.AddSingleton<PrototypeWorkflowCommandBuilder>();
builder.Services.AddSingleton<PrototypeArtifactIndexer>();
builder.Services.AddSingleton<PrototypeWorkflowService>();
builder.Services.AddSingleton<PrototypeFeedbackIterationService>();
builder.Services.AddSingleton<PrototypeQuickFixService>();
builder.Services.AddSingleton<PrototypeIterationPlanService>();
builder.Services.AddSingleton<PrototypeIterationGoalService>();
builder.Services.AddSingleton<PrototypeCommandBuilder>();
builder.Services.AddSingleton<PrototypeTddArtifactIndexer>();
builder.Services.AddSingleton<PrototypeCommandService>();
builder.Services.AddSingleton<SkillActionCatalog>();
builder.Services.AddSingleton<SkillActionService>();
builder.Services.AddSingleton<ArtifactReadbackService>();
builder.Services.AddSingleton<ProjectPackageService>();
builder.Services.AddSingleton<ProjectPackageDownloadTicketService>();
builder.Services.AddSingleton<LlmBindingService>();
builder.Services.AddSingleton<LlmStopLossService>();
builder.Services.AddHttpClient<INewApiChatClient, NewApiChatClient>();
builder.Services.AddSingleton<ICodexChatClient, CodexCliChatClient>();
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
        (context.Request.Path.StartsWithSegments("/projects") &&
         context.Request.Path.Value?.Contains("/packages/", StringComparison.Ordinal) == true &&
         context.Request.Query.ContainsKey("ticket")))
    {
        await next(context);
        return;
    }

    var authOptions = context.RequestServices.GetRequiredService<PhaseAPlatformOptions>();
    var role = PhaseAAuth.GetRole(context.Request, authOptions);
    if (role is null)
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        await context.Response.WriteAsJsonAsync(new { error = PhaseAAuth.AuthFailureCode });
        return;
    }

    context.Items["phasea.role"] = role;
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
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    return Results.Ok(await readback.ListProjectsAsync(adminAccountId, cancellationToken));
});

app.MapGet("/api/project-creation-failures/latest", async (
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var failure = await readback.GetLatestProjectCreationFailureAsync(adminAccountId, cancellationToken);
    return failure is null ? Results.NotFound(new { error = "project_creation_failure_not_found" }) : Results.Ok(failure);
});

app.MapGet("/api/session", (HttpContext context) => Results.Ok(new
{
    authenticated = true,
    role = context.Items.TryGetValue("phasea.role", out var role) ? role?.ToString() ?? "user" : "user"
}));

app.MapGet("/api/account/active-run", async (
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    return Results.Ok(await readback.GetActiveRunAsync(adminAccountId, cancellationToken));
});

app.MapGet("/api/projects/{projectId}/runs", async (
    string projectId,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var result = await readback.GetProjectRunsAsync(projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/packages", async (
    string projectId,
    [FromServices] ProjectPackageService packages,
    CancellationToken cancellationToken) =>
{
    var result = await packages.CreatePackageAsync(adminAccountId, projectId, cancellationToken);
    return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
});

app.MapGet("/api/projects/{projectId}/packages", async (
    string projectId,
    [FromServices] ProjectPackageService packages,
    CancellationToken cancellationToken) =>
{
    var result = await packages.ListPackagesAsync(adminAccountId, projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapGet("/projects/{projectId}/packages/{fileName}", async (
    string projectId,
    string fileName,
    HttpRequest request,
    [FromServices] ProjectPackageService packages,
    [FromServices] ProjectPackageDownloadTicketService tickets,
    CancellationToken cancellationToken) =>
{
    var ticket = request.Query["ticket"].FirstOrDefault();
    if (!tickets.IsValid(ticket, projectId, fileName))
    {
        return Results.Unauthorized();
    }

    var result = await packages.ReadPackageAsync(adminAccountId, projectId, fileName, cancellationToken);
    return result is null
        ? Results.NotFound(new { error = "project_package_not_found" })
        : Results.File(result.Content, result.ContentType, result.FileName);
});

app.MapPost("/api/projects/{projectId}/packages/{fileName}/download-ticket", (
    string projectId,
    string fileName,
    [FromServices] ProjectPackageDownloadTicketService tickets) =>
{
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

app.MapGet("/projects/{projectId}", async (
    string projectId,
    [FromServices] ArtifactReadbackService readback,
    [FromServices] BrowserUiRenderer ui,
    CancellationToken cancellationToken) =>
{
    var result = await readback.GetProjectRunsAsync(projectId, cancellationToken);
    if (result is null)
    {
        return Results.NotFound(new { error = "project_not_found" });
    }

    return Results.Content(ui.RenderProject(result.Project, result.Runs), "text/html; charset=utf-8");
});

app.MapGet("/api/runs/{runId}", async (
    string runId,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var run = await readback.GetRunAsync(runId, cancellationToken);
    if (run is null)
    {
        return Results.NotFound(new { error = "run_not_found" });
    }

    var artifacts = await readback.ListArtifactsForRunAsync(runId, cancellationToken);
    return Results.Ok(new { run, artifacts });
});

app.MapGet("/runs/{runId}", async (
    string runId,
    [FromServices] ArtifactReadbackService readback,
    [FromServices] BrowserUiRenderer ui,
    CancellationToken cancellationToken) =>
{
    var run = await readback.GetRunAsync(runId, cancellationToken);
    if (run is null)
    {
        return Results.NotFound(new { error = "run_not_found" });
    }

    var artifacts = await readback.ListArtifactsForRunAsync(runId, cancellationToken);
    return Results.Content(ui.RenderRun(run, artifacts), "text/html; charset=utf-8");
});

app.MapGet("/api/artifacts/{artifactId}", async (
    string artifactId,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var artifact = await readback.ReadArtifactAsync(artifactId, cancellationToken);
    return artifact is null ? Results.NotFound(new { error = "artifact_not_found" }) : Results.Ok(artifact);
});

app.MapGet("/artifacts/{artifactId}", async (
    string artifactId,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var artifact = await readback.ReadArtifactAsync(artifactId, cancellationToken);
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
    [FromServices] LlmBindingService llmBinding,
    CancellationToken cancellationToken) =>
{
    var binding = await llmBinding.GetAsync(adminAccountId, cancellationToken);
    return binding is null ? Results.NotFound(new { error = "llm_binding_not_found" }) : Results.Ok(binding);
});

app.MapPost("/api/admin/llm-binding", async (
    LlmBindingRequest request,
    [FromServices] LlmBindingService llmBinding,
    CancellationToken cancellationToken) =>
{
    var result = await llmBinding.BindAsync(adminAccountId, request, cancellationToken);
    return result.Succeeded ? Results.Ok(result.Binding) : Results.BadRequest(result);
});

app.MapPost("/api/projects/{projectId}/chat", async (
    string projectId,
    ChatRequest request,
    [FromServices] ChatService chat,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await chat.SendAsync(projectId, request, cancellationToken);
        if (result.Status == "succeeded")
        {
            await chatHistory.AppendAsync(adminAccountId, projectId, "user", request.Message, null, cancellationToken);
            await chatHistory.AppendAsync(adminAccountId, projectId, "assistant", result.AssistantMessage, null, cancellationToken);
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
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    var result = await chatHistory.ListAsync(adminAccountId, projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/iteration-plan", async (
    string projectId,
    PrototypeIterationPlanRequest request,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await iterationPlans.CreateAsync(adminAccountId, projectId, request, cancellationToken);
        if (result.Status == "ready")
        {
            await chatHistory.AppendAsync(adminAccountId, projectId, "user", request.Message, "iteration-plan-request", cancellationToken);
            var goalSummary = result.Goals.Count == 0
                ? result.Summary
                : $"{result.Summary}\n\n本次目标拆分：\n{string.Join("\n", result.Goals.Select(goal => $"{goal.GoalIndex}. {goal.Title}"))}";
            await chatHistory.AppendAsync(adminAccountId, projectId, "assistant", goalSummary, "iteration-plan-result", cancellationToken);
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
    [FromServices] PrototypeIterationPlanService iterationPlans,
    CancellationToken cancellationToken) =>
{
    var result = await iterationPlans.GetLatestAsync(adminAccountId, projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "iteration_plan_not_found" }) : Results.Ok(result);
});

app.MapPost("/api/projects/{projectId}/iteration-plan/evaluate", async (
    string projectId,
    [FromServices] PrototypeIterationPlanService iterationPlans,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var progress = await prototypeWorkflow.GetProgressAsync(projectId, cancellationToken);
        var result = await iterationPlans.EvaluateAsync(adminAccountId, projectId, progress, cancellationToken);
        return Results.Ok(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/iteration-plan/execute-next", async (
    string projectId,
    [FromServices] PrototypeIterationGoalService iterationGoals,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await iterationGoals.ExecuteNextAsync(adminAccountId, projectId, cancellationToken);
        if (result.Status is "completed" or "failed" or "needs_fix")
        {
            await chatHistory.AppendAsync(
                adminAccountId,
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
    [FromServices] PrototypeFeedbackIterationService feedbackIterations,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        await chatHistory.AppendAsync(adminAccountId, projectId, "user", request.Feedback, "formal-feedback", cancellationToken);
        var result = await feedbackIterations.SubmitAsync(projectId, request, cancellationToken);
        if (result.Status == "completed" || result.Status == "failed")
        {
            await chatHistory.AppendAsync(
                adminAccountId,
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

app.MapPost("/api/projects/{projectId}/prototype-quick-fixes", async (
    string projectId,
    PrototypeFeedbackRequest request,
    [FromServices] PrototypeQuickFixService quickFixes,
    [FromServices] ProjectChatHistoryService chatHistory,
    CancellationToken cancellationToken) =>
{
    try
    {
        await chatHistory.AppendAsync(adminAccountId, projectId, "user", request.Feedback, "quick-fix", cancellationToken);
        var result = await quickFixes.SubmitAsync(projectId, request, cancellationToken);
        if (result.Status == "completed" || result.Status == "failed")
        {
            await chatHistory.AppendAsync(
                adminAccountId,
                projectId,
                "assistant",
                result.AssistantMessage,
                result.Status == "completed" ? "quick-fix-result" : "quick-fix-failed",
                cancellationToken);
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
    [FromServices] SkillActionService skillActions,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await skillActions.RunAsync(projectId, actionId, request, cancellationToken);
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

    var result = await projects.CreateProjectAsync(adminAccountId, request, cancellationToken);
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
        var result = await draftImport.AnalyzeAsync(projectId, file.FileName, memory.ToArray(), form["model"].FirstOrDefault(), cancellationToken);
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
    [FromServices] ProjectDraftImportService draftImport,
    CancellationToken cancellationToken) =>
{
    var result = await draftImport.GetLatestAsync(adminAccountId, projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "prototype_draft_not_found" }) : Results.Ok(result);
});

app.MapDelete("/api/projects/{projectId}", async (
    string projectId,
    [FromBody] ProjectDeletionRequest request,
    [FromServices] ProjectCreationService projects,
    CancellationToken cancellationToken) =>
{
    var result = await projects.DeleteProjectAsync(adminAccountId, projectId, request, cancellationToken);
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
    [FromServices] Chapter2BootstrapService chapter2,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await chapter2.RunAsync(projectId, cancellationToken);
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
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeWorkflow.QueueAsync(projectId, request, cancellationToken);
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
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        return Results.Ok(await prototypeWorkflow.GetProgressAsync(projectId, cancellationToken));
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-7day-playable/repair", async (
    string projectId,
    PrototypeRepairRequest request,
    [FromServices] PrototypeWorkflowService prototypeWorkflow,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeWorkflow.RepairAsync(projectId, request, cancellationToken);
        return result.Status == "queued" ? Results.Json(result, statusCode: StatusCodes.Status202Accepted) : Results.BadRequest(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.MapPost("/api/projects/{projectId}/prototype-tdd", async (
    string projectId,
    PrototypeTddRequest request,
    [FromServices] PrototypeCommandService prototypeCommands,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeCommands.RunTddAsync(projectId, request, cancellationToken);
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
    [FromServices] PrototypeCommandService prototypeCommands,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await prototypeCommands.CreateSceneAsync(projectId, request, cancellationToken);
        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
    }
    catch (InvalidOperationException ex)
    {
        return Results.NotFound(new { error = ex.Message });
    }
});

app.Run(options.AppBindUrl);

public partial class Program;
