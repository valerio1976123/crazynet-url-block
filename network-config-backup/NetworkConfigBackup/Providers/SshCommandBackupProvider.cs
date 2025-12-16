using System.Text;
using NetworkConfigBackup.Core;
using Renci.SshNet;
using Renci.SshNet.Common;

namespace NetworkConfigBackup.Providers;

public sealed class SshCommandBackupProvider : IBackupProvider
{
    public Task<BackupBlob> FetchAsync(Device device, CancellationToken cancellationToken)
    {
        // SSH.NET is synchronous; run it on a worker thread.
        return Task.Run(() => FetchSync(device), cancellationToken);
    }

    private static BackupBlob FetchSync(Device device)
    {
        var command = device.Command ?? DefaultCommand(device.Type);
        if (string.IsNullOrWhiteSpace(command))
            throw new ArgumentException($"No command configured for {device.Name} ({device.Type})");

        var connInfo = BuildConnectionInfo(device);
        using var client = new SshClient(connInfo);

        try
        {
            client.Connect();
            var cmd = client.RunCommand(command);
            if (cmd.ExitStatus != 0 && !string.IsNullOrWhiteSpace(cmd.Error))
                throw new SshException(cmd.Error);

            var output = cmd.Result ?? string.Empty;
            if (string.IsNullOrWhiteSpace(output))
                throw new InvalidOperationException("Empty output (check permissions/command)");

            var bytes = Encoding.UTF8.GetBytes(output);
            return new BackupBlob(bytes, ".cfg");
        }
        finally
        {
            if (client.IsConnected)
                client.Disconnect();
        }
    }

    private static ConnectionInfo BuildConnectionInfo(Device d)
    {
        if (string.IsNullOrWhiteSpace(d.Username))
            throw new ArgumentException($"Missing username for SSH device: {d.Name}");

        var methods = new List<AuthenticationMethod>();

        if (!string.IsNullOrWhiteSpace(d.PrivateKeyPath))
        {
            var keyFile = string.IsNullOrWhiteSpace(d.PrivateKeyPassphrase)
                ? new PrivateKeyFile(d.PrivateKeyPath)
                : new PrivateKeyFile(d.PrivateKeyPath, d.PrivateKeyPassphrase);

            methods.Add(new PrivateKeyAuthenticationMethod(d.Username, keyFile));
        }

        if (!string.IsNullOrWhiteSpace(d.Password))
        {
            methods.Add(new PasswordAuthenticationMethod(d.Username, d.Password));
        }

        if (methods.Count == 0)
            throw new ArgumentException($"Missing password or privateKeyPath for SSH device: {d.Name}");

        return new ConnectionInfo(d.Host, d.Port, d.Username, methods.ToArray());
    }

    private static string DefaultCommand(string type)
    {
        var t = type.Trim().ToLowerInvariant();
        return t switch
        {
            "cisco_ios" or "cisco" => "show running-config",
            "fortigate" or "forti" => "show full-configuration",
            "mikrotik" or "routeros" => "/export show-sensitive",
            "generic_ssh" => "show running-config",
            _ => string.Empty,
        };
    }
}
