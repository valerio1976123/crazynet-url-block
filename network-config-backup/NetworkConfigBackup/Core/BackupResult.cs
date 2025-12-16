namespace NetworkConfigBackup.Core;

public sealed record BackupResult(
    string DeviceName,
    string DeviceType,
    bool Success,
    string? OutputPath,
    string? Error,
    DateTimeOffset StartedAt,
    DateTimeOffset FinishedAt
);
