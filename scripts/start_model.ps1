param(
    [switch]$Cpu,
    [ValidateRange(2048, 32768)][int]$ContextSize = 8192,
    [ValidateRange(1, 32)][int]$Threads = 6
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot '.runtime'
$ManifestPath = Join-Path $RuntimeRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw 'Run python scripts/setup_model.py first.'
}
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$ServerPath = Join-Path $ProjectRoot $Manifest.runtime.server
$ModelPath = Join-Path $ProjectRoot $Manifest.model.path
if (-not (Test-Path -LiteralPath $ServerPath) -or -not (Test-Path -LiteralPath $ModelPath)) {
    throw 'Runtime or model file is missing. Run python scripts/setup_model.py.'
}

# Reuse this alias if it is already serving; never stop another process on the port.
try {
    $Existing = Invoke-RestMethod 'http://127.0.0.1:8766/v1/models' -TimeoutSec 2
    if ($Existing.data.id -contains 'catalog-qwen') {
        Write-Output 'catalog-qwen is already available at http://127.0.0.1:8766/v1'
        exit 0
    }
    throw 'Port 8766 is occupied by a different model server.'
} catch {
    if ($_.Exception.Message -like '*different model server*') { throw }
}

$GpuLayers = if ($Cpu -or $Manifest.runtime.backend -eq 'cpu') { 0 } else { 99 }
$Device = if ($GpuLayers -eq 0) { 'none' } else { 'Vulkan0' }
# Paths are quoted for Start-Process native command-line parsing. All other
# values are constants or validated integers. Nothing is installed globally.
$Arguments = @(
    '--model', ('"{0}"' -f $ModelPath),
    '--alias', 'catalog-qwen', '--host', '127.0.0.1', '--port', '8766',
    '--ctx-size', $ContextSize, '--parallel', '1', '--threads', $Threads,
    '--gpu-layers', $GpuLayers, '--device', $Device, '--jinja', '--reasoning', 'off',
    '--reasoning-budget', '0', '--no-webui'
)
$StdoutLog = Join-Path $RuntimeRoot 'model.stdout.log'
$StderrLog = Join-Path $RuntimeRoot 'model.stderr.log'
$Process = Start-Process -FilePath $ServerPath -ArgumentList $Arguments `
    -WorkingDirectory (Split-Path -Parent $ServerPath) -WindowStyle Hidden `
    -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
$Process.Id | Set-Content -LiteralPath (Join-Path $RuntimeRoot 'model.pid')
Write-Output "Started local model process $($Process.Id); checking readiness."

for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    Start-Sleep -Seconds 1
    $Process.Refresh()
    if ($Process.HasExited) {
        Get-Content -LiteralPath $StderrLog -Tail 20
        throw 'Model server exited. If Vulkan is unavailable, retry with -Cpu.'
    }
    try {
        $Health = Invoke-RestMethod 'http://127.0.0.1:8766/health' -TimeoutSec 1
        if ($Health.status -eq 'ok') {
            Write-Output 'Ready: http://127.0.0.1:8766/v1/chat/completions (model: catalog-qwen)'
            Write-Output "Log: $StderrLog"
            exit 0
        }
    } catch { }
}
throw "The model is still loading. Inspect $StderrLog and query http://127.0.0.1:8766/health."
