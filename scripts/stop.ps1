$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $RootDir '.starter-server.pid'

if (-not (Test-Path $PidFile)) {
    Write-Output 'Server is not running.'
    exit 0
}

$Pid = Get-Content $PidFile
Stop-Process -Id $Pid -ErrorAction SilentlyContinue
Remove-Item $PidFile -Force
Write-Output 'Server stopped.'
