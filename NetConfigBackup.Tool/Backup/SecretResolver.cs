namespace NetConfigBackup.Tool.Backup;

public static class SecretResolver
{
    // Supports: ${ENV:NAME}
    public static string? Resolve(string? value, bool strict = true)
    {
        if (string.IsNullOrEmpty(value))
            return value;

        var trimmed = value.Trim();
        if (!trimmed.StartsWith("${", StringComparison.Ordinal) || !trimmed.EndsWith('}'))
            return value;

        var inner = trimmed[2..^1];
        if (inner.StartsWith("ENV:", StringComparison.OrdinalIgnoreCase))
        {
            var key = inner[4..].Trim();
            if (string.IsNullOrWhiteSpace(key))
                throw new ArgumentException("Placeholder ENV senza nome variabile");

            var env = Environment.GetEnvironmentVariable(key);
            if (string.IsNullOrEmpty(env))
            {
                if (strict)
                    throw new ArgumentException($"Variabile d'ambiente non trovata o vuota: {key}");
                return value;
            }

            return env;
        }

        return value;
    }

    public static void ResolveInPlace(DeviceConfig d, bool strict = true)
    {
        d.Username = Resolve(d.Username, strict);
        d.Password = Resolve(d.Password, strict);
        d.PrivateKeyPath = Resolve(d.PrivateKeyPath, strict);
        d.PrivateKeyPassphrase = Resolve(d.PrivateKeyPassphrase, strict);
        d.ApiKey = Resolve(d.ApiKey, strict);
        d.AccessToken = Resolve(d.AccessToken, strict);
    }
}
