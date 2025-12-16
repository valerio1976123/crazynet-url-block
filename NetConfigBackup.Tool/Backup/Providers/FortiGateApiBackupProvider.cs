using NetConfigBackup.Core;

namespace NetConfigBackup.Tool.Backup.Providers;

public sealed class FortiGateApiBackupProvider : IBackupProvider
{
    public bool CanHandle(DeviceConfig device)
    {
        var type = (device.Type ?? "").Trim().ToLowerInvariant();
        if (type is "fortigate-api" or "forti-api" or "fortigate")
            return !string.IsNullOrWhiteSpace(device.AccessToken);

        // auto
        var v = device.Vendor.Trim().ToLowerInvariant();
        return (v is "forti" or "fortigate" or "fortinet") && !string.IsNullOrWhiteSpace(device.AccessToken);
    }

    public async Task<BackupResult> BackupAsync(DeviceConfig device, BackupContext ctx, CancellationToken ct)
    {
        var token = device.AccessToken ?? throw new ArgumentException($"[{device.DisplayName}] accessToken mancante");
        var useHttps = device.UseHttps ?? true;
        var port = device.Port ?? (useHttps ? 443 : 80);
        var scope = string.IsNullOrWhiteSpace(device.Scope) ? "global" : device.Scope!.Trim();
        var ignoreTls = device.IgnoreTlsErrors ?? ctx.IgnoreTlsErrors;

        var scheme = useHttps ? "https" : "http";
        var baseUrl = $"{scheme}://{device.Host}:{port}";

        var qs = new List<string>
        {
            $"scope={Uri.EscapeDataString(scope)}",
            $"access_token={Uri.EscapeDataString(token)}",
        };

        if (!string.IsNullOrWhiteSpace(device.Vdom))
            qs.Add($"vdom={Uri.EscapeDataString(device.Vdom!.Trim())}");

        var url = $"{baseUrl}/api/v2/monitor/system/config/backup?{string.Join("&", qs)}";

        using var client = HttpUtils.CreateHttpClient(ignoreTls);
        client.Timeout = TimeSpan.FromSeconds(ctx.TimeoutSeconds);

        using var resp = await client.GetAsync(url, ct);
        var bytes = await resp.Content.ReadAsByteArrayAsync(ct);
        if (!resp.IsSuccessStatusCode)
        {
            var body = System.Text.Encoding.UTF8.GetString(bytes);
            throw new InvalidOperationException($"HTTP {(int)resp.StatusCode} {resp.ReasonPhrase}: {body}");
        }

        var runId = ctx.StartedAtUtc.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture);
        var outDir = Path.Combine(ctx.OutputRoot, FileUtils.SafePathSegment(device.Vendor), FileUtils.SafePathSegment(device.DisplayName), runId);
        Directory.CreateDirectory(outDir);

        var path = Path.Combine(outDir, "fortigate.conf");
        await File.WriteAllBytesAsync(path, bytes, ct);

        return new BackupResult
        {
            Device = device,
            Success = true,
            FilesWritten = [path],
        };
    }
}
