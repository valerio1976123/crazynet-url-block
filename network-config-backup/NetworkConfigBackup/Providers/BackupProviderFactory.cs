using NetworkConfigBackup.Core;

namespace NetworkConfigBackup.Providers;

public sealed class BackupProviderFactory : IBackupProviderFactory
{
    public IBackupProvider Create(Device device)
    {
        var t = device.Type.Trim().ToLowerInvariant();
        return t switch
        {
            "paloalto" or "panos" => new PaloAltoApiBackupProvider(),
            "cisco_ios" or "cisco" or "fortigate" or "forti" or "mikrotik" or "routeros" or "generic_ssh" => new SshCommandBackupProvider(),
            _ => throw new NotSupportedException($"Unsupported device type: {device.Type}")
        };
    }
}
