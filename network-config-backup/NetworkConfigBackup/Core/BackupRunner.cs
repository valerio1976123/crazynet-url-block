using System.Text.Json;

namespace NetworkConfigBackup.Core;

public sealed class BackupRunner
{
    private readonly IBackupProviderFactory _factory;

    public BackupRunner(IBackupProviderFactory factory)
    {
        _factory = factory;
    }

    public async Task<IReadOnlyList<BackupResult>> RunAsync(
        Inventory inventory,
        string outputDir,
        int parallelism,
        TimeSpan timeout,
        HashSet<string>? onlyNames = null,
        CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(outputDir);

        var devices = inventory.Devices
            .Where(d => onlyNames == null || onlyNames.Contains(d.Name))
            .ToList();

        var sem = new SemaphoreSlim(Math.Max(1, parallelism));
        var results = new List<BackupResult>(devices.Count);
        var tasks = devices.Select(async device =>
        {
            await sem.WaitAsync(cancellationToken);
            try
            {
                var startedAt = DateTimeOffset.UtcNow;
                try
                {
                    var provider = _factory.Create(device);
                    using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                    cts.CancelAfter(timeout);

                    var blob = await provider.FetchAsync(device, cts.Token);

                    var ts = DateTimeOffset.UtcNow.ToString("yyyyMMdd_HHmmss");
                    var deviceDir = Path.Combine(outputDir, Sanitize(device.Name));
                    Directory.CreateDirectory(deviceDir);

                    var fileName = $"{ts}_{Sanitize(device.Type)}{blob.Extension}";
                    var outPath = Path.Combine(deviceDir, fileName);
                    await File.WriteAllBytesAsync(outPath, blob.Bytes, cancellationToken);

                    // Convenience copy
                    var latestPath = Path.Combine(deviceDir, $"latest{blob.Extension}");
                    File.Copy(outPath, latestPath, overwrite: true);

                    lock (results)
                    {
                        results.Add(new BackupResult(device.Name, device.Type, true, outPath, null, startedAt, DateTimeOffset.UtcNow));
                    }
                }
                catch (Exception ex)
                {
                    lock (results)
                    {
                        results.Add(new BackupResult(device.Name, device.Type, false, null, ex.Message, startedAt, DateTimeOffset.UtcNow));
                    }
                }
            }
            finally
            {
                sem.Release();
            }
        });

        await Task.WhenAll(tasks);

        // Write run summary
        var indexPath = Path.Combine(outputDir, $"run_{DateTimeOffset.UtcNow:yyyyMMdd_HHmmss}.json");
        await File.WriteAllTextAsync(indexPath, JsonSerializer.Serialize(results, new JsonSerializerOptions { WriteIndented = true }), cancellationToken);

        return results;
    }

    private static string Sanitize(string value)
    {
        foreach (var c in Path.GetInvalidFileNameChars())
            value = value.Replace(c, '_');
        return value.Trim();
    }
}
