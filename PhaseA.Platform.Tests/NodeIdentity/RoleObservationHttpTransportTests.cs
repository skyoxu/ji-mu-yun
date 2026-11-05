using System.Net;
using Xunit;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061: fixture transport limits do not define product capacity or readiness policy.
internal static class RoleObservationHttpTransport
{
    internal static HttpClient CreateClient(string url, HttpMessageHandler? handler = null) =>
        new(handler ?? new HttpClientHandler())
        {
            BaseAddress = new Uri(url),
            Timeout = TimeSpan.FromSeconds(30)
        };

    internal static async Task<bool> IsHealthyAsync(HttpClient client)
    {
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        try
        {
            using var response = await client.GetAsync("/healthz", deadline.Token);
            return response.IsSuccessStatusCode;
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException)
        {
            return false;
        }
    }
}

public sealed class RoleObservationHttpTransportTests
{
    [Fact]
    public async Task SessionResponseCanArriveAfterTheReadinessAttemptDeadline()
    {
        using var client = RoleObservationHttpTransport.CreateClient("http://fixture.invalid",
            new DelayedResponse(TimeSpan.FromMilliseconds(2500)));
        using var response = await client.GetAsync("/api/session");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task ReadinessStillCancelsAnUnresponsiveAttempt()
    {
        var handler = new DelayedResponse(Timeout.InfiniteTimeSpan);
        using var client = RoleObservationHttpTransport.CreateClient("http://fixture.invalid", handler);
        Assert.False(await RoleObservationHttpTransport.IsHealthyAsync(client));
        Assert.True(handler.CancellationObserved);
    }

    [Fact]
    public async Task FailedHealthResponseDoesNotDeclareReadiness()
    {
        using var client = RoleObservationHttpTransport.CreateClient("http://fixture.invalid",
            new DelayedResponse(TimeSpan.Zero, HttpStatusCode.ServiceUnavailable));
        Assert.False(await RoleObservationHttpTransport.IsHealthyAsync(client));
    }

    private sealed class DelayedResponse(TimeSpan delay, HttpStatusCode status = HttpStatusCode.OK)
        : HttpMessageHandler
    {
        internal bool CancellationObserved { get; private set; }
        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            try { await Task.Delay(delay, cancellationToken); }
            catch (OperationCanceledException) { CancellationObserved = true; throw; }
            return new HttpResponseMessage(status);
        }
    }
}
