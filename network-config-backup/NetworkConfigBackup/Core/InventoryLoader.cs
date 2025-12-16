using System.Text.Json;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace NetworkConfigBackup.Core;

public static class InventoryLoader
{
    public static Inventory Load(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException($"Inventory file not found: {path}");

        var raw = EnvSubstitution.Substitute(File.ReadAllText(path));
        var ext = Path.GetExtension(path).ToLowerInvariant();

        Inventory inv;
        if (ext is ".yaml" or ".yml")
        {
            var deserializer = new DeserializerBuilder()
                .WithNamingConvention(CamelCaseNamingConvention.Instance)
                .IgnoreUnmatchedProperties()
                .Build();
            inv = deserializer.Deserialize<Inventory>(raw) ?? new Inventory();
        }
        else if (ext is ".json")
        {
            inv = JsonSerializer.Deserialize<Inventory>(raw, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            }) ?? new Inventory();
        }
        else
        {
            throw new ArgumentException("Inventory must be .yml/.yaml or .json");
        }

        foreach (var d in inv.Devices)
        {
            d.Type = d.Type.Trim();
            d.Name = d.Name.Trim();
            d.Host = d.Host.Trim();
        }

        return inv;
    }
}
