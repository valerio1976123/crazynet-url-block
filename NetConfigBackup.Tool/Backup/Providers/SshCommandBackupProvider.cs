using System.Text;
using NetConfigBackup.Core;
using Renci.SshNet;
using Renci.SshNet.Common;

namespace NetConfigBackup.Tool.Backup.Providers;

public sealed class SshCommandBackupProvider : IBackupProvider
{
    public bool CanHandle(DeviceConfig device)
    {
        var type = (device.Type ?? "").Trim().ToLowerInvariant();
        if (type is "ssh" or "cli" or "command")
            return true;

        // auto: if it looks like an SSH device
        return !string.IsNullOrWhiteSpace(device.Username) &&
               (!string.IsNullOrWhiteSpace(device.Password) || !string.IsNullOrWhiteSpace(device.PrivateKeyPath) || (device.Commands?.Count > 0));
    }

    public async Task<BackupResult> BackupAsync(DeviceConfig device, BackupContext ctx, CancellationToken ct)
    {
        var port = device.Port ?? 22;
        var user = device.Username ?? throw new ArgumentException($"[{device.DisplayName}] username mancante");

        var acceptUnknownHostKey = device.AcceptUnknownHostKey ?? ctx.AcceptUnknownHostKeyDefault;
        var combine = device.CombineOutputs ?? true;

        var commands = device.Commands;
        if (commands is null || commands.Count == 0)
        {
            commands = DefaultCommands(device.Vendor);
            if (commands.Count == 0)
                throw new ArgumentException($"[{device.DisplayName}] commands mancanti (e nessun default per vendor={device.Vendor})");
        }

        var runId = ctx.StartedAtUtc.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture);
        var outDir = Path.Combine(ctx.OutputRoot, FileUtils.SafePathSegment(device.Vendor), FileUtils.SafePathSegment(device.DisplayName), runId);
        Directory.CreateDirectory(outDir);

        return await Task.Run(() =>
        {
            var files = new List<string>();

            ConnectionInfo connectionInfo = BuildConnectionInfo(device.Host, port, user, device.Password, device.PrivateKeyPath, device.PrivateKeyPassphrase);

            using var client = new SshClient(connectionInfo);
            if (acceptUnknownHostKey)
            {
                client.HostKeyReceived += (_, e) =>
                {
                    e.CanTrust = true;
                };
            }

            client.ErrorOccurred += (_, e) =>
            {
                ctx.LogError($"[{device.DisplayName}] SSH error: {e.Exception.Message}");
            };

            client.Connect();

            var combined = new StringBuilder();

            for (var idx = 0; idx < commands.Count; idx++)
            {
                ct.ThrowIfCancellationRequested();

                var cmdText = commands[idx];
                var cmd = client.CreateCommand(cmdText);
                cmd.CommandTimeout = TimeSpan.FromSeconds(ctx.TimeoutSeconds);

                var output = cmd.Execute();
                var error = cmd.Error;

                var safeCmd = FileUtils.SafeFileName(cmdText);
                var fileName = $"{idx + 1:000}_{safeCmd}.txt";
                var path = Path.Combine(outDir, fileName);

                var content = new StringBuilder();
                content.AppendLine($"# host={device.Host} vendor={device.Vendor} name={device.DisplayName}");
                content.AppendLine($"# cmd: {cmdText}");
                content.AppendLine("# ---- output ----");
                content.Append(output);
                if (!string.IsNullOrWhiteSpace(error))
                {
                    content.AppendLine();
                    content.AppendLine("# ---- stderr ----");
                    content.Append(error);
                }

                File.WriteAllText(path, content.ToString(), new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
                files.Add(path);

                if (combine)
                {
                    combined.AppendLine($"# ===== {idx + 1:000}: {cmdText} =====");
                    combined.Append(output);
                    if (!string.IsNullOrWhiteSpace(error))
                    {
                        combined.AppendLine();
                        combined.AppendLine("# ---- stderr ----");
                        combined.Append(error);
                    }
                    combined.AppendLine();
                }
            }

            if (combine)
            {
                var combinedPath = Path.Combine(outDir, "combined.txt");
                File.WriteAllText(combinedPath, combined.ToString(), new UTF8Encoding(false));
                files.Add(combinedPath);
            }

            client.Disconnect();

            return new BackupResult
            {
                Device = device,
                Success = true,
                FilesWritten = files,
            };
        }, ct);
    }

    private static ConnectionInfo BuildConnectionInfo(string host, int port, string username, string? password, string? privateKeyPath, string? privateKeyPassphrase)
    {
        if (!string.IsNullOrWhiteSpace(privateKeyPath))
        {
            var keyFile = string.IsNullOrWhiteSpace(privateKeyPassphrase)
                ? new PrivateKeyFile(privateKeyPath)
                : new PrivateKeyFile(privateKeyPath, privateKeyPassphrase);

            var auth = new List<AuthenticationMethod>
            {
                new PrivateKeyAuthenticationMethod(username, keyFile),
            };

            // Optional: allow password as fallback
            if (!string.IsNullOrWhiteSpace(password))
                auth.Add(new PasswordAuthenticationMethod(username, password));

            return new ConnectionInfo(host, port, username, auth.ToArray());
        }

        if (!string.IsNullOrWhiteSpace(password))
            return new PasswordConnectionInfo(host, port, username, password);

        throw new ArgumentException("Credenziali SSH mancanti: password o privateKeyPath");
    }

    private static List<string> DefaultCommands(string vendor)
    {
        var v = (vendor ?? "").Trim().ToLowerInvariant();

        // Defaults are conservative; you can override in devices.json
        return v switch
        {
            "cisco" or "cisco_ios" or "ios" or "nxos" or "cisco_nxos" =>
                ["terminal length 0", "show running-config"],

            "forti" or "fortigate" or "fortinet" =>
                ["config global", "show full-configuration"],

            "mikrotik" or "routeros" =>
                ["/export compact"],

            _ => [],
        };
    }
}
