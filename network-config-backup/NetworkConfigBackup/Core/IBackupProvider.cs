namespace NetworkConfigBackup.Core;

public sealed record BackupBlob(byte[] Bytes, string Extension);

public interface IBackupProvider
{
    Task<BackupBlob> FetchAsync(Device device, CancellationToken cancellationToken);
}

public interface IBackupProviderFactory
{
    IBackupProvider Create(Device device);
}
