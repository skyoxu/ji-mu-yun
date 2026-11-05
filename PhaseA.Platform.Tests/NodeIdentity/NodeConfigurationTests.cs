using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.NodeIdentity;

public sealed class NodeConfigurationTests(ITestOutputHelper output)
{
    // ADR-0061: this real parser observation is supplementary, never provenance/authority proof.
    // ADR-0061: real existing parser/HTTPS validation; source claim assessment remains in Python.
    // ADR-0061: real built metadata and a fresh shared in-memory schema; no deployment or WAL claim.
    [Fact]
    public async Task StackPinsAndWindowsConstraintsPreserved()
    {
        var platform = typeof(PhaseAPlatformOptionsLoader).Assembly;
        var configuration = new DirectoryInfo(AppContext.BaseDirectory).Parent!.Name;
        var productionOutput = Path.Combine(S206TestSupport.RepositoryRoot, "PhaseA.Platform", "bin", configuration, "net8.0");
        var depsPath = Path.Combine(productionOutput, "PhaseA.Platform.deps.json");
        using var deps = JsonDocument.Parse(File.ReadAllBytes(depsPath));
        var libraries = deps.RootElement.GetProperty("libraries").EnumerateObject().Select(x => x.Name).Order().ToArray();
        var sourceDll = Path.Combine(productionOutput, "PhaseA.Platform.dll");
        var connectionString = new Microsoft.Data.Sqlite.SqliteConnectionStringBuilder
        {
            DataSource = "stack-" + Guid.NewGuid().ToString("N"), Mode = Microsoft.Data.Sqlite.SqliteOpenMode.Memory,
            Cache = Microsoft.Data.Sqlite.SqliteCacheMode.Shared, Pooling = false
        }.ToString();
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT sqlite_version();";
        var engine = (string)(await command.ExecuteScalarAsync())!;
        command.CommandText = "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='accounts';";
        var schemaTables = Convert.ToInt64(await command.ExecuteScalarAsync());
        command.CommandText = "PRAGMA database_list;";
        var databases = new List<object>();
        await using (var rows = await command.ExecuteReaderAsync())
            while (await rows.ReadAsync()) databases.Add(new { name = rows.GetString(1), file = rows.GetString(2) });
        output.WriteLine("S206_STACK:" + JsonSerializer.Serialize(new
        {
            schema = "s206.built-stack.v1", framework = System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription,
            platform = StackAssemblyMetadata(platform), test = StackAssemblyMetadata(GetType().Assembly),
            aspnet = StackAssemblyMetadata(typeof(Microsoft.AspNetCore.Builder.WebApplication).Assembly),
            sqlite = StackAssemblyMetadata(typeof(Microsoft.Data.Sqlite.SqliteConnection).Assembly),
            batteries = StackAssemblyMetadata(typeof(SQLitePCL.Batteries_V2).Assembly),
            schemaOwnerAssembly = typeof(SqliteMetadataSchema).Assembly.GetName().FullName,
            builtAssemblyIdentity = System.Reflection.AssemblyName.GetAssemblyName(sourceDll).FullName,
            builtAssemblySha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(sourceDll))).ToLowerInvariant(),
            depsTarget = deps.RootElement.GetProperty("runtimeTarget").GetProperty("name").GetString(),
            depsSha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(depsPath))).ToLowerInvariant(),
            sqliteLibraries = libraries.Where(x => x.Contains("sqlite", StringComparison.OrdinalIgnoreCase)).ToArray(),
            engineVersion = engine, schemaAccountsTables = schemaTables, databases,
            isWindows = OperatingSystem.IsWindows(), osDescription = System.Runtime.InteropServices.RuntimeInformation.OSDescription
        }));
    }

    private static object StackAssemblyMetadata(System.Reflection.Assembly assembly)
    {
        var target = assembly.GetCustomAttributes(typeof(System.Runtime.Versioning.TargetFrameworkAttribute), false)
            .Cast<System.Runtime.Versioning.TargetFrameworkAttribute>().SingleOrDefault()?.FrameworkName;
        var name = assembly.GetName();
        return new
        {
            name = name.Name, identity = name.FullName, version = name.Version!.ToString(), target,
            productVersion = System.Diagnostics.FileVersionInfo.GetVersionInfo(assembly.Location).ProductVersion,
            sha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(assembly.Location))).ToLowerInvariant()
        };
    }

    // ADR-0061 AD15: actual identity validation fails closed without any service/network action.
    [Fact]
    public void O_116AC63F1FFB()
    {
        var observations = new List<object>();
        foreach (var topology in new[] { "single_service", "independent_services", "cross_host" })
        {
            var settings = new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "topology-" + Guid.NewGuid().ToString("N")),
                ["PHASEA_SERVICE_STATE"] = "test", ["PHASEA_NODE_ID"] = "isolated-config-node",
                ["PHASEA_NODE_SCOPE"] = "single_node_test", ["PHASEA_NODE_TOPOLOGY"] = topology,
                ["PHASEA_ENABLED_ROLES"] = "entry,production", ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = "false"
            };
            var rejected = false; string? diagnostic = null;
            PhaseAPlatformOptions? configuration = null;
            try { configuration = PhaseAPlatformOptionsLoader.FromDictionary(settings); configuration.ValidateServiceIdentity(); }
            catch (PhaseAPlatformConfigException error) { rejected = true; diagnostic = error.Message; }
            observations.Add(new { requested = topology, actual = configuration?.NodeTopology, parserReturned = configuration is not null, rejected, diagnostic,
                node = configuration?.NodeId, scope = configuration?.NodeScope, roles = configuration?.EnabledRoles.Order().ToArray() });
        }
        output.WriteLine("S206_TOPOLOGY_BOUNDARY:" + JsonSerializer.Serialize(new
        {
            schema = "s206.config-topology-boundary.v1", observations,
            sourceHashes = new[] { "PhaseA.Platform/Configuration/PhaseAPlatformOptions.cs", "PhaseA.Platform/Configuration/PhaseAPlatformOptionsLoader.cs",
                "docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md", "docs/workflows/phase-service-node-identity-and-roles.md" }
                .ToDictionary(p => p, p => Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(Path.Combine(S206TestSupport.RepositoryRoot, p)))).ToLowerInvariant())
        }));
    }

    [Fact]
    public void O_3541A1914CAF()
    {
        var settings = new Dictionary<string, string?>
        {
            ["PHASEA_SERVICE_STATE"] = "test",
            ["PUBLIC_BASE_URL"] = "https://localhost",
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s162-scope-" + Guid.NewGuid().ToString("N"))
        };
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(settings);
        settings["PUBLIC_BASE_URL"] = "http://localhost";
        var insecureRejected = false;
        try { _ = PhaseAPlatformOptionsLoader.FromDictionary(settings); }
        catch (PhaseAPlatformConfigException) { insecureRejected = true; }
        output.WriteLine("S206_SCOPE_BOUNDARY:" + JsonSerializer.Serialize(new
        {
            @case = "O-3541A1914CAF", phaseServiceState = configuration.PhaseServiceState,
            httpsAccepted = Uri.TryCreate(configuration.PublicBaseUrl, UriKind.Absolute, out var publicUrl) && publicUrl.Scheme == Uri.UriSchemeHttps,
            insecurePublicUrlRejected = insecureRejected,
            actualConfigurationType = configuration.GetType().FullName,
            productionRoleEnabled = configuration.ProductionRoleEnabled
        }));
    }

    // ADR-0061: real existing parser/HTTPS validation; source claim assessment remains in Python.
    [Fact]
    public void O_57C432D34201()
    {
        var settings = new Dictionary<string, string?>
        {
            ["PHASEA_SERVICE_STATE"] = "test",
            ["PUBLIC_BASE_URL"] = "https://localhost",
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s162-scope-" + Guid.NewGuid().ToString("N"))
        };
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(settings);
        settings["PUBLIC_BASE_URL"] = "http://localhost";
        var insecureRejected = false;
        try { _ = PhaseAPlatformOptionsLoader.FromDictionary(settings); }
        catch (PhaseAPlatformConfigException) { insecureRejected = true; }
        output.WriteLine("S206_SCOPE_BOUNDARY:" + JsonSerializer.Serialize(new
        {
            @case = "O-57C432D34201", phaseServiceState = configuration.PhaseServiceState,
            httpsAccepted = Uri.TryCreate(configuration.PublicBaseUrl, UriKind.Absolute, out var publicUrl) && publicUrl.Scheme == Uri.UriSchemeHttps,
            insecurePublicUrlRejected = insecureRejected,
            actualConfigurationType = configuration.GetType().FullName,
            productionRoleEnabled = configuration.ProductionRoleEnabled
        }));
    }

    // ADR-0061: real existing parser/HTTPS validation; source claim assessment remains in Python.
    [Fact]
    public void O_5FB690F6AA79()
    {
        var settings = new Dictionary<string, string?>
        {
            ["PHASEA_SERVICE_STATE"] = "test",
            ["PUBLIC_BASE_URL"] = "https://localhost",
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s162-scope-" + Guid.NewGuid().ToString("N"))
        };
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(settings);
        settings["PUBLIC_BASE_URL"] = "http://localhost";
        var insecureRejected = false;
        try { _ = PhaseAPlatformOptionsLoader.FromDictionary(settings); }
        catch (PhaseAPlatformConfigException) { insecureRejected = true; }
        output.WriteLine("S206_SCOPE_BOUNDARY:" + JsonSerializer.Serialize(new
        {
            @case = "O-5FB690F6AA79", phaseServiceState = configuration.PhaseServiceState,
            httpsAccepted = Uri.TryCreate(configuration.PublicBaseUrl, UriKind.Absolute, out var publicUrl) && publicUrl.Scheme == Uri.UriSchemeHttps,
            insecurePublicUrlRejected = insecureRejected,
            actualConfigurationType = configuration.GetType().FullName,
            productionRoleEnabled = configuration.ProductionRoleEnabled
        }));
    }

    // ADR-0061: real existing parser/HTTPS validation; source claim assessment remains in Python.
    [Fact]
    public void O_B6F8A8621F40()
    {
        var settings = new Dictionary<string, string?>
        {
            ["PHASEA_SERVICE_STATE"] = "test",
            ["PUBLIC_BASE_URL"] = "https://localhost",
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s162-scope-" + Guid.NewGuid().ToString("N"))
        };
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(settings);
        settings["PUBLIC_BASE_URL"] = "http://localhost";
        var insecureRejected = false;
        try { _ = PhaseAPlatformOptionsLoader.FromDictionary(settings); }
        catch (PhaseAPlatformConfigException) { insecureRejected = true; }
        output.WriteLine("S206_SCOPE_BOUNDARY:" + JsonSerializer.Serialize(new
        {
            @case = "O-B6F8A8621F40", phaseServiceState = configuration.PhaseServiceState,
            httpsAccepted = Uri.TryCreate(configuration.PublicBaseUrl, UriKind.Absolute, out var publicUrl) && publicUrl.Scheme == Uri.UriSchemeHttps,
            insecurePublicUrlRejected = insecureRejected,
            actualConfigurationType = configuration.GetType().FullName,
            productionRoleEnabled = configuration.ProductionRoleEnabled
        }));
    }

    // ADR-0061: real existing parser/HTTPS validation; source claim assessment remains in Python.
    [Fact]
    public void O_E0AF971772C4()
    {
        var settings = new Dictionary<string, string?>
        {
            ["PHASEA_SERVICE_STATE"] = "test",
            ["PUBLIC_BASE_URL"] = "https://localhost",
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s162-scope-" + Guid.NewGuid().ToString("N"))
        };
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(settings);
        settings["PUBLIC_BASE_URL"] = "http://localhost";
        var insecureRejected = false;
        try { _ = PhaseAPlatformOptionsLoader.FromDictionary(settings); }
        catch (PhaseAPlatformConfigException) { insecureRejected = true; }
        output.WriteLine("S206_SCOPE_BOUNDARY:" + JsonSerializer.Serialize(new
        {
            @case = "O-E0AF971772C4", phaseServiceState = configuration.PhaseServiceState,
            httpsAccepted = Uri.TryCreate(configuration.PublicBaseUrl, UriKind.Absolute, out var publicUrl) && publicUrl.Scheme == Uri.UriSchemeHttps,
            insecurePublicUrlRejected = insecureRejected,
            actualConfigurationType = configuration.GetType().FullName,
            productionRoleEnabled = configuration.ProductionRoleEnabled
        }));
    }

    [Fact]
    public void O_A45D4EDED200()
    {
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_SERVICE_STATE"] = "test",
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s162-provenance-" + Guid.NewGuid().ToString("N"))
        });
        output.WriteLine("S206_SOURCE_PROVENANCE:" + JsonSerializer.Serialize(new
        {
            entry = "PhaseAPlatformOptionsLoader.FromDictionary", phaseServiceState = configuration.PhaseServiceState,
            actualConfigurationType = configuration.GetType().FullName,
            productionRoleEnabled = configuration.ProductionRoleEnabled
        }));
    }

    [Fact]
    public async Task O_C8FCBDB2A9F7()
    {
        var observations = new List<object>();
        foreach (var phase in new[] { "development", "test", "production" })
        {
            // Directly exercise the declared current production parser, without creating a substitute.
            var parsed = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
                ["PHASEA_SERVICE_STATE"] = phase,
                ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-options-" + Guid.NewGuid().ToString("N"))
            });
            Assert.Equal(phase, parsed.PhaseServiceState);
            foreach (var roles in new string?[] { null, "", "unknown", "entry", "production", "entry,production" })
                observations.Add(await S206TestSupport.ObserveRoleAsync(phase, roles));
        }
        Assert.Equal(18, observations.Count);
        output.WriteLine("S206_ROLE_OBSERVATIONS:" + JsonSerializer.Serialize(observations));
    }

    [Fact]
    public async Task O_C145D65BFB3C()
    {
        var root = Path.Combine(Path.GetTempPath(), "s206-capacity-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3"),
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces")
        });
        var connection = "Data Source=" + options.MetadataDatabasePath;
        await SqliteMetadataSchema.InitializeAsync(connection);
        var store = new PhaseAMetadataStore(connection, options);
        var first = await store.CreateUserAccountAsync("capacity-one", 1);
        var second = await store.CreateUserAccountAsync("capacity-two", 1);
        var observations = new List<object>();
        foreach (var policy in new[] { true, false })
            observations.Add(await S206TestSupport.ObserveRoleAsync("test", "entry,production", policy, root));
        var accounts = await store.ListAccountsAsync();
        Assert.Contains(accounts, item => item.AccountId == first.AccountId);
        Assert.Contains(accounts, item => item.AccountId == second.AccountId);
        output.WriteLine("S206_CAPACITY_OBSERVATIONS:" + JsonSerializer.Serialize(observations));
    }

    private async Task ObserveCapacityMatrixAsync(PhaseAPlatformOptions baseline)
    {
        var observations = new List<object>();
        var root = Path.Combine(Path.GetTempPath(), "s206-capacity-matrix-" + Guid.NewGuid().ToString("N"));
        foreach (var policy in new[] { false, true })
        foreach (var reference in new string?[] { null, "unknown-reference", "stale-reference", "unavailable-reference" })
        {
            var instance = policy ? "diagnostic-beta" : "diagnostic-alpha";
            observations.Add(await S206TestSupport.ObserveRoleAsync("test", "entry,production", policy,
                root, instance, reference, exerciseExistingProject: policy && reference == "unavailable-reference"));
        }
        Assert.Equal(8, observations.Count);
        var defaults = baseline;
        var overridden = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
            ["PHASEA_MAX_CONCURRENT_OTHER_RUNS"] = "2",
            ["PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS"] = "2"
        });
        var availability = new List<object>();
        foreach (var policy in new[] { false, true })
        {
            var local = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
                ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces"),
                ["PHASEA_METADATA_DB_PATH"] = Path.Combine(root, "metadata.sqlite3"),
                ["PHASEA_NODE_ID"] = "test-physical-node",
                ["PHASEA_NODE_SCOPE"] = "single_node_test",
                ["PHASEA_NODE_TOPOLOGY"] = "single_service",
                ["PHASEA_ENABLED_ROLES"] = "entry,production",
                ["PHASEA_ACCEPT_NEW_ACCOUNTS"] = policy ? "true" : "false"
            });
            using var host = new HostBuilder().ConfigureServices(services =>
            {
                services.AddSingleton(local);
                services.AddSingleton<NodeExecutionOptions>((NodeExecutionOptions)local);
                services.AddSingleton(new PhaseAMetadataStore("Data Source=" + local.MetadataDatabasePath, local));
                services.AddSingleton<NodeProjectMetadata>(services =>
                    (NodeProjectMetadata)services.GetRequiredService<PhaseAMetadataStore>());
                services.AddSingleton(new HeavyRunnerQueueService());
                services.AddKeyedSingleton("prototype-creation", new HeavyRunnerQueueService());
                services.AddKeyedSingleton("asset-generation", new HeavyRunnerQueueService());
                services.AddKeyedSingleton("web-preview", new HeavyRunnerQueueService());
                services.AddSingleton<ArtifactReadbackService>();
            }).Build();
            var reader = host.Services.GetRequiredService<ArtifactReadbackService>();
            var lifetime = host.Services.GetRequiredService<IHostApplicationLifetime>();
            // Safe runtime observation for a not-yet-implemented result, never missing-type RED.
            var read = reader.GetType().GetMethod("GetLocalNodeCapacity", Type.EmptyTypes);
            await host.StartAsync();
            availability.Add(new { policy, online = lifetime.ApplicationStarted.IsCancellationRequested &&
                !lifetime.ApplicationStopping.IsCancellationRequested, readback = JsonSerializer.SerializeToElement(
                    read?.Invoke(reader, null), new JsonSerializerOptions(JsonSerializerDefaults.Web)) });
            await host.StopAsync();
            availability.Add(new { policy, online = lifetime.ApplicationStarted.IsCancellationRequested &&
                !lifetime.ApplicationStopping.IsCancellationRequested, readback = JsonSerializer.SerializeToElement(
                    read?.Invoke(reader, null), new JsonSerializerOptions(JsonSerializerDefaults.Web)) });
        }
        output.WriteLine("S206_CAPACITY_MATRIX:" + JsonSerializer.Serialize(new
        {
            observations,
            availability,
            defaultOtherRuns = defaults.MaxConcurrentOtherRuns,
            defaultCreations = defaults.MaxConcurrentProjectCreations,
            defaultPerAccount = defaults.MaxConcurrentProjectCreationsPerAccount,
            overrideOtherRuns = overridden.MaxConcurrentOtherRuns,
            overrideCreations = overridden.MaxConcurrentProjectCreations
        }));
    }

    [Fact]
    public Task O_44305F724FA7()
    {
        var baseline = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-capacity-options-" + Guid.NewGuid().ToString("N"))
        });
        return ObserveCapacityMatrixAsync(baseline);
    }

    [Fact]
    public Task O_9BF16D4EDE9E()
    {
        var baseline = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-capacity-options-" + Guid.NewGuid().ToString("N"))
        });
        return ObserveCapacityMatrixAsync(baseline);
    }

    [Fact]
    public Task O_A960BE607452()
    {
        var baseline = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-capacity-options-" + Guid.NewGuid().ToString("N"))
        });
        return ObserveCapacityMatrixAsync(baseline);
    }

    [Fact]
    public Task O_C740CE8BB7BA()
    {
        var baseline = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-capacity-options-" + Guid.NewGuid().ToString("N"))
        });
        return ObserveCapacityMatrixAsync(baseline);
    }

    [Fact]
    public Task O_D15470FAB535()
    {
        var baseline = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-capacity-options-" + Guid.NewGuid().ToString("N"))
        });
        return ObserveCapacityMatrixAsync(baseline);
    }

    [Fact]
    public Task O_D8D207360833()
    {
        var baseline = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-capacity-options-" + Guid.NewGuid().ToString("N"))
        });
        return ObserveCapacityMatrixAsync(baseline);
    }

    [Fact]
    public void O_5044D91BC32C()
    {
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-authority-options")
        });
        new NodePersistenceTests(output).WriteAuthorityObservation(configuration);
    }

    [Fact]
    public void O_A18D7D0A4419()
    {
        var configuration = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = S206TestSupport.RepositoryRoot,
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(Path.GetTempPath(), "s206-authority-options")
        });
        new NodePersistenceTests(output).WriteAuthorityObservation(configuration);
    }
}
