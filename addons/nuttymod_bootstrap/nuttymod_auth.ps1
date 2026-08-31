$ErrorActionPreference = "Stop"
$port = $env:NUTTYMOD_AUTH_PORT
$secret = $env:NUTTYMOD_AUTH_SECRET
if ([string]::IsNullOrWhiteSpace($port) -or [string]::IsNullOrWhiteSpace($secret)) { throw "NuttyMod Auth is missing its local settings." }
$host.UI.RawUI.WindowTitle = "NuttyMod Auth"
Write-Host ""; Write-Host "NUTTYMOD AUTH" -ForegroundColor Cyan
Write-Host "Create a local account. Your auth phrase is never stored." -ForegroundColor White
$username = Read-Host "NuttyMod account name"
$secure = Read-Host "NuttyMod auth phrase" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $phrase = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $request = @{ secret=$secret; action="register"; username=$username; proof=$phrase } | ConvertTo-Json -Compress
    $client = [Net.Sockets.TcpClient]::new("127.0.0.1", [int]$port)
    try {
        $stream=$client.GetStream(); $writer=[IO.StreamWriter]::new($stream,[Text.UTF8Encoding]::new($false),1024,$true); $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8,$false,1024,$true)
        $writer.WriteLine($request); $writer.Flush(); $result=($reader.ReadLine() | ConvertFrom-Json)
    } finally { if($writer){$writer.Dispose()}; if($reader){$reader.Dispose()}; $client.Dispose() }
    if(-not $result.ok){$message=if($result.error){[string]$result.error}else{"NuttyMod Auth rejected the account."};throw $message}
    Write-Host "Signed in as $($result.username). You can return to the game." -ForegroundColor Green; Start-Sleep -Seconds 2
} finally { if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}; $phrase=$null }
