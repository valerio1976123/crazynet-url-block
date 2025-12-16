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
    public required NetConfigBackup.Core.DeviceConfig Device { get; init; }
    public required bool Success { get; init; }
    public string? Message { get; init; }
    public List<string> FilesWritten { get; init; } = new();
}

public interface IBackupProvider
{
    bool CanHandle(NetConfigBackup.Core.DeviceConfig device);
    Task<BackupResult> BackupAsync(NetConfigBackup.Core.DeviceConfig device, BackupContext ctx, CancellationToken ct);
}
