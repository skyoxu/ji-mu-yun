using System.Net;
using Xunit;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061: only a failed transport proves the already-stopped fixture unavailable.
public sealed class StoppedHostObservationTests
{
    [Theory]
    [InlineData("response", false)]
    [InlineData("connection", true)]
    [InlineData("timeout", true)]
    public async Task RecognizesTransportFailureWithoutTreatingAResponseAsUnavailable(string mode, bool expected)
    {
        using var client = new HttpClient(new ProbeHandler(mode)) { BaseAddress = new Uri("http://127.0.0.1") };
        Assert.Equal(expected, await S206TestSupport.ObserveStoppedHostAsync(client));
    }

    [Fact]
    public async Task ArbitraryCancellationDoesNotCountAsAnUnavailableTransport()
    {
        using var client = new HttpClient(new ProbeHandler("cancelled")) { BaseAddress = new Uri("http://127.0.0.1") };
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => S206TestSupport.ObserveStoppedHostAsync(client));
    }

    private sealed class ProbeHandler(string mode) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => mode switch
            {
                "connection" => Task.FromException<HttpResponseMessage>(new HttpRequestException("Owned connection refused.")),
                "timeout" => Task.FromException<HttpResponseMessage>(new TaskCanceledException("Owned timeout.", new TimeoutException())),
                "cancelled" => Task.FromException<HttpResponseMessage>(new TaskCanceledException("Unrelated cancellation.")),
                _ => Task.FromResult(new HttpResponseMessage(HttpStatusCode.Unauthorized))
            };
    }
}
