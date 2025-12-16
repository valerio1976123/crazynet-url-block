using System.Text;
using NetConfigBackup.Core;

namespace NetConfigBackup.Tool.Backup.Providers;

public sealed class PaloAltoApiBackupProvider : IBackupProvider
{
    public bool CanHandle(DeviceConfig device)
    {
        var type = (device.Type ?? "").Trim().ToLowerInvariant();
        if (type is "paloalto-api" or "panos-api" or "paloalto")
            return !string.IsNullOrWhiteSpace(device.ApiKey);

        // auto
        return device.Vendor.Trim().Equals("paloalto", StringComparison.OrdinalIgnoreCase) &&
               !string.IsNullOrWhiteSpace(device.ApiKey);
    }

    public async Task<BackupResult> BackupAsync(DeviceConfig device, BackupContext ctx, CancellationToken ct)
    {
        var apiKey = device.ApiKey ?? throw new ArgumentException($"[{device.DisplayName}] apiKey mancante");
        var useHttps = device.UseHttps ?? true;
        var port = device.Port ?? (useHttps ? 443 : 80);
        var ignoreTls = device.IgnoreTlsErrors ?? ctx.IgnoreTlsErrors;

        var scheme = useHttps ? "https" : "http";
        var url = $"{scheme}://{device.Host}:{port}/api/?type=export&category=configuration&key={Uri.EscapeDataString(apiKey)}";

        using var client = HttpUtils.CreateHttpClient(ignoreTls);
        client.Timeout = TimeSpan.FromSeconds(ctx.TimeoutSeconds);

        var xml = await client.GetStringAsync(url, ct);

        var runId = ctx.StartedAtUtc.ToString("yyyyMMdd_HHmmss", System.Globalization.CultureInfo.InvariantCulture);
        var outDir = Path.Combine(ctx.OutputRoot, FileUtils.SafePathSegment(device.Vendor), FileUtils.SafePathSegment(device.DisplayName), runId);
        Directory.CreateDirectory(outDir);

        var path = Path.Combine(outDir, "configuration.xml");
        await File.WriteAllTextAsync(path, xml, new UTF8Encoding(false), ct);

        return new BackupResult
        {
            Device = device,
            Success = true,
            FilesWritten = [path],
        };
    }
}
