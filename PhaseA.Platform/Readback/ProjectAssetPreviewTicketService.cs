using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed class ProjectAssetPreviewTicketService
{
    private static readonly TimeSpan TicketLifetime = TimeSpan.FromMinutes(10);
    private static readonly ConcurrentDictionary<(string AccountId, string ProjectId), long> TicketGenerations = new();

    private readonly NodeTicketSigner _signer;
    private readonly NodeProjectMetadata? _authority;

    public ProjectAssetPreviewTicketService(NodeTicketSigner signer) : this(signer, null) { }

    public ProjectAssetPreviewTicketService(NodeTicketSigner signer, NodeProjectMetadata? authority)
    {
        _signer = signer;
        _authority = authority;
    }

    public string CreateTicket(string accountId, string projectId, string resourcePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(resourcePath);

        // ADR-0061 AD19: the host issuer admits only the current project authority.
        var revision = _authority?.DemandCurrent(accountId, projectId);
        var expiresUnix = DateTimeOffset.UtcNow.Add(TicketLifetime).ToUnixTimeSeconds();
        var nonce = Convert.ToHexString(RandomNumberGenerator.GetBytes(12)).ToLowerInvariant();
        var payload = JsonSerializer.Serialize(new TicketPayload(
            accountId,
            projectId,
            resourcePath,
            expiresUnix,
            nonce,
            CurrentGeneration(accountId, projectId), revision));
        var signature = SignRequired(payload);
        return $"{Base64UrlEncode(Encoding.UTF8.GetBytes(payload))}.{Base64UrlEncode(signature)}";
    }

    public bool IsValid(string? ticket, string accountId, string projectId, string resourcePath)
    {
        if (string.IsNullOrWhiteSpace(ticket) ||
            string.IsNullOrWhiteSpace(accountId) ||
            string.IsNullOrWhiteSpace(projectId) ||
            string.IsNullOrWhiteSpace(resourcePath))
        {
            return false;
        }

        var parts = ticket.Split('.', 2);
        if (parts.Length != 2)
        {
            return false;
        }

        string payload;
        byte[] providedSignature;
        try
        {
            payload = Encoding.UTF8.GetString(Base64UrlDecode(parts[0]));
            providedSignature = Base64UrlDecode(parts[1]);
        }
        catch
        {
            return false;
        }

        TicketPayload? parsed;
        try
        {
            parsed = JsonSerializer.Deserialize<TicketPayload>(payload);
        }
        catch (JsonException)
        {
            return false;
        }

        if (parsed is null || !MatchesRequestedResource(parsed, accountId, projectId, resourcePath))
        {
            return false;
        }

        if (DateTimeOffset.UtcNow.ToUnixTimeSeconds() > parsed.ExpiresUnix ||
            parsed.Generation != CurrentGeneration(accountId, projectId))
        {
            return false;
        }

        var expectedSignature = TrySign(payload);
        if (expectedSignature is null)
        {
            return false;
        }

        if (providedSignature.Length != expectedSignature.Length ||
            !CryptographicOperations.FixedTimeEquals(providedSignature, expectedSignature)) return false;
        // A standalone cryptographic helper cannot mint an admitted host ticket.
        if (_authority is null) return true;
        try { return parsed.AuthorityRevision is long revision && _authority.IsCurrentTicket(accountId, projectId, revision); }
        catch (UnauthorizedAccessException) { return false; }
    }

    internal IDisposable BeginRead(string? ticket, string accountId, string projectId, string resourcePath)
    {
        if (_authority is null || !IsValid(ticket, accountId, projectId, resourcePath))
            throw new UnauthorizedAccessException("ticket_authority_required");
        return _authority.UseAssetTicketRead(ticket!, accountId, projectId, resourcePath);
    }

    internal long RequireCurrentRevision(string ticket, string accountId, string projectId, string resourcePath)
    {
        if (!IsValid(ticket, accountId, projectId, resourcePath))
            throw new UnauthorizedAccessException("ticket_authority_required");
        return JsonSerializer.Deserialize<TicketPayload>(Encoding.UTF8.GetString(Base64UrlDecode(ticket.Split('.', 2)[0])))!
            .AuthorityRevision ?? throw new UnauthorizedAccessException("ticket_revision_required");
    }

    private byte[] SignRequired(string payload)
    {
        return TrySign(payload) ??
               throw new InvalidOperationException("Ticket signing secret is not configured.");
    }

    private byte[]? TrySign(string payload) => _signer.TrySign(payload);

    public static void InvalidateTickets(string accountId, string projectId)
    {
        TicketGenerations.AddOrUpdate(
            (accountId, projectId),
            1,
            static (_, generation) => checked(generation + 1));
    }

    private static long CurrentGeneration(string accountId, string projectId)
    {
        return TicketGenerations.GetOrAdd((accountId, projectId), 0);
    }

    private static bool MatchesRequestedResource(TicketPayload ticket, string accountId, string projectId, string resourcePath)
    {
        return string.Equals(ticket.AccountId, accountId, StringComparison.Ordinal) &&
               string.Equals(ticket.ProjectId, projectId, StringComparison.Ordinal) &&
               string.Equals(ticket.ResourcePath, resourcePath, StringComparison.Ordinal);
    }

    private static string Base64UrlEncode(byte[] bytes)
    {
        return Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
    }

    private static byte[] Base64UrlDecode(string value)
    {
        var padded = value.Replace('-', '+').Replace('_', '/');
        padded = padded.PadRight(padded.Length + (4 - padded.Length % 4) % 4, '=');
        return Convert.FromBase64String(padded);
    }

    private sealed record TicketPayload(
        string AccountId,
        string ProjectId,
        string ResourcePath,
        long ExpiresUnix,
        string Nonce,
        long Generation,
        long? AuthorityRevision = null);
}
