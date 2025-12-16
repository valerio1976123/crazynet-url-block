using NetworkConfigBackup.Core;

namespace NetworkConfigBackup.Providers;

public sealed class PaloAltoApiBackupProvider : IBackupProvider
{
    public async Task<BackupBlob> FetchAsync(Device device, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(device.ApiKey))
            throw new ArgumentException($"Missing apiKey for Palo Alto device: {device.Name}");

        var handler = new HttpClientHandler();
        if (!device.VerifyTls)
        {
            handler.ServerCertificateCustomValidationCallback = (_, _, _, _) => true;
        }

        using var http = new HttpClient(handler)
        {
            Timeout = Timeout.InfiniteTimeSpan,
        };

        var host = device.Host;
        if (!host.StartsWith("http://", StringComparison.OrdinalIgnoreCase) &&
            !host.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
        {
            host = "https://" + host;
        }

        // PAN-OS XML API: export running config
        var uri = new Uri($"{host.TrimEnd('/')}/api/?type=export&category=configuration&key={Uri.EscapeDataString(device.ApiKey)}");

        using var resp = await http.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        resp.EnsureSuccessStatusCode();
        var bytes = await resp.Content.ReadAsByteArrayAsync(cancellationToken);
        if (bytes.Length == 0)
            throw new InvalidOperationException("Empty response from Palo Alto API");

        return new BackupBlob(bytes, ".xml");
    }
}
