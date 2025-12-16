using System.Text.Json.Serialization;

namespace NetworkConfigBackup.Core;

public sealed class Inventory
{
    [JsonPropertyName("devices")]
    public List<Device> Devices { get; set; } = new();
}

public sealed class Device
{
    [JsonPropertyName("name")]
    public required string Name { get; set; }

    // cisco_ios | fortigate | mikrotik | paloalto | generic_ssh
    [JsonPropertyName("type")]
    public required string Type { get; set; }

    [JsonPropertyName("host")]
    public required string Host { get; set; }

    [JsonPropertyName("port")]
    public int Port { get; set; } = 22;

    [JsonPropertyName("username")]
    public string? Username { get; set; }

    [JsonPropertyName("password")]
    public string? Password { get; set; }

    // Optional: SSH private key (OpenSSH) as file path
    [JsonPropertyName("privateKeyPath")]
    public string? PrivateKeyPath { get; set; }

    [JsonPropertyName("privateKeyPassphrase")]
    public string? PrivateKeyPassphrase { get; set; }

    // For Palo Alto API
    [JsonPropertyName("apiKey")]
    public string? ApiKey { get; set; }

    [JsonPropertyName("verifyTls")]
    public bool VerifyTls { get; set; } = true;

    // Override default command for SSH devices
    [JsonPropertyName("command")]
    public string? Command { get; set; }

    // Optional tags (free-form)
    [JsonPropertyName("tags")]
    public List<string> Tags { get; set; } = new();
}
