using System.Diagnostics;
using System.Text.Json;

namespace PhaseA.Platform.Tests.Data;

// ADR-0005: retain real source/template bytes without seeding CI tool downloads into every project.
public sealed class HostedSourceRepositoryFixture : IDisposable
{
    private readonly string _checkoutRoot = FindCheckoutRoot();
    private string? _projectionRoot;

    public string RepositoryRoot(string sourceRoot)
    {
        sourceRoot = Path.GetFullPath(sourceRoot);
        // Explicit, mutable test repositories retain their original behavior.
        if (!string.Equals(sourceRoot, _checkoutRoot, StringComparison.OrdinalIgnoreCase))
        {
            return sourceRoot;
        }
        if (_projectionRoot is not null)
        {
            return _projectionRoot;
        }

        var destination = Path.Combine(Path.GetTempPath(), $"phase-a-source-fixture-{Guid.NewGuid():N}");
        var timer = Stopwatch.StartNew();
        var copied = 0;
        var excluded = new List<string>();
        try
        {
            CopyDirectory(sourceRoot, destination, "", excluded, ref copied);
        }
        catch
        {
            if (Directory.Exists(destination)) Directory.Delete(destination, recursive: true);
            throw;
        }
        _projectionRoot = destination;
        if (Environment.GetEnvironmentVariable("PHASEA_CI_FIXTURES") == "1")
        {
            var logs = Path.Combine(_checkoutRoot, "logs", "ci", DateTime.UtcNow.ToString("yyyy-MM-dd"), "source-fixtures");
            Directory.CreateDirectory(logs);
            File.WriteAllText(Path.Combine(logs, $"{Guid.NewGuid():N}.json"), JsonSerializer.Serialize(new
            {
                elapsed_ms = timer.ElapsedMilliseconds,
                files_copied = copied,
                excluded_root_directories = excluded
            }));
        }
        return destination;
    }

    private static void CopyDirectory(string source, string destination, string relative, List<string> excluded, ref int copied)
    {
        Directory.CreateDirectory(destination);
        foreach (var directory in Directory.EnumerateDirectories(source))
        {
            var name = Path.GetFileName(directory);
            var path = Path.Combine(relative, name).Replace('\\', '/');
            var requiredGdUnitBinary = path.StartsWith("Tests.Godot/addons/gdUnit4/bin", StringComparison.OrdinalIgnoreCase);
            var transient = name is ".git" or ".dotnet" or ".vs" or ".vscode" or "logs" or "TestResults" or
                "execution-plans" or "_bmad-output" or ".fastctx" or "buildcache" or "node_modules" ||
                ((name is "bin" or "obj") && !requiredGdUnitBinary) ||
                (relative.Length == 0 && (name is "godot" or ".godot"));
            if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0 || transient)
            {
                if (relative.Length == 0) excluded.Add(name);
                continue;
            }
            CopyDirectory(directory, Path.Combine(destination, name), path, excluded, ref copied);
        }
        foreach (var file in Directory.EnumerateFiles(source))
        {
            File.Copy(file, Path.Combine(destination, Path.GetFileName(file)));
            copied++;
        }
    }

    private static string FindCheckoutRoot()
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "docs", "game-type-guides", "game-types.csv")))
            {
                return directory.FullName;
            }
        }
        throw new InvalidOperationException("Test checkout with game-type catalog was not found.");
    }

    public void Dispose()
    {
        if (_projectionRoot is not null && Directory.Exists(_projectionRoot))
        {
            Directory.Delete(_projectionRoot, recursive: true);
        }
    }
}
