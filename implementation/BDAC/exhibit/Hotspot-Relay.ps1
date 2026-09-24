param(
    [string]$ListenAddress = '192.168.137.1',
    [int]$ListenPort = 8766,
    [Parameter(Mandatory = $true)]
    [string]$TargetAddress,
    [int]$TargetPort = 8766
)

$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;

public static class VeilTcpRelay
{
    public static async Task Run(
        string listenAddress,
        int listenPort,
        string targetAddress,
        int targetPort,
        CancellationToken cancellationToken)
    {
        var listener = new TcpListener(IPAddress.Parse(listenAddress), listenPort);
        listener.Start();
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var client = await listener.AcceptTcpClientAsync();
                var forwarding = Forward(client, targetAddress, targetPort);
            }
        }
        finally
        {
            listener.Stop();
        }
    }

    private static async Task Forward(TcpClient client, string targetAddress, int targetPort)
    {
        using (client)
        using (var target = new TcpClient())
        {
            try
            {
                await target.ConnectAsync(targetAddress, targetPort);
                var incoming = client.GetStream();
                var outgoing = target.GetStream();
                await Task.WhenAny(
                    incoming.CopyToAsync(outgoing),
                    outgoing.CopyToAsync(incoming));
            }
            catch (SocketException)
            {
                // The browser will retry while the WSL server is starting.
            }
        }
    }
}
'@

$cancellation = [Threading.CancellationTokenSource]::new()
try {
    [VeilTcpRelay]::Run(
        $ListenAddress,
        $ListenPort,
        $TargetAddress,
        $TargetPort,
        $cancellation.Token
    ).GetAwaiter().GetResult()
}
finally {
    $cancellation.Cancel()
    $cancellation.Dispose()
}
