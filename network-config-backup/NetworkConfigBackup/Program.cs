using NetworkConfigBackup.Core;
using NetworkConfigBackup.Providers;

static int Usage()
{
    Console.WriteLine("NetworkConfigBackup (C#/.NET)");
    Console.WriteLine();
    Console.WriteLine("Usage:");
    Console.WriteLine("  dotnet run --project network-config-backup/NetworkConfigBackup -- backup --inventory inventory.yml --out backups");
    Console.WriteLine();
    Console.WriteLine("Options:");
    Console.WriteLine("  --inventory <path>   Inventory file (.yml/.yaml/.json) [default: inventory.yml]");
    Console.WriteLine("  --out <dir>          Output directory [default: backups]");
    Console.WriteLine("  --parallel <n>        Parallelism [default: 4]");
    Console.WriteLine("  --timeout <sec>       Per-device timeout in seconds [default: 60]");
    Console.WriteLine("  --only <a,b,c>        Only these device names");
    return 2;
}

static string? GetArg(string[] args, string name)
{
    for (var i = 0; i < args.Length - 1; i++)
        if (args[i].Equals(name, StringComparison.OrdinalIgnoreCase))
            return args[i + 1];
    return null;
}

static bool HasArg(string[] args, string name)
    => args.Any(a => a.Equals(name, StringComparison.OrdinalIgnoreCase));

if (args.Length == 0 || HasArg(args, "-h") || HasArg(args, "--help"))
    return Usage();

if (!args[0].Equals("backup", StringComparison.OrdinalIgnoreCase))
    return Usage();

var inventoryPath = GetArg(args, "--inventory") ?? "inventory.yml";
var outDir = GetArg(args, "--out") ?? "backups";
var parallel = int.TryParse(GetArg(args, "--parallel"), out var p) ? p : 4;
var timeoutSec = int.TryParse(GetArg(args, "--timeout"), out var t) ? t : 60;
var onlyCsv = GetArg(args, "--only");
HashSet<string>? only = null;
if (!string.IsNullOrWhiteSpace(onlyCsv))
    only = onlyCsv.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToHashSet(StringComparer.OrdinalIgnoreCase);

Inventory inv;
try
{
    inv = InventoryLoader.Load(inventoryPath);
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Failed to load inventory: {ex.Message}");
    return 1;
}

var runner = new BackupRunner(new BackupProviderFactory());
var results = await runner.RunAsync(inv, outDir, parallel, TimeSpan.FromSeconds(timeoutSec), only);

var ok = results.Count(r => r.Success);
var bad = results.Count - ok;
Console.WriteLine($"Done. success={ok} failed={bad} output={Path.GetFullPath(outDir)}");
foreach (var r in results.OrderBy(r => r.DeviceName))
{
    if (r.Success)
        Console.WriteLine($"  OK   {r.DeviceName} ({r.DeviceType}) -> {r.OutputPath}");
    else
        Console.WriteLine($"  FAIL {r.DeviceName} ({r.DeviceType}): {r.Error}");
}

return bad == 0 ? 0 : 1;
