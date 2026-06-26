using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Readback;

public sealed class ProjectAssetPreviewTicketService
{
    private static readonly TimeSpan TicketLifetime = TimeSpan.FromMinutes(10);

    private readonly PhaseAPlatformOptions _options;

    public ProjectAssetPreviewTicketService(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public string CreateTicket(string accountId, string projectId, string resourcePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(resourcePath);

        var expiresUnix = DateTimeOffset.UtcNow.Add(TicketLifetime).ToUnixTimeSeconds();
        var nonce = Convert.ToHexString(RandomNumberGenerator.GetBytes(12)).ToLowerInvariant();
        var payload = JsonSerializer.Serialize(new TicketPayload(accountId, projectId, resourcePath, expiresUnix, nonce));
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

        if (parsed is null ||
            !string.Equals(parsed.AccountId, accountId, StringComparison.Ordinal) ||
            !string.Equals(parsed.ProjectId, projectId, StringComparison.Ordinal) ||
            !string.Equals(parsed.ResourcePath, resourcePath, StringComparison.Ordinal))
        {
            return false;
        }

        if (DateTimeOffset.UtcNow.ToUnixTimeSeconds() > parsed.ExpiresUnix)
        {
            return false;
        }

        var expectedSignature = TrySign(payload);
        if (expectedSignature is null)
        {
            return false;
        }

        return providedSignature.Length == expectedSignature.Length &&
               CryptographicOperations.FixedTimeEquals(providedSignature, expectedSignature);
    }

    private byte[] SignRequired(string payload)
    {
        return TrySign(payload) ??
               throw new InvalidOperationException("Ticket signing secret is not configured.");
    }

    private byte[]? TrySign(string payload)
    {
        var secret = SigningSecret();
        if (string.IsNullOrWhiteSpace(secret))
        {
            return null;
        }

        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        return hmac.ComputeHash(Encoding.UTF8.GetBytes(payload));
    }

    private string? SigningSecret()
    {
        return _options.TicketSigningSecret;
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
        string Nonce);
}
