using Microsoft.AspNetCore.Routing;
using System.Collections;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061 AD14/17/25: actual protected Program composition and disposable SQLite.
public sealed class NodeNoticeTests(ITestOutputHelper output)
{
    [Fact]
    public async Task O_EDDBA9629B7A()
    {
        var rows=new List<object>();
        foreach(var mode in new[]{"valid-pair","no-context","forged-context","forged-admin","revoked",
            "foreign-home","missing-home","foreign-local","stale-projection"})
            rows.Add(await ObserveModeAsync(mode));
        output.WriteLine("S206_NOTICE_SCOPE:"+JsonSerializer.Serialize(new{rows,nativeWindowsEvidence=false,
            scope="same-host local notice contract; no remote/UI/Windows completion"}));
    }

    [Fact]
    public async Task O_38765C481069() => output.WriteLine("S206_NOTICE_INTEGRATION:"+JsonSerializer.Serialize(await ObserveAtomicAsync()));

    internal static async Task<object> ObserveAtomicAsync()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        await using var host=await NoticeHost.StartAsync(f);
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        var reader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        var old=new NodeNoticePublication("atomic",1,"old body","account",f.First.AccountId,
            DateTimeOffset.UtcNow.AddMinutes(-1),DateTimeOffset.UtcNow.AddMinutes(5),true,1,"change-1");
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))await publisher.PublishAsync(old);
        var before=await StateAsync(f.ConnectionString);
        // The conditional trigger fires only after the actual fact revision-2 write
        // and before the matching projection write in the real product transaction.
        await ExecuteFixtureSqlAsync(f.ConnectionString,"""
            CREATE TRIGGER fixture_notice_late_update BEFORE UPDATE ON node_notice_projections
            WHEN (SELECT revision FROM notice_facts WHERE notice_id=NEW.notice_id)=2
            BEGIN SELECT RAISE(ABORT,'fixture_notice_after_actual_fact'); END;
            """);
        var interrupted=false;
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
        {
            try{await publisher.PublishAsync(old with {Revision=2,Body="new body",ChangeRevision=2,ChangeRef="change-2"});}
            catch(SqliteException e) when(e.SqliteErrorCode==19 && e.Message.Contains("fixture_notice_after_actual_fact",StringComparison.Ordinal))
            {interrupted=true;}
        }
        var after=await StateAsync(f.ConnectionString);
        var independentlyReopened=new PhaseAMetadataStore(f.ConnectionString,f.Options).CreateNoticeReader();
        NodeNotice? reopened;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))reopened=await independentlyReopened.DetailAsync("atomic");
        await ExecuteFixtureSqlAsync(f.ConnectionString,"DROP TRIGGER fixture_notice_late_update;");
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
            await publisher.PublishAsync(old with {Revision=2,Body="new body",ChangeRevision=2,ChangeRef="change-2"});
        NodeNotice? retry;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))retry=await reader.DetailAsync("atomic");
        return new{interrupted,before,after,reopened,retry,
            final=await StateAsync(f.ConnectionString),nativeWindowsEvidence=false,scope="same-host"};
    }

    [Fact]
    public async Task O_AF6F5C359B10() => output.WriteLine("S206_NOTICE_INTEGRATION:"+JsonSerializer.Serialize(await ObserveMembershipAsync()));

    internal static async Task<object> ObserveMembershipAsync()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        await using var host=await NoticeHost.StartAsync(f);
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        var reader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        await f.Store.SetUserDisabledAsync(f.Second.AccountId,true);
        var from=DateTimeOffset.UtcNow.AddMinutes(-1);var until=DateTimeOffset.UtcNow.AddMinutes(5);
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
        {
            await publisher.PublishAsync(new("all-existing",1,"all body","all",null,from,until,true,1,"all-change"));
            await publisher.PublishAsync(new("node-existing",1,"node body","node",f.Options.NodeId,from,until,true,1,"node-change"));
            await publisher.PublishAsync(new("private-a",1,"private A","account",f.First.AccountId,from,until,true,1,"account-change"));
            await publisher.PublishAsync(new("expired",1,"expired body","all",null,from.AddMinutes(-5),from,true,1,"expired-change"));
        }
        var before=await StateAsync(f.ConnectionString);var disabledDenied=false;
        using(S206TestSupport.EnterCurrentContext(f.Second.Context))
            try{await reader.ListAsync();}catch(UnauthorizedAccessException){disabledDenied=true;}
        await f.Store.SetUserDisabledAsync(f.Second.AccountId,false);
        IReadOnlyList<NodeNotice> first,activated;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))first=await reader.ListAsync();
        using(S206TestSupport.EnterCurrentContext(f.Second.Context))activated=await reader.ListAsync();
        var after=await StateAsync(f.ConnectionString);
        await f.FaultAsync(f.Second,"foreign-home");var wrongHomeDenied=false;
        using(S206TestSupport.EnterCurrentContext(f.Second.Context))
            try{await reader.ListAsync();}catch(UnauthorizedAccessException){wrongHomeDenied=true;}
        return new{before,after,disabledDenied,wrongHomeDenied,
            first,activated,nativeWindowsEvidence=false,scope="same-host"};
    }

    [Fact]
    public async Task O_F1A2E019E2FE() => output.WriteLine("S206_NOTICE_INTEGRATION:"+JsonSerializer.Serialize(await ObserveExpiryAsync()));

    internal static async Task<object> ObserveExpiryAsync()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        await using var host=await NoticeHost.StartAsync(f);
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        var reader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        var expires=DateTimeOffset.UtcNow.AddSeconds(2);
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
        {
            await publisher.PublishAsync(new("expiring",1,"expiring body","all",null,expires.AddMinutes(-1),expires,true,1,"expiry-change"));
            await publisher.PublishAsync(new("still-valid",1,"valid body","all",null,expires.AddMinutes(-1),expires.AddMinutes(5),true,1,"valid-change"));
        }
        var before=await StateAsync(f.ConnectionString);
        using var current=S206TestSupport.EnterCurrentContext(f.First.Context);
        var initial=await reader.ListAsync();var initialDetail=await reader.DetailAsync("expiring");var initialCount=await reader.UnreadCountAsync();
        var wait=expires-DateTimeOffset.UtcNow+TimeSpan.FromMilliseconds(20);
        if(wait>TimeSpan.Zero)await Task.Delay(wait);
        var listed=await reader.ListAsync();var expiredDetail=await reader.DetailAsync("expiring");var count=await reader.UnreadCountAsync();
        var expiredRead=await reader.MarkReadAsync("expiring",1);var afterExpired=await StateAsync(f.ConnectionString);
        var validDetail=await reader.DetailAsync("still-valid");var validRead=await reader.MarkReadAsync("still-valid",1);
        return new{before,initial,initialDetail,initialCount,
            listed,expiredDetail,count,expiredRead,afterExpired,validDetail,validRead,expires,
            observedUtc=DateTimeOffset.UtcNow,nativeWindowsEvidence=false,scope="same-host with no projection refresh"};
    }

    private static async Task ExecuteFixtureSqlAsync(string connectionString,string sql)
    {
        await using var connection=new SqliteConnection(connectionString);await connection.OpenAsync();
        await using var command=connection.CreateCommand();command.CommandText=sql;await command.ExecuteNonQueryAsync();
    }

    [Fact]
    public async Task O_04DE2124065A() => await EmitEligibilityAsync();
    [Fact]
    public async Task O_A59C66EA9D03() => await EmitEligibilityAsync();
    [Fact]
    public async Task O_4820F52CA2AD() => await EmitEligibilityAsync();
    [Fact]
    public async Task O_980F4FF195AC() => await EmitEligibilityAsync();
    [Fact]
    public async Task O_BC2947090115()
    {
        var matrix=await ObserveEligibilityAsync();
        var membership=await ObserveMembershipAsync();var expiry=await ObserveExpiryAsync();var forgery=await ObserveForgeryAsync();
        output.WriteLine("S206_NOTICE_FIXTURE:"+JsonSerializer.Serialize(new{matrix,membership,expiry,forgery}));
    }
    [Fact]
    public async Task O_F3B019B69748() => await EmitEligibilityAsync();

    private async Task EmitEligibilityAsync() => output.WriteLine("S206_NOTICE_INTEGRATION:"+JsonSerializer.Serialize(await ObserveEligibilityAsync()));

    private static async Task<object> ObserveEligibilityAsync()
    {
        // Every exact bound case independently invokes actual operations. Common
        // fixture construction does not substitute another case's result/receipt.
        await using var f=await S206AuthorityFixture.CreateAsync();
        await using var host=await NoticeHost.StartAsync(f);
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        var reader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        var from=DateTimeOffset.UtcNow.AddMinutes(-1);var until=DateTimeOffset.UtcNow.AddMinutes(5);
        var originals=new[]
        {
            new NodeNoticePublication("all",1,"all body","all",null,from,until,true,1,"all-ref"),
            new NodeNoticePublication("node",1,"node body","node",f.Options.NodeId,from,until,true,1,"node-ref"),
            new NodeNoticePublication("only-a",1,"private A","account",f.First.AccountId,from,until,true,1,"a-ref"),
            new NodeNoticePublication("only-b",1,"private B","account",f.Second.AccountId,from,until,true,1,"b-ref"),
            new NodeNoticePublication("other-node",1,"foreign body","node","other-node",from,until,true,1,"foreign-ref"),
            new NodeNoticePublication("future",1,"future body","all",null,until,until.AddMinutes(5),true,1,"future-ref"),
            new NodeNoticePublication("expired",1,"expired body","all",null,from.AddMinutes(-2),from,true,1,"expired-ref")
        };
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
            foreach(var notice in originals)await publisher.PublishAsync(notice);
        var baseline=await StateAsync(f.ConnectionString);
        var contentA=f.ContentHash(f.First);var contentB=f.ContentHash(f.Second);
        var accountObservations=new List<object>();
        foreach(var account in new[]{f.First,f.Second})
        {
            using var current=S206TestSupport.EnterCurrentContext(account.Context);
            var list=await reader.ListAsync();var count=await reader.UnreadCountAsync();
            var details=new Dictionary<string,NodeNotice?>();
            foreach(var notice in originals)details.Add(notice.NoticeId,await reader.DetailAsync(notice.NoticeId));
            details.Add("unknown",await reader.DetailAsync("unknown"));
            accountObservations.Add(new{account=account.AccountId,list,count,details});
        }
        var afterQuery=await StateAsync(f.ConnectionString);
        bool ownRead,repeatRead,foreignRead,staleRead,unknownRead;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
        {
            ownRead=await reader.MarkReadAsync("only-a",1);repeatRead=await reader.MarkReadAsync("only-a",1);
            foreignRead=await reader.MarkReadAsync("only-b",1);staleRead=await reader.MarkReadAsync("only-a",2);
            unknownRead=await reader.MarkReadAsync("unknown",1);
        }
        var afterRead=await StateAsync(f.ConnectionString);
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
            await publisher.PublishAsync(originals.Single(n=>n.NoticeId=="only-a") with {Revision=2,Body="private A revised",ChangeRevision=2,ChangeRef="a-ref-2"});
        NodeNotice? newRevision;bool newRead;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
        {
            newRevision=await reader.DetailAsync("only-a");newRead=await reader.MarkReadAsync("only-a",2);
        }
        var afterNewRead=await StateAsync(f.ConnectionString);
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
            await publisher.PublishAsync(originals.Single(n=>n.NoticeId=="all") with {Active=false,ChangeRevision=2,ChangeRef="all-withdrawn"});
        var withdrawal=new List<object>();
        foreach(var account in new[]{f.First,f.Second})
        {
            using var current=S206TestSupport.EnterCurrentContext(account.Context);
            withdrawal.Add(new{account=account.AccountId,list=await reader.ListAsync(),detail=await reader.DetailAsync("all"),
                count=await reader.UnreadCountAsync(),read=await reader.MarkReadAsync("all",1)});
        }
        var final=await StateAsync(f.ConnectionString);
        var authority=new List<object>();
        foreach(var mode in new[]{"no-context","forged-context","forged-admin","revoked","foreign-home","missing-home","foreign-local","stale-projection"})
            authority.Add(await ObserveModeAsync(mode));
        return new{baseline,afterQuery,accountObservations,
            ownRead,repeatRead,foreignRead,staleRead,unknownRead,afterRead,newRevision,newRead,afterNewRead,withdrawal,final,authority,
            expectedAccount=f.First.AccountId,otherAccount=f.Second.AccountId,nodeId=f.Options.NodeId,
            privateContentUnchanged=contentA==f.ContentHash(f.First)&&contentB==f.ContentHash(f.Second),nativeWindowsEvidence=false,scope="same-host"};
    }

    [Fact]
    public async Task O_39AACBD7EDD7() => await EmitForgeryAsync();
    [Fact]
    public async Task O_444FAE230351() => await EmitForgeryAsync();

    private async Task EmitForgeryAsync() => output.WriteLine("S206_NOTICE_FORGERY:"+JsonSerializer.Serialize(await ObserveForgeryAsync()));

    private static async Task<object> ObserveForgeryAsync()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        await using var host=await NoticeHost.StartAsync(f);
        var reader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        var original=new NodeNoticePublication("protected",1,"protected body","all",null,
            DateTimeOffset.UtcNow.AddMinutes(-1),DateTimeOffset.UtcNow.AddMinutes(5),true,1,"protected-change");
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))await publisher.PublishAsync(original);
        var before=await StateAsync(f.ConnectionString);
        using var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();
        var endpoint="http://127.0.0.1:"+((IPEndPoint)listener.LocalEndpoint).Port;
        var attempted=new List<object>();
        foreach(var actor in new[]{"project","port","forged-admin"})
        foreach(var operation in new[]{"insert","replace"})
        {
            var input=JsonSerializer.SerializeToElement(new{NoticeId=operation=="insert"?"forged":"protected",Revision=2L,
                Body="forged body",AudienceKind="all",AudienceId=(string?)null,ValidFromUtc=original.ValidFromUtc,
                ValidUntilUtc=original.ValidUntilUtc,Active=true,ChangeRevision=2L,ChangeRef="forged-ref",
                NodeId=f.Options.NodeId,Port=9000,IsAdmin=true,Adapter="project-supplied",Endpoint=endpoint});
            var publication=input.Deserialize<NodeNoticePublication>()!;
            var context=actor=="forged-admin"?f.First.Context with {Roles=new HashSet<string>{PhaseAAuth.AdminRole}}:
                actor=="port"?f.First.Context with {PrincipalId=f.Options.NodeId+":9000"}:f.First.Context;
            var denied=false;
            using(S206TestSupport.EnterCurrentContext(context))
                try{await publisher.PublishAsync(publication);}catch(UnauthorizedAccessException){denied=true;}
            attempted.Add(new{actor,operation,denied,stateUnchanged=(await StateAsync(f.ConnectionString)).GetRawText()==before.GetRawText()});
        }
        var constructors=new List<object>();
        foreach(var type in new[]{typeof(NodeNoticeReader),typeof(CentralNoticePublisher)})
        {
            var refused=false;
            try{_ = Activator.CreateInstance(type);}catch(MissingMethodException){refused=true;}
            constructors.Add(new{name=type.Name,refused,publicConstructors=type.GetConstructors().Length});
        }
        var node=new OrdinaryMetadataSurfaceInspector(host.Host.Services.GetRequiredService<NodeProjectMetadata>());
        var projectEscape=node.PublicNoticeOrWriterEscapes();
        var routes=host.Host.Services.GetRequiredService<EndpointDataSource>().Endpoints.OfType<RouteEndpoint>()
            .Select(e=>e.RoutePattern.RawText).Where(t=>t is not null).ToArray();
        using var http=new HttpClient{BaseAddress=new Uri(Environment.GetEnvironmentVariable("APP_BIND_URL")!),Timeout=TimeSpan.FromSeconds(2)};
        http.DefaultRequestHeaders.Authorization=new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer",f.SyntheticToken(f.First));
        using var response=await http.PostAsync("/api/notices/ingest",new StringContent("{\"nodeId\":\"test-physical-node\",\"port\":9000}",System.Text.Encoding.UTF8,"application/json"));
        var endpointContacts=0;while(listener.Pending()){using var contact=listener.AcceptTcpClient();endpointContacts++;}
        NodeNotice? positive;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))positive=await reader.DetailAsync("protected");
        return new{attempted,constructors,projectEscape,routes,
            missingIngestStatus=(int)response.StatusCode,endpointContacts,positive,before,after=await StateAsync(f.ConnectionString),
            selectedReaderUnchanged=ReferenceEquals(reader,host.Host.Services.GetRequiredService<NodeNoticeReader>()),
            selectedPublisherUnchanged=ReferenceEquals(publisher,host.Host.Services.GetRequiredService<CentralNoticePublisher>()),
            nativeWindowsEvidence=false,scope="same-host fixed adapter"};
    }

    private sealed class OrdinaryMetadataSurfaceInspector(NodeProjectMetadata ordinary)
    {
        internal string[] PublicNoticeOrWriterEscapes()=>ordinary.GetType().GetMethods(BindingFlags.Public|BindingFlags.Instance)
            .Where(m=>m.ReturnType==typeof(NodeNoticeReader)||m.ReturnType==typeof(CentralNoticePublisher)||
                m.ReturnType==typeof(PhaseAMetadataStore)||m.ReturnType==typeof(IServiceProvider)||m.ReturnType==typeof(SqliteConnection))
            .Select(m=>m.Name).ToArray();
    }

    [Fact]
    public async Task O_863894E117B8()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        await using var host=await NoticeHost.StartAsync(f);
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        var reader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        var marker=Path.Combine(f.First.Project.RepoPath,"notice-command-must-not-run.txt");
        var body=JsonSerializer.Serialize(new{command="touch "+marker,agent="start project agent",
            install="install untrusted helper",node_id="other-node",port=9000});
        var before=await RunRowsAsync(f.ConnectionString);var contentA=f.ContentHash(f.First);var contentB=f.ContentHash(f.Second);
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
            await publisher.PublishAsync(new("inert",1,body,"account",f.First.AccountId,
                DateTimeOffset.UtcNow.AddMinutes(-1),DateTimeOffset.UtcNow.AddMinutes(5),true,1,"inert-change"));
        var stateBeforeReads=await StateAsync(f.ConnectionString);
        NodeNotice? detail;IReadOnlyList<NodeNotice> list;int count;bool read;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
        {
            list=await reader.ListAsync();detail=await reader.DetailAsync("inert");count=await reader.UnreadCountAsync();
        }
        var afterQueries=await StateAsync(f.ConnectionString);
        using(S206TestSupport.EnterCurrentContext(f.First.Context))read=await reader.MarkReadAsync("inert",1);
        NodeNotice? foreign;bool foreignRead;
        using(S206TestSupport.EnterCurrentContext(f.Second.Context))
        {foreign=await reader.DetailAsync("inert");foreignRead=await reader.MarkReadAsync("inert",1);}
        var final=await StateAsync(f.ConnectionString);var after=await RunRowsAsync(f.ConnectionString);
        var markerAbsent=!File.Exists(marker);
        // A separate ordinary IO control proves this test observes real owned files;
        // the adversarial notice strings themselves are never executed by the fixture.
        var observerControl=Path.Combine(f.First.Project.RepoPath,"notice-observer-control.txt");
        await File.WriteAllTextAsync(observerControl,"observed control");
        var observerWorks=await File.ReadAllTextAsync(observerControl)=="observed control";
        await host.DisposeAsync();
        var publicRecords=JsonSerializer.Serialize(new{stateBeforeReads,afterQueries,final,list,detail,count,read,foreign,foreignRead});
        var secrets=new[]{f.SyntheticToken(f.First),f.SyntheticToken(f.Second),f.SyntheticToken(f.Admin),
            f.First.Context.CredentialId,f.Second.Context.CredentialId,f.Admin.Context.CredentialId};
        var recordMatches=secrets.Count(x=>publicRecords.Contains(x,StringComparison.Ordinal));
        var logMatches=secrets.Count(x=>host.CapturedLogs.Contains(x,StringComparison.Ordinal));
        output.WriteLine("S206_NOTICE_BODY:"+JsonSerializer.Serialize(new{bodyReturnedUnchanged=detail?.Body==body,
            listBodyReturnedUnchanged=list.Single().Body==body,count,read,foreignBodyReturned=foreign is not null,foreignRead,
            markerAbsent,observerWorks,before,after,stateBeforeReads,afterQueries,final,
            privateContentUnchanged=contentA==f.ContentHash(f.First)&&contentB==f.ContentHash(f.Second),recordMatches,logMatches,
            logChannelObserved=host.CapturedLogs.Length>0,expectedAccount=f.First.AccountId,
            runtimeWindows=OperatingSystem.IsWindows(),nativeWindowsEvidence=false,
            limits="Actual project-file/run-state effects and service-only scope; no Windows process isolation proof."}));
    }

    private static async Task<JsonElement> RunRowsAsync(string connectionString)
    {
        await using var connection=new SqliteConnection(connectionString);await connection.OpenAsync();
        await using var command=connection.CreateCommand();command.CommandText="SELECT id,project_id,status FROM runs ORDER BY id;";
        var rows=new List<object[]>();await using var values=await command.ExecuteReaderAsync();
        while(await values.ReadAsync())rows.Add(new object[]{values.GetString(0),values.GetString(1),values.GetString(2)});
        return JsonSerializer.SerializeToElement(rows);
    }

    [Fact]
    public async Task O_C11143A9F8A7()
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        await using var host=await NoticeHost.StartAsync(f);
        var publisher=host.Host.Services.GetRequiredService<CentralNoticePublisher>();
        var reader=host.Host.Services.GetRequiredService<NodeNoticeReader>();
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
            await publisher.PublishAsync(new("local-scope",1,"local contract body","all",null,
                DateTimeOffset.UtcNow.AddMinutes(-1),DateTimeOffset.UtcNow.AddMinutes(5),true,1,"local-change"));
        NodeNotice? actual;bool read;
        using(S206TestSupport.EnterCurrentContext(f.First.Context))
        {actual=await reader.DetailAsync("local-scope");read=await reader.MarkReadAsync("local-scope",1);}
        await using var connection=new SqliteConnection(f.ConnectionString);await connection.OpenAsync();
        await using var command=connection.CreateCommand();command.CommandText="PRAGMA database_list;";
        var databases=new List<string>();var expectedFile=false;
        await using(var rows=await command.ExecuteReaderAsync())
            while(await rows.ReadAsync())
            {
                databases.Add(rows.GetString(1));
                if(rows.GetString(1)=="main")expectedFile=Path.GetFullPath(rows.GetString(2))==Path.GetFullPath(f.Options.MetadataDatabasePath);
            }
        var hash=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(typeof(PhaseAMetadataStore).Assembly.Location))).ToLowerInvariant();
        output.WriteLine("S206_NOTICE_LIMITS:"+JsonSerializer.Serialize(new{actual,read,databases,expectedFile,
            processId=Environment.ProcessId,runtimeOs=System.Runtime.InteropServices.RuntimeInformation.OSDescription,
            runtimeVersion=Environment.Version.ToString(),productionAssemblySha256=hash,
            scope=f.Options.NodeScope,sameProcessHost=host.Host.Services.GetRequiredService<NodeNoticeReader>()==reader,
            unproved=new[]{"cross-host-transport","offline-recovery","full-notification-product","native-Windows-isolation"},
            nativeWindowsEvidence=false}));
    }

    private static async Task<object> ObserveModeAsync(string mode)
    {
        await using var f=await S206AuthorityFixture.CreateAsync();
        // Direct, existing production bindings are exercised before optional future seam discovery.
        await SqliteMetadataSchema.InitializeSingleNodeTestAsync(f.ConnectionString,f.Options);
        var central=new PhaseAMetadataStore(f.ConnectionString,f.Options);
        await using var host=await NoticeHost.StartAsync(f);
        var assembly=typeof(PhaseAMetadataStore).Assembly;
        var readerType=assembly.GetType("PhaseA.Platform.Data.NodeNoticeReader");
        var publisherType=assembly.GetType("PhaseA.Platform.Data.CentralNoticePublisher");
        var reader=readerType is null?null:host.Host.Services.GetService(readerType);
        var publisher=publisherType is null?null:host.Host.Services.GetService(publisherType);
        if(reader is null || publisher is null)
            return new{mode,available=false,observation="actual protected composition has no usable local notification capability"};
        var ordinaryEscapes=new List<string>();
        foreach(var name in new[]{"ProjectCreationService","ProjectDraftImportService","ProjectInitializationService",
            "ProjectInitializationRecoveryService","HeavyRunnerQueueService","RunCancellationService",
            "ArtifactReadbackService","ProjectAssetInventoryService","ProjectAssetLibraryService",
            "ProjectPackageService","ProjectWebPreviewService","ChatService","PrototypeCommandService",
            "WorkspaceStorageService","RestoreService"})
        {
            var type=assembly.GetTypes().Single(t=>t.Name==name);
            var value=host.Host.Services.GetService(type)
                ?? host.Host.Services.GetServices<IHostedService>().SingleOrDefault(type.IsInstanceOfType)
                ?? throw new InvalidOperationException("Actual registered ordinary consumer unavailable: "+name);
            foreach(var field in type.GetFields(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic))
            {
                var held=field.GetValue(value);
                if(held is not null && (readerType!.IsInstanceOfType(held)||publisherType!.IsInstanceOfType(held)||held is IServiceProvider))
                    ordinaryEscapes.Add(name+"."+field.Name);
            }
        }
        foreach(var m in typeof(NodeProjectMetadata).GetMethods(BindingFlags.Public|BindingFlags.Instance))
            if(m.ReturnType==readerType||m.ReturnType==publisherType)
                ordinaryEscapes.Add("NodeProjectMetadata."+m.Name);
        var publicConstruction=readerType!.GetConstructors().Length+publisherType!.GetConstructors().Length;
        var notice="account-notice";var shared="all-notice";
        using(S206TestSupport.EnterCurrentContext(f.Admin.Context))
        {
            await PublishAsync(publisher,notice,"account",f.First.AccountId);
            await PublishAsync(publisher,shared,"all",null);
        }
        var baseline=await StateAsync(f.ConnectionString);
        var context=mode switch
        {
            "no-context"=>null,
            "forged-context"=>f.First.Context with {AccountId=f.Second.AccountId},
            "forged-admin"=>f.First.Context with {Roles=new HashSet<string>{PhaseAAuth.AdminRole}},
            _=>f.First.Context
        };
        if(mode is "revoked" or "foreign-home" or "missing-home" or "foreign-local" or "stale-projection")
            await f.FaultAsync(f.First,mode);
        var before=await StateAsync(f.ConnectionString);
        var operations=new Dictionary<string,JsonElement>();var denials=new List<string>();
        using(var current=context is null?null:S206TestSupport.EnterCurrentContext(context))
        {
            foreach(var operation in new[]{"ListAsync","DetailAsync","UnreadCountAsync","MarkReadAsync"})
            {
                try
                {
                    object?[] args=operation=="DetailAsync"?[notice]:operation=="MarkReadAsync"?[notice,1L]:[];
                    operations[operation]=await CallAsync(reader,operation,args);
                }
                catch(UnauthorizedAccessException){denials.Add(operation);}
            }
        }
        var after=await StateAsync(f.ConnectionString);
        JsonElement? otherList=null;var otherRead=false;var otherDetail=false;
        if(mode=="valid-pair")
        {
            using var other=S206TestSupport.EnterCurrentContext(f.Second.Context);
            otherList=await CallAsync(reader,"ListAsync");
            otherRead=(await CallAsync(reader,"MarkReadAsync",notice,1L)).GetBoolean();
            otherDetail=(await CallAsync(reader,"DetailAsync",notice)).ValueKind!=JsonValueKind.Null;
        }
        var final=await StateAsync(f.ConnectionString);
        var publishDenied=false;
        using(var current=context is null?null:S206TestSupport.EnterCurrentContext(context))
        {
            try {await PublishAsync(publisher,"forged-notice","all",null);}
            catch(UnauthorizedAccessException){publishDenied=true;}
        }
        var postAttack=await StateAsync(f.ConnectionString);
        return new{mode,available=true,operations,denials,baseline,before,after,otherList,otherRead,otherDetail,
            final,postAttack,publishDenied,publicConstruction,ordinaryEscapes,
            expectedAccount=f.First.AccountId,otherAccount=f.Second.AccountId,
            privateContentUnchanged=f.ContentHash(f.First)==Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
                System.Text.Encoding.UTF8.GetBytes(f.First.Sentinel)))};
    }

    private static async Task PublishAsync(object publisher,string id,string audience,string? audienceId)
    {
        var method=publisher.GetType().GetMethod("PublishAsync")
            ?? throw new InvalidOperationException("Declared publisher has no executable publication operation.");
        var input=new {NoticeId=id,Revision=1L,Body="Inert fixture notice",AudienceKind=audience,AudienceId=audienceId,
            ValidFromUtc=DateTimeOffset.UtcNow.AddMinutes(-1),ValidUntilUtc=DateTimeOffset.UtcNow.AddMinutes(5),
            Active=true,ChangeRevision=1L,ChangeRef="fixture-approved-local-change"};
        var argument=JsonSerializer.Deserialize(JsonSerializer.Serialize(input),method.GetParameters()[0].ParameterType)!;
        await CallAsync(publisher,"PublishAsync",argument);
    }

    private static async Task<JsonElement> CallAsync(object target,string name,params object?[] args)
    {
        var method=target.GetType().GetMethod(name,BindingFlags.Public|BindingFlags.Instance)
            ?? throw new InvalidOperationException("Present capability lacks its declared executable operation: "+name);
        var parameters=method.GetParameters();var actual=new object?[parameters.Length];
        for(var i=0;i<actual.Length;i++)actual[i]=i<args.Length?args[i]:parameters[i].HasDefaultValue?parameters[i].DefaultValue:
            throw new InvalidOperationException("Unbound required operation parameter.");
        Task task;
        try {task=(Task)method.Invoke(target,actual)!;}
        catch(TargetInvocationException ex) when(ex.InnerException is UnauthorizedAccessException){throw ex.InnerException;}
        await task;
        var result=task.GetType().GetProperty("Result")?.GetValue(task);
        return JsonSerializer.SerializeToElement(result,result?.GetType()??typeof(object));
    }

    private static async Task<JsonElement> StateAsync(string connectionString)
    {
        await using var connection=new SqliteConnection(connectionString);await connection.OpenAsync();
        var values=new Dictionary<string,List<object?[]>>();
        foreach(var table in new[]{"notice_facts","node_notice_projections","notice_read_state"})
        {
            await using var command=connection.CreateCommand();command.CommandText="SELECT * FROM "+table+" ORDER BY 1,2,3;";
            await using var rows=await command.ExecuteReaderAsync();var data=new List<object?[]>();
            while(await rows.ReadAsync())data.Add(Enumerable.Range(0,rows.FieldCount).Select(i=>rows.IsDBNull(i)?null:rows.GetValue(i)).ToArray());
            values.Add(table,data);
        }
        return JsonSerializer.SerializeToElement(values);
    }

    private sealed class NoticeHost(S206AuthorityFixture fixture,IHost host,Task program,Dictionary<string,string?> previous,TextWriter oldOut,TextWriter oldError,StringWriter logOut,StringWriter logError):IAsyncDisposable
    {
        private bool _disposed;
        internal IHost Host=>host;
        internal string CapturedLogs=>logOut.ToString()+logError.ToString();
        internal static async Task<NoticeHost> StartAsync(S206AuthorityFixture f,string roles="entry,production")
        {
            using var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();var port=((IPEndPoint)listener.LocalEndpoint).Port;listener.Stop();
            var address="http://127.0.0.1:"+port;
            var settings=new Dictionary<string,string?>
            {
                ["APP_BIND_URL"]=address,["ASPNETCORE_URLS"]=address,["PUBLIC_BASE_URL"]="https://localhost",
                ["PHASEA_METADATA_DB_PATH"]=f.Options.MetadataDatabasePath,["HOSTED_WORKSPACE_ROOT"]=f.Options.HostedWorkspaceRoot,
                ["PHASEA_REPOSITORY_ROOT"]=S206TestSupport.RepositoryRoot,["PHASEA_ADMIN_TOKEN_HASH"]=PhaseAAuth.HashTokenForStorage(f.SyntheticToken(f.Admin)),
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
                return new NoticeHost(f,host,program,previous,oldOut,oldError,logOut,logError);
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
