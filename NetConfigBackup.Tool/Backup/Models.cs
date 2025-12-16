using System.Text.Json.Serialization;

namespace NetConfigBackup.Tool.Backup;

public sealed class BackupOptions
{
    public string ConfigPath { get; set; } = "devices.json";
    public string? OutputDirOverride { get; set; }
    public int? ParallelismOverride { get; set; }
    public int? TimeoutSecondsOverride { get; set; }
    public bool DryRun { get; set; }
    public bool? IgnoreTlsErrorsOverride { get; set; }

    public List<string> DeviceFilters { get; set; } = new();
    public List<string> VendorFilters { get; set; } = new();
}

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

public sealed class BackupContext
{
    public required string OutputRoot { get; init; }
    public required DateTimeOffset StartedAtUtc { get; init; }
    public required int TimeoutSeconds { get; init; }
    public required bool AcceptUnknownHostKeyDefault { get; init; }
    public required bool IgnoreTlsErrors { get; init; }
    public required Action<string> LogInfo { get; init; }
    public required Action<string> LogError { get; init; }
}

public sealed class BackupResult
{
    public required DeviceConfig Device { get; init; }
    public required bool Success { get; init; }
    public string? Message { get; init; }
    public List<string> FilesWritten { get; init; } = new();
}

public interface IBackupProvider
{
    bool CanHandle(DeviceConfig device);
    Task<BackupResult> BackupAsync(DeviceConfig device, BackupContext ctx, CancellationToken ct);
}
