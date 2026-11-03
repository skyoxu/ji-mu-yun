using System.Collections.Concurrent;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class RunCancellationService
{
    private readonly ConcurrentDictionary<string, CancellationTokenSource> _tokens = new(StringComparer.Ordinal);
    private readonly NodeProjectMetadata? _authority;

    public RunCancellationService(NodeProjectMetadata? authority=null) => _authority=authority;

    // ADR-0061 AD20: registration and finally-cleanup belong to trusted consumers,
    // not the ordinary cancellation capability. Revocation cannot disable cleanup.
    internal CancellationTokenSource CreateLinkedTokenSource(string runId, CancellationToken cancellationToken)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        var source = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        _tokens.AddOrUpdate(
            runId,
            source,
            (_, existing) =>
            {
                existing.Dispose();
                return source;
            });
        return source;
    }

    public bool Cancel(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        if(_authority is null)throw new UnauthorizedAccessException("cancellation_authority_required");
        _authority.DemandCurrentControl(write:true);
        if(!_tokens.TryGetValue(runId,out var source))return false;
        _authority.DemandRunControl(runId);
        return TryCancel(source);
    }

    internal bool IsCancellationRequested(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        return _tokens.TryGetValue(runId, out var source) && source.IsCancellationRequested;
    }

    internal void Unregister(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        if (_tokens.TryRemove(runId, out var source))
        {
            source.Dispose();
        }
    }

    private static bool TryCancel(CancellationTokenSource source)
    {
        try
        {
            source.Cancel();
            return true;
        }
        catch (ObjectDisposedException)
        {
            return false;
        }
    }
}
