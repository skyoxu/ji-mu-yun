using System.Security.Cryptography;
using System.Text;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Readback;

public sealed class ProjectPackageDownloadTicketService
{
    private static readonly TimeSpan TicketLifetime = TimeSpan.FromMinutes(10);

    private readonly PhaseAPlatformOptions _options;

    public ProjectPackageDownloadTicketService(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public string CreateTicket(string projectId, string fileName)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);

        var expiresUnix = DateTimeOffset.UtcNow.Add(TicketLifetime).ToUnixTimeSeconds();
        var nonce = Convert.ToHexString(RandomNumberGenerator.GetBytes(12)).ToLowerInvariant();
        var payload = $"{projectId}|{fileName}|{expiresUnix}|{nonce}";
        var signature = Sign(payload);
        return $"{Base64UrlEncode(Encoding.UTF8.GetBytes(payload))}.{Base64UrlEncode(signature)}";
    }

    public bool IsValid(string? ticket, string projectId, string fileName)
    {
        if (string.IsNullOrWhiteSpace(ticket) ||
            string.IsNullOrWhiteSpace(projectId) ||
            string.IsNullOrWhiteSpace(fileName))
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

        var payloadParts = payload.Split('|');
        if (payloadParts.Length != 4 ||
            !string.Equals(payloadParts[0], projectId, StringComparison.Ordinal) ||
            !string.Equals(payloadParts[1], fileName, StringComparison.Ordinal) ||
            !long.TryParse(payloadParts[2], out var expiresUnix))
        {
            return false;
        }

        if (DateTimeOffset.UtcNow.ToUnixTimeSeconds() > expiresUnix)
        {
            return false;
        }

        var expectedSignature = Sign(payload);
        return providedSignature.Length == expectedSignature.Length &&
               CryptographicOperations.FixedTimeEquals(providedSignature, expectedSignature);
    }

    private byte[] Sign(string payload)
    {
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(SigningSecret()));
        return hmac.ComputeHash(Encoding.UTF8.GetBytes(payload));
    }

    private string SigningSecret()
    {
        return _options.AdminTokenHash ??
               _options.UserTokenHash ??
               _options.AdminPasswordHash ??
               _options.MetadataDatabasePath;
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
}
