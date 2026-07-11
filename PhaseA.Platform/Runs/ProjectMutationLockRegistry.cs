using System.Collections.Concurrent;

namespace PhaseA.Platform.Runs;

internal sealed class ProjectMutationLockRegistry
{
    public static ProjectMutationLockRegistry Shared { get; } = new();

    private readonly ConcurrentDictionary<string, Entry> _entries = new(StringComparer.Ordinal);

    internal int EntryCount => _entries.Count;

    public async ValueTask<IAsyncDisposable> AcquireAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var key = $"{accountId}:{projectId}";
        while (true)
        {
            var entry = _entries.GetOrAdd(key, static _ => new Entry());
            lock (entry.SyncRoot)
            {
                if (entry.Retired)
                {
                    continue;
                }

                entry.ReferenceCount++;
            }

            try
            {
                await entry.Semaphore.WaitAsync(cancellationToken);
                return new Lease(this, key, entry);
            }
            catch
            {
                ReleaseReference(key, entry, releaseSemaphore: false);
                throw;
            }
        }
    }

    private void ReleaseReference(string key, Entry entry, bool releaseSemaphore)
    {
        if (releaseSemaphore)
        {
            entry.Semaphore.Release();
        }

        var remove = false;
        lock (entry.SyncRoot)
        {
            entry.ReferenceCount--;
            if (entry.ReferenceCount == 0)
            {
                entry.Retired = true;
                remove = true;
            }
        }

        if (remove)
        {
            _entries.TryRemove(new KeyValuePair<string, Entry>(key, entry));
            entry.Semaphore.Dispose();
        }
    }

    private sealed class Entry
    {
        public object SyncRoot { get; } = new();
        public SemaphoreSlim Semaphore { get; } = new(1, 1);
        public int ReferenceCount { get; set; }
        public bool Retired { get; set; }
    }

    private sealed class Lease(ProjectMutationLockRegistry owner, string key, Entry entry) : IAsyncDisposable
    {
        private int _disposed;

        public ValueTask DisposeAsync()
        {
            if (Interlocked.Exchange(ref _disposed, 1) == 0)
            {
                owner.ReleaseReference(key, entry, releaseSemaphore: true);
            }

            return ValueTask.CompletedTask;
        }
    }
}
