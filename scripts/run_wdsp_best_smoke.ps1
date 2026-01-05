$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Stop-Listener([int]$port) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($conns) {
    $pids = $conns.OwningProcess | Select-Object -Unique
    foreach ($pid in $pids) { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue }
  }
}

function Wait-Port([int]$port, [int]$maxSeconds) {
  for ($i=0; $i -lt ($maxSeconds * 4); $i++) {
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port $port -InformationLevel Quiet) { return $true }
    Start-Sleep -Milliseconds 250
  }
  return $false
}

function Download-And-Preview([string]$csvPath, [string]$tag) {
  if (-not $csvPath) { throw "[$tag] No csv_url returned" }
  $dlUrl = if ($csvPath -match '^https?://') { $csvPath } else { "http://127.0.0.1:8000$csvPath" }
  $tmp = Join-Path $env:TEMP ("wdsp-$tag-$ts.csv")
  Invoke-WebRequest -Uri $dlUrl -OutFile $tmp -TimeoutSec 180 | Out-Null
  Write-Host "[$tag] DOWNLOADED_TO=$tmp"
  Get-Content $tmp -TotalCount 6
}

# Clean ports
Stop-Listener 8000
Start-Sleep -Milliseconds 300

$python = Join-Path $root '.venv312\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "Python venv not found at $python" }

$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$backendOut = Join-Path $root "backend\uvicorn.smoke.$ts.out.log"
$backendErr = Join-Path $root "backend\uvicorn.smoke.$ts.err.log"

$backend = Start-Process -FilePath $python -WorkingDirectory (Join-Path $root 'backend') -ArgumentList @(
  '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'
) -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru

try {
  if (-not (Wait-Port 8000 10)) {
    Write-Host 'Backend failed to start. Tail err log:'
    Get-Content $backendErr -Tail 120 -ErrorAction SilentlyContinue
    throw 'Backend not listening on 8000'
  }

  $uaHeaders = @{ 'User-Agent' = 'Mozilla/5.0 (WDSP smoke test)' }

  # 1) Document mode (Wikipedia) — server-rendered table
  Write-Host "\n=== 1) Document: Wikipedia table ==="
  $docBody = @{
    url = 'https://en.wikipedia.org/wiki/List_of_countries_by_population_(United_Nations)'
    requested_fields = @('Country','Population')
    headers = $uaHeaders
    pagination = $null
  } | ConvertTo-Json -Depth 10

  $docResp = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/analyze/document' -ContentType 'application/json' -Body $docBody -TimeoutSec 120
  Write-Host "[document] mode_used=$($docResp.mode_used) has_data=$($docResp.has_data) record_count=$($docResp.record_count)"
  Download-And-Preview -csvPath $docResp.csv_url -tag 'document-wikipedia'

  # 2) XHR mode page-based (JSONPlaceholder)
  Write-Host "\n=== 2) XHR: JSONPlaceholder page-based ==="
  $xhrPageBody = @{
    api_url = 'https://jsonplaceholder.typicode.com/posts'
    requested_fields = @('userId','id','title')
    headers = $uaHeaders
    params = @{}
    pagination = @{ type = 'page_param'; param = '_page'; start = 1; end = 3 }
  } | ConvertTo-Json -Depth 12

  $xhrPageResp = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/analyze/xhr' -ContentType 'application/json' -Body $xhrPageBody -TimeoutSec 120
  Write-Host "[xhr-page] mode_used=$($xhrPageResp.mode_used) has_data=$($xhrPageResp.has_data) record_count=$($xhrPageResp.record_count)"
  Download-And-Preview -csvPath $xhrPageResp.csv_url -tag 'xhr-jsonplaceholder-page'

  # 3) XHR mode cursor-based (OpenAlex)
  Write-Host "\n=== 3) XHR: OpenAlex cursor-based ==="
  $xhrCursorBody = @{
    api_url = 'https://api.openalex.org/works'
    requested_fields = @('id','display_name','publication_year')
    headers = $uaHeaders
    params = @{ 'per-page' = 25 }
    pagination = @{ type = 'cursor'; cursor_param = 'cursor'; cursor_field = 'meta.next_cursor'; initial_cursor = '*'; max_pages = 2 }
  } | ConvertTo-Json -Depth 12

  $xhrCursorResp = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/analyze/xhr' -ContentType 'application/json' -Body $xhrCursorBody -TimeoutSec 180
  Write-Host "[xhr-cursor] mode_used=$($xhrCursorResp.mode_used) has_data=$($xhrCursorResp.has_data) record_count=$($xhrCursorResp.record_count)"
  Download-And-Preview -csvPath $xhrCursorResp.csv_url -tag 'xhr-openalex-cursor'

  # 4) Selenium mode page-based (Quotes to Scrape JS)
  Write-Host "\n=== 4) Selenium: Quotes JS page-based ==="
  $selBody = @{
    url = 'https://quotes.toscrape.com/js/'
    requested_fields = @('text','author')
    css_selector = '.quote'
    wait_time = 20
    pagination = @{ type = 'page_param'; param = 'page'; start = 1; end = 2 }
  } | ConvertTo-Json -Depth 12

  try {
    $selResp = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/analyze/selenium' -ContentType 'application/json' -Body $selBody -TimeoutSec 240
    Write-Host "[selenium] mode_used=$($selResp.mode_used) has_data=$($selResp.has_data) record_count=$($selResp.record_count)"
    if ($selResp.csv_url) {
      Download-And-Preview -csvPath $selResp.csv_url -tag 'selenium-quotes'
    } else {
      Write-Host "[selenium] No csv_url returned. Message: $($selResp.message)"
    }
  }
  catch {
    Write-Host "[selenium] FAILED: $($_.Exception.Message)"
    Write-Host "If Chrome/Edge WebDriver is not available on this machine, Selenium can fail."
  }

  Write-Host "\nSmoke run completed."
}
finally {
  Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}
