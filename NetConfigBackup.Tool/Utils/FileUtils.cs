using System.Text.RegularExpressions;

namespace NetConfigBackup.Tool.Utils;

public static partial class FileUtils
{
    private static readonly Regex UnsafeFileChars = UnsafeFileCharsRegex();

    public static string SafeFileName(string input)
    {
        if (string.IsNullOrWhiteSpace(input))
            return "cmd";

        var s = input.Trim();
        s = UnsafeFileChars.Replace(s, "_");
        s = s.Replace(' ', '_');

        if (s.Length > 80)
            s = s[..80];

        return s;
    }

    public static string SafePathSegment(string input)
    {
        if (string.IsNullOrWhiteSpace(input))
            return "unknown";

        var s = input.Trim();
        s = UnsafeFileChars.Replace(s, "_");
        s = s.Replace(' ', '_');

        if (s.Length > 60)
            s = s[..60];

        return s;
    }

    [GeneratedRegex("[^a-zA-Z0-9._-]+", RegexOptions.Compiled)]
    private static partial Regex UnsafeFileCharsRegex();
}
