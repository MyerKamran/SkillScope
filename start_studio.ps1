Write-Host "Starting SkillScope Studio (Python API :8050 + Next.js React :3000)..." -ForegroundColor Cyan

$apiProc = Start-Process -FilePath "python" -ArgumentList "-u", "frontend/app.py" -WorkingDirectory $PSScriptRoot -PassThru

try {
    Start-Sleep -Seconds 2
    $nextLink = Join-Path $PSScriptRoot "frontend-next"
    $item = Get-Item $nextLink
    $nextDir = if ($item.Target) { ($item.Target | Select-Object -First 1) } else { $nextLink }
    Set-Location $nextDir
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing frontend dependencies cleanly (npm install)..." -ForegroundColor Yellow
        npm install
    }
    npm run dev
}
finally {
    if ($apiProc -and !$apiProc.HasExited) {
        Write-Host "Stopping Python API backend..." -ForegroundColor Yellow
        Stop-Process -Id $apiProc.Id -Force
    }
}
