using System.Net.Http;

namespace NetConfigBackup.Tool.Utils;

public static class HttpUtils
{
    public static HttpClient CreateHttpClient(bool ignoreTlsErrors)
    {
        if (!ignoreTlsErrors)
            return new HttpClient();

        var handler = new HttpClientHandler
        {
            ServerCertificateCustomValidationCallback = HttpClientHandler.DangerousAcceptAnyServerCertificateValidator,
        };

        return new HttpClient(handler);
    }
}
