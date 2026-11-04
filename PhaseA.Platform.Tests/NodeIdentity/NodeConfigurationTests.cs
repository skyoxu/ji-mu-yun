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
