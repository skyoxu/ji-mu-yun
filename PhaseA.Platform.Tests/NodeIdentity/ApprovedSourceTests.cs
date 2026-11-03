using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using PhaseA.Platform.Data;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Security;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061 AD24: actual protected catalog, actual Program and two independent projects.
public sealed class ApprovedSourceTests(ITestOutputHelper output)
{
    [Fact]
    public async Task GlobalVersionChangesNeverOverwriteUserEditedCopies() =>
        output.WriteLine("S206_APPROVED_SOURCE:"+JsonSerializer.Serialize(await ObserveAsync("copy")));

    [Fact]
    public async Task Ac08FixtureHasOneApprovedVersionAndTwoRealAccounts() =>
        output.WriteLine("S206_APPROVED_SOURCE:"+JsonSerializer.Serialize(await ObserveAsync("accounts")));

    [Fact]
    public async Task SharedQueryCacheUsesAllKeysAndBoundedHostOwnership() =>
        output.WriteLine("S206_APPROVED_SOURCE:"+JsonSerializer.Serialize(await ObserveAsync("cache")));

    private static string Hash(byte[] value)=>Convert.ToHexString(SHA256.HashData(value)).ToLowerInvariant();

    private static async Task<object> ObserveAsync(string scenario)
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        var repository=Path.Combine(f.Root,"protected-approved-repository");
        var guides=Path.Combine(repository,"docs","game-type-guides");
        var catalog=Path.Combine(guides,"game-types.csv");
        var first=Path.Combine(guides,"versions","one","rpg.md");
        Directory.CreateDirectory(Path.GetDirectoryName(first)!);
        const string original="Alpha shared approved version one.\nPrivate projects are separate.\n";
        await File.WriteAllTextAsync(first,original,new UTF8Encoding(false));
        await PublishCatalogAsync(catalog,"versions/one/rpg.md","Approved one");
        var approvedHash=Hash(await File.ReadAllBytesAsync(first));
        var approvalHash=Hash(await File.ReadAllBytesAsync(catalog));
        // The real startup reconciler removes unfinished bootstrap projects by design.
        // These are ready read/copy fixtures, not abandoned initialization attempts.
        foreach(var resource in new[]{f.First,f.Second,f.Admin})
            await f.Store.SetProjectBootstrapStatusAsync(resource.Project.ProjectId,"succeeded",null);
        await using var host=await SourceHost.StartAsync(f,repository);
        var type=typeof(ProjectAssetInventoryService).Assembly.GetType("PhaseA.Platform.Readback.NodeApprovedSourceReader");
        var reader=type is null?null:host.Host.Services.GetService(type);
        var identities=new[]{f.First.AccountId,f.Second.AccountId};
        // Independently reopen the real declared metadata owner for fixture ownership.
        var reopenedStore=new PhaseAMetadataStore(f.ConnectionString,f.Options);
        var owned=new List<bool>();
        foreach(var resource in new[]{f.First,f.Second})
        {
            using var current=S206TestSupport.EnterCurrentContext(resource.Context);
            var actual=await reopenedStore.GetProjectSnapshotAsync(resource.Project.ProjectId);
            owned.Add(actual?.AccountId==resource.AccountId);
        }
        if(reader is null)
            return new {scenario,available=false,identities,owned,approvedHash,approvalHash,
                actualProgramBuilt=host.Host is not null,caseAttempts=4,
                missing="Approved local source operation unavailable from actual protected Program"};
        JsonElement reference;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
            reference=await CallAsync(reader,"ResolveAsync",f.First.AccountId,f.First.Project.ProjectId,"rpg");
        var cases=new List<object>();
        foreach(var resource in new[]{f.First,f.Second})
        {
            using var current=S206TestSupport.EnterCurrentContext(resource.Context);
            var read=await CallAsync(reader,"ReadAsync",resource.AccountId,resource.Project.ProjectId,reference);
            var forged=JsonSerializer.SerializeToElement(new {SourceId=resource.Project.RepoPath,
                Version=reference.GetProperty("Version").GetString(),ContentHash=approvedHash,
                ApprovalRef=reference.GetProperty("ApprovalRef").GetString()});
            var denied=await DeniedAsync(()=>CallAsync(reader,"ReadAsync",resource.AccountId,resource.Project.ProjectId,forged));
            cases.Add(new {account=resource.AccountId,read,privateAsSourceDenied=denied,
                privateHash=Hash(await File.ReadAllBytesAsync(Path.Combine(resource.Project.RepoPath,"private.txt")))});
        }
        var approvalUnchanged=approvalHash==Hash(await File.ReadAllBytesAsync(catalog));
        if(scenario=="accounts")
            return new {scenario,available=true,identities,owned,approvedHash,approvalHash,reference,cases,approvalUnchanged};
        if(scenario=="copy")
        {
            var copies=new List<object>();
            var copyPaths=new List<string>();
            foreach(var resource in new[]{f.First,f.Second})
            {
                using var current=S206TestSupport.EnterCurrentContext(resource.Context);
                var copied=await CallAsync(reader,"CopyAsync",resource.AccountId,resource.Project.ProjectId,reference);
                var relative=copied.GetProperty("RelativePath").GetString()!;
                var path=Path.GetFullPath(Path.Combine(resource.Project.RepoPath,relative));
                if(!path.StartsWith(resource.Project.RepoPath+Path.DirectorySeparatorChar,StringComparison.Ordinal))
                    throw new InvalidOperationException("Copy result escaped the real owned repository");
                var initial=await File.ReadAllBytesAsync(path);
                await File.WriteAllTextAsync(path,"Independent edit by "+resource.AccountId,new UTF8Encoding(false));
                copyPaths.Add(path);
                copies.Add(new {account=resource.AccountId,copied,initialHash=Hash(initial),editedHash=Hash(await File.ReadAllBytesAsync(path))});
            }
            var before=await Task.WhenAll(copyPaths.Select(path=>File.ReadAllBytesAsync(path)));
            var second=Path.Combine(guides,"versions","two","rpg.md");Directory.CreateDirectory(Path.GetDirectoryName(second)!);
            const string updated="Beta approved version two.\n";
            await File.WriteAllTextAsync(second,updated,new UTF8Encoding(false));
            await PublishCatalogAsync(catalog,"versions/two/rpg.md","Approved two");
            JsonElement newReference,newRead;
            using(S206TestSupport.EnterCurrentContext(f.First.Context))
            {
                newReference=await CallAsync(reader,"ResolveAsync",f.First.AccountId,f.First.Project.ProjectId,"rpg");
                newRead=await CallAsync(reader,"ReadAsync",f.First.AccountId,f.First.Project.ProjectId,newReference);
            }
            var after=await Task.WhenAll(copyPaths.Select(path=>File.ReadAllBytesAsync(path)));
            return new {scenario,available=true,identities,owned,approvedHash,approvalHash,reference,cases,approvalUnchanged,
                copies,newReference,newRead,expectedUpdated=updated,updatedHash=Hash(await File.ReadAllBytesAsync(second)),
                before=before.Select(Hash).ToArray(),after=after.Select(Hash).ToArray(),
                originalUnchanged=approvedHash==Hash(await File.ReadAllBytesAsync(first))};
        }
        var observations=new List<object>();
        async Task Query(string label,S206AuthorityFixture.Resource resource,JsonElement referenceValue,string term,string implementation)
        {
            using var current=S206TestSupport.EnterCurrentContext(resource.Context);
            var result=await CallAsync(reader,"QueryAsync",resource.AccountId,resource.Project.ProjectId,referenceValue,term,implementation);
            observations.Add(new {label,account=resource.AccountId,result});
        }
        await Query("parameter-first",f.First,reference,"Alpha","contains-ordinal-v1");
        await Query("parameter-hit",f.First,reference,"Alpha","contains-ordinal-v1");
        await Query("parameter-change",f.First,reference,"absent","contains-ordinal-v1");
        await Query("case-sensitive",f.First,reference,"alpha","contains-ordinal-v1");
        await Query("implementation-change",f.First,reference,"alpha","contains-ignorecase-v1");
        await Query("implementation-hit",f.First,reference,"alpha","contains-ignorecase-v1");
        await Query("visibility-change",f.Second,reference,"alpha","contains-ignorecase-v1");
        await Query("visibility-hit",f.Second,reference,"alpha","contains-ignorecase-v1");
        // A project cannot impersonate either the protected catalog or the host cache.
        var imitation=Path.Combine(f.First.Project.RepoPath,"docs","game-type-guides");Directory.CreateDirectory(imitation);
        await File.WriteAllTextAsync(Path.Combine(imitation,"game-types.csv"),"attacker-controlled imitation");
        await File.WriteAllTextAsync(Path.Combine(f.First.Project.RepoPath,"shared-query-cache.json"),"{\"Matched\":false}");
        await Query("project-imitation",f.Second,reference,"alpha","contains-ignorecase-v1");
        // Change the protected catalog version while preserving the approved source bytes.
        await PublishCatalogAsync(catalog,"versions/one/rpg.md","Approved same bytes new catalog revision");
        JsonElement currentReference;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
            currentReference=await CallAsync(reader,"ResolveAsync",f.First.AccountId,f.First.Project.ProjectId,"rpg");
        await Query("version-change",f.First,currentReference,"alpha","contains-ignorecase-v1");
        await Query("version-hit",f.First,currentReference,"alpha","contains-ignorecase-v1");
        bool oldDenied,badHashDenied,corruptSourceDenied,revokedDenied,foreignProjectDenied;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
        {
            oldDenied=await DeniedAsync(()=>CallAsync(reader,"QueryAsync",f.First.AccountId,f.First.Project.ProjectId,reference,"alpha","contains-ignorecase-v1"));
            var altered=JsonSerializer.SerializeToElement(new {SourceId="rpg",Version=currentReference.GetProperty("Version").GetString(),
                ContentHash=new string('0',64),ApprovalRef=currentReference.GetProperty("ApprovalRef").GetString()});
            badHashDenied=await DeniedAsync(()=>CallAsync(reader,"QueryAsync",f.First.AccountId,f.First.Project.ProjectId,altered,"alpha","contains-ignorecase-v1"));
            await File.WriteAllTextAsync(first,"Corrupted protected source",new UTF8Encoding(false));
            corruptSourceDenied=await DeniedAsync(()=>CallAsync(reader,"QueryAsync",f.First.AccountId,f.First.Project.ProjectId,currentReference,"alpha","contains-ignorecase-v1"));
            await File.WriteAllTextAsync(first,original,new UTF8Encoding(false));
            foreignProjectDenied=await DeniedAsync(()=>CallAsync(reader,"QueryAsync",f.First.AccountId,f.Second.Project.ProjectId,currentReference,"alpha","contains-ignorecase-v1"));
        }
        // Pressure the real finite policy, rather than testing a local cache model.
        for(var i=0;i<40;i++)await Query("pressure-"+i,f.First,currentReference,"missing-"+i,"contains-ordinal-v1");
        await Query("evicted-original",f.First,currentReference,"alpha","contains-ignorecase-v1");
        await Query("recomputed-hit",f.First,currentReference,"alpha","contains-ignorecase-v1");
        await f.FaultAsync(f.First,"revoked");
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
            revokedDenied=await DeniedAsync(()=>CallAsync(reader,"QueryAsync",f.First.AccountId,f.First.Project.ProjectId,currentReference,"alpha","contains-ignorecase-v1"));
        return new {scenario,available=true,identities,owned,approvedHash,approvalHash,reference,cases,approvalUnchanged,
            currentReference,observations,oldDenied,badHashDenied,corruptSourceDenied,revokedDenied,foreignProjectDenied,
            protectedSourceUnchanged=approvedHash==Hash(await File.ReadAllBytesAsync(first))};
    }

    private static async Task PublishCatalogAsync(string path,string fragment,string name)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        await File.WriteAllTextAsync(path,"id,name,description,genre_tags,fragment_file\nrpg,"+name+",Approved repository guide,rpg,"+fragment+"\n",new UTF8Encoding(false));
    }

    private static async Task<bool> DeniedAsync(Func<Task<JsonElement>> operation)
    {
        try {await operation();return false;}
        catch(UnauthorizedAccessException){return true;}
        catch(InvalidDataException){return true;}
    }

    private static async Task<JsonElement> CallAsync(object target,string name,params object?[] values)
    {
        var method=target.GetType().GetMethod(name,BindingFlags.Public|BindingFlags.Instance)
            ??throw new InvalidOperationException("Present approved adapter lacks the required actual operation");
        var parameters=method.GetParameters();var args=new object?[parameters.Length];
        for(var i=0;i<args.Length;i++)
            args[i]=i<values.Length?(values[i] is JsonElement element?JsonSerializer.Deserialize(element.GetRawText(),parameters[i].ParameterType):values[i]):
                parameters[i].HasDefaultValue?parameters[i].DefaultValue:throw new InvalidOperationException("Unbound operation parameter");
        Task task;
        try {task=(Task)method.Invoke(target,args)!;}
        catch(TargetInvocationException ex) when(ex.InnerException is UnauthorizedAccessException or InvalidDataException){throw ex.InnerException;}
        await task;var value=task.GetType().GetProperty("Result")?.GetValue(task);
        return JsonSerializer.SerializeToElement(value,value?.GetType()??typeof(object));
    }

    private sealed class SourceHost(S206AuthorityFixture fixture,IHost host,Task program,Dictionary<string,string?> previous,TextWriter oldOut,TextWriter oldError,StringWriter logOut,StringWriter logError):IAsyncDisposable
    {
        private bool _disposed;
        internal IHost Host=>host;
        internal string CapturedLogs=>logOut.ToString()+logError.ToString();
        internal static async Task<SourceHost> StartAsync(S206AuthorityFixture f,string repositoryRoot,string roles="entry,production")
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
                {if(e.Key=="HostBuilt" && e.Value is IHost h)source.TrySetResult(h);}));
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
                return new SourceHost(f,host,program,previous,oldOut,oldError,logOut,logError);
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
            try{await host.StopAsync();await program.WaitAsync(TimeSpan.FromSeconds(20));}
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
