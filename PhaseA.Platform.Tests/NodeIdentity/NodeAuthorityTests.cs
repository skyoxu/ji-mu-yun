using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Sockets;
using System.Reflection;
using System.Text.Json;
using System.Text;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Runs;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061 AD14: inspect actual Program objects, not an alternate test DI graph.
public sealed class NodeAuthorityTests(ITestOutputHelper output)
{
    [Fact]
    public async Task O_2F129B75AF64()
    {
        var root=S206TestSupport.RepositoryRoot;
        using var scope=JsonDocument.Parse(File.ReadAllText(Path.Combine(root,"logs/s2-06-resume-20261031/source-scope-root-path-r5.v1.json")));
        var allowed=scope.RootElement.GetProperty("write_paths").EnumerateArray().Select(x=>x.GetString()!)
            .Concat(scope.RootElement.GetProperty("support_paths").EnumerateArray().Select(x=>x.GetString()!)).ToHashSet(StringComparer.Ordinal);
        var changed=GitScopeText(root,"diff","--name-only","25580d700da91d2702fd234a024a616d55419f90","--","PhaseA.Platform")
            .Split('\n',StringSplitOptions.RemoveEmptyEntries)
            .Concat(GitScopeText(root,"ls-files","--others","--exclude-standard","--","PhaseA.Platform")
                .Split('\n',StringSplitOptions.RemoveEmptyEntries)).Distinct().ToArray();
        var realChanges=new List<string>();var outside=new List<string>();
        foreach(var path in changed)
        {
            var present=Path.Combine(root,path);
            if(File.Exists(present))
            {
                if(new FileInfo(present).LinkTarget is not null){outside.Add("symbolic-link:"+path);continue;}
                var indexed=GitScopeText(root,new[]{"ls-files","--error-unmatch","--",path},allowFailure:true).Length>0;
                if(indexed)
                {
                    var baseline=GitScopeText(root,new[]{"show","25580d700da91d2702fd234a024a616d55419f90:"+path},allowFailure:true);
                    if(baseline.Length>0 && baseline.Replace("\r\n","\n")==File.ReadAllText(present).Replace("\r\n","\n"))continue;
                }
            }
            realChanges.Add(path);if(!allowed.Contains(path))outside.Add(path);
        }
        var forbiddenTypes=new[]{typeof(PhaseAMetadataStore),typeof(PhaseAPlatformOptions),typeof(IServiceProvider),typeof(SqliteConnection),typeof(Delegate)};
        bool Escapes(Type type) => forbiddenTypes.Any(t=>t.IsAssignableFrom(type)) ||
            (type.IsGenericType && type.GetGenericArguments().Any(Escapes));
        var escapes=new List<string>();
        foreach(var type in new[]{typeof(NodeNoticeReader),typeof(CentralNoticePublisher)})
        {
            if(!type.IsSealed || type.GetConstructors().Length>0)escapes.Add(type.Name+":public-construction-or-inheritance");
            foreach(var m in type.GetMethods(BindingFlags.Public|BindingFlags.Instance|BindingFlags.Static|BindingFlags.DeclaredOnly))
                if(Escapes(m.ReturnType) || m.GetParameters().Any(p=>Escapes(p.ParameterType)))
                    escapes.Add(type.Name+"."+m.Name);
        }
        var atomic=await NodeNoticeTests.ObserveAtomicAsync();
        output.WriteLine("S206_NOTICE_REFINEMENT:"+JsonSerializer.Serialize(new{realChanges,outside,escapes,atomic,
            acceptedOwner="docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md",
            runtimeWindows=OperatingSystem.IsWindows(),nativeWindowsEvidence=false}));
    }

    private static string GitScopeText(string root,params string[] arguments)=>GitScopeText(root,arguments,allowFailure:false);
    private static string GitScopeText(string root,string[] arguments,bool allowFailure)
    {
        var start=new ProcessStartInfo("git"){WorkingDirectory=root,UseShellExecute=false,RedirectStandardOutput=true,
            RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};
        foreach(var argument in arguments)start.ArgumentList.Add(argument);
        using var child=Process.Start(start)??throw new InvalidOperationException("Scoped Git observation did not start.");
        var text=child.StandardOutput.ReadToEnd();var error=child.StandardError.ReadToEnd();
        if(!child.WaitForExit(5000)){child.Kill(entireProcessTree:true);throw new TimeoutException("Scoped Git observation timed out.");}
        if(child.ExitCode!=0 && !allowFailure)throw new InvalidOperationException("Scoped Git observation failed: "+error);
        return child.ExitCode==0?text:string.Empty;
    }

    // ADR-0061 AD19: actual backend monitor, current central fault and real persisted snapshot.
    // First causal protected-write counterexamples; not all writer-family closure.
    [Fact]
    public async Task O_BC733E999001()
    {
        var rows=new List<object>();
        foreach(var attack in new[]{"valid","revoked","foreign-project","foreign-local","stale-projection"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var root=f.First.Project.RepoPath;
            var positive="positive-"+Guid.NewGuid().ToString("N");
            f.Storage.CreateSnapshot(f.First.Context,root,positive,f.First.Project.WorkspaceId,
                f.First.Project.ProjectId,"s236-positive",new HashSet<string>());
            var positiveObserved=File.Exists(Path.Combine(root,".snapshots-"+positive+".json"));
            var backend=typeof(WorkspaceStorageService).GetField("_backend",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(f.Storage)!;
            var gate=backend.GetType().GetField("_gate",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(backend)!;
            var id="post-permit-"+Guid.NewGuid().ToString("N");
            using var entered=new ManualResetEventSlim();
            var before=f.ContentHash(f.First);Task<(bool published,bool denied)> work;
            var wasBlocked=false;
            Monitor.Enter(gate);
            try
            {
                work=Task.Run(()=>
                {
                    try
                    {
                        f.Storage.CreateSnapshot(f.First.Context,root,id,f.First.Project.WorkspaceId,
                            f.First.Project.ProjectId,"s236-after-permit",new AdmissionObservedSet(entered));
                        return(published:true,denied:false);
                    }
                    catch(UnauthorizedAccessException){return(published:false,denied:true);}
                });
                // Enumeration is inside the real backend, after the outer current check.
                if(!entered.Wait(TimeSpan.FromSeconds(8)))throw new TimeoutException("Snapshot did not reach real backend before its mutating lock.");
                wasBlocked=!work.IsCompleted;
                if(attack!="valid")f.FaultAsync(f.First,attack).GetAwaiter().GetResult();
            }
            finally {Monitor.Exit(gate);}
            var result=await work.WaitAsync(TimeSpan.FromSeconds(10));
            long stored;
            await using(var connection=new SqliteConnection(f.ConnectionString))
            {
                await connection.OpenAsync();await using var command=connection.CreateCommand();
                command.CommandText="SELECT count(*) FROM workspace_snapshots WHERE snapshot_id=$id;";
                command.Parameters.AddWithValue("$id",id);stored=Convert.ToInt64(await command.ExecuteScalarAsync());
            }
            rows.Add(new{attack,positiveObserved,admissionObserved=entered.IsSet,wasBlocked,result.published,result.denied,
                manifestExists=File.Exists(Path.Combine(root,".snapshots-"+id+".json")),
                payloadExists=File.Exists(Path.Combine(root,".snapshots-"+id+".protected")),stored,
                projectBytesUnchanged=before==f.ContentHash(f.First)});
        }
        var bindings=new List<object>();
        foreach(var attack in new[]{"valid","foreign-root","wrong-workspace","generation-after-admission"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var id="binding-"+Guid.NewGuid().ToString("N");
            var root=attack=="foreign-root"?f.Second.Project.RepoPath:f.First.Project.RepoPath;
            var workspace=attack=="wrong-workspace"?f.Second.Project.WorkspaceId:f.First.Project.WorkspaceId;
            // An actual normal snapshot proves this fixture's current write path first.
            var control="binding-control-"+Guid.NewGuid().ToString("N");
            f.Storage.CreateSnapshot(f.First.Context,f.First.Project.RepoPath,control,
                f.First.Project.WorkspaceId,f.First.Project.ProjectId,"s236-control",new HashSet<string>());
            var positiveObserved=File.Exists(Path.Combine(f.First.Project.RepoPath,".snapshots-"+control+".json"));
            var backend=typeof(WorkspaceStorageService).GetField("_backend",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(f.Storage)!;
            var gate=backend.GetType().GetField("_gate",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(backend)!;
            using var entered=new ManualResetEventSlim();
            var generationChanged=false;var denied=false;WorkspaceSnapshotRecord? record=null;
            Task<WorkspaceSnapshotRecord?>? waiting=null;
            if(attack=="generation-after-admission")
            {
                Monitor.Enter(gate);
                try
                {
                    waiting=Task.Run(()=>
                    {
                        try {return f.Storage.CreateSnapshot(f.First.Context,root,id,workspace,
                            f.First.Project.ProjectId,"s236-generation",new AdmissionObservedSet(entered));}
                        catch(UnauthorizedAccessException){return null;}
                    });
                    if(!entered.Wait(TimeSpan.FromSeconds(8)))throw new TimeoutException("Real snapshot admission not reached.");
                    var generationRoot=Path.Combine(WorkspaceGenerationPaths.StorageRoot(f.First.Project),".s236-generation",id);
                    foreach(var child in new[]{"repo","runtime","meta"})Directory.CreateDirectory(Path.Combine(generationRoot,child));
                    File.WriteAllText(Path.Combine(generationRoot,"repo","private.txt"),"current-generation");
                    using var current=S206TestSupport.EnterCurrentContext(f.First.Context);
                    NodeProjectMetadata node=f.Store;
                    if(!node.TryAcquireRunnerLockAsync(f.First.Project.ProjectId,f.First.RunId).GetAwaiter().GetResult())
                        throw new InvalidOperationException("Actual generation positive lock unavailable.");
                    node.MarkRunStartedAsync(f.First.RunId,1).GetAwaiter().GetResult();
                    node.ActivateWorkspaceGenerationAsync(f.First.Project,f.First.RunId,f.First.SnapshotId,
                        id,generationRoot,f.First.Context.CredentialId).GetAwaiter().GetResult();
                    var currentProject=node.GetProjectSnapshotAsync(f.First.Project.ProjectId).GetAwaiter().GetResult();
                    generationChanged=currentProject?.RepoPath==Path.Combine(generationRoot,"repo");
                }
                finally {Monitor.Exit(gate);}
                record=await waiting!.WaitAsync(TimeSpan.FromSeconds(10));denied=record is null;
            }
            else
            {
                try {record=f.Storage.CreateSnapshot(f.First.Context,root,id,workspace,
                    f.First.Project.ProjectId,"s236-path-binding",new HashSet<string>());}
                catch(UnauthorizedAccessException){denied=true;}
            }
            var leakedOtherAccount=record is not null && record.Manifest.ReadProtectedContent().TryGetValue("private.txt",out var content)
                && Encoding.UTF8.GetString(content)==f.Second.Sentinel;
            bindings.Add(new{attack,positiveObserved,denied,published=record is not null,
                manifestExists=File.Exists(Path.Combine(root,".snapshots-"+id+".json")),
                payloadExists=File.Exists(Path.Combine(root,".snapshots-"+id+".protected")),
                generationChanged,leakedOtherAccount});
        }
        var restoreControls=await ObserveRestoreEntryControlsAsync();
        var deletionControls=await ObserveSnapshotDeletionControlsAsync();
        var contractWaitControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveContractFreezeAfterMutationWaitAsync();
        var goalPublishControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveGoalPublicationAfterProcessAsync();
        var postprocessControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObservePostprocessConsumersAsync();
        var requirementMapControls=await PhaseA.Platform.Tests.Runs.GddToModuleBackendContractServiceTests.ObserveModelReplyBoundaryAsync("requirements");
        output.WriteLine("S206_WRITE_COUNTEREXAMPLES:"+JsonSerializer.Serialize(new{rows,bindings,restoreControls,deletionControls,contractWaitControls,goalPublishControls,postprocessControls,requirementMapControls,
            source="actual WorkspaceStorageService and its actual backend monitor; central protected fixture faults",
            coverageScope="snapshot mutating-lock counterexamples; complete protected-write matrix still required",
            nativeWindowsEvidence=false}));
    }

    // ADR-0061 AD19/21: real lease lookup and protected restore-intent persistence.
    // The retained route-authority refusal is the positive boundary, not Windows restore success.
    private static async Task<List<object>> ObserveRestoreEntryControlsAsync()
    {
        var rows=new List<object>();
        foreach(var overload in new[]{"default-key","explicit-key"})
        foreach(var mode in new[]{"valid","detached-explicit","foreign-account","forged-admin","foreign-home",
            "foreign-project","foreign-local","stale-projection","revoked"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var restore=f.Store.CreateRestoreService();
            WorkspaceSnapshotRecord record;RunnerLease? lease;
            using(var current=S206TestSupport.EnterCurrentContext(f.First.Context))
            {
                NodeProjectMetadata node=f.Store;
                if(!await node.TryAcquireRunnerLockAsync(f.First.Project.ProjectId,f.First.RunId))
                    throw new InvalidOperationException("Actual runner lock/lease control unavailable.");
                lease=restore.GetAuthoritativeLease(f.First.AccountId,f.First.Project.ProjectId);
                record=f.Storage.ListSnapshots(f.First.AccountId,f.First.Project.ProjectId)
                    .Single(s=>s.Manifest.SnapshotId==f.First.SnapshotId);
            }
            if(lease is null || lease.LeaseId!=f.First.RunId || lease.Fence<=0)
                throw new InvalidOperationException("Real metadata-produced lease not observed.");
            var context=mode=="foreign-account"?f.Second.Context:mode=="forged-admin"?
                f.First.Context with {Roles=new HashSet<string>{PhaseAAuth.AdminRole}}:f.First.Context;
            if(mode is "foreign-home" or "foreign-project" or "foreign-local" or "stale-projection" or "revoked")
                await f.FaultAsync(f.First,mode);
            var key=overload=="default-key"?$"restore:{record.Manifest.SnapshotId}:{record.Manifest.WorkspaceId}":
                "restore-entry-"+Guid.NewGuid().ToString("N");
            var hash=f.ContentHash(f.First);var leaseDenied=false;var leaseVisible=false;var restoreDenied=false;
            RestoreAttempt? attempt=null;
            using(var current=mode=="detached-explicit"?null:S206TestSupport.EnterCurrentContext(context))
            {
                try {leaseVisible=restore.GetAuthoritativeLease(f.First.AccountId,f.First.Project.ProjectId)?.LeaseId==lease.LeaseId;}
                catch(UnauthorizedAccessException){leaseDenied=true;}
                try
                {
                    attempt=overload=="default-key"?
                        restore.Restore(context,record.Manifest,f.First.Project.RepoPath,f.First.Project.WorkspaceRootPath,lease):
                        restore.Restore(context,record.Manifest,f.First.Project.RepoPath,f.First.Project.WorkspaceRootPath,lease,key);
                }
                catch(UnauthorizedAccessException){restoreDenied=true;}
            }
            using var connection=new SqliteConnection(f.ConnectionString);connection.Open();
            using var command=connection.CreateCommand();
            command.CommandText="SELECT count(*),MAX(failure_category) FROM restore_attempts WHERE idempotency_key=$key;";
            command.Parameters.AddWithValue("$key",key);using var reader=command.ExecuteReader();reader.Read();
            var stored=reader.GetInt64(0);var persistedFailureCategory=reader.IsDBNull(1)?null:reader.GetString(1);
            rows.Add(new{overload,mode,positiveLeaseObserved=true,leaseDenied,leaseVisible,restoreDenied,stored,
                routeRefusalRetained=attempt?.Status==RestoreAttemptStatus.Quarantined && persistedFailureCategory=="route_authority_missing",
                persistedFailureCategory,
                published=attempt?.Status==RestoreAttemptStatus.Published,privateBytesUnchanged=hash==f.ContentHash(f.First)});
        }
        return rows;
    }

    // Observe the real DemandAccount call inside the actual mutation monitor.
    // The roles wrapper delegates every answer to the genuinely authenticated set;
    // it neither replaces the current verifier nor supplies authorization answers.
    private static async Task<List<object>> ObserveSnapshotDeletionControlsAsync()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid","valid-historical","role-closed","revoked","foreign-project","foreign-local","stale-projection"})
        {
            await using var f=await S206AuthorityFixture.CreateAsync();
            var id="delete-boundary-"+Guid.NewGuid().ToString("N");
            f.Storage.CreateSnapshot(f.First.Context,f.First.Project.RepoPath,id,f.First.Project.WorkspaceId,
                f.First.Project.ProjectId,"s236-delete",new HashSet<string>());
            var roles=new HashSet<string>{"entry","production"};
            var store=new PhaseAMetadataStore(f.ConnectionString,f.Options with {EnabledRoles=roles});
            var storage=store.CreateWorkspaceStorageService();
            var generationChanged=false;
            if(mode=="valid-historical")
            {
                var generationRoot=Path.Combine(WorkspaceGenerationPaths.StorageRoot(f.First.Project),".s236-delete-history",id);
                foreach(var child in new[]{"repo","runtime","meta"})Directory.CreateDirectory(Path.Combine(generationRoot,child));
                File.WriteAllText(Path.Combine(generationRoot,"repo","private.txt"),"new-current-generation");
                using var current=S206TestSupport.EnterCurrentContext(f.First.Context);
                NodeProjectMetadata node=store;
                if(!await node.TryAcquireRunnerLockAsync(f.First.Project.ProjectId,f.First.RunId))
                    throw new InvalidOperationException("Historical-snapshot generation control unavailable.");
                await node.MarkRunStartedAsync(f.First.RunId,1);
                await node.ActivateWorkspaceGenerationAsync(f.First.Project,f.First.RunId,f.First.SnapshotId,
                    id,generationRoot,f.First.Context.CredentialId);
                generationChanged=(await node.GetProjectSnapshotAsync(f.First.Project.ProjectId))?.RepoPath==Path.Combine(generationRoot,"repo");
            }
            var backend=typeof(WorkspaceStorageService).GetField("_backend",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(storage)!;
            var gate=backend.GetType().GetField("_gate",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(backend)!;
            using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();
            var insideMutationLock=false;
            var context=f.First.Context with {Roles=new ObservedAccountDemandRoles(f.First.Context.Roles,()=>
            {
                insideMutationLock=Monitor.IsEntered(gate);entered.Set();
                if(!release.Wait(TimeSpan.FromSeconds(8)))throw new TimeoutException("Current-authority fault was not released.");
            })};
            var before=ReadSnapshotState(f.ConnectionString,id);var hash=f.ContentHash(f.First);
            var operation=Task.Run(()=>
            {
                try {storage.SoftDeleteSnapshot(context,id);return false;}
                catch(UnauthorizedAccessException){return true;}
            });
            try
            {
                if(!entered.Wait(TimeSpan.FromSeconds(8)))throw new TimeoutException("Real snapshot deletion did not reach its mutation monitor.");
                if(mode=="role-closed")roles.Remove("production");
                else if(mode is "revoked" or "foreign-project" or "foreign-local" or "stale-projection")
                    await f.FaultAsync(f.First,mode);
            }
            finally {release.Set();}
            var denied=await operation.WaitAsync(TimeSpan.FromSeconds(10));
            rows.Add(new{mode,denied,insideMutationLock,admissionObserved=entered.IsSet,generationChanged,
                before,after=ReadSnapshotState(f.ConnectionString,id),privateBytesUnchanged=hash==f.ContentHash(f.First)});
        }
        return rows;
    }

    private static long[] ReadSnapshotState(string connectionString,string id)
    {
        using var connection=new SqliteConnection(connectionString);connection.Open();using var command=connection.CreateCommand();
        command.CommandText="""
            SELECT s.deleted,q.used_bytes,
              (SELECT count(*) FROM snapshot_retention_audit a WHERE a.snapshot_id=s.snapshot_id),s.size_bytes
            FROM workspace_snapshots s JOIN workspace_quotas q ON q.account_id=s.account_id WHERE s.snapshot_id=$id;
            """;
        command.Parameters.AddWithValue("$id",id);using var reader=command.ExecuteReader();
        if(!reader.Read())throw new InvalidOperationException("Actual snapshot/quota control missing.");
        return Enumerable.Range(0,4).Select(reader.GetInt64).ToArray();
    }

    private sealed class ObservedAccountDemandRoles(IReadOnlySet<string> actual,Action observe):IReadOnlySet<string>
    {
        private int _observed;
        public int Count=>actual.Count;
        public bool Contains(string item)
        {if(item==PhaseAAuth.AdminRole && Interlocked.CompareExchange(ref _observed,1,0)==0)observe();return actual.Contains(item);}
        public bool SetEquals(IEnumerable<string> other)=>actual.SetEquals(other);
        public bool IsSubsetOf(IEnumerable<string> other)=>actual.IsSubsetOf(other);
        public bool IsSupersetOf(IEnumerable<string> other)=>actual.IsSupersetOf(other);
        public bool IsProperSubsetOf(IEnumerable<string> other)=>actual.IsProperSubsetOf(other);
        public bool IsProperSupersetOf(IEnumerable<string> other)=>actual.IsProperSupersetOf(other);
        public bool Overlaps(IEnumerable<string> other)=>actual.Overlaps(other);
        public IEnumerator<string> GetEnumerator()=>actual.GetEnumerator();
        System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator()=>GetEnumerator();
    }

    private sealed class AdmissionObservedSet(ManualResetEventSlim entered):HashSet<string>,IEnumerable<string>
    {
        IEnumerator<string> IEnumerable<string>.GetEnumerator(){entered.Set();return base.GetEnumerator();}
    }

    [Fact]
    public async Task O_840CB12CA43E()
    {
        // ADR-0061 AD17: the positive request authenticates through the actual
        // Program/PhaseAAuth middleware, never a fixture-installed HTTP identity.
        await using var f=await S206AuthorityFixture.CreateAsync(startHost:true);
        NodeProjectMetadata node=f.Store;
        var hash=f.ContentHash(f.First);
        using var original=f.Client(f.First);
        using var session=await original.GetAsync("/api/session?accountId="+f.Second.AccountId+"&role=admin&nodeId=foreign");
        using var sessionBody=JsonDocument.Parse(await session.Content.ReadAsStringAsync());
        using var projects=await original.GetAsync("/api/projects?accountId="+f.Second.AccountId);
        using var projectsBody=JsonDocument.Parse(await projects.Content.ReadAsStringAsync());
        var projectIds=projectsBody.RootElement.ValueKind==JsonValueKind.Array
            ? projectsBody.RootElement.EnumerateArray().Select(p=>p.GetProperty("projectId").GetString()).ToArray():[];

        async Task<bool> DirectRead(RequestContext context)
        {
            using var scope=S206TestSupport.EnterCurrentContext(context);
            try {return await node.GetProjectSnapshotAsync(f.First.Project.ProjectId) is not null;}
            catch(UnauthorizedAccessException){return false;}
        }
        var forgedDenied=!await DirectRead(f.First.Context with {CredentialId=f.Second.Context.CredentialId});
        var roleForgeryDenied=!await DirectRead(f.First.Context with {Roles=new HashSet<string>{PhaseAAuth.AdminRole}});
        var unknownDenied=!await DirectRead(f.First.Context with {CredentialId=Guid.NewGuid().ToString("N")});
        var rotated=await f.Store.RotateUserTokenAsync(f.First.AccountId)
            ?? throw new InvalidOperationException("Real central rotation control unavailable.");
        using var oldRequest=await original.GetAsync("/api/projects");
        var oldDirectDenied=!await DirectRead(f.First.Context);
        var oldCentralRejected=await f.Store.ResolveAccountByTokenHashAsync(f.First.Context.CredentialId) is null;
        var currentHash=PhaseAAuth.HashTokenForStorage(rotated.Token);
        var current=await f.Store.ResolveAccountByTokenHashAsync(currentHash);
        using var fresh=f.Host!.Client(rotated.Token);
        using var freshRequest=await fresh.GetAsync("/api/projects");
        var currentContext=RequestContext.FromIdentity(new AccountIdentity(f.First.AccountId,"current-a",PhaseAAuth.UserRole),
            f.First.AccountId,currentHash,"current-verifier-test");
        var currentDirect=await DirectRead(currentContext);
        await f.FaultAsync(f.First,"stale-projection");
        using var staleRequest=await fresh.GetAsync("/api/projects");
        var staleDirectDenied=!await DirectRead(currentContext);
        // Real central state transactions refresh the actual projection; no
        // test-owned verifier or local credential authority grants this control.
        await f.Store.SetUserDisabledAsync(f.First.AccountId,true);
        await f.Store.SetUserDisabledAsync(f.First.AccountId,false);
        using var restored=await fresh.GetAsync("/api/projects");
        await f.Store.SetUserDisabledAsync(f.First.AccountId,true);
        using var revoked=await fresh.GetAsync("/api/projects");
        var revokedDirectDenied=!await DirectRead(currentContext);
        var revokedCentralRejected=await f.Store.ResolveAccountByTokenHashAsync(currentHash) is null;
        var columns=new List<string>();
        await using(var connection=new SqliteConnection(f.ConnectionString))
        {
            await connection.OpenAsync();await using var command=connection.CreateCommand();
            command.CommandText="PRAGMA table_info(account_node_projections);";
            await using var reader=await command.ExecuteReaderAsync();
            while(await reader.ReadAsync())columns.Add(reader.GetString(1));
        }
        output.WriteLine("S206_EXISTING_VERIFIER:"+JsonSerializer.Serialize(new {
            sessionStatus=(int)session.StatusCode,session=sessionBody.RootElement.Clone(),projectStatus=(int)projects.StatusCode,
            projectIds,expectedAccount=f.First.AccountId,expectedProject=f.First.Project.ProjectId,otherProject=f.Second.Project.ProjectId,
            forgedDenied,roleForgeryDenied,unknownDenied,oldStatus=(int)oldRequest.StatusCode,oldDirectDenied,oldCentralRejected,
            freshStatus=(int)freshRequest.StatusCode,currentCentralAccount=current?.AccountId,currentDirect,
            staleStatus=(int)staleRequest.StatusCode,staleDirectDenied,restoredStatus=(int)restored.StatusCode,
            revokedStatus=(int)revoked.StatusCode,revokedDirectDenied,revokedCentralRejected,columns,
            contentUnchanged=hash==f.ContentHash(f.First),nativeWindowsEvidence=false
        }));
    }

    [Fact]
    public async Task RestrictedObjectsReplacePrivilegedEscapes()
    {
        var root = Path.Combine(Path.GetTempPath(), "s206-capability-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var database = Path.Combine(root, "metadata.sqlite3");
        var offline = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string,string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root,"workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = database
        });
        await SqliteMetadataSchema.InitializeAsync("Data Source=" + database);
        var central = new PhaseAMetadataStore("Data Source=" + database,offline);
        var first = await central.CreateUserAccountAsync("capability-a",2);
        var second = await central.CreateUserAccountAsync("capability-b",2);
        var adminToken = Guid.NewGuid().ToString("N");
        var syntheticSecret = "s206-synthetic-secret-" + Guid.NewGuid().ToString("N");
        using var listener = new TcpListener(IPAddress.Loopback,0);
        listener.Start(); var port = ((IPEndPoint)listener.LocalEndpoint).Port; listener.Stop();
        var address = "http://127.0.0.1:" + port;
        var variables = new Dictionary<string,string?>
        {
            ["APP_BIND_URL"] = address, ["ASPNETCORE_URLS"] = address,
            ["PUBLIC_BASE_URL"] = "https://localhost",
            ["PHASEA_METADATA_DB_PATH"] = database,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root,"workspaces"),
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["PHASEA_ADMIN_TOKEN_HASH"] = PhaseAAuth.HashTokenForStorage(adminToken),
            ["PHASEA_SERVICE_STATE"] = "test", ["PHASEA_NODE_ID"] = "test-physical-node",
            ["PHASEA_NODE_SCOPE"] = "single_node_test", ["PHASEA_NODE_TOPOLOGY"] = "single_service",
            ["PHASEA_ENABLED_ROLES"] = "entry,production", ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = "true",
            ["PHASEA_LOGIN_ENDPOINT"] = "https://login.example.invalid",
            ["PHASEA_WORKBENCH_ENDPOINT"] = "https://workbench.example.invalid",
            ["PHASEA_ACTIVE_CONTENT_ORIGIN"] = "https://content.example.invalid",
            ["PHASEA_HOSTED_CONTEXT_SIGNING_KEY"] = syntheticSecret
        };
        var originals = variables.Keys.ToDictionary(key=>key,Environment.GetEnvironmentVariable);
        foreach (var row in variables) Environment.SetEnvironmentVariable(row.Key,row.Value);
        var hostSource = new TaskCompletionSource<IHost>(TaskCreationOptions.RunContinuationsAsynchronously);
        using var subscriptions = DiagnosticListener.AllListeners.Subscribe(new CallbackObserver<DiagnosticListener>(source =>
        {
            if(source.Name == "Microsoft.Extensions.Hosting")
                source.Subscribe(new CallbackObserver<KeyValuePair<string,object?>>(evt =>
                { if(evt.Key == "HostBuilt" && evt.Value is IHost host) hostSource.TrySetResult(host); }));
        }));
        Task? program = null; IHost? actualHost = null;
        try
        {
            var entry = typeof(ArtifactReadbackService).Assembly.EntryPoint!;
            program = Task.Run(async () =>
            {
                var result = entry.Invoke(null,new object[]{new[]{"--contentRoot",Path.Combine(S206TestSupport.RepositoryRoot,"PhaseA.Platform")}});
                if(result is Task asynchronousMain) await asynchronousMain;
            });
            var winner = await Task.WhenAny(hostSource.Task,program,Task.Delay(TimeSpan.FromSeconds(20)));
            if (winner != hostSource.Task)
            {
                if(program.IsCompleted) await program;
                throw new TimeoutException("Actual Program did not publish its HostBuilt diagnostic.");
            }
            actualHost = await hostSource.Task;
            using var http = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(2) };
            http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer",adminToken);
            var healthy = false;
            for(var i=0;i<50;i++)
            {
                try { healthy = (await http.GetAsync("/healthz")).IsSuccessStatusCode; }
                catch(HttpRequestException) {} catch(TaskCanceledException) {}
                if(healthy) break;
                await Task.Delay(100);
            }
            if(!healthy) throw new InvalidOperationException("Actual Program did not become healthy.");
            // The exact live composition root supplies both the HTTP route and object under inspection.
            var readback = actualHost.Services.GetRequiredService<ArtifactReadbackService>();
            var actualStore = actualHost.Services.GetRequiredService<PhaseAMetadataStore>();
            var options = actualHost.Services.GetRequiredService<PhaseAPlatformOptions>();
            var projectId = Guid.NewGuid().ToString("N");
            var layout = WorkspaceLayoutBuilder.Build(options.HostedWorkspaceRoot,first.AccountId,projectId);
            foreach(var path in new[]{layout.RootPath,layout.RepoPath,layout.RuntimePath,layout.MetaPath}) Directory.CreateDirectory(path);
            var created = await actualStore.CreateProjectAsync(new ProjectCreationCommand(projectId,first.AccountId,
                "Capability control","Capability control","manual","general",false,[],
                layout.RootPath,layout.RepoPath,layout.RuntimePath,layout.MetaPath));
            IReadOnlyList<ProjectListItem> allowed,other;
            using(S206TestSupport.EnterCurrentContext(new RequestContext(first.AccountId,first.AccountId,
                new HashSet<string>{PhaseAAuth.UserRole},PhaseAAuth.HashTokenForStorage(first.Token),"capability-a")))
                allowed=await readback.ListProjectsAsync(first.AccountId);
            using(S206TestSupport.EnterCurrentContext(new RequestContext(second.AccountId,second.AccountId,
                new HashSet<string>{PhaseAAuth.UserRole},PhaseAAuth.HashTokenForStorage(second.Token),"capability-b")))
                other=await readback.ListProjectsAsync(second.AccountId);
            var compositionText = File.ReadAllText(Path.Combine(S206TestSupport.RepositoryRoot,"PhaseA.Platform/Program.cs"));
            // Bound production owners only: central account/key-pool adapters are not ordinary roots.
            var ownerNames = new HashSet<string>(StringComparer.Ordinal) { "ProjectWebPreviewSemanticAdapterService", "ProjectWebPreviewDedicatedAdapterService", "ProjectAssetImageGenerator", "ChatService", "LlmStopLossService", "ProjectChatHistoryService", "ProjectCreationService", "ProjectDraftImportService", "ProjectInitializationRecoveryService", "ProjectInitializationService", "WindowsProjectRunnerProvisioner", "ProjectGameTypeMatchBackfillService", "ProjectGameTypeMatchService", "ArtifactReadbackService", "ProjectAssetInventoryService", "ProjectAssetLibraryService", "ProjectAssetPreviewTicketService", "ProjectPackageDownloadTicketService", "ProjectPackageRestoreService", "ProjectPackageService", "ProjectWebPreviewService", "Chapter2BootstrapService", "GameDesignDocumentService", "GameDesignQuestionFormRestoreService", "GameDesignQuestionFormService", "GameDesignRequirementMapService", "GameDesignSceneRouteService", "GddMilestoneStepService", "GddToModulePhase1StateService", "GodotFailureDiagnosticService", "ProjectWorkflowRouteService", "PrototypeCommandService", "PrototypeContractFreezeService", "PrototypeFeedbackIterationService", "PrototypeGodotSmokeService", "PrototypeIterationGoalService", "PrototypeIterationPlanService", "PrototypeNeedsFixRouteService", "PrototypeQuickFixService", "PrototypeRepairPlanService", "PrototypeSmokeSceneResolver", "PrototypeUiOptimizationService", "PrototypeWorkflowService", "SkillActionService", "ProjectWorkspaceMaintenanceService", "ProjectWorkspaceSeeder", "RestoreService", "WorkspaceStorageService" };
            var productionTypes = typeof(ArtifactReadbackService).Assembly.GetTypes().Where(t =>
                t.IsClass && ownerNames.Contains(t.Name)).OrderBy(t=>t.FullName,StringComparer.Ordinal).ToArray();
            var objects = new List<object> { readback };
            var resolutionErrors = new List<string>();
            var staticOwners = new List<string>();
            var hosted = actualHost.Services.GetServices<IHostedService>().ToArray();
            foreach(var type in productionTypes)
            {
                if(type.IsAbstract && type.IsSealed) { staticOwners.Add(type.FullName!); continue; }
                try
                {
                    var value = actualHost.Services.GetService(type) ?? hosted.FirstOrDefault(o=>o.GetType()==type);
                    if(value is null)
                    {
                        var serviceInterface = type.GetInterfaces().FirstOrDefault(i=>
                            compositionText.Contains("<"+i.Name+", "+type.Name+">") ||
                            compositionText.Contains("<"+i.Name+","+type.Name+">"));
                        if(serviceInterface is not null) value=actualHost.Services.GetService(serviceInterface);
                    }
                    // Nonregistered direct-construction owners use the real Program provider, never alternate services.
                    value ??= ActivatorUtilities.CreateInstance(actualHost.Services,type);
                    if(!objects.Contains(value)) objects.Add(value);
                }
                catch(Exception ex) { resolutionErrors.Add(type.FullName+":"+ex.GetType().Name+":"+ex.Message); }
            }
            var pendingObjects=new Queue<object>(objects);
            var seen=new HashSet<object>(System.Collections.Generic.ReferenceEqualityComparer.Instance);
            var boundaryNames=new HashSet<string>(StringComparer.Ordinal) { "NodeProjectMetadata", "NodeOperationGuard", "NodeExecutionOptions", "NodeLlmBindingReader", "NodeRuntimeCredentialReader", "NodeTicketSigner", "NodePreviewRuntime", "LlmRouteEngine", "CodexCliChatClient", "AiCodeMirrorBillingClient", "CentralWorkspaceStorageBackend", "CentralRestoreBackend" };
            while(pendingObjects.Count>0)
            {
                var instance=pendingObjects.Dequeue();
                if(!seen.Add(instance)) continue;
                if(boundaryNames.Contains(instance.GetType().Name)) continue;
                foreach(var field in instance.GetType().GetFields(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance))
                {
                    var value=field.GetValue(instance);
                    if(value is null || value.GetType().Assembly!=typeof(ArtifactReadbackService).Assembly || boundaryNames.Contains(value.GetType().Name)) continue;
                    if(value is PhaseAMetadataStore || value is PhaseAPlatformOptions) continue; // Already classified directly, never inspect their private central data.
                    if(!objects.Any(o=>ReferenceEquals(o,value))) objects.Add(value);
                    pendingObjects.Enqueue(value);
                }
            }
            var forbidden = new List<object>(); var exposedSecrets = new List<string>();
            var centralMutationAttempts = new List<object>();
            foreach(var consumer in objects)
            {
                foreach(var field in consumer.GetType().GetFields(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance))
                {
                    var held = field.GetValue(consumer);
                    if(held is null) continue;
                    var kind = held is PhaseAMetadataStore ? "full_store" : held is PhaseAPlatformOptions ? "unrestricted_options" :
                        held is IServiceProvider || held is IServiceScopeFactory ? "service_locator" :
                        held.GetType().FullName?.Contains("SqliteConnection") == true ? "sql_connection" : null;
                    if(held is string text && field.Name.Contains("connection",StringComparison.OrdinalIgnoreCase) &&
                        text.Contains("Data Source",StringComparison.OrdinalIgnoreCase)) kind="sql_connection_string";
                    if(kind is null && IsBroadCapability(field.FieldType)) kind="typed_factory_or_locator";
                    if(kind is null && IsBroadCapability(held.GetType())) kind="privileged_central_reference";
                    if(kind is not null) forbidden.Add(new { consumer=consumer.GetType().FullName,field=field.Name,kind });
                    // Only public facade surface is traversed; private trusted backing state is deliberately untouched.
                    foreach(var member in held.GetType().GetMethods(BindingFlags.Public|BindingFlags.Instance|BindingFlags.DeclaredOnly))
                    {
                        if(IsBroadCapability(member.ReturnType) || member.GetParameters().Any(p=>IsBroadCapability(p.ParameterType)) ||
                            member.Name is "CreateUserAccountAsync" or "SetUserDisabledAsync" or "RotateUserTokenAsync" or "BindAsync")
                            forbidden.Add(new { consumer=consumer.GetType().FullName,field=field.Name,kind="public_privileged_capability:"+member.Name });
                    }
                    if(held is PhaseAPlatformOptions privileged)
                    {
                        // Only synthetic fixture values are compared; no values are returned in the observation.
                        var suppliedHash = PhaseAAuth.HashTokenForStorage(adminToken);
                        if(privileged.AdminTokenHash==suppliedHash || privileged.MetadataDatabasePath==database)
                            exposedSecrets.Add(consumer.GetType().FullName+"."+field.Name);
                    }
                    if(held is PhaseAMetadataStore writable)
                    {
                        var before=await actualStore.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(second.Token));
                        await writable.SetUserDisabledAsync(second.AccountId,true);
                        var after=await actualStore.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(second.Token));
                        centralMutationAttempts.Add(new { consumer=consumer.GetType().FullName,centralWriteSucceeded=before is not null && after is null });
                        await actualStore.SetUserDisabledAsync(second.AccountId,false);
                    }
                }
            }
            using var session = await http.GetAsync("/api/session");
            output.WriteLine("S206_CAPABILITY:"+JsonSerializer.Serialize(new {
                source="actual_Program_HostBuilt_and_service_provider", liveSessionStatus=(int)session.StatusCode,
                staticOwners, resolvedConsumers=objects.Select(o=>o.GetType().FullName).Order().ToArray(), resolutionErrors,
                forbidden,exposedSecrets,centralMutationAttempts,
                allowedProjectIds=allowed.Select(x=>x.ProjectId).ToArray(), otherProjectIds=other.Select(x=>x.ProjectId).ToArray(),
                expectedProjectId=projectId,accountsRetained=(await actualStore.ListAccountsAsync()).Count>=3,
                nativeWindowsEvidence=false
            }));
        }
        finally
        {
            actualHost?.Services.GetRequiredService<IHostApplicationLifetime>().StopApplication();
            if(program is not null) await program.WaitAsync(TimeSpan.FromSeconds(15));
            foreach(var row in originals) Environment.SetEnvironmentVariable(row.Key,row.Value);
        }
    }

    [Fact]
    public async Task O_5A39371CE268()
    {
        // ADR-0061 AD16/17: real store and creation service; synthetic game content
        // does not replace node authority. This does not test Windows Runner setup.
        var root = Path.Combine(Path.GetTempPath(), "s206-project-stamp-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var database = Path.Combine(root, "metadata.sqlite3");
        var connectionString = "Data Source=" + database;
        var settings = new Dictionary<string,string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root,"workspaces"),
            ["PHASEA_METADATA_DB_PATH"] = database,
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["PHASEA_SERVICE_STATE"] = "test", ["PHASEA_NODE_ID"] = "test-physical-node",
            ["PHASEA_NODE_SCOPE"] = "single_node_test", ["PHASEA_NODE_TOPOLOGY"] = "single_service",
            ["PHASEA_ENABLED_ROLES"] = "entry,production", ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = "true",
            ["PHASEA_LOGIN_ENDPOINT"] = "https://login.example.invalid",
            ["PHASEA_WORKBENCH_ENDPOINT"] = "https://workbench.example.invalid",
            ["PHASEA_ACTIVE_CONTENT_ORIGIN"] = "https://content.example.invalid"
        };
        var options = PhaseAPlatformOptionsLoader.FromDictionary(settings);
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        await using var sql = new SqliteConnection(connectionString);
        await sql.OpenAsync();
        await using var query = sql.CreateCommand();
        query.CommandText = "PRAGMA table_info(projects);";
        bool? notNull = null;
        await using (var reader = await query.ExecuteReaderAsync())
            while(await reader.ReadAsync())
                if(reader.GetString(1)=="node_id") notNull=reader.GetInt64(3)!=0;
        await SqliteMetadataSchema.InitializeSingleNodeTestAsync(connectionString, options);
        var store = new PhaseAMetadataStore(connectionString, options);
        var user = await store.CreateUserAccountAsync("project-stamp", 10);
        using var current=S206TestSupport.EnterCurrentContext(new RequestContext(user.AccountId,user.AccountId,
            new HashSet<string>{PhaseAAuth.UserRole},PhaseAAuth.HashTokenForStorage(user.Token),"project-stamp"));
        var seeder = new StampingGameContentSeeder();
        var creation = new ProjectCreationService(store, options, new ProjectRuleCatalog(), seeder);
        var forged = JsonSerializer.Deserialize<ProjectCreationRequest>(
            "{\"gameName\":\"Stamp control\",\"gameTypeSource\":\"manual\",\"nodeId\":\"foreign-node\",\"homeNodeId\":\"foreign-node\"}",
            new JsonSerializerOptions(JsonSerializerDefaults.Web))!;
        var created = await creation.CreateProjectAsync(user.AccountId, forged);
        if(!created.Succeeded || created.ProjectId is null)
            throw new InvalidOperationException("Actual creation control failed: " + created.FailureCode);
        var directId = Guid.NewGuid().ToString("N");
        var layout = WorkspaceLayoutBuilder.Build(options.HostedWorkspaceRoot,user.AccountId,directId);
        var direct = await store.CreateProjectAsync(new ProjectCreationCommand(directId,user.AccountId,
            "Direct stamp","Direct stamp","manual",ProjectRuleCatalog.DefaultRuleId,false,[],
            layout.RootPath,layout.RepoPath,layout.RuntimePath,layout.MetaPath));
        if(!direct.Succeeded) throw new InvalidOperationException("Actual direct creation control failed.");
        var import = new ProjectDraftImportService(store, options, new UnusedStampCodex());
        var parsed = import.ImportPlainText("draft.txt",Encoding.UTF8.GetBytes(
            "game_name: Imported control\nnode_id: foreign-node\nhome_node_id: foreign-node\nport: 9000"));
        var conflicting = new PhaseAMetadataStore(connectionString,
            PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string,string?>(settings)
                { ["PHASEA_NODE_ID"]="foreign-node" }));
        var rejectedId = Guid.NewGuid().ToString("N");
        bool denied = false;
        try
        {
            var mismatch = await conflicting.CreateProjectAsync(new ProjectCreationCommand(rejectedId,user.AccountId,
                "Mismatch","Mismatch","manual",ProjectRuleCatalog.DefaultRuleId,false,[],
                layout.RootPath,layout.RepoPath,layout.RuntimePath,layout.MetaPath));
            denied = !mismatch.Succeeded;
        }
        catch(UnauthorizedAccessException) { denied=true; }
        var nodes = new Dictionary<string,string?>();
        query.CommandText="SELECT id,node_id FROM projects ORDER BY id;";
        await using(var reader=await query.ExecuteReaderAsync())
            while(await reader.ReadAsync()) nodes.Add(reader.GetString(0),reader.IsDBNull(1)?null:reader.GetString(1));
        output.WriteLine("S206_PROJECT_STAMP:"+JsonSerializer.Serialize(new {
            nullableAtInstall=notNull==false,projectId=created.ProjectId,directId,rejectedId,nodes,denied,
            gameClaimPresent=File.ReadAllText(Path.Combine(created.WorkspaceRootPath!,"repo","node.json")).Contains("foreign-node",StringComparison.Ordinal),
            importStatus=parsed.Status,nativeWindowsEvidence=false
        }));
    }

    private sealed class StampingGameContentSeeder : IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string projectRepoPath)
        {
            Directory.CreateDirectory(projectRepoPath);
            File.WriteAllText(Path.Combine(projectRepoPath,"node.json"),"{\"node_id\":\"foreign-node\",\"port\":9000}");
        }
    }

    private sealed class UnusedStampCodex : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(string projectRoot,string model,string prompt,
            CodexChatClientOptions? options=null,string? billingApiKeyName=null,CancellationToken cancellationToken=default)
            => throw new InvalidOperationException("Plain import must not call a model.");
    }

    [Fact]
    public async Task O_71CCE9337ECA()
    {
        // Real protected consumers plus actual authenticated HTTP/ticket routes.
        var cases=new List<object>();
        var attacks=new[]{"forged-context","missing-home","foreign-home","missing-projection",
            "foreign-project","foreign-local","stale-projection","revoked","admin-missing-home","admin-foreign-home"};
        foreach(var attack in attacks)
        {
            await using var fixture=await S206AuthorityFixture.CreateAsync(startHost:true);
            var resource=attack.StartsWith("admin-",StringComparison.Ordinal)?fixture.Admin:fixture.First;
            var readback=new ArtifactReadbackService(fixture.Store,fixture.Options,fixture.Queue(),fixture.Queue(),fixture.Queue(),fixture.Queue());
            var packages=new ProjectPackageService(fixture.Store,fixture.Options,heavyRunnerQueue:fixture.Queue(),processRunner:new HostedProcessRunner(authority:fixture.Store),storage:fixture.Storage);
            using var client=fixture.Client(resource);
            AccessEffects positive;
            using(S206TestSupport.EnterCurrentContext(resource.Context))
                positive=await ReadActualAccessAsync(fixture,resource,readback,packages);
            using var httpControl=await client.GetAsync("/api/artifacts/"+resource.ArtifactId+"?home_node_id=forged&node_id=forged&port=1");
            using var issueControl=await client.PostAsync("/api/projects/"+resource.Project.ProjectId+"/packages/fixture.zip/download-ticket",null);
            if(!httpControl.IsSuccessStatusCode || !issueControl.IsSuccessStatusCode)
                throw new InvalidOperationException("Actual HTTP artifact/ticket positive control unavailable.");
            using var issued=JsonDocument.Parse(await issueControl.Content.ReadAsStringAsync());
            var url=issued.RootElement.GetProperty("downloadUrl").GetString()!;
            using var redeemControl=await client.GetAsync(url);
            if(!redeemControl.IsSuccessStatusCode || (await redeemControl.Content.ReadAsByteArrayAsync()).Length==0)
                throw new InvalidOperationException("Real signed package-ticket redemption control unavailable.");
            var usedContext=resource.Context;
            if(attack=="forged-context")
                usedContext=resource.Context with { AccountId=fixture.Second.AccountId,
                    Roles=new HashSet<string>(StringComparer.Ordinal){PhaseAAuth.AdminRole} };
            else await fixture.FaultAsync(resource,attack.Replace("admin-","",StringComparison.Ordinal));
            var before=await fixture.OwnershipAsync(resource);var hash=fixture.ContentHash(resource);
            AccessEffects attempted;
            using(S206TestSupport.EnterCurrentContext(usedContext))
                attempted=await ReadActualAccessAsync(fixture,resource,readback,packages);
            int? httpStatus=null,issueStatus=null,redeemStatus=null;
            if(attack!="forged-context")
            {
                using var badRead=await client.GetAsync("/api/artifacts/"+resource.ArtifactId);
                using var badIssue=await client.PostAsync("/api/projects/"+resource.Project.ProjectId+"/packages/fixture.zip/download-ticket",null);
                using var badRedeem=await client.GetAsync(url);
                httpStatus=(int)badRead.StatusCode;issueStatus=(int)badIssue.StatusCode;redeemStatus=(int)badRedeem.StatusCode;
            }
            cases.Add(new { attack, positive,attempted,httpStatus,issueStatus,redeemStatus,
                unchanged=before==await fixture.OwnershipAsync(resource) && hash==fixture.ContentHash(resource),
                resource.AccountId,resource.Project.ProjectId,resource.RunId,resource.SnapshotId });
        }
        output.WriteLine("S206_CURRENT_ACCESS:"+JsonSerializer.Serialize(new { cases,nativeWindowsEvidence=false }));
    }

    [Fact]
    public async Task O_AEDD71ADAEA1()
    {
        await using var fixture=await S206AuthorityFixture.CreateAsync();
        var resource=fixture.First;
        var readback=new ArtifactReadbackService(fixture.Store,fixture.Options,fixture.Queue(),fixture.Queue(),fixture.Queue(),fixture.Queue());
        var packages=new ProjectPackageService(fixture.Store,fixture.Options,heavyRunnerQueue:fixture.Queue(),processRunner:new HostedProcessRunner(authority:fixture.Store),storage:fixture.Storage);
        var queue=fixture.Queue();
        var ownership=await fixture.OwnershipAsync(resource);var contentHash=fixture.ContentHash(resource);
        AccessEffects positive,foreign;
        string? runProject=null;bool execution=false,foreignExecution=false;
        using(S206TestSupport.EnterCurrentContext(resource.Context))
        {
            positive=await ReadActualAccessAsync(fixture,resource,readback,packages);
            execution=await queue.ExecuteAsync("s206-valid-"+Guid.NewGuid().ToString("N"),resource.AccountId,
                resource.Project.ProjectId,"s206-contract",async token=>
                {
                    NodeProjectMetadata actual=fixture.Store;
                    var run=await actual.GetRunSnapshotAsync(resource.RunId,token);
                    runProject=run?.ProjectId;return runProject==resource.Project.ProjectId;
                });
        }
        using(S206TestSupport.EnterCurrentContext(fixture.Second.Context))
        {
            foreign=await ReadActualAccessAsync(fixture,resource,readback,packages);
            try
            {
                foreignExecution=await queue.ExecuteAsync("s206-foreign-"+Guid.NewGuid().ToString("N"),resource.AccountId,
                    resource.Project.ProjectId,"s206-contract",_=>Task.FromResult(true));
            }
            catch(UnauthorizedAccessException) { }
        }
        output.WriteLine("S206_ONE_HOME:"+JsonSerializer.Serialize(new {
            positive,foreign,execution,foreignExecution,runProject,accountId=resource.AccountId,projectId=resource.Project.ProjectId,
            workspaceId=resource.Project.WorkspaceId,runId=resource.RunId,snapshotId=resource.SnapshotId,
            ownership,unchanged=ownership==await fixture.OwnershipAsync(resource) && contentHash==fixture.ContentHash(resource),
            nativeWindowsEvidence=false
        }));
    }

    [Fact]
    public async Task O_EFCE3FE74915()
    {
        var cases=new List<object>();
        foreach(var attack in new[]{"forged-context","missing-home","foreign-home","foreign-project","foreign-local","revoked"})
        {
            await using var fixture=await S206AuthorityFixture.CreateAsync();
            var resource=fixture.First;
            // This is the actual queue. The optional future constructor receives a real
            // restricted production capability, never a fixture Boolean authorizer.
            var queue=fixture.Queue();
            bool positive;
            using(S206TestSupport.EnterCurrentContext(resource.Context))
                positive=await queue.ExecuteAsync("s206-positive-"+Guid.NewGuid().ToString("N"),resource.AccountId,
                    resource.Project.ProjectId,"s206-contract",_=>Task.FromResult(true));
            var entered=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var release=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var marker=Path.Combine(fixture.Root,"untrusted-work-start.txt");
            var usedContext=attack=="forged-context" ? resource.Context with { AccountId=fixture.Second.AccountId,
                Roles=new HashSet<string>(StringComparer.Ordinal){PhaseAAuth.AdminRole} } : resource.Context;
            Task<bool> held,waiting;
            using(S206TestSupport.EnterCurrentContext(resource.Context))
                held=queue.ExecuteAsync("s206-held-"+Guid.NewGuid().ToString("N"),resource.AccountId,
                    resource.Project.ProjectId,"s206-contract",async token=>
                    { entered.SetResult();await release.Task.WaitAsync(token);return true; });
            await entered.Task.WaitAsync(TimeSpan.FromSeconds(5));
            using(S206TestSupport.EnterCurrentContext(usedContext))
                waiting=queue.ExecuteAuthorizedAsync("s206-waiting-"+Guid.NewGuid().ToString("N"),resource.AccountId,
                    resource.Project.ProjectId,"s206-contract",usedContext,
                    (_,token)=>fixture.Store.ProjectBelongsToAccountAsync(resource.AccountId,resource.Project.ProjectId,token),
                    async token=>{await File.WriteAllTextAsync(marker,"started",token);return true;});
            try
            {
                if(attack!="forged-context") await fixture.FaultAsync(resource,attack);
                var before=await fixture.OwnershipAsync(resource);var hash=fixture.ContentHash(resource);
                release.SetResult();await held.WaitAsync(TimeSpan.FromSeconds(5));
                bool denied=false;
                try { denied=!await waiting.WaitAsync(TimeSpan.FromSeconds(5)); }
                catch(UnauthorizedAccessException){denied=true;}
                cases.Add(new { attack,positive,denied,started=File.Exists(marker),
                    unchanged=before==await fixture.OwnershipAsync(resource) && hash==fixture.ContentHash(resource) });
            }
            finally
            {
                release.TrySetResult();
                try { await Task.WhenAll(held,waiting).WaitAsync(TimeSpan.FromSeconds(5)); }
                catch(UnauthorizedAccessException) { }
            }
        }
        output.WriteLine("S206_CURRENT_DISPATCH:"+JsonSerializer.Serialize(new {cases,nativeWindowsEvidence=false}));
    }

    private sealed record AccessEffects(bool Artifact,bool Package,bool Snapshot,bool Ticket);

    private static async Task<AccessEffects> ReadActualAccessAsync(S206AuthorityFixture fixture,
        S206AuthorityFixture.Resource resource,ArtifactReadbackService readback,ProjectPackageService packages)
    {
        bool artifact=false,package=false,snapshot=false,ticket=false;
        try { artifact=(await readback.ReadArtifactForAccountAsync(resource.AccountId,resource.ArtifactId))?.Content==resource.Sentinel; }
        catch(UnauthorizedAccessException) { }
        try { package=(await packages.ReadPackageAsync(resource.AccountId,resource.Project.ProjectId,"fixture.zip"))?.Content.Length>0; }
        catch(UnauthorizedAccessException) { }
        try { snapshot=fixture.Storage.ListSnapshots(resource.AccountId,resource.Project.ProjectId).Any(r=>r.Manifest.SnapshotId==resource.SnapshotId); }
        catch(UnauthorizedAccessException) { }
        NodeTicketSigner signer=fixture.Options;NodeProjectMetadata authority=fixture.Store;
        var constructor=typeof(ProjectPackageDownloadTicketService).GetConstructor([typeof(NodeTicketSigner),typeof(NodeProjectMetadata)]);
        var tickets=constructor is null ? new ProjectPackageDownloadTicketService(signer)
            : (ProjectPackageDownloadTicketService)constructor.Invoke([signer,authority]);
        try
        {
            var value=tickets.CreateTicket(resource.AccountId,resource.Project.ProjectId,"fixture.zip");
            ticket=tickets.IsValid(value,resource.AccountId,resource.Project.ProjectId,"fixture.zip");
        }
        catch(UnauthorizedAccessException) { }
        return new AccessEffects(artifact,package,snapshot,ticket);
    }

    private static bool IsBroadCapability(Type type)
    {
        if(type==typeof(PhaseAMetadataStore) || type==typeof(PhaseAPlatformOptions) ||
            type==typeof(PhaseA.Platform.Llm.LlmBindingService) || type==typeof(PhaseA.Platform.Llm.AiCodeMirrorKeyPoolService) ||
            typeof(IServiceProvider).IsAssignableFrom(type) || typeof(IServiceScopeFactory).IsAssignableFrom(type) ||
            typeof(System.Data.IDbConnection).IsAssignableFrom(type) || typeof(IServiceScope).IsAssignableFrom(type)) return true;
        return type.IsGenericType && type.GetGenericArguments().Any(IsBroadCapability);
    }

    private sealed class CallbackObserver<T>(Action<T> action) : IObserver<T>
    {
        public void OnNext(T value)=>action(value);
        public void OnError(Exception error) {}
        public void OnCompleted() {}
    }
}
