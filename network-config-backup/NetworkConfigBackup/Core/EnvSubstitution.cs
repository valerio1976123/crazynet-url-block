using System.Text.RegularExpressions;

namespace NetworkConfigBackup.Core;

public static class EnvSubstitution
{
    private static readonly Regex EnvPattern = new(@"\$\{ENV:(?<name>[A-Za-z_][A-Za-z0-9_]*)\}", RegexOptions.Compiled);

    public static string Substitute(string input)
    {
        return EnvPattern.Replace(input, m =>
        {
            var name = m.Groups["name"].Value;
            return Environment.GetEnvironmentVariable(name) ?? string.Empty;
        });
    }
}
