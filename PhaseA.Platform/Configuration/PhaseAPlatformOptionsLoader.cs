using System.Globalization;

namespace PhaseA.Platform.Configuration;

public static class PhaseAPlatformOptionsLoader
{
    public const int DefaultHostedProjectLimit = 2;

    public static PhaseAPlatformOptions FromEnvironment()
    {
        return Load(Environment.GetEnvironmentVariable);
    }

    public static PhaseAPlatformOptions FromDictionary(IReadOnlyDictionary<string, string?> values)
    {
        ArgumentNullException.ThrowIfNull(values);
        return Load(name => values.TryGetValue(name, out var value) ? value : null);
    }

    private static PhaseAPlatformOptions Load(Func<string, string?> get)
    {
        var workspaceRoot = NormalizeWorkspaceRoot(GetString(get, "HOSTED_WORKSPACE_ROOT", @"C:\workspaces"));
        var projectLimit = GetPositiveInt(get, "HOSTED_PROJECT_LIMIT", DefaultHostedProjectLimit);
        var httpsTermination = GetString(get, "HTTPS_TERMINATION", "caddy");
        var appBindUrl = ValidateAbsoluteUrl(GetString(get, "APP_BIND_URL", "http://127.0.0.1:8080"), "APP_BIND_URL");
        ValidateCaddyLocalBinding(httpsTermination, appBindUrl);
        var publicBaseUrl = ValidateHttpsUrl(GetString(get, "PUBLIC_BASE_URL", "https://localhost"), "PUBLIC_BASE_URL");
        var llmGatewayProvider = GetString(get, "LLM_GATEWAY_PROVIDER", "new-api");
        var llmGatewayBaseUrl = ValidateHttpsUrl(GetString(get, "LLM_GATEWAY_BASE_URL", "https://localhost/v1"), "LLM_GATEWAY_BASE_URL");
        var tokenMode = GetString(get, "LLM_GATEWAY_TOKEN_MODE", "per-account");
        var bindingMode = GetString(get, "LLM_GATEWAY_BINDING_MODE", "manual-admin");
        var perRunStopLoss = GetPositiveDecimal(get, "LLM_COST_STOP_LOSS_PER_RUN_CNY", 2.00m);
        var dailyStopLoss = GetPositiveDecimal(get, "LLM_COST_STOP_LOSS_DAILY_ACCOUNT_CNY", 20.00m);
        var metadataDatabasePath = NormalizeDatabasePath(GetString(get, "PHASEA_METADATA_DB_PATH", Path.Combine(AppContext.BaseDirectory, "phase-a-platform.sqlite3")));
        var repositoryRoot = NormalizeDirectoryPath(GetString(get, "PHASEA_REPOSITORY_ROOT", AppContext.BaseDirectory), "PHASEA_REPOSITORY_ROOT");
        var pythonCommand = GetString(get, "PHASEA_PYTHON_COMMAND", "py");
        var godotBin = GetOptionalString(get, "GODOT_BIN");
        var deliveryProfile = GetString(get, "DELIVERY_PROFILE", "fast-ship");
        var adminUsername = GetString(get, "PHASEA_ADMIN_USERNAME", "admin");
        var adminPasswordHash = GetOptionalString(get, "PHASEA_ADMIN_PASSWORD_HASH");
        var adminTokenHash = GetOptionalString(get, "PHASEA_ADMIN_TOKEN_HASH");
        var userTokenHash = GetOptionalString(get, "PHASEA_USER_TOKEN_HASH");

        return new PhaseAPlatformOptions(
            workspaceRoot,
            projectLimit,
            httpsTermination,
            appBindUrl,
            publicBaseUrl,
            llmGatewayProvider,
            llmGatewayBaseUrl,
            tokenMode,
            bindingMode,
            perRunStopLoss,
            dailyStopLoss,
            metadataDatabasePath,
            repositoryRoot,
            pythonCommand,
            godotBin,
            deliveryProfile,
            adminUsername,
            adminPasswordHash,
            adminTokenHash,
            userTokenHash);
    }

    private static string GetString(Func<string, string?> get, string name, string defaultValue)
    {
        var value = get(name);
        if (string.IsNullOrWhiteSpace(value))
        {
            return defaultValue;
        }

        return value.Trim();
    }

    private static string? GetOptionalString(Func<string, string?> get, string name)
    {
        var value = get(name);
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    }

    private static int GetPositiveInt(Func<string, string?> get, string name, int defaultValue)
    {
        var value = get(name);
        if (string.IsNullOrWhiteSpace(value))
        {
            return defaultValue;
        }

        if (!int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var parsed) || parsed < 1)
        {
            throw new PhaseAPlatformConfigException($"{name} must be a positive integer.");
        }

        return parsed;
    }

    private static decimal GetPositiveDecimal(Func<string, string?> get, string name, decimal defaultValue)
    {
        var value = get(name);
        if (string.IsNullOrWhiteSpace(value))
        {
            return defaultValue;
        }

        if (!decimal.TryParse(value, NumberStyles.Number, CultureInfo.InvariantCulture, out var parsed) || parsed <= 0m)
        {
            throw new PhaseAPlatformConfigException($"{name} must be a positive decimal.");
        }

        return parsed;
    }

    private static string ValidateAbsoluteUrl(string value, string name)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri))
        {
            throw new PhaseAPlatformConfigException($"{name} must be an absolute URL.");
        }

        if (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps)
        {
            throw new PhaseAPlatformConfigException($"{name} must use HTTP or HTTPS.");
        }

        return uri.ToString().TrimEnd('/');
    }

    private static void ValidateCaddyLocalBinding(string httpsTermination, string appBindUrl)
    {
        if (!string.Equals(httpsTermination, "caddy", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        var uri = new Uri(appBindUrl);
        var host = uri.Host;
        if (uri.Scheme != Uri.UriSchemeHttp)
        {
            throw new PhaseAPlatformConfigException("APP_BIND_URL must use HTTP when HTTPS_TERMINATION=caddy.");
        }

        if (!string.Equals(host, "127.0.0.1", StringComparison.OrdinalIgnoreCase) &&
            !string.Equals(host, "localhost", StringComparison.OrdinalIgnoreCase))
        {
            throw new PhaseAPlatformConfigException("APP_BIND_URL must bind to localhost when HTTPS_TERMINATION=caddy.");
        }
    }

    private static string ValidateHttpsUrl(string value, string name)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) || uri.Scheme != Uri.UriSchemeHttps)
        {
            throw new PhaseAPlatformConfigException($"{name} must be an absolute HTTPS URL.");
        }

        return uri.ToString().TrimEnd('/');
    }

    private static string NormalizeWorkspaceRoot(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new PhaseAPlatformConfigException("HOSTED_WORKSPACE_ROOT must not be empty.");
        }

        if (value.IndexOfAny(Path.GetInvalidPathChars()) >= 0)
        {
            throw new PhaseAPlatformConfigException("HOSTED_WORKSPACE_ROOT contains invalid path characters.");
        }

        if (!Path.IsPathRooted(value))
        {
            throw new PhaseAPlatformConfigException("HOSTED_WORKSPACE_ROOT must be an absolute path.");
        }

        var fullPath = Path.GetFullPath(value);
        var root = Path.GetPathRoot(fullPath);
        if (string.Equals(fullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar), root?.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
        {
            throw new PhaseAPlatformConfigException("HOSTED_WORKSPACE_ROOT must not be a drive root.");
        }

        return fullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    }

    private static string NormalizeDatabasePath(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new PhaseAPlatformConfigException("PHASEA_METADATA_DB_PATH must not be empty.");
        }

        if (!Path.IsPathRooted(value))
        {
            throw new PhaseAPlatformConfigException("PHASEA_METADATA_DB_PATH must be an absolute path.");
        }

        return Path.GetFullPath(value);
    }

    private static string NormalizeDirectoryPath(string value, string name)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new PhaseAPlatformConfigException($"{name} must not be empty.");
        }

        if (!Path.IsPathRooted(value))
        {
            throw new PhaseAPlatformConfigException($"{name} must be an absolute path.");
        }

        return Path.GetFullPath(value).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    }
}
