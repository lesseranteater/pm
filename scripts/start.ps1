$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $RootDir '.pm-server.pid'
$LogFile = Join-Path $RootDir '.pm-server.log'
$ErrorLogFile = Join-Path $RootDir '.pm-server-error.log'
$Port = if ($env:PORT) { $env:PORT } else { '8000' }

if (Test-Path $PidFile) {
    $ExistingPid = Get-Content $PidFile
    if (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue) {
        Write-Output "Server is already running with PID $ExistingPid"
        exit 0
    }
    Remove-Item $PidFile -Force
}

if (-not (Test-Path (Join-Path $RootDir 'frontend/build/index.html'))) {
    pnpm --dir (Join-Path $RootDir 'frontend') build
}

$Process = Start-Process -FilePath 'uv' -ArgumentList @('run', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', $Port) -WorkingDirectory $RootDir -RedirectStandardOutput $LogFile -RedirectStandardError $ErrorLogFile -PassThru
$Process.Id | Set-Content $PidFile
Write-Output "Server started at http://127.0.0.1:$Port"
