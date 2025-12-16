using NetConfigBackup.Tool.Backup.Providers;
using NetConfigBackup.Core;

namespace NetConfigBackup.Tool.Backup;

public sealed class BackupRunner
{
    private readonly List<IBackupProvider> _providers =
    [
        new PaloAltoApiBackupProvider(),
        new FortiGateApiBackupProvider(),
        new SshCommandBackupProvider(),
    ];

    public async Task<int> RunAsync(BackupOptions options)
    {
        if (!File.Exists(options.ConfigPath))
        {
            Console.Error.WriteLine($"File config non trovato: {options.ConfigPath}");
            return 2;
        }

        BackupConfigFile cfg;
        try
        {
            cfg = await BackupConfigIo.LoadAsync(options.ConfigPath);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Errore parsing JSON: {ex.Message}");
            return 2;
        }

        var outputRoot = options.OutputDirOverride ?? cfg.Defaults.OutputDir;
        var timeout = options.TimeoutSecondsOverride ?? cfg.Defaults.TimeoutSeconds;
        var parallelism = options.ParallelismOverride ?? cfg.Defaults.Parallelism;
        var ignoreTls = options.IgnoreTlsErrorsOverride ?? cfg.Defaults.IgnoreTlsErrors;

        var devices = ApplyFilters(cfg.Devices, options.DeviceFilters, options.VendorFilters);
        if (devices.Count == 0)
        {
            Console.Error.WriteLine("Nessun device selezionato (filtri troppo restrittivi o lista vuota)."
            );
            return 2;
        }

        var startedAt = DateTimeOffset.UtcNow;
        var ctx = new BackupContext
        {
            OutputRoot = Path.GetFullPath(outputRoot),
            StartedAtUtc = startedAt,
            TimeoutSeconds = timeout,
            AcceptUnknownHostKeyDefault = cfg.Defaults.AcceptUnknownHostKey,
            IgnoreTlsErrors = ignoreTls,
            LogInfo = s => Console.WriteLine(s),
            LogError = s => Console.Error.WriteLine(s),
        };

        if (options.DryRun)
        {
            ctx.LogInfo($"DRY-RUN: output={ctx.OutputRoot}, parallel={parallelism}, timeout={timeout}s");
            foreach (var d in devices)
                ctx.LogInfo($"DRY-RUN: {d.DisplayName} ({d.Vendor}, {d.Type ?? "auto"}) -> {PickProvider(d)?.GetType().Name ?? "(nessun provider)"}");
            return 0;
        }

        // Resolve secrets only when really running backups (strict).
        foreach (var d in devices)
            SecretResolver.ResolveInPlace(d, strict: true);

        Directory.CreateDirectory(ctx.OutputRoot);

        using var sem = new SemaphoreSlim(parallelism);
        var tasks = devices.Select(async d =>
        {
            await sem.WaitAsync();
            try
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(timeout));
                return await BackupOneAsync(d, ctx, cts.Token);
            }
            finally
            {
                sem.Release();
            }
        }).ToArray();

        var results = await Task.WhenAll(tasks);

        var ok = results.Count(r => r.Success);
        var ko = results.Length - ok;

        ctx.LogInfo($"Completato. OK={ok} KO={ko} Output={ctx.OutputRoot}");
        foreach (var r in results.Where(r => !r.Success))
            ctx.LogError($"KO {r.Device.DisplayName}: {r.Message}");

        return ko == 0 ? 0 : 1;
    }

    private async Task<BackupResult> BackupOneAsync(DeviceConfig device, BackupContext ctx, CancellationToken ct)
    {
        var provider = PickProvider(device);
        if (provider is null)
        {
            return new BackupResult
            {
                Device = device,
                Success = false,
                Message = "Nessun provider compatibile (controlla type/vendor/credenziali)",
            };
        }

        try
        {
            ctx.LogInfo($"[{device.DisplayName}] start ({provider.GetType().Name})");
            var res = await provider.BackupAsync(device, ctx, ct);
            ctx.LogInfo($"[{device.DisplayName}] {(res.Success ? "OK" : "KO")} ({res.FilesWritten.Count} file)");
            return res;
        }
        catch (OperationCanceledException)
        {
            return new BackupResult
            {
                Device = device,
                Success = false,
                Message = $"Timeout ({ctx.TimeoutSeconds}s)",
            };
        }
        catch (Exception ex)
        {
            return new BackupResult
            {
                Device = device,
                Success = false,
                Message = ex.Message,
            };
        }
    }

    private IBackupProvider? PickProvider(DeviceConfig device)
        => _providers.FirstOrDefault(p => p.CanHandle(device));

    private static List<DeviceConfig> ApplyFilters(List<DeviceConfig> devices, List<string> deviceFilters, List<string> vendorFilters)
    {
        IEnumerable<DeviceConfig> q = devices;

        if (vendorFilters.Count > 0)
        {
            var set = new HashSet<string>(vendorFilters.Select(Normalize), StringComparer.OrdinalIgnoreCase);
            q = q.Where(d => set.Contains(Normalize(d.Vendor)));
        }

        if (deviceFilters.Count > 0)
        {
            var set = new HashSet<string>(deviceFilters.Select(Normalize), StringComparer.OrdinalIgnoreCase);
            q = q.Where(d => set.Contains(Normalize(d.DisplayName)) || set.Contains(Normalize(d.Host)));
        }

        return q.Where(d => !string.IsNullOrWhiteSpace(d.Host)).ToList();

        static string Normalize(string s) => (s ?? "").Trim().ToLowerInvariant();
    }
}
