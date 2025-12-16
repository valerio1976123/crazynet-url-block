using System.Globalization;

namespace NetConfigBackup.Tool.Backup;

public static class Cli
{
    public static async Task<int> RunAsync(string[] args)
    {
        if (args.Length == 0 || IsHelp(args[0]))
        {
            PrintHelp();
            return 2;
        }

        var cmd = args[0].Trim();
        var rest = args.Skip(1).ToArray();

        return cmd switch
        {
            "backup" => await RunBackupAsync(rest),
            _ => UnknownCommand(cmd),
        };
    }

    private static bool IsHelp(string s) => s is "-h" or "--help" or "help";

    private static int UnknownCommand(string cmd)
    {
        Console.Error.WriteLine($"Comando sconosciuto: {cmd}");
        PrintHelp();
        return 2;
    }

    private static void PrintHelp()
    {
        Console.WriteLine(
            "NetConfigBackup (C#/.NET)\n" +
            "\n" +
            "Uso:\n" +
            "  dotnet run --project NetConfigBackup.Tool -- backup --config devices.json --out ./backups\n" +
            "\n" +
            "Opzioni (backup):\n" +
            "  --config <path>         Path al file JSON (default: devices.json)\n" +
            "  --out <dir>             Directory output (override)\n" +
            "  --parallel <n>          Parallelismo (override)\n" +
            "  --timeout <seconds>     Timeout per device (override)\n" +
            "  --device <nameOrHost>   Filtra device (ripetibile)\n" +
            "  --vendor <vendor>       Filtra vendor (ripetibile)\n" +
            "  --dry-run               Stampa cosa farebbe\n" +
            "  --insecure              Ignora errori TLS per chiamate HTTP\n" +
            "  -h|--help               Help\n"
        );
    }

    private static async Task<int> RunBackupAsync(string[] args)
    {
        var opt = new BackupOptions
        {
            ConfigPath = "devices.json",
        };

        var devicesFilter = new List<string>();
        var vendorsFilter = new List<string>();

        for (var i = 0; i < args.Length; i++)
        {
            var a = args[i];
            if (IsHelp(a))
            {
                PrintHelp();
                return 2;
            }

            if (a == "--dry-run")
            {
                opt.DryRun = true;
                continue;
            }

            if (a == "--insecure")
            {
                opt.IgnoreTlsErrorsOverride = true;
                continue;
            }

            if (TryGetValue(args, ref i, "--config", out var config))
            {
                opt.ConfigPath = config;
                continue;
            }

            if (TryGetValue(args, ref i, "--out", out var outDir))
            {
                opt.OutputDirOverride = outDir;
                continue;
            }

            if (TryGetValue(args, ref i, "--parallel", out var par))
            {
                opt.ParallelismOverride = ParseInt(par, "--parallel");
                continue;
            }

            if (TryGetValue(args, ref i, "--timeout", out var timeout))
            {
                opt.TimeoutSecondsOverride = ParseInt(timeout, "--timeout");
                continue;
            }

            if (TryGetValue(args, ref i, "--device", out var dev))
            {
                devicesFilter.Add(dev);
                continue;
            }

            if (TryGetValue(args, ref i, "--vendor", out var ven))
            {
                vendorsFilter.Add(ven);
                continue;
            }

            Console.Error.WriteLine($"Argomento non riconosciuto: {a}");
            return 2;
        }

        opt.DeviceFilters = devicesFilter;
        opt.VendorFilters = vendorsFilter;

        var runner = new BackupRunner();
        return await runner.RunAsync(opt);
    }

    private static int ParseInt(string s, string name)
    {
        if (!int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out var v) || v <= 0)
            throw new ArgumentException($"Valore non valido per {name}: {s}");
        return v;
    }

    private static bool TryGetValue(string[] args, ref int i, string key, out string value)
    {
        value = "";
        var a = args[i];

        if (a == key)
        {
            if (i + 1 >= args.Length)
                throw new ArgumentException($"Manca il valore per {key}");
            value = args[i + 1];
            i++;
            return true;
        }

        if (a.StartsWith(key + "=", StringComparison.Ordinal))
        {
            value = a[(key.Length + 1)..];
            return true;
        }

        return false;
    }
}
