using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.DependencyInjection;
using System.Net.Sockets;
using System.Net;
using System.Diagnostics;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Readback;
using System.Reflection;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.NodeIdentity;

[CollectionDefinition("S206 role closure environment", DisableParallelization = true)]
public sealed class S206RoleClosureEnvironmentCollection { }

// ADR-0061 AD19/20: Program fixtures mutate process environment and console state.
[Collection("S206 role closure environment")]
// ADR-0061 AD19/20: all state is disposable; actual services and real hosted timer.
public sealed class NodeRoleClosureTests(ITestOutputHelper output)
{
    [Fact]
    public async Task ProgramDetachedPreviewAndRestoreAdmissionObservations()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","revoked","stale-projection","foreign-home","foreign-project"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            foreach(var resource in new[]{f.First,f.Second,f.Admin})
                await f.Store.SetProjectBootstrapStatusAsync(resource.Project.ProjectId,"succeeded",null);
            // Seed the existing legacy package catalog prerequisite through actual metadata APIs.
            // This fixture record is not evidence of a real packager or Windows restore run.
            using(S206TestSupport.EnterCurrentContext(f.First.Context))
            {
                await f.Store.AddArtifactAsync(new ArtifactCreationCommand(f.First.RunId,f.First.Project.ProjectId,
                    "project-package-zip","exports/fixture.zip","Owned legacy package fixture"));
                await f.Store.CompleteRunAsync(f.First.RunId,"succeeded",0,"Owned package fixture prerequisite.","","{}");
            }
            await using var host=await LifetimeHost.StartAsync(f,CreateTinySource(f.Root));
            using var client=new HttpClient{BaseAddress=new Uri(host.Address)};
            client.DefaultRequestHeaders.Authorization=new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer",f.SyntheticToken(f.First));
            var restorePath="/api/projects/"+f.First.Project.ProjectId+"/packages/fixture.zip/restore";
            using var initialRestore=await client.PostAsync(restorePath,System.Net.Http.Json.JsonContent.Create(new{operationKey="owned-initial"}));
            var initialRestoreBody=await initialRestore.Content.ReadAsStringAsync();
            if((int)initialRestore.StatusCode!=409 || !initialRestoreBody.Contains("package_snapshot_unavailable",StringComparison.Ordinal))
                throw new InvalidOperationException("Actual non-versioned package restore gate unavailable: "+initialRestoreBody);
            var queue=host.Host.Services.GetRequiredKeyedService<HeavyRunnerQueueService>("web-preview");
            var held=new List<IAsyncDisposable>();
            try
            {
                using(S206TestSupport.EnterCurrentContext(f.First.Context))
                    // The real queue serializes each project, independently of global capacity.
                    // One owned lease blocks this project's detached callback without self-deadlock.
                    for(var i=0;i<1;i++)
                    {
                        var id=await f.Store.CreateRunAsync(f.First.Project.ProjectId,f.First.Project.WorkspaceId,"s236-owned-preview-blocker");
                        held.Add(await queue.EnterAsync(id,f.First.AccountId,f.First.Project.ProjectId,"s236-owned-preview-blocker"));
                    }
                using var response=await client.PostAsync("/api/projects/"+f.First.Project.ProjectId+"/packages/fixture.zip/web-preview",null);
                var responseBody=await response.Content.ReadAsStringAsync();
                if((int)response.StatusCode!=202)throw new InvalidOperationException("Actual HTTP preview admission unavailable: "+responseBody);
                using var value=JsonDocument.Parse(responseBody);
                var runId=value.RootElement.GetProperty("runId").GetString()!;
                var queued=false;
                var timer=Stopwatch.StartNew();
                while(timer.Elapsed<TimeSpan.FromSeconds(10))
                {
                    using(S206TestSupport.EnterCurrentContext(f.First.Context))
                        queued=queue.GetReadback(f.First.AccountId,false).Items.Any(item=>item.RunId==runId);
                    if(queued)break;
                    await Task.Delay(10);
                }
                if(!queued)throw new InvalidOperationException("Actual Program detached callback did not reach its real queue wait.");
                Dictionary<string,string> Files()=>Directory.EnumerateFiles(f.First.Project.WorkspaceRootPath,"*",SearchOption.AllDirectories)
                    .ToDictionary(path=>Path.GetRelativePath(f.First.Project.WorkspaceRootPath,path),path=>Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(path))),StringComparer.Ordinal);
                var before=Files();
                if(mode!="valid")await f.FaultAsync(f.First,mode);
                foreach(var lease in held)await lease.DisposeAsync();
                held.Clear();
                var observed=false;
                RunSnapshot? run=null;
                timer.Restart();
                while(timer.Elapsed<TimeSpan.FromSeconds(20))
                {
                    run=await f.Store.GetRunSnapshotAsync(runId);
                    observed=mode=="valid" ? run?.FinishedUtc is not null :
                        host.CapturedLogs.Contains("Web preview generation failed unexpectedly.",StringComparison.Ordinal)&&host.CapturedLogs.Contains(runId,StringComparison.Ordinal);
                    if(observed)break;
                    await Task.Delay(10);
                }
                if(!observed)throw new InvalidOperationException("Actual Program callback outcome not observed: "+mode);
                using var restoreAfter=await client.PostAsync(restorePath,System.Net.Http.Json.JsonContent.Create(new{operationKey="owned-after"}));
                var after=Files();
                var changed=before.Keys.Union(after.Keys).Where(path=>!before.TryGetValue(path,out var left)||
                    !after.TryGetValue(path,out var right)||left!=right).Order().ToArray();
                rows.Add(new{mode,httpAccepted=true,queueWaitObserved=queued,callbackObserved=observed,
                    started=run?.StartedUtc is not null,status=run?.Status,finished=run?.FinishedUtc is not null,changed,
                    restoreInitialStatus=(int)initialRestore.StatusCode,restoreInitialCode="package_snapshot_unavailable",restoreAfterStatus=(int)restoreAfter.StatusCode,
                    proofScope="actual HTTP Task.Run and queue/current-authority boundary; initial restore is a safe non-versioned-package rejection, not native restore/ACL activation"});
            }
            finally { foreach(var lease in held)await lease.DisposeAsync(); }
        }
        output.WriteLine("S206_PROGRAM_BOUNDARIES:"+JsonSerializer.Serialize(rows));
    }

    [Fact]
    public async Task AuthorityFixturesDoNotChangeProcessSnapshotKeyRoot()
    {
        var original = Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT");
        await using (var first = await S206AuthorityFixture.CreateAsync())
        {
            Assert.Equal(original, Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT"));
            await using (var second = await S206AuthorityFixture.CreateAsync())
                Assert.Equal(original, Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT"));
            Assert.Equal(original, Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT"));
        }
        Assert.Equal(original, Environment.GetEnvironmentVariable("PHASEA_SNAPSHOT_KEY_ROOT"));
    }

    // ADR-0061 AD20: concrete counterexamples for the constructor/default portion.
    // This is not the complete all-consumer publication/Windows closure claim.
    [Fact]
    public async Task O_7486EC7571D0()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        var options=f.Options with {RepositoryRoot=CreateTinySource(f.Root)};
        NodeProjectMetadata node=f.Store;
        var codex=new NeverDispatchCodex();
        var process=new HostedProcessRunner(authority:node);
        var bindings=(NodeLlmBindingReader)new LlmBindingService(f.Store,f.Options);
        var stopLoss=new LlmStopLossService(node,options);
        using var unusedHttp=new HttpClient();
        var seederControl=ActualSeeder(options,node);
        var factories=new Dictionary<string,Func<object>>(StringComparer.Ordinal)
        {
            ["ProjectCreationService.legacy"]=()=>new ProjectCreationService(node,options,new ProjectRuleCatalog()),
            ["ProjectDraftImportService.legacy"]=()=>new ProjectDraftImportService(node,options,codex),
            ["ProjectAssetInventoryService.legacy"]=()=>new ProjectAssetInventoryService(node,options,codex),
            ["PrototypeCommandService.legacy"]=()=>new PrototypeCommandService(node,options,process,
                new PrototypeCommandBuilder(options),new PrototypeTddArtifactIndexer()),
            ["PrototypeQuickFixService.legacy"]=()=>new PrototypeQuickFixService(node,options,process),
            ["PrototypeUiOptimizationService.legacy"]=()=>new PrototypeUiOptimizationService(node,options,process),
            ["PrototypeIterationGoalService.legacy"]=()=>new PrototypeIterationGoalService(node,options,process),
            ["PrototypeFeedbackIterationService.legacy"]=()=>new PrototypeFeedbackIterationService(node,options,process),
            ["PrototypeWorkflowService.legacy"]=()=>new PrototypeWorkflowService(node,options,process,
                new PrototypeRecordWriter(options),new PrototypeWorkflowCommandBuilder(options),new PrototypeArtifactIndexer(),bindings,stopLoss),
            ["ChatService.legacy"]=()=>new ChatService(node,options,bindings,stopLoss,new NewApiChatClient(unusedHttp),codex),
            ["Chapter2BootstrapService.legacy"]=()=>new Chapter2BootstrapService(node,options,process,
                new Chapter2BootstrapCommandBuilder(options),new ProjectHealthArtifactIndexer()),
            ["GameDesignDocumentService.omitted-queue"]=()=>new GameDesignDocumentService(node,options,process,seederControl),
            ["ArtifactReadbackService.omitted-queues"]=()=>new ArtifactReadbackService(node,options),
            ["ProjectPackageService.omitted-consumers"]=()=>new ProjectPackageService(node,options,storage:f.Storage),
            ["ProjectWebPreviewService.omitted-consumers"]=()=>new ProjectWebPreviewService(node,(NodePreviewRuntime)options),
            ["ProjectAssetLibraryService.omitted-consumers"]=()=>new ProjectAssetLibraryService(node,options,new ProjectAssetImageGenerator(options,process))
        };
        var legacy=new List<object>();
        foreach(var pair in factories)
        {
            var denied=false;var constructedQueues=0;var constructedSeeders=0;
            var seen=new HashSet<object>(System.Collections.Generic.ReferenceEqualityComparer.Instance);
            try
            {
                var instance=pair.Value();
                // A compatible pure parser may exist, but its ordinary producer must deny.
                if(instance is ProjectDraftImportService draft)
                {
                    using var current=S206TestSupport.EnterCurrentContext(f.First.Context);
                    try {await draft.AnalyzeAsync(f.First.AccountId,f.First.Project.ProjectId,"draft.txt",
                        System.Text.Encoding.UTF8.GetBytes("game_name: No production from a parser facade"),null);}
                    catch(UnauthorizedAccessException){denied=true;}
                }
                foreach(var field in instance.GetType().GetFields(BindingFlags.Instance|BindingFlags.NonPublic))
                {
                    var value=field.GetValue(instance);
                    if(value is null || !seen.Add(value))continue;
                    if(value is HeavyRunnerQueueService)constructedQueues++;
                    if(value is ProjectWorkspaceSeeder)constructedSeeders++;
                }
            }
            catch(UnauthorizedAccessException){denied=true;}
            legacy.Add(new{family=pair.Key,denied,constructedQueues,constructedSeeders});
        }
        // Real supported constructor with explicit protected dependencies.
        var queue=f.Queue();var seeder=ActualSeeder(options,node);
        var explicitServices=new object[]
        {
            new ProjectDraftImportService(node,options,codex,null,null,seeder,heavyRunnerQueue:queue),
            new ProjectAssetInventoryService(node,options,codex,seeder,heavyRunnerQueue:queue),
            new PrototypeCommandService(node,options,process,new PrototypeCommandBuilder(options),
                new PrototypeTddArtifactIndexer(),seeder,queue)
        };
        var controls=new List<object>();
        using(var current=S206TestSupport.EnterCurrentContext(f.First.Context))
        {
            seeder.EnsureSeeded(f.First.Project.RepoPath);
            foreach(var service in explicitServices)
            {
                var held=(HeavyRunnerQueueService)service.GetType().GetField("_heavyRunnerQueue",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(service)!;
                var count=0;
                var result=await held.ExecuteAsync(Guid.NewGuid().ToString("N"),f.First.AccountId,
                    f.First.Project.ProjectId,"s236-constructor-control",ct=>Task.FromResult(++count));
                controls.Add(new{family=service.GetType().Name,registeredQueue=ReferenceEquals(held,queue),result,count});
            }
        }
        var invalidStarted=false;var invalidDenied=false;
        using(var current=S206TestSupport.EnterCurrentContext(f.Second.Context))
        {
            try {await queue.ExecuteAsync(Guid.NewGuid().ToString("N"),f.First.AccountId,f.First.Project.ProjectId,
                "s236-cross-account",ct=>{invalidStarted=true;return Task.FromResult(1);});}
            catch(UnauthorizedAccessException){invalidDenied=true;}
        }
        var entryOptions=options with {EnabledRoles=new HashSet<string>{"entry"}};
        NodeProjectMetadata entryNode=new PhaseAMetadataStore(f.ConnectionString,entryOptions);
        var entryQueue=new HeavyRunnerQueueService(TimeSpan.FromSeconds(1),1,entryNode);
        var entryStarted=false;var entryDenied=false;
        using(var current=S206TestSupport.EnterCurrentContext(f.First.Context))
        {
            try {await entryQueue.ExecuteAsync(Guid.NewGuid().ToString("N"),f.First.AccountId,f.First.Project.ProjectId,
                "s236-entry-only",ct=>{entryStarted=true;return Task.FromResult(1);});}
            catch(UnauthorizedAccessException){entryDenied=true;}
        }
        var pureImportSupported=false;
        try
        {
            var parser=new ProjectDraftImportService(node,options,codex);
            pureImportSupported=parser.ImportPlainText("draft.txt",System.Text.Encoding.UTF8.GetBytes(
                "game_name: Imported control\nnode_id: foreign-node\nhome_node_id: foreign-node\nport: 9000")).Status=="succeeded";
        }
        catch(UnauthorizedAccessException){ }
        var queueControls=await ObserveQueueControlsAsync();
        var cancellationControls=await ObserveCancellationControlsAsync();
        var queueOverloads=await ObserveQueueOverloadsAsync();
        var shutdownControls=await ObserveShutdownControlsAsync();
        var ticketControls=await ObserveTicketControlsAsync();
        var routeReadControls=await ObserveRouteReadControlsAsync();
        var artifactReadControls=await ObserveArtifactReadControlsAsync();
        var questionFormControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveModelReplyBoundaryAsync("question-form");
        var warmQuestionFormControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveWarmQuestionFormAsync();
        var sceneReplyControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveSceneReplyBoundaryAsync();
        var iterationPlanReplies=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveIterationPlanReplyBoundaryAsync();
        var backfillEntries=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveGameTypeBackfillEntriesAsync();
        var assetInventoryReplies=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveAssetInventoryReplyBoundaryAsync();
        var repairAndMilestoneReplies=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveRepairAndMilestoneReplyBoundaryAsync();
        var assetAndPreviewPublications=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveAssetAndPreviewPublicationAsync();
        var assetImportsAndSelections=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveAssetImportAndSelectionAsync();
        var childProducerPublications=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveChildProducerPublicationAsync();
        var chatHistoryControls=await ObserveChatHistoryControlsAsync();
        var savedReadbackControls=await ObserveSavedReadbackControlsAsync();
        var chatReplyControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveChatReplyBoundaryAsync();
        var directExecutionContinuations=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveDirectExecutionContinuationsAsync();
        var repairExecutionAndNewRound=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveRepairExecutionAndNewRoundAsync();
        var milestoneMutationWaits=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveMilestoneMutationWaitsAsync();
        output.WriteLine("S206_CONSUMER_COUNTEREXAMPLES:"+JsonSerializer.Serialize(new{legacy,controls,pureImportSupported,queueControls,cancellationControls,queueOverloads,shutdownControls,ticketControls,routeReadControls,artifactReadControls,questionFormControls,warmQuestionFormControls,sceneReplyControls,iterationPlanReplies,backfillEntries,assetInventoryReplies,repairAndMilestoneReplies,assetAndPreviewPublications,assetImportsAndSelections,childProducerPublications,
            chatHistoryControls,savedReadbackControls,chatReplyControls,directExecutionContinuations,repairExecutionAndNewRound,milestoneMutationWaits,
            seedControl=File.Exists(Path.Combine(f.First.Project.RepoPath,"Directory.Build.props")),
            invalidDenied,invalidStarted,entryDenied,entryStarted,networkCalls=codex.Calls,
            coverageScope="constructor/default counterexamples; complete callable and Windows closure still required",
            nativeWindowsEvidence=false}));
    }

    [Fact]
    public async Task HostedRegisteredProjectLaunchObservations()
    {
        var rows=await ObserveHostedLaunchControlsAsync();
        output.WriteLine("S206_NATIVE_LAUNCH_COUNTEREXAMPLES:"+JsonSerializer.Serialize(rows));
    }

    // ADR-0061 AD20: real owned child effects, never simulated native Windows isolation.
    private static async Task<object> ObserveHostedLaunchControlsAsync()
    {
        var python=Environment.GetEnvironmentVariable("S206_TEST_PYTHON");
        if(string.IsNullOrWhiteSpace(python) || !Path.IsPathRooted(python) || !File.Exists(python))
            throw new InvalidOperationException("Owned bridge Python executable unavailable.");
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","detached-current","no-context","foreign-account","forged-context",
            "revoked","foreign-home","stale-projection","foreign-project","foreign-local","entry-only","no-authority"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            HostedProcessCommand Command(S206AuthorityFixture.Resource resource,string file)
                =>new(python,["-I","-S","-c",
                    "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('owned-launch', encoding='utf-8'); print('S206_OWNED_CHILD')",file],
                    resource.Project.RepoPath,new Dictionary<string,string>(),TotalTimeout:TimeSpan.FromSeconds(10),
                    InactivityTimeout:TimeSpan.FromSeconds(10));
            var controlRunner=new HostedProcessRunner(authority:f.Store);
            foreach(var resource in new[]{f.First,f.Second})
            {
                using var current=S206TestSupport.EnterCurrentContext(resource.Context);
                var result=await controlRunner.RunAsync(Command(resource,"s206-launch-control.txt"));
                if(result.ExitCode!=0 || !result.Stdout.Contains("S206_OWNED_CHILD",StringComparison.Ordinal) ||
                    await File.ReadAllTextAsync(Path.Combine(resource.Project.RepoPath,"s206-launch-control.txt"))!="owned-launch")
                    throw new InvalidOperationException("Actual owned registered-project launch positive unavailable.");
            }
            if(mode is "revoked" or "foreign-home" or "stale-projection" or "foreign-local")
                await f.FaultAsync(f.First,mode);
            var target=mode=="foreign-project"?f.Second:f.First;
            NodeProjectMetadata node=mode=="entry-only"?new PhaseAMetadataStore(f.ConnectionString,
                f.Options with{EnabledRoles=new HashSet<string>{"entry"}}):f.Store;
            var runner=new HostedProcessRunner(authority:mode=="no-authority"?null:node);
            var context=mode=="foreign-account"?f.Second.Context:mode=="forged-context"?
                f.First.Context with{CredentialId=f.Second.Context.CredentialId}:mode=="detached-current"?
                f.First.Context.ForBackground(f.First.RunId):f.First.Context;
            var before=f.ContentHash(f.First)+f.ContentHash(f.Second);
            HostedProcessResult attempt;
            using(var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context))
                attempt=await runner.RunAsync(Command(target,"s206-launch-attempt.txt"));
            var marker=Path.Combine(target.Project.RepoPath,"s206-launch-attempt.txt");
            rows.Add(new{mode,exitCode=attempt.ExitCode,childOutput=attempt.Stdout.Contains("S206_OWNED_CHILD",StringComparison.Ordinal),
                markerExists=File.Exists(marker),markerMatches=File.Exists(marker) && await File.ReadAllTextAsync(marker)=="owned-launch",
                filesUnchanged=before==f.ContentHash(f.First)+f.ContentHash(f.Second),actualWindowsEvidence=false});
        }
        return rows;
    }

    // ADR-0061 AD20: actual persisted private readback, with distinct two-account payloads.
    private static async Task<object> ObserveSavedReadbackControlsAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","no-context","foreign-account","forged-context","revoked",
            "foreign-home","stale-projection","foreign-project","foreign-local","entry-only"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            foreach(var resource in new[]{f.First,f.Second})
            {
                using var current=S206TestSupport.EnterCurrentContext(resource.Context);
                var run=await f.Store.CreateRunAsync(resource.Project.ProjectId,resource.Project.WorkspaceId,"game-design-gdd");
                var prompt=Path.Combine(resource.Project.RepoPath,"logs","phase-a-gdd",resource.Project.ProjectId,run,"gdd-prompt.md");
                Directory.CreateDirectory(Path.GetDirectoryName(prompt)!);
                await File.WriteAllTextAsync(prompt,"Question-form answers:\n1. Private answer: "+resource.Sentinel+"\n");
                var scene=Path.Combine(resource.Project.RepoPath,"meta","routes","scene-route","latest.json");
                Directory.CreateDirectory(Path.GetDirectoryName(scene)!);
                await File.WriteAllTextAsync(scene,JsonSerializer.Serialize(new{status="confirmed",entry_scene="S1",
                    scene_count_intent="single",scenes=new[]{new{scene_id="S1",scene_name=resource.Sentinel,
                        role="entry",m1_required=true,player_goal=resource.Sentinel}},transitions=Array.Empty<object>()}));
                var map=Path.Combine(resource.Project.RepoPath,"meta","routes","gdd-requirements","latest.json");
                Directory.CreateDirectory(Path.GetDirectoryName(map)!);
                await File.WriteAllTextAsync(map,JsonSerializer.Serialize(new{status="ready",requirements=new[]{new{
                    requirement_id="R1",normalized_requirement=resource.Sentinel,source_section="fixture",
                    normalized_source_summary=resource.Sentinel,source_language="en",priority="P1",kind="behavior",
                    status="mapped",mapped_scene_ids=new[]{"S1"},mapped_required_module_ids=new[]{"M1"}}}}));
                await f.Store.CreateProjectIterationSessionAsync(resource.AccountId,resource.Project.ProjectId,
                    "repair_plan",resource.Sentinel,resource.Sentinel,
                    [new ProjectIterationGoalCreateCommand(1,resource.Sentinel,resource.Sentinel,resource.Sentinel)]);
            }
            var target=f.First;
            Dictionary<string,Func<Task<object?>>> Entries(NodeProjectMetadata node)
            {
                var answers=new GameDesignQuestionFormRestoreService(node,f.Options);
                var routes=new GddToModulePhase1StateService(node);
                var map=new GameDesignRequirementMapService(node);
                var queue=new HeavyRunnerQueueService(null,HeavyRunnerQueueService.DefaultMaxConcurrentOtherRuns,node);
                var quickFix=new PrototypeQuickFixService(node,f.Options,new HostedProcessRunner(authority:node),
                    ActualSeeder(f.Options,node),new PhaseA.Platform.Skills.SkillActionCatalog(),heavyRunnerQueue:queue);
                var repair=new PrototypeRepairPlanService(node,quickFix);
                return new(){
                    ["question-answers"]=async()=>await answers.ReadLatestAsync(f.First.AccountId,target.Project.ProjectId),
                    ["scene-route"]=async()=>await routes.GetSceneRouteAsync(f.First.AccountId,target.Project.ProjectId),
                    ["requirement-map"]=async()=>await map.GetLatestAsync(f.First.AccountId,target.Project.ProjectId),
                    ["repair-plan"]=async()=>await repair.GetLatestAsync(f.First.AccountId,target.Project.ProjectId)};
            }
            using(S206TestSupport.EnterCurrentContext(f.First.Context))
                foreach(var (entry,call) in Entries(f.Store))
                    if(!JsonSerializer.Serialize(await call()).Contains(f.First.Sentinel,StringComparison.Ordinal))
                        throw new InvalidOperationException("Actual saved readback positive unavailable: "+entry);
            if(mode is "revoked" or "foreign-home" or "stale-projection" or "foreign-local")
                await f.FaultAsync(f.First,mode);
            if(mode=="foreign-project")target=f.Second;
            NodeProjectMetadata authority=mode=="entry-only"?new PhaseAMetadataStore(f.ConnectionString,
                f.Options with{EnabledRoles=new HashSet<string>{"entry"}}):f.Store;
            var context=mode=="foreign-account"?f.Second.Context:mode=="forged-context"?
                f.First.Context with{CredentialId=f.Second.Context.CredentialId}:f.First.Context;
            var files=f.ContentHash(f.First)+f.ContentHash(f.Second);
            foreach(var (entry,call) in Entries(authority))
            {
                var denied=false;var returned=false;var ownPayload=false;var foreignPayload=false;
                using(var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context))
                {
                    try
                    {
                        var result=await call();returned=result is not null;denied=result is null;
                        var payload=JsonSerializer.Serialize(result);
                        ownPayload=payload.Contains(f.First.Sentinel,StringComparison.Ordinal);
                        foreignPayload=payload.Contains(f.Second.Sentinel,StringComparison.Ordinal);
                    }
                    catch(UnauthorizedAccessException){denied=true;}
                }
                rows.Add(new{mode,entry,denied,returned,ownPayload,foreignPayload,
                    privateFilesUnchanged=files==f.ContentHash(f.First)+f.ContentHash(f.Second)});
            }
        }
        return rows;
    }

    // ADR-0061 AD20: exercise both real chat history methods, not a constructor census.
    private static async Task<object> ObserveChatHistoryControlsAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","no-context","foreign-account","forged-context","revoked",
            "foreign-home","stale-projection","foreign-project","foreign-local","entry-only"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            NodeProjectMetadata node=f.Store;
            var service=new ProjectChatHistoryService(node);
            foreach(var resource in new[]{f.First,f.Second})
            {
                using var current=S206TestSupport.EnterCurrentContext(resource.Context);
                await service.AppendAsync(resource.AccountId,resource.Project.ProjectId,"user",resource.Sentinel,"plain");
                var control=await service.ListAsync(resource.AccountId,resource.Project.ProjectId);
                if(control?.Messages.SingleOrDefault()?.Content!=resource.Sentinel)
                    throw new InvalidOperationException("Actual two-account chat history positive unavailable.");
            }
            if(mode is "revoked" or "foreign-home" or "stale-projection" or "foreign-local")
                await f.FaultAsync(f.First,mode);
            if(mode=="entry-only")
                service=new ProjectChatHistoryService(new PhaseAMetadataStore(f.ConnectionString,
                    f.Options with{EnabledRoles=new HashSet<string>{"entry"}}));
            var target=mode=="foreign-project"?f.Second:f.First;
            var context=mode=="foreign-account"?f.Second.Context:mode=="forged-context"?
                f.First.Context with{CredentialId=f.Second.Context.CredentialId}:f.First.Context;
            string ChatRows()
            {
                using var connection=new Microsoft.Data.Sqlite.SqliteConnection(f.ConnectionString);
                connection.Open();using var command=connection.CreateCommand();
                command.CommandText="SELECT id,account_id,project_id,role,content,kind,created_utc FROM project_chat_messages ORDER BY id";
                using var reader=command.ExecuteReader();var values=new List<object>();
                while(reader.Read())values.Add(Enumerable.Range(0,reader.FieldCount)
                    .Select(i=>reader.IsDBNull(i)?null:reader.GetValue(i)).ToArray());
                return JsonSerializer.Serialize(values);
            }
            var initialRows=ChatRows();var files=f.ContentHash(f.First)+f.ContentHash(f.Second);
            foreach(var entry in new[]{"list","append"})
            {
                var before=ChatRows();var denied=false;var returned=false;var exposed=false;
                using(var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context))
                {
                    try
                    {
                        if(entry=="list")
                        {
                            var result=await service.ListAsync(f.First.AccountId,target.Project.ProjectId);
                            returned=result is not null;
                            exposed=result?.Messages.Any(m=>m.Content==f.Second.Sentinel)==true;
                            denied=result is null;
                            if(mode=="valid" && result?.Messages.SingleOrDefault()?.Content!=f.First.Sentinel)
                                throw new InvalidOperationException("Current own chat history bytes missing.");
                        }
                        else
                        {
                            await service.AppendAsync(f.First.AccountId,target.Project.ProjectId,"user","owned-chat-append","plain");
                            returned=true;
                        }
                    }
                    catch(UnauthorizedAccessException){denied=true;}
                }
                rows.Add(new{mode,entry,denied,returned,exposed,rowsChanged=before!=ChatRows(),
                    privateFilesUnchanged=files==f.ContentHash(f.First)+f.ContentHash(f.Second),
                    initialRowsPreserved=entry=="list"?initialRows==ChatRows():true});
            }
        }
        return rows;
    }

    // ADR-0061 AD20: cancellation/readback are bounded control operations, never production admission.
    private static async Task<List<object>> ObserveQueueControlsAsync()
    {
        var rows=new List<object>();
        foreach(var position in new[]{"running","waiting"})
        foreach(var mode in new[]{"own","foreign-account","no-context","revoked","entry-only","admin"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var roles=new HashSet<string>{"entry","production"};
            var options=f.Options with {EnabledRoles=roles};
            NodeProjectMetadata authority=new PhaseAMetadataStore(f.ConnectionString,options);
            var queue=new HeavyRunnerQueueService(TimeSpan.FromSeconds(1),1,authority);
            var started=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var release=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var run="queue-control-"+Guid.NewGuid().ToString("N");
            var waitingRun=run+"-waiting";var waitingStarted=false;
            Task<bool> running;Task<bool>? waiting=null;
            using(var current=S206TestSupport.EnterCurrentContext(f.First.Context))
                running=queue.ExecuteAsync(run,f.First.AccountId,f.First.Project.ProjectId,"s236-control",async ct=>
                {started.SetResult();await release.Task.WaitAsync(ct);return true;});
            await started.Task.WaitAsync(TimeSpan.FromSeconds(5));
            if(position=="waiting")
            {
                using var current=S206TestSupport.EnterCurrentContext(f.First.Context);
                waiting=queue.ExecuteAsync(waitingRun,f.First.AccountId,f.First.Project.ProjectId,"s236-control",
                    ct=>{waitingStarted=true;return Task.FromResult(true);});
            }
            var context=mode=="foreign-account"?f.Second.Context:mode=="admin"?f.Admin.Context:f.First.Context;
            if(mode=="revoked")await f.FaultAsync(f.First,"revoked");
            if(mode=="entry-only")roles.Remove("production");
            var visible=false;var readDenied=false;var allDenied=false;var allVisible=false;
            var cancelDenied=false;var cancelled=false;var dispatchDenied=false;var dispatched=false;
            try
            {
                using var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context);
                try
                {
                    var read=queue.GetReadback(f.First.AccountId,false);
                    visible=read.Current?.RunId==run && (position!="waiting"||read.Items.Any(i=>i.RunId==waitingRun));
                }
                catch(UnauthorizedAccessException){readDenied=true;}
                try
                {
                    var read=queue.GetReadback(context.AccountId,true);
                    allVisible=read.Current?.RunId==run;
                }
                catch(UnauthorizedAccessException){allDenied=true;}
                try {cancelled=queue.CancelRun(position=="waiting"?waitingRun:run);}
                catch(UnauthorizedAccessException){cancelDenied=true;}
                if(mode=="entry-only")
                {
                    try {await queue.ExecuteAsync(run+"-forbidden",f.First.AccountId,f.First.Project.ProjectId,
                        "s236-no-production",ct=>{dispatched=true;return Task.FromResult(true);});}
                    catch(UnauthorizedAccessException){dispatchDenied=true;}
                }
            }
            finally
            {
                // Release only this fixture's own callback; no privileged product cleanup replacement.
                release.TrySetResult();
            }
            var targetCancelled=false;
            try {await (waiting??running).WaitAsync(TimeSpan.FromSeconds(5));}
            catch(OperationCanceledException){targetCancelled=true;}
            catch(UnauthorizedAccessException){}
            try {await running.WaitAsync(TimeSpan.FromSeconds(5));}
            catch(OperationCanceledException){}
            rows.Add(new{position,mode,visible,readDenied,allDenied,allVisible,cancelDenied,cancelled,
                targetCancelled,waitingStarted,dispatchDenied,dispatched});
        }
        return rows;
    }

    private static async Task<List<object>> ObserveCancellationControlsAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"own","foreign-account","forged-admin","no-context","revoked","entry-only"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var roles=new HashSet<string>{"entry","production"};
            NodeProjectMetadata node=new PhaseAMetadataStore(f.ConnectionString,f.Options with {EnabledRoles=roles});
            var constructor=typeof(RunCancellationService).GetConstructor([typeof(NodeProjectMetadata)]);
            var service=constructor is null?new RunCancellationService():
                (RunCancellationService)constructor.Invoke([node]);
            CancellationTokenSource token;
            using(var current=S206TestSupport.EnterCurrentContext(f.First.Context))
                token=service.CreateLinkedTokenSource(f.First.RunId,CancellationToken.None);
            var context=mode=="foreign-account"?f.Second.Context:mode=="forged-admin"?
                f.First.Context with {Roles=new HashSet<string>{PhaseAAuth.AdminRole}}:f.First.Context;
            if(mode=="revoked")await f.FaultAsync(f.First,"revoked");
            if(mode=="entry-only")roles.Remove("production");
            var before=await f.OwnershipAsync(f.First);var cancelled=false;var denied=false;
            using(var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context))
            {
                try {cancelled=service.Cancel(f.First.RunId);}
                catch(UnauthorizedAccessException){denied=true;}
            }
            var requested=token.IsCancellationRequested;
            // Existing trusted finally-cleanup must work even after current authority closes.
            service.Unregister(f.First.RunId);
            var publicMethods=typeof(RunCancellationService).GetMethods(BindingFlags.Instance|BindingFlags.Public)
                .Select(m=>m.Name).ToHashSet(StringComparer.Ordinal);
            rows.Add(new{mode,cancelled,denied,requested,ownershipUnchanged=before==await f.OwnershipAsync(f.First),
                trustedRegistrationNotPublic=!publicMethods.Contains("CreateLinkedTokenSource"),
                trustedCleanupNotPublic=!publicMethods.Contains("Unregister"),
                privateTokenStateNotPublic=!publicMethods.Contains("IsCancellationRequested")});
        }
        return rows;
    }

    private static async Task<List<object>> ObserveQueueOverloadsAsync()
    {
        var rows=new List<object>();
        foreach(var entry in new[]{"execute","execute-start","authorized","enter","try-enter","creation-wrapper"})
        foreach(var mode in new[]{"valid","entry-only","no-context","forged-context","revoked","foreign-home",
            "foreign-project","foreign-local","stale-projection","detached-explicit"})
        {
            if(mode=="detached-explicit" && entry!="authorized")continue;
            await using var f=await S206AuthorityFixture.CreateAsync();
            var options=mode=="entry-only"?f.Options with {EnabledRoles=new HashSet<string>{"entry"}}:f.Options;
            NodeProjectMetadata node=new PhaseAMetadataStore(f.ConnectionString,options);
            var queue=new HeavyRunnerQueueService(TimeSpan.FromSeconds(1),1,node);
            var creation=new ProjectCreationRunnerQueue(queue);
            var context=mode=="forged-context"?f.First.Context with {CredentialId=f.Second.Context.CredentialId}:f.First.Context;
            if(mode is "revoked" or "foreign-home" or "foreign-project" or "foreign-local" or "stale-projection")
                await f.FaultAsync(f.First,mode);
            var started=0;var result=0;var rejected=false;var leaseObserved=false;
            async Task<int> Work(CancellationToken ct)
            {
                started++;
                var run=await node.GetRunSnapshotAsync(f.First.RunId,ct);
                return run?.ProjectId==f.First.Project.ProjectId?1:0;
            }
            using(var current=mode is "no-context" or "detached-explicit"?null:S206TestSupport.EnterCurrentContext(context))
            {
                try
                {
                    switch(entry)
                    {
                        case "execute": result=await queue.ExecuteAsync(f.First.RunId,f.First.AccountId,f.First.Project.ProjectId,"s236-overload",Work);break;
                        case "execute-start": result=await queue.ExecuteAsync(f.First.RunId,f.First.AccountId,f.First.Project.ProjectId,"s236-overload",(_,ct)=>Work(ct));break;
                        case "authorized": result=await queue.ExecuteAuthorizedAsync(f.First.RunId,f.First.AccountId,f.First.Project.ProjectId,"s236-overload",
                            mode=="no-context"?null!:context,(_,ct)=>f.Store.ProjectBelongsToAccountAsync(f.First.AccountId,f.First.Project.ProjectId,ct),Work);break;
                        case "enter":
                            await using(var lease=await queue.EnterAsync(f.First.RunId,f.First.AccountId,f.First.Project.ProjectId,"s236-overload"))
                            {leaseObserved=queue.GetReadback(f.First.AccountId,false).Running;result=await Work(CancellationToken.None);}break;
                        case "try-enter":
                            await using(var lease=queue.TryEnter(f.First.RunId,f.First.AccountId,f.First.Project.ProjectId,"s236-overload"))
                            {if(lease is not null){leaseObserved=queue.GetReadback(f.First.AccountId,false).Running;result=await Work(CancellationToken.None);}}break;
                        case "creation-wrapper": result=await creation.Queue.ExecuteAsync(f.First.RunId,f.First.AccountId,f.First.Project.ProjectId,"s236-overload",Work);break;
                    }
                }
                catch(UnauthorizedAccessException){rejected=true;}
                catch(ArgumentNullException)when(entry=="authorized" && mode=="no-context"){rejected=true;}
            }
            var running=(System.Collections.ICollection)typeof(HeavyRunnerQueueService)
                .GetField("_running",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(queue)!;
            var waiting=(System.Collections.ICollection)typeof(HeavyRunnerQueueService)
                .GetField("_waiting",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(queue)!;
            rows.Add(new{entry,mode,started,result,rejected,leaseObserved,remainingRunning=running.Count,
                remainingWaiting=waiting.Count,creationWrapperSameQueue=ReferenceEquals(queue,creation.Queue)});
        }
        return rows;
    }

    private sealed class NeverDispatchCodex:ICodexChatClient
    {
        internal int Calls;
        public Task<CodexChatClientResult> CompleteAsync(string projectRoot,string model,string prompt,
            CodexChatClientOptions? options=null,string? billingApiKeyName=null,CancellationToken cancellationToken=default)
        {Interlocked.Increment(ref Calls);throw new InvalidOperationException("Constructor guards must not dispatch a model.");}
    }

    [Fact]
    public async Task O_F3517D4EEF1B()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","entry-only","no-context","forged-context","missing-home","foreign-project","foreign-local","revoked"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var source=CreateTinySource(f.Root);
            var options=f.Options with {RepositoryRoot=source};
            if(mode=="entry-only")options=options with {EnabledRoles=new HashSet<string>{"entry"}};
            if(mode is "missing-home" or "foreign-project" or "foreign-local" or "revoked")await f.FaultAsync(f.First,mode);
            NodeProjectMetadata node=new PhaseAMetadataStore(f.ConnectionString,options);
            var context=mode=="forged-context" ? f.First.Context with {CredentialId=f.Second.Context.CredentialId}:f.First.Context;
            using var scope=mode=="no-context" ? null:S206TestSupport.EnterCurrentContext(context);
            var seeder=ActualSeeder(options,node);
            var marker=Path.Combine(f.First.Project.RepoPath,"Directory.Build.props");
            var before=await f.OwnershipAsync(f.First);var hash=f.ContentHash(f.First);
            var seeded=false;
            try {seeder.EnsureSeeded(f.First.Project.RepoPath);seeded=File.ReadAllText(marker)=="s206-template-v1";}
            catch(UnauthorizedAccessException) { }
            var logger=new CaptureLogger<ProjectInitializationService>();
            var bootstrap=new Chapter2BootstrapService(node,options,new HostedProcessRunner(authority:node),
                new Chapter2BootstrapCommandBuilder(options),new ProjectHealthArtifactIndexer(),seeder,
                heavyRunnerQueue:f.Queue());
            var initialization=new ProjectInitializationService(node,bootstrap,logger);
            // A real completed bootstrap makes the harmless positive path observable
            // without an engine, fake runner or Windows launch claim.
            var run=await f.Store.CreateRunAsync(f.First.Project.ProjectId,f.First.Project.WorkspaceId,"chapter2-bootstrap");
            await f.Store.CompleteRunAsync(run,"succeeded",0,"", "", "{}");
            await f.Store.SetProjectBootstrapStatusAsync(f.First.Project.ProjectId,"initial",null);
            var startDenied=false;
            try {initialization.StartChapter2Bootstrap(f.First.Project.ProjectId);}
            catch(UnauthorizedAccessException){startDenied=true;}
            var observed=startDenied;
            for(var i=0;i<100&&!observed;i++)
            {
                var current=await f.Store.GetProjectSnapshotAsync(f.First.Project.ProjectId);
                observed=current?.BootstrapStatus=="succeeded"||logger.ErrorObserved;
                if(!observed)await Task.Delay(10);
            }
            var after=await f.Store.GetProjectSnapshotAsync(f.First.Project.ProjectId);
            var reconcilesDenied=new List<bool>();
            foreach(var action in new Func<Task>[] {()=>initialization.ReconcileInterruptedInitializationsAsync(),()=>initialization.ReconcileStaleInitializationsAsync()})
            {
                try {await action();reconcilesDenied.Add(false);}catch(UnauthorizedAccessException){reconcilesDenied.Add(true);}
            }
            var maintenance=new ProjectWorkspaceMaintenanceService(node,seeder,NullLogger<ProjectWorkspaceMaintenanceService>.Instance);
            var maintenanceDenied=false;
            try {await maintenance.EnsureAllWorkspacesSeededAsync();}catch(UnauthorizedAccessException){maintenanceDenied=true;}
            rows.Add(new {mode,seeded,observed,bootstrapSucceeded=after?.BootstrapStatus=="succeeded",
                projectRetained=after is not null,unchanged=before==await f.OwnershipAsync(f.First)&&hash==f.ContentHash(f.First),
                reconcilesDenied,maintenanceDenied});
        }

        // Actual Program startup and actual 30-second BackgroundService scan.
        // Tiny source contents prevent copying the real repository into fixtures.
        var hosted=new List<object>();
        foreach(var mode in new[]{"valid","entry-only","foreign-project","missing-home"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var source=CreateTinySource(f.Root);
            foreach(var resource in new[]{f.First,f.Second,f.Admin})
                await f.Store.SetProjectBootstrapStatusAsync(resource.Project.ProjectId,"succeeded",null);
            if(mode is "foreign-project" or "missing-home")await f.FaultAsync(f.First,mode);
            var before=await f.OwnershipAsync(f.First);var hash=f.ContentHash(f.First);
            var rawAdmin=Guid.NewGuid().ToString("N");
            var host=await S206OwnedHost.StartAsync(f.Root,rawAdmin,
                enabledRoles:mode=="entry-only"?"entry":"entry,production",repositoryRoot:source);
            var marker=Path.Combine(f.First.Project.RepoPath,"Directory.Build.props");
            var startupSeed=File.Exists(marker)&&File.ReadAllText(marker)=="s206-template-v1";
            var timerObserved=false;var timerSeed=false;
            var started=host.Started;var pid=host.ProcessId;
            try
            {
            if(mode=="valid"&&host.Started)
            {
                File.WriteAllText(Path.Combine(source,"Directory.Build.props"),"s206-template-v2");
                for(var i=0;i<380;i++)
                {
                    if(File.Exists(marker)&&File.ReadAllText(marker)=="s206-template-v2")
                    {timerObserved=true;timerSeed=true;break;}
                    await Task.Delay(100);
                }
                // Lack of a real effect is a product failure, not invented timer proof.
            }
            }
            finally {await host.DisposeAsync();}
            var nativeLog=await File.ReadAllTextAsync(Path.Combine(f.Root,"host-"+pid+".stdout.log"));
            var preheatObserved=nativeLog.Contains("Godot3 web preview health preheat",StringComparison.Ordinal);
            hosted.Add(new {mode,started,startupSeed,timerObserved,timerSeed,preheatObserved,
                unchanged=before==await f.OwnershipAsync(f.First)&&hash==f.ContentHash(f.First),
                firstProjectRetained=await f.Store.GetProjectSnapshotAsync(f.First.Project.ProjectId) is not null});
        }
        output.WriteLine("S206_RECOVERY:"+JsonSerializer.Serialize(new {direct=rows,hosted,nativeWindowsEvidence=false}));
    }

    private static string CreateTinySource(string root)
    {
        var source=Path.Combine(root,"tiny-source");Directory.CreateDirectory(source);
        File.WriteAllText(Path.Combine(source,"Directory.Build.props"),"s206-template-v1");
        return source;
    }

    private static ProjectWorkspaceSeeder ActualSeeder(PhaseAPlatformOptions options,NodeProjectMetadata node)
    {
        var constructor=typeof(ProjectWorkspaceSeeder).GetConstructor([typeof(NodeExecutionOptions),typeof(NodeProjectMetadata)]);
        return constructor is null?new ProjectWorkspaceSeeder(options):
            (ProjectWorkspaceSeeder)constructor.Invoke([(NodeExecutionOptions)options,node]);
    }

    private sealed class CaptureLogger<T>:ILogger<T>
    {
        private int _error;
        internal bool ErrorObserved=>Volatile.Read(ref _error)!=0;
        public IDisposable? BeginScope<TState>(TState state)where TState:notnull=>null;
        public bool IsEnabled(LogLevel level)=>true;
        public void Log<TState>(LogLevel level,EventId id,TState state,Exception? exception,Func<TState,Exception?,string> formatter)
        {if(level>=LogLevel.Error)Interlocked.Exchange(ref _error,1);}
    }
    // Actual composed host, all five owned queues and real stopping tokens.
    private static async Task<object> ObserveArtifactReadControlsAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","no-context","foreign-account","forged-context","revoked",
            "foreign-home","stale-projection","foreign-project","foreign-local"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            NodeProjectMetadata node=f.Store;var queue=f.Queue();
            var options=f.Options with{RepositoryRoot=CreateTinySource(f.Root)};
            var publicHealth=Path.Combine(options.RepositoryRoot,"logs","ci","project-health","latest.json");
            Directory.CreateDirectory(Path.GetDirectoryName(publicHealth)!);
            await File.WriteAllTextAsync(publicHealth,"{\"status\":\"public-health-control\"}");
            var service=new ArtifactReadbackService(node,options,queue,queue,queue,queue);
            foreach(var resource in new[]{f.First,f.Second})
            {
                var path=Path.Combine(resource.Project.RepoPath,"logs","ci","project-health","latest.json");
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                await File.WriteAllTextAsync(path,JsonSerializer.Serialize(new{status="private-health-"+resource.Project.ProjectId}));
            }
            var target=f.First;
            var entries=new Dictionary<string,(Func<Task<object?>> Call,Func<object?,bool> Matches)>
            {
                ["project-runs"]=(async()=>await service.GetProjectRunsAsync(target.Project.ProjectId),
                    value=>value is ProjectRunsReadback read && read.Project.ProjectId==target.Project.ProjectId),
                ["account-project-runs"]=(async()=>await service.GetProjectRunsForAccountAsync(f.First.AccountId,target.Project.ProjectId),
                    value=>value is ProjectRunsReadback read && read.Project.ProjectId==target.Project.ProjectId),
                ["run"]=(async()=>await service.GetRunAsync(target.RunId),
                    value=>value is RunSnapshot run && run.RunId==target.RunId),
                ["account-run"]=(async()=>await service.GetRunForAccountAsync(f.First.AccountId,target.RunId),
                    value=>value is RunSnapshot run && run.RunId==target.RunId),
                ["artifacts"]=(async()=>await service.ListArtifactsForRunAsync(target.RunId),
                    value=>value is IReadOnlyList<ArtifactSnapshot> artifacts && artifacts.Any(a=>a.ArtifactId==target.ArtifactId)),
                ["artifact"]=(async()=>await service.ReadArtifactAsync(target.ArtifactId),
                    value=>value is ArtifactReadResult read && read.Content==target.Sentinel),
                ["account-artifact"]=(async()=>await service.ReadArtifactForAccountAsync(f.First.AccountId,target.ArtifactId),
                    value=>value is ArtifactReadResult read && read.Content==target.Sentinel),
                ["health-summary"]=( () =>Task.FromResult<object?>(service.ReadProjectHealthSummary(target.Project.RepoPath)),
                    value=>value is ProjectHealthSummary health && health.Status=="private-health-"+target.Project.ProjectId)
            };
            using(S206TestSupport.EnterCurrentContext(f.First.Context))
                foreach(var (name,entry) in entries)
                    if(!entry.Matches(await entry.Call()))throw new InvalidOperationException("Actual artifact read positive unavailable: "+name);
            if(mode is "revoked" or "foreign-home" or "stale-projection" or "foreign-local")await f.FaultAsync(f.First,mode);
            if(mode=="foreign-project")target=f.Second;
            var context=mode=="foreign-account"?f.Second.Context:mode=="forged-context"?
                f.First.Context with{CredentialId=f.Second.Context.CredentialId}:f.First.Context;
            var beforeFirst=f.ContentHash(f.First);var beforeSecond=f.ContentHash(f.Second);
            foreach(var (name,entry) in entries)
            {
                var denied=false;var exposed=false;
                using var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context);
                try{var result=await entry.Call();exposed=entry.Matches(result);denied=result is null;}
                catch(UnauthorizedAccessException){denied=true;}
                var publicHealthCompatible=service.ReadProjectHealthSummary()?.Status=="public-health-control";
                rows.Add(new{mode,entry=name,denied,exposed,publicHealthCompatible,privateFilesUnchanged=
                    beforeFirst==f.ContentHash(f.First) && beforeSecond==f.ContentHash(f.Second)});
            }
        }
        return rows;
    }

    private static async Task<object> ObserveRouteReadControlsAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","no-context","foreign-account","forged-context","revoked","foreign-home",
            "stale-projection","foreign-project","swapped-path","legacy","stopped"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            foreach(var resource in new[]{f.First,f.Second,f.Admin})
                await f.Store.SetProjectBootstrapStatusAsync(resource.Project.ProjectId,"succeeded",null);
            await using var host=await LifetimeHost.StartAsync(f,CreateTinySource(f.Root));
            var expected="private-route-source-"+f.First.Project.ProjectId;
            foreach(var resource in new[]{f.First,f.Second})
            {
                var path=Path.Combine(resource.Project.RepoPath,"meta","routes","gdd-document","latest.json");
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                await File.WriteAllTextAsync(path,JsonSerializer.Serialize(new{schema_version="gdd-document-generation.v1",
                    status="succeeded",source_gdd_hash="private-route-source-"+resource.Project.ProjectId}));
                var gdd=Path.Combine(resource.Project.RepoPath,"docs","gdd","GDD.md");
                Directory.CreateDirectory(Path.GetDirectoryName(gdd)!);
                await File.WriteAllTextAsync(gdd,"# Private source "+resource.Project.ProjectId);
            }
            var service=host.Host.Services.GetRequiredService<ProjectRouteStateArtifactService>();
            var contract=host.Host.Services.GetRequiredService<PrototypeContractFreezeService>();
            string GddHash(S206AuthorityFixture.Resource resource) =>
                Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
                    System.Text.Encoding.UTF8.GetBytes("# Private source "+resource.Project.ProjectId))).ToLowerInvariant();
            var bindings=new Dictionary<string,ProjectRoutePromptEvidenceBinding>(StringComparer.Ordinal);
            var artifactIds=new HashSet<string>(StringComparer.Ordinal);
            var target=f.First.Project;
            var calls=new Dictionary<string,Func<ProjectRouteStateArtifactService,ProjectSnapshot,ProjectRouteStateArtifactReadback>>
            {
                ["default"]=(reader,project)=>reader.Read(project),
                ["bindings"]=(reader,project)=>reader.Read(project,bindings),
                ["full"]=(reader,project)=>reader.Read(project,bindings,artifactIds)
            };
            bool SawOwn(ProjectRouteStateArtifactReadback read)=>read.Artifacts.Single(x=>x.Route=="gdd-document-generation").SourceGddHash==expected;
            using(S206TestSupport.EnterCurrentContext(f.First.Context))
            {
                foreach(var call in calls.Values)
                    if(!SawOwn(call(service,target)))throw new InvalidOperationException("Actual registered route-source read positive control unavailable.");
                if(contract.EvaluateNewChainGuard(target).ContractStatus.SourceGddHash!=GddHash(f.First))
                    throw new InvalidOperationException("Actual contract-source hash positive control unavailable.");
            }
            if(mode is "revoked" or "foreign-home" or "stale-projection")await f.FaultAsync(f.First,mode);
            if(mode=="foreign-project")target=f.Second.Project;
            if(mode=="swapped-path")target=target with {RepoPath=f.Second.Project.RepoPath,MetaPath=f.Second.Project.MetaPath};
            if(mode=="legacy")service=new ProjectRouteStateArtifactService();
            if(mode=="stopped")await host.StopForObservationAsync();
            var context=mode=="foreign-account"?f.Second.Context:mode=="forged-context"?
                f.First.Context with {CredentialId=f.Second.Context.CredentialId}:f.First.Context;
            var beforeFirst=f.ContentHash(f.First);var beforeSecond=f.ContentHash(f.Second);
            foreach(var (entry,call) in calls)
            {
                var denied=false;var read=false;var foreignRead=false;
                using var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context);
                try
                {
                    var result=call(service,target);read=SawOwn(result);
                    foreignRead=result.Artifacts.Single(x=>x.Route=="gdd-document-generation").SourceGddHash=="private-route-source-"+f.Second.Project.ProjectId;
                }
                catch(UnauthorizedAccessException){denied=true;}
                rows.Add(new{mode,entry,denied,read,foreignRead,
                    privateFilesUnchanged=beforeFirst==f.ContentHash(f.First) && beforeSecond==f.ContentHash(f.Second)});
            }
            {
                var denied=false;var read=false;var foreignRead=false;
                using var current=mode=="no-context"?null:S206TestSupport.EnterCurrentContext(context);
                try
                {
                    var result=contract.EvaluateNewChainGuard(target);
                    read=result.ContractStatus.SourceGddHash==GddHash(f.First);
                    foreignRead=result.ContractStatus.SourceGddHash==GddHash(f.Second);
                }
                catch(UnauthorizedAccessException){denied=true;}
                rows.Add(new{mode,entry="contract-guard",denied,read,foreignRead,
                    privateFilesUnchanged=beforeFirst==f.ContentHash(f.First) && beforeSecond==f.ContentHash(f.Second)});
            }
        }
        return rows;
    }

    // ADR-0061 AD19: actual signed transport and direct issuer boundaries, not cryptography-only verdicts.
    private static async Task<object> ObserveTicketControlsAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","revoked","foreign-home","stale-projection","foreign-project"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            foreach(var resource in new[]{f.First,f.Second,f.Admin})
                await f.Store.SetProjectBootstrapStatusAsync(resource.Project.ProjectId,"succeeded",null);
            await using var host=await LifetimeHost.StartAsync(f,CreateTinySource(f.Root));
            using var authenticated=new HttpClient{BaseAddress=new Uri(host.Address)};
            authenticated.DefaultRequestHeaders.Authorization=new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer",f.SyntheticToken(f.First));
            using var anonymous=new HttpClient{BaseAddress=new Uri(host.Address)};
            var assetBytes=System.Text.Encoding.UTF8.GetBytes("owned preview bytes "+f.First.Project.ProjectId);
            var gddBytes=System.Text.Encoding.UTF8.GetBytes("owned GDD bytes "+f.First.Project.ProjectId);
            await File.WriteAllBytesAsync(Path.Combine(f.First.Project.RepoPath,"preview.png"),assetBytes);
            var gddFile=Path.Combine(f.First.Project.RepoPath,"docs","gdd","GDD.md");
            Directory.CreateDirectory(Path.GetDirectoryName(gddFile)!);await File.WriteAllBytesAsync(gddFile,gddBytes);
            var packageBytes=await File.ReadAllBytesAsync(Path.Combine(f.First.Project.RepoPath,"exports","fixture.zip"));
            var assets=host.Host.Services.GetRequiredService<ProjectAssetPreviewTicketService>();
            var packages=host.Host.Services.GetRequiredService<ProjectPackageDownloadTicketService>();
            using(S206TestSupport.EnterCurrentContext(f.First.Context))
            {
                if(!(await host.Host.Services.GetRequiredService<ProjectAssetInventoryService>().ReadPreviewAsync(
                    f.First.AccountId,f.First.Project.ProjectId,"res://preview.png"))!.Content.SequenceEqual(assetBytes) ||
                   !(await host.Host.Services.GetRequiredService<GameDesignDocumentService>().ReadAsync(
                    f.First.AccountId,f.First.Project.ProjectId))!.Content.SequenceEqual(gddBytes) ||
                   !(await host.Host.Services.GetRequiredService<ProjectPackageService>().ReadPackageAsync(
                    f.First.AccountId,f.First.Project.ProjectId,"fixture.zip"))!.Content.SequenceEqual(packageBytes))
                    throw new InvalidOperationException("Actual authenticated private read controls unavailable.");
            }
            var issued=new List<(string Kind,string Url,byte[] Expected)>();
            foreach(var kind in new[]{"asset","gdd","package"})
            {
                var route="/api/projects/"+f.First.Project.ProjectId+(kind=="asset"?"/asset-preview-ticket":
                    kind=="gdd"?"/gdd/download-ticket":"/packages/fixture.zip/download-ticket");
                using var body=kind=="asset"?System.Net.Http.Json.JsonContent.Create(new{resourcePath="res://preview.png"}):null;
                using var response=await authenticated.PostAsync(route,body);
                if(!response.IsSuccessStatusCode)throw new InvalidOperationException("Actual authenticated ticket issue control unavailable: "+kind+":"+(int)response.StatusCode);
                using var value=JsonDocument.Parse(await response.Content.ReadAsStringAsync());
                issued.Add((kind,value.RootElement.GetProperty(kind=="asset"?"previewUrl":"downloadUrl").GetString()!,
                    kind=="asset"?assetBytes:kind=="gdd"?gddBytes:packageBytes));
            }
            bool Rejected(Action action){try{action();return false;}catch(UnauthorizedAccessException){return true;}}
            var assetNoContext=Rejected(()=>assets.CreateTicket(f.First.AccountId,f.First.Project.ProjectId,"res://preview.png"));
            var packageNoContext=Rejected(()=>packages.CreateTicket(f.First.AccountId,f.First.Project.ProjectId,"fixture.zip"));
            bool assetForeign;bool packageForeign;bool assetForged;bool packageForged;
            using(S206TestSupport.EnterCurrentContext(f.First.Context))
            {
                assetForeign=Rejected(()=>assets.CreateTicket(f.Second.AccountId,f.Second.Project.ProjectId,"res://preview.png"));
                packageForeign=Rejected(()=>packages.CreateTicket(f.Second.AccountId,f.Second.Project.ProjectId,"fixture.zip"));
            }
            using(S206TestSupport.EnterCurrentContext(f.First.Context with {CredentialId=f.Second.Context.CredentialId}))
            {
                assetForged=Rejected(()=>assets.CreateTicket(f.First.AccountId,f.First.Project.ProjectId,"res://preview.png"));
                packageForged=Rejected(()=>packages.CreateTicket(f.First.AccountId,f.First.Project.ProjectId,"fixture.zip"));
            }
            var legacyAssets=new ProjectAssetPreviewTicketService((NodeTicketSigner)f.Options);
            var legacyAsset=legacyAssets.CreateTicket(f.First.AccountId,f.First.Project.ProjectId,"res://preview.png");
            var legacyAccepted=assets.IsValid(legacyAsset,f.First.AccountId,f.First.Project.ProjectId,"res://preview.png");
            var beforeFirst=f.ContentHash(f.First);var beforeSecond=f.ContentHash(f.Second);
            if(mode is "revoked" or "foreign-home" or "stale-projection")await f.FaultAsync(f.First,mode);
            foreach(var (kind,original,expected) in issued)
            {
                var url=mode=="foreign-project"?original.Replace(f.First.Project.ProjectId,f.Second.Project.ProjectId,StringComparison.Ordinal):original;
                using var result=await anonymous.GetAsync(url);var bytes=await result.Content.ReadAsByteArrayAsync();
                var signatureStart=url.LastIndexOf('.')+1;
                if(signatureStart<=0 || signatureStart>=url.Length)throw new InvalidOperationException("Actual ticket signature boundary unavailable.");
                var tampered=url[..signatureStart]+(url[signatureStart]=='A'?'B':'A')+url[(signatureStart+1)..];
                byte[] Signature(string value)
                {
                    var encoded=value[(value.LastIndexOf('.')+1)..].Replace('-','+').Replace('_','/');
                    return Convert.FromBase64String(encoded.PadRight(encoded.Length+(4-encoded.Length%4)%4,'='));
                }
                var corruptSignatureChanged=!Signature(url).SequenceEqual(Signature(tampered));
                if(!corruptSignatureChanged)throw new InvalidOperationException("Tamper fixture did not change actual signature bytes.");
                using var corrupt=await anonymous.GetAsync(tampered);
                rows.Add(new{mode,kind,status=(int)result.StatusCode,bytesMatch=bytes.SequenceEqual(expected),
                    corruptStatus=(int)corrupt.StatusCode,corruptSignatureChanged,assetNoContext,packageNoContext,assetForeign,packageForeign,
                    assetForged,packageForged,legacyAssetRejected=!legacyAccepted,
                    privateFilesUnchanged=beforeFirst==f.ContentHash(f.First) && beforeSecond==f.ContentHash(f.Second)});
            }
        }
        return rows;
    }

    private static async Task<object> ObserveShutdownControlsAsync()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        foreach(var resource in new[]{f.First,f.Second,f.Admin})
            await f.Store.SetProjectBootstrapStatusAsync(resource.Project.ProjectId,"succeeded",null);
        var repository=CreateTinySource(f.Root);
        await using var host=await LifetimeHost.StartAsync(f,repository);
        var node=host.Host.Services.GetRequiredService<NodeProjectMetadata>();
        var seeder=host.Host.Services.GetRequiredService<IProjectWorkspaceSeeder>();
        var lifetime=host.Host.Services.GetRequiredService<IHostApplicationLifetime>();
        var noticeReader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
            await publisher.PublishAsync(new NodeNoticePublication("s236-shutdown",1,"Inert shutdown control","account",f.First.AccountId,
                DateTimeOffset.UtcNow.AddMinutes(-1),DateTimeOffset.UtcNow.AddMinutes(5),true,1,"s236-shutdown-control"));
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
            if((await noticeReader.DetailAsync("s236-shutdown"))?.NoticeId!="s236-shutdown")
                throw new InvalidOperationException("Real notice positive control unavailable before stop");
        async Task<long> NoticeReads()
        {
            await using var connection=new Microsoft.Data.Sqlite.SqliteConnection(f.ConnectionString);await connection.OpenAsync();
            await using var command=connection.CreateCommand();
            command.CommandText="SELECT count(*) FROM notice_read_state WHERE account_id=$account AND notice_id='s236-shutdown';";
            command.Parameters.AddWithValue("$account",f.First.AccountId);
            return Convert.ToInt64(await command.ExecuteScalarAsync());
        }
        var beforeNoticeReads=await NoticeReads();

        var queues=new Dictionary<string,HeavyRunnerQueueService>
        {
            ["creation"]=host.Host.Services.GetRequiredService<ProjectCreationRunnerQueue>().Queue,
            ["ordinary"]=host.Host.Services.GetRequiredService<HeavyRunnerQueueService>(),
            ["prototype"]=host.Host.Services.GetRequiredKeyedService<HeavyRunnerQueueService>("prototype-creation"),
            ["asset"]=host.Host.Services.GetRequiredKeyedService<HeavyRunnerQueueService>("asset-generation"),
            ["preview"]=host.Host.Services.GetRequiredKeyedService<HeavyRunnerQueueService>("web-preview")
        };
        var states=new List<(string Kind,HeavyRunnerQueueService Queue,Task<int> Running,Task<int> Waiting,
            TaskCompletionSource Release,Func<bool> Cancelled,Func<bool> WaitingStarted,Func<bool> ProjectMatched)>();
        var beforeOwnership=await f.OwnershipAsync(f.First);
        var initialMarker=File.ReadAllText(Path.Combine(f.First.Project.RepoPath,"Directory.Build.props"));
        string positiveRun;
        using(var current=S206TestSupport.EnterCurrentContext(f.First.Context))
        {
            positiveRun=await node.CreateRunAsync(f.First.Project.ProjectId,f.First.Project.WorkspaceId,"s236-stop-control");
            foreach(var (kind,queue) in queues)
            {
                var entered=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
                var release=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
                CancellationToken observedToken=default;var waitingStarted=false;var projectMatched=false;
                var running=queue.ExecuteAsync("shutdown-"+kind+"-running",f.First.AccountId,f.First.Project.ProjectId,
                    "s236-stop-control",async ct=>
                    {
                        observedToken=ct;var actual=await node.GetRunSnapshotAsync(positiveRun,ct);
                        projectMatched=actual?.ProjectId==f.First.Project.ProjectId;
                        entered.TrySetResult();await release.Task.WaitAsync(ct);return 1;
                    });
                await entered.Task.WaitAsync(TimeSpan.FromSeconds(5));
                var waiting=queue.ExecuteAsync("shutdown-"+kind+"-waiting",f.First.AccountId,f.First.Project.ProjectId,
                    "s236-stop-control",ct=>{waitingStarted=true;return Task.FromResult(1);});
                var read=queue.GetReadback(f.First.AccountId,false);
                if(read.Items.Count!=1 || waitingStarted || !projectMatched)
                    throw new InvalidOperationException("Real owned running/waiting positive controls unavailable");
                states.Add((kind,queue,running,waiting,release,()=>observedToken.IsCancellationRequested,
                    ()=>waitingStarted,()=>projectMatched));
            }
        }
        var rows=new List<object>();var stopObserved=false;var writeDenied=false;var seedDenied=false;
        var controlDenied=false;var noticeReadDenied=false;var noticeChanged=false;
        var newDispatches=0;var newDispatchDenials=new List<string>();
        var beforeRuns=(await f.Store.ListRunsForProjectAsync(f.First.Project.ProjectId)).Count;
        try
        {
            await host.StopForObservationAsync();
            stopObserved=lifetime.ApplicationStopping.IsCancellationRequested && lifetime.ApplicationStopped.IsCancellationRequested;
            var cancelledAtStop=states.ToDictionary(s=>s.Kind,s=>s.Cancelled());
            foreach(var state in states)state.Release.TrySetResult();
            foreach(var state in states)
            {
                rows.Add(new {kind=state.Kind,projectMatched=state.ProjectMatched(),cancelledAtStop=cancelledAtStop[state.Kind],
                    running=await TaskOutcomeAsync(state.Running),waiting=await TaskOutcomeAsync(state.Waiting),
                    waitingStarted=state.WaitingStarted()});
            }
            using var current=S206TestSupport.EnterCurrentContext(f.First.Context);
            try{await node.CreateRunAsync(f.First.Project.ProjectId,f.First.Project.WorkspaceId,"s236-forbidden-after-stop");}
            catch(UnauthorizedAccessException){writeDenied=true;}
            try{noticeChanged=await noticeReader.MarkReadAsync("s236-shutdown",1);}
            catch(UnauthorizedAccessException){noticeReadDenied=true;}
            File.WriteAllText(Path.Combine(repository,"Directory.Build.props"),"s236-stop-source-update");
            try{seeder.EnsureSeeded(f.First.Project.RepoPath);}
            catch(UnauthorizedAccessException){seedDenied=true;}
            foreach(var (kind,queue) in queues)
            {
                try{await queue.ExecuteAsync("shutdown-"+kind+"-new",f.First.AccountId,f.First.Project.ProjectId,
                    "s236-forbidden-after-stop",ct=>Task.FromResult(++newDispatches));}
                catch(UnauthorizedAccessException){newDispatchDenials.Add(kind);}
                try{queue.GetReadback(f.First.AccountId,false);queue.CancelRun("shutdown-"+kind+"-running");}
                catch(UnauthorizedAccessException){controlDenied=true;}
            }
        }
        finally
        {
            foreach(var state in states)state.Release.TrySetResult();
            foreach(var state in states)
            {
                await TaskOutcomeAsync(state.Running);await TaskOutcomeAsync(state.Waiting);
            }
        }
        return new {stopObserved,positiveRun,rows,writeDenied,seedDenied,controlDenied,noticeReadDenied,noticeChanged,
            beforeNoticeReads,afterNoticeReads=await NoticeReads(),newDispatches,newDispatchDenials,
            beforeRuns,afterRuns=(await f.Store.ListRunsForProjectAsync(f.First.Project.ProjectId)).Count,
            initialMarker,finalMarker=File.ReadAllText(Path.Combine(f.First.Project.RepoPath,"Directory.Build.props")),
            ownershipUnchanged=beforeOwnership==await f.OwnershipAsync(f.First),nativeWindowsEvidence=false};
    }

    private static async Task<string> TaskOutcomeAsync(Task<int> task)
    {
        try{await task.WaitAsync(TimeSpan.FromSeconds(5));return "completed";}
        catch(OperationCanceledException){return "cancelled";}
        catch(UnauthorizedAccessException){return "denied";}
    }

    private sealed class LifetimeHost(S206AuthorityFixture fixture,IHost host,Task program,Dictionary<string,string?> previous,TextWriter oldOut,TextWriter oldError,StringWriter logOut,StringWriter logError,string address):IAsyncDisposable
    {
        private bool _disposed;
        private bool _stopped;
        internal async Task StopForObservationAsync()
        { await host.StopAsync();await program.WaitAsync(TimeSpan.FromSeconds(20));_stopped=true; }
        internal IHost Host=>host;
        internal string Address=>address;
        internal string CapturedLogs=>logOut.ToString()+logError.ToString();
        internal static async Task<LifetimeHost> StartAsync(S206AuthorityFixture f,string repositoryRoot,string roles="entry,production")
        {
            using var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();var port=((IPEndPoint)listener.LocalEndpoint).Port;listener.Stop();
            var address="http://127.0.0.1:"+port;
            var settings=new Dictionary<string,string?>
            {
                ["APP_BIND_URL"]=address,["ASPNETCORE_URLS"]=address,["PUBLIC_BASE_URL"]="https://localhost",
                ["PHASEA_METADATA_DB_PATH"]=f.Options.MetadataDatabasePath,["HOSTED_WORKSPACE_ROOT"]=f.Options.HostedWorkspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"]=repositoryRoot,["PHASEA_ADMIN_TOKEN_HASH"]=PhaseAAuth.HashTokenForStorage(f.SyntheticToken(f.Admin)),
                ["PHASEA_SERVICE_STATE"]="test",["PHASEA_NODE_ID"]="test-physical-node",["PHASEA_NODE_SCOPE"]="single_node_test",
                ["PHASEA_NODE_TOPOLOGY"]="single_service",["PHASEA_ENABLED_ROLES"]=roles,["PHASEA_ACCEPT_NEW_ACCOUNTS"]="true",
                ["PHASEA_LOGIN_ENDPOINT"]="https://login.example.invalid",["PHASEA_WORKBENCH_ENDPOINT"]="https://workbench.example.invalid",
                ["PHASEA_ACTIVE_CONTENT_ORIGIN"]="https://content.example.invalid",
                ["PHASEA_TICKET_SIGNING_SECRET"]=f.Options.TicketSigningSecret,
                ["PHASEA_HOSTED_CONTEXT_SIGNING_KEY"]="synthetic-notice-host-"+Guid.NewGuid().ToString("N")
            };
            settings["Logging__LogLevel__Default"]="Information";
            var previous=settings.Keys.ToDictionary(k=>k,Environment.GetEnvironmentVariable);
            var oldOut=Console.Out;var oldError=Console.Error;var logOut=new StringWriter();var logError=new StringWriter();
            Console.SetOut(TextWriter.Synchronized(logOut));Console.SetError(TextWriter.Synchronized(logError));
            foreach(var r in settings)Environment.SetEnvironmentVariable(r.Key,r.Value);
            var source=new TaskCompletionSource<IHost>(TaskCreationOptions.RunContinuationsAsynchronously);
            using var subscription=DiagnosticListener.AllListeners.Subscribe(new Observer<DiagnosticListener>(listener=>
            {
                if(listener.Name=="Microsoft.Extensions.Hosting")listener.Subscribe(new Observer<KeyValuePair<string,object?>>(e=>
                {
                    // ADR-0061: a global diagnostic event must identify this exact owned host.
                    if(e.Key=="HostBuilt" && e.Value is IHost h &&
                        h.Services.GetService<PhaseAPlatformOptions>() is { } actual &&
                        string.Equals(actual.MetadataDatabasePath,f.Options.MetadataDatabasePath,StringComparison.Ordinal) &&
                        string.Equals(actual.AppBindUrl,address,StringComparison.Ordinal))
                        source.TrySetResult(h);
                }));
            }));
            Task program=Task.Run(async()=>
            {
                var entry=typeof(PhaseAMetadataStore).Assembly.EntryPoint!;
                if(entry.Invoke(null,new object[]{new[]{"--contentRoot",Path.Combine(S206TestSupport.RepositoryRoot,"PhaseA.Platform")}}) is Task t)await t;
            });
            IHost? host=null;
            try
            {
                var winner=await Task.WhenAny(source.Task,program,Task.Delay(TimeSpan.FromSeconds(20)));
                if(winner!=source.Task){if(program.IsCompleted)await program;throw new InvalidOperationException("Actual Program host unavailable.");}
                host=await source.Task;
                using var http=new HttpClient{BaseAddress=new Uri(address)};
                var healthy=false;
                for(var i=0;i<50;i++)
                {
                    try{healthy=(await http.GetAsync("/healthz")).IsSuccessStatusCode;}catch(HttpRequestException){}
                    if(healthy)break;await Task.Delay(100);
                }
                if(!healthy)throw new InvalidOperationException("Actual Program did not become healthy.");
                return new LifetimeHost(f,host,program,previous,oldOut,oldError,logOut,logError,address);
            }
            catch
            {
                if(host is not null)await host.StopAsync();
                foreach(var r in previous)Environment.SetEnvironmentVariable(r.Key,r.Value);
                Console.SetOut(oldOut);Console.SetError(oldError);
                throw;
            }
        }
        public async ValueTask DisposeAsync()
        {
            if(_disposed)return;_disposed=true;
            try{if(!_stopped)await StopForObservationAsync();}
            finally
            {
                host.Dispose();foreach(var r in previous)Environment.SetEnvironmentVariable(r.Key,r.Value);
                Console.SetOut(oldOut);Console.SetError(oldError);
            }
        }
    }

    private sealed class Observer<T>(Action<T> next):IObserver<T>
    {
        public void OnNext(T value)=>next(value);
        public void OnError(Exception error){}
        public void OnCompleted(){}
    }
}
