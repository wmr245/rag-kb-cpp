param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Command
)

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$tmpRoot = $env:TEMP
$token = [Guid]::NewGuid().ToString('N')
$scriptPath = Join-Path $tmpRoot ("wsl_utf8_{0}.sh" -f $token)
$outPath = Join-Path $tmpRoot ("wsl_utf8_{0}.out" -f $token)
$errPath = Join-Path $tmpRoot ("wsl_utf8_{0}.err" -f $token)

try {
    $scriptContent = "#!/usr/bin/env bash`n$Command`n"
    [System.IO.File]::WriteAllText($scriptPath, $scriptContent, $utf8NoBom)

    $drive = $scriptPath.Substring(0, 1).ToLower()
    $rest = $scriptPath.Substring(2) -replace '\\', '/'
    $wslScriptPath = "/mnt/$drive$rest"

    $cmdLine = 'chcp 65001>nul && wsl bash "{0}" 1> "{1}" 2> "{2}"' -f $wslScriptPath, $outPath, $errPath
    $proc = Start-Process -FilePath cmd.exe -ArgumentList '/d', '/c', $cmdLine -WorkingDirectory $tmpRoot -NoNewWindow -Wait -PassThru

    if (Test-Path $outPath) {
        Get-Content -Path $outPath -Encoding UTF8
    }

    if ((Test-Path $errPath) -and (Get-Item $errPath).Length -gt 0) {
        $errBytes = [System.IO.File]::ReadAllBytes($errPath)
        $isUtf16Le = $errBytes.Length -ge 4 -and $errBytes[1] -eq 0x00 -and $errBytes[3] -eq 0x00
        if ($isUtf16Le) {
            [System.Text.Encoding]::Unicode.GetString($errBytes).TrimEnd()
        }
        else {
            Get-Content -Path $errPath -Encoding UTF8
        }
    }

    exit $proc.ExitCode
}
finally {
    Remove-Item $scriptPath, $outPath, $errPath -ErrorAction SilentlyContinue
}
