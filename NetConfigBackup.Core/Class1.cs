using System.Text.Json;
using System.Text.Json.Serialization;
using System.Net.Http;
using System.Text.RegularExpressions;

namespace NetConfigBackup.Core;

public sealed class BackupConfigFile
{
    [JsonPropertyName("defaults")]
    public BackupDefaults Defaults { get; set; } = new();

    [JsonPropertyName("devices")]
    public List<DeviceConfig> Devices { get; set; } = new();
}

public sealed class BackupDefaults
{
    [JsonPropertyName("outputDir")]
    public string OutputDir { get; set; } = "./backups";

    [JsonPropertyName("timeoutSeconds")]
    public int TimeoutSeconds { get; set; } = 45;

    [JsonPropertyName("parallelism")]
    public int Parallelism { get; set; } = 4;

    [JsonPropertyName("acceptUnknownHostKey")]
    public bool AcceptUnknownHostKey { get; set; } = true;

    [JsonPropertyName("ignoreTlsErrors")]
    public bool IgnoreTlsErrors { get; set; } = false;
}

public sealed class DeviceConfig
{
    [JsonPropertyName("name")]
    public string? Name { get; set; }

    [JsonPropertyName("vendor")]
    public string Vendor { get; set; } = "ssh";

    [JsonPropertyName("type")]
    public string? Type { get; set; }

    [JsonPropertyName("host")]
    public string Host { get; set; } = "";

    [JsonPropertyName("port")]
    public int? Port { get; set; }

    // --- SSH ---
    [JsonPropertyName("username")]
    public string? Username { get; set; }

    [JsonPropertyName("password")]
    public string? Password { get; set; }

    [JsonPropertyName("privateKeyPath")]
    public string? PrivateKeyPath { get; set; }

    [JsonPropertyName("privateKeyPassphrase")]
    public string? PrivateKeyPassphrase { get; set; }

    [JsonPropertyName("acceptUnknownHostKey")]
    public bool? AcceptUnknownHostKey { get; set; }

    [JsonPropertyName("commands")]
    public List<string>? Commands { get; set; }

    [JsonPropertyName("combineOutputs")]
    public bool? CombineOutputs { get; set; }

    // --- Palo Alto API ---
    [JsonPropertyName("apiKey")]
    public string? ApiKey { get; set; }

    [JsonPropertyName("useHttps")]
    public bool? UseHttps { get; set; }

    [JsonPropertyName("ignoreTlsErrors")]
    public bool? IgnoreTlsErrors { get; set; }

    // --- FortiGate API ---
    [JsonPropertyName("accessToken")]
    public string? AccessToken { get; set; }

    [JsonPropertyName("scope")]
    public string? Scope { get; set; }

    [JsonPropertyName("vdom")]
    public string? Vdom { get; set; }

    public string DisplayName => string.IsNullOrWhiteSpace(Name) ? Host : Name!.Trim();
}

public static class BackupConfigIo
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
        WriteIndented = true,
    };

    public static async Task<BackupConfigFile> LoadAsync(string path, CancellationToken ct = default)
    {
        var json = await File.ReadAllTextAsync(path, ct);
        return JsonSerializer.Deserialize<BackupConfigFile>(json, JsonOptions) ?? new BackupConfigFile();
    }

    public static async Task SaveAsync(string path, BackupConfigFile cfg, CancellationToken ct = default)
    {
        var json = JsonSerializer.Serialize(cfg, JsonOptions);
        await File.WriteAllTextAsync(path, json, ct);
    }
}

public static class SecretResolver
{
    // Supports: ${ENV:NAME}
    public static string? Resolve(string? value, bool strict = true)
    {
        if (string.IsNullOrEmpty(value))
            return value;

        var trimmed = value.Trim();
        if (!trimmed.StartsWith("${", StringComparison.Ordinal) || !trimmed.EndsWith('}'))
            return value;

        var inner = trimmed[2..^1];
        if (inner.StartsWith("ENV:", StringComparison.OrdinalIgnoreCase))
        {
            var key = inner[4..].Trim();
            if (string.IsNullOrWhiteSpace(key))
                throw new ArgumentException("Placeholder ENV senza nome variabile");

            var env = Environment.GetEnvironmentVariable(key);
            if (string.IsNullOrEmpty(env))
            {
                if (strict)
                    throw new ArgumentException($"Variabile d'ambiente non trovata o vuota: {key}");
                return value;
            }

            return env;
        }

        return value;
    }

    public static void ResolveInPlace(DeviceConfig d, bool strict = true)
    {
        d.Username = Resolve(d.Username, strict);
        d.Password = Resolve(d.Password, strict);
        d.PrivateKeyPath = Resolve(d.PrivateKeyPath, strict);
        d.PrivateKeyPassphrase = Resolve(d.PrivateKeyPassphrase, strict);
        d.ApiKey = Resolve(d.ApiKey, strict);
        d.AccessToken = Resolve(d.AccessToken, strict);
    }
}

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

public static class HttpUtils
{
    public static HttpClient CreateHttpClient(bool ignoreTlsErrors)
    {
        if (!ignoreTlsErrors)
            return new HttpClient();

        var handler = new HttpClientHandler
        {
            ServerCertificateCustomValidationCallback = HttpClientHandler.DangerousAcceptAnyServerCertificateValidator,
        };

        return new HttpClient(handler);
    }
}
