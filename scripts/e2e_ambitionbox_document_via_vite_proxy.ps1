$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Stop-Listener([int]$port) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($conns) {
    $pids = $conns.OwningProcess | Select-Object -Unique
    foreach ($pid in $pids) {
      Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
  }
}

Stop-Listener 8000
Stop-Listener 5173
Start-Sleep -Milliseconds 300

$python = Join-Path $root '.venv312\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "Python venv not found at $python" }

$node = 'C:\Program Files\nodejs\node.exe'
if (-not (Test-Path $node)) { throw "Node not found at $node" }

$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$backendOut = Join-Path $root "backend\uvicorn.ab.$ts.out.log"
$backendErr = Join-Path $root "backend\uvicorn.ab.$ts.err.log"
$frontendOut = Join-Path $root "frontend\vite.ab.$ts.out.log"
$frontendErr = Join-Path $root "frontend\vite.ab.$ts.err.log"

$backend = Start-Process -FilePath $python -WorkingDirectory (Join-Path $root 'backend') -ArgumentList @(
  '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'
) -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru

$frontend = Start-Process -FilePath $node -WorkingDirectory (Join-Path $root 'frontend') -ArgumentList @(
  '.\node_modules\vite\bin\vite.js','--host','127.0.0.1','--port','5173'
) -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru

Write-Host "BACKEND_PID=$($backend.Id) FRONTEND_PID=$($frontend.Id)"

# Wait for ports
$ok8000 = $false
$ok5173 = $false
for ($i=0; $i -lt 80; $i++) {
  if (-not $ok8000) { $ok8000 = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet }
  if (-not $ok5173) { $ok5173 = Test-NetConnection -ComputerName 127.0.0.1 -Port 5173 -InformationLevel Quiet }
  if ($ok8000 -and $ok5173) { break }
  Start-Sleep -Milliseconds 250
}

if (-not ($ok8000 -and $ok5173)) {
  Write-Host 'Backend tail:'
  Get-Content $backendErr -Tail 80 -ErrorAction SilentlyContinue
  Write-Host 'Frontend tail:'
  Get-Content $frontendErr -Tail 80 -ErrorAction SilentlyContinue
  throw 'Servers did not start on 8000/5173'
}

$bodyObj = @{
  url = 'https://www.ambitionbox.com/list-of-companies?page=1'
  requested_fields = @('company_name','rating','reviews_count','company_url')
  headers = @{ 'User-Agent' = 'Mozilla/5.0' }
  pagination = @{ type = 'page_param'; param = 'page'; start = 1; end = 5 }
}
$body = $bodyObj | ConvertTo-Json -Depth 10

try {
  $resp = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5173/analyze/document' -ContentType 'application/json' -Body $body -TimeoutSec 180
  Write-Host "MODE_USED=$($resp.mode_used) HAS_DATA=$($resp.has_data) RECORDS=$($resp.record_count)"
  Write-Host "CSV_URL=$($resp.csv_url)"

  if (-not $resp.csv_url) { throw 'No csv_url returned' }

  $dlUrl = if ("$($resp.csv_url)" -match '^https?://') { "$($resp.csv_url)" } else { "http://127.0.0.1:5173$($resp.csv_url)" }
  $tmp = Join-Path $env:TEMP "wdsp-ambitionbox-proxy-$ts.csv"
  Invoke-WebRequest -Uri $dlUrl -OutFile $tmp -TimeoutSec 180 | Out-Null

  Write-Host "DOWNLOADED_TO=$tmp"
  Get-Content $tmp -TotalCount 6
}
finally {
  Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
  Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}

Write-Host 'Stopped.'
