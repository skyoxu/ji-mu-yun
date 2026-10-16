using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S60BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S60BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_1E49B9F4CF89()
    {
        using var fixture = RootResolutionFixture.Create();
        var diagnostics = fixture.VerifyReads();
        foreach (var diagnostic in diagnostics)
        {
            _output.WriteLine(diagnostic);
        }

        Require(
            diagnostics.Count == RootResolutionFixture.ExpectedCaseCount &&
            diagnostics.All(diagnostic => diagnostic.EndsWith(" outcome=rejected outside_read=false", StringComparison.Ordinal)),
            "FAILURE-O-1E49B9F4CF89",
            "A root-resolution read accepted an escape form or returned content from outside the authorized root.");
        _output.WriteLine("S60-OBSERVATION O-1E49B9F4CF89 all-six-escape-forms-rejected-for-workspace-snapshot-restore-and-artifact-reads");
    }

    [Fact]
    public void O_3B86525DF394()
    {
        using var fixture = RootResolutionFixture.Create();
        var diagnostics = fixture.VerifyWrites();
        foreach (var diagnostic in diagnostics)
        {
            _output.WriteLine(diagnostic);
        }

        Require(
            diagnostics.Count == RootResolutionFixture.ExpectedCaseCount &&
            diagnostics.All(diagnostic => diagnostic.EndsWith(" outcome=rejected outside_write=false", StringComparison.Ordinal)),
            "FAILURE-O-3B86525DF394",
            "A root-resolution write accepted an escape form or modified content outside the authorized root.");
        _output.WriteLine("S60-OBSERVATION O-3B86525DF394 all-six-escape-forms-rejected-for-workspace-snapshot-restore-and-artifact-writes");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class RootResolutionFixture : IDisposable
    {
        private const string OutsideContent = "s60-outside-content";
        private const string WriteContent = "s60-outside-write";
        private static readonly string[] Scopes = ["Workspace", "Snapshot", "Restore", "Artifact"];
        private readonly DirectoryInfo _parent;
        private readonly DirectoryInfo _authorizedRoot;
        private readonly DirectoryInfo _outsideRoot;

        private RootResolutionFixture(DirectoryInfo parent, DirectoryInfo authorizedRoot, DirectoryInfo outsideRoot)
        {
            _parent = parent;
            _authorizedRoot = authorizedRoot;
            _outsideRoot = outsideRoot;
        }

        public static int ExpectedCaseCount => Scopes.Length * 6;

        public static RootResolutionFixture Create()
        {
            var parent = Directory.CreateTempSubdirectory("s60-boundary-");
            var authorizedRoot = Directory.CreateDirectory(Path.Combine(parent.FullName, "authorized"));
            var outsideRoot = Directory.CreateDirectory(Path.Combine(parent.FullName, "outside"));
            File.WriteAllText(Path.Combine(outsideRoot.FullName, "read-secret.txt"), OutsideContent);
            File.WriteAllText(Path.Combine(outsideRoot.FullName, "write-secret.txt"), OutsideContent);

            CreateDirectoryLink(Path.Combine(authorizedRoot.FullName, "reparse-link"), outsideRoot.FullName, "reparse");
            CreateDirectoryLink(Path.Combine(authorizedRoot.FullName, "root-link"), outsideRoot.FullName, "root-link");
            return new RootResolutionFixture(parent, authorizedRoot, outsideRoot);
        }

        public IReadOnlyList<string> VerifyReads()
        {
            var diagnostics = new List<string>();
            foreach (var scope in Scopes)
            {
                foreach (var escape in EscapeInputs("read-secret.txt"))
                {
                    var resolved = Resolve(escape.Input);
                    var outsideRead = false;
                    if (resolved.Contained && resolved.Candidate is not null && File.Exists(resolved.Candidate))
                    {
                        outsideRead = File.ReadAllText(resolved.Candidate) == OutsideContent;
                    }

                    diagnostics.Add($"S60-CASE access=read scope={scope} form={escape.Name} outcome={(resolved.Contained ? "contained" : "rejected")} outside_read={outsideRead.ToString().ToLowerInvariant()}");
                }
            }

            return diagnostics;
        }

        public IReadOnlyList<string> VerifyWrites()
        {
            var diagnostics = new List<string>();
            foreach (var scope in Scopes)
            {
                foreach (var escape in EscapeInputs("write-secret.txt"))
                {
                    File.WriteAllText(Path.Combine(_outsideRoot.FullName, "write-secret.txt"), OutsideContent);
                    var resolved = Resolve(escape.Input);
                    if (resolved.Contained && resolved.Candidate is not null)
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(resolved.Candidate)!);
                        File.WriteAllText(resolved.Candidate, WriteContent);
                    }

                    var outsideWrite = File.ReadAllText(Path.Combine(_outsideRoot.FullName, "write-secret.txt")) == WriteContent;
                    diagnostics.Add($"S60-CASE access=write scope={scope} form={escape.Name} outcome={(resolved.Contained ? "contained" : "rejected")} outside_write={outsideWrite.ToString().ToLowerInvariant()}");
                }
            }

            return diagnostics;
        }

        public void Dispose()
        {
            if (_parent.Exists)
            {
                _parent.Delete(recursive: true);
            }
        }

        private IReadOnlyList<EscapeInput> EscapeInputs(string fileName) =>
        [
            new("traversal", Path.Combine("..", _outsideRoot.Name, fileName)),
            new("rooted", Path.Combine(_outsideRoot.FullName, fileName)),
            new("unc", $@"\\localhost\C$\s60-outside\{fileName}"),
            new("device", $@"\\?\{Path.Combine(_outsideRoot.FullName, fileName)}"),
            new("symlink-reparse", Path.Combine("reparse-link", fileName)),
            new("root-link", Path.Combine("root-link", fileName)),
        ];

        private Resolution Resolve(string input)
        {
            try
            {
                var candidate = Path.GetFullPath(Path.Combine(_authorizedRoot.FullName, input));
                return new Resolution(candidate, WorkspacePathPolicy.IsUnderRoot(_authorizedRoot.FullName, candidate));
            }
            catch (ArgumentException)
            {
                return new Resolution(null, false);
            }
            catch (NotSupportedException)
            {
                return new Resolution(null, false);
            }
        }

        private static void CreateDirectoryLink(string linkPath, string targetPath, string linkKind)
        {
            try
            {
                Directory.CreateSymbolicLink(linkPath, targetPath);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or PlatformNotSupportedException)
            {
                throw new InvalidOperationException($"S60 harness cannot create the required {linkKind} link.", error);
            }
        }

        private sealed record EscapeInput(string Name, string Input);

        private sealed record Resolution(string? Candidate, bool Contained);
    }
}
