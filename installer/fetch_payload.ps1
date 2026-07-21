<#
    fetch_payload.ps1 — download the optional "inbuilt AI" payload for the
    installer: Ollama's official Windows installer and the assistant model
    weights (a ~1 GB GGUF). Run this ONCE before build.ps1 if you want a
    Setup.exe that carries the offline AI engine (total ~1.7 GB).

    Skip it and build.ps1 still produces a perfectly good installer — just a
    lean one where the Assistant pulls a model on first use instead.

    Usage:
        .\fetch_payload.ps1            Download whatever is missing
        .\fetch_payload.ps1 -Force    Re-download even if present

    Nothing here is committed to git (.gitignore excludes *.gguf and vendor\).
    Both artefacts are permissively licensed:
        Ollama            — MIT
        Qwen2.5-Coder-1.5B-Instruct GGUF — Apache-2.0
#>
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is far faster without the bar

# tag -> the GGUF file name the Modelfile expects (keep in sync with
# construction_app\model_provision.py GGUF_NAME and installer\ai\Modelfile).
$ggufName = 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf'
$ggufUrl  = "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/$ggufName"
$ollamaUrl = 'https://ollama.com/download/OllamaSetup.exe'

$aiDir     = Join-Path $here 'ai'
$vendorDir = Join-Path $here 'vendor'
New-Item -ItemType Directory -Force $aiDir     | Out-Null
New-Item -ItemType Directory -Force $vendorDir | Out-Null

function Get-File($url, $dest, $label) {
    if ((Test-Path $dest) -and -not $Force) {
        $mb = [math]::Round((Get-Item $dest).Length / 1MB, 1)
        Write-Host "  $label already present ($mb MB) — skipping. Use -Force to re-fetch."
        return
    }
    Write-Host "  Downloading $label ..."
    Write-Host "    $url"
    $tmp = "$dest.part"
    Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
    Move-Item -Force $tmp $dest
    $mb = [math]::Round((Get-Item $dest).Length / 1MB, 1)
    Write-Host "    -> $dest ($mb MB)"
}

Write-Host "Fetching inbuilt-AI payload into installer\ ..."
Get-File $ollamaUrl (Join-Path $vendorDir 'OllamaSetup.exe') 'Ollama installer'
Get-File $ggufUrl   (Join-Path $aiDir $ggufName)            'Qwen2.5-Coder 1.5B model'

Write-Host ""
Write-Host "Payload ready:"
Write-Host "  installer\vendor\OllamaSetup.exe"
Write-Host "  installer\ai\$ggufName"
Write-Host "  installer\ai\Modelfile   (tracked in git)"
Write-Host ""
Write-Host "Now run  .\build.ps1  to produce the inbuilt-AI installer (~1.7 GB)."
