$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $RootDir '.starter-server.pid'

if (-not (Test-Path $PidFile)) {
    Write-Output 'Server is not running.'
    exit 0
}

$ServerProcessId = Get-Content $PidFile
Start-Process taskkill.exe -ArgumentList @('/PID', $ServerProcessId, '/T', '/F') -NoNewWindow -Wait
Remove-Item $PidFile -Force
Write-Output 'Server stopped.'
