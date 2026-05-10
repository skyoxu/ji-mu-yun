using PhaseA.Platform.Browser;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
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
builder.Services.AddSingleton<ProjectCreationService>();
builder.Services.AddSingleton<IHostedProcessRunner, HostedProcessRunner>();
builder.Services.AddSingleton<Chapter2BootstrapCommandBuilder>();
builder.Services.AddSingleton<ProjectHealthArtifactIndexer>();
builder.Services.AddSingleton<Chapter2BootstrapService>();
builder.Services.AddSingleton<PrototypeRecordWriter>();
builder.Services.AddSingleton<PrototypeWorkflowCommandBuilder>();
builder.Services.AddSingleton<PrototypeArtifactIndexer>();
builder.Services.AddSingleton<PrototypeWorkflowService>();
builder.Services.AddSingleton<PrototypeCommandBuilder>();
builder.Services.AddSingleton<PrototypeTddArtifactIndexer>();
builder.Services.AddSingleton<PrototypeCommandService>();
builder.Services.AddSingleton<ArtifactReadbackService>();
builder.Services.AddSingleton<LlmBindingService>();
builder.Services.AddSingleton<LlmStopLossService>();
builder.Services.AddSingleton<BrowserUiRenderer>();

var app = builder.Build();
var metadataStore = app.Services.GetRequiredService<PhaseAMetadataStore>();
var adminAccountId = await metadataStore.EnsureSingleAdminAsync();

app.Use(async (context, next) =>
{
    if (context.Request.Path == "/healthz" ||
        context.Request.Path == "/" ||
        context.Request.Path == "/ui")
    {
        await next(context);
        return;
    }

    var authOptions = context.RequestServices.GetRequiredService<PhaseAPlatformOptions>();
    if (!PhaseAAuth.IsAuthorized(context.Request, authOptions))
    {
        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
        await context.Response.WriteAsJsonAsync(new { error = PhaseAAuth.AuthFailureCode });
        return;
    }

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

app.MapGet("/api/projects/{projectId}/runs", async (
    string projectId,
    [FromServices] ArtifactReadbackService readback,
    CancellationToken cancellationToken) =>
{
    var result = await readback.GetProjectRunsAsync(projectId, cancellationToken);
    return result is null ? Results.NotFound(new { error = "project_not_found" }) : Results.Ok(result);
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

app.MapPost("/api/projects", async (
    JsonElement payload,
    [FromServices] ProjectCreationService projects,
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
    return result.Succeeded ? Results.Ok(result) : Results.BadRequest(result);
});

app.MapPost("/api/projects/{projectId}/chapter2-bootstrap", async (
    string projectId,
    [FromServices] Chapter2BootstrapService chapter2,
    CancellationToken cancellationToken) =>
{
    try
    {
        var result = await chapter2.RunAsync(projectId, cancellationToken);
        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
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
        var result = await prototypeWorkflow.RunAsync(projectId, request, cancellationToken);
        if (result.Status == "missing_required_fields")
        {
            return Results.BadRequest(result);
        }

        return result.Status == "succeeded" ? Results.Ok(result) : Results.BadRequest(result);
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
