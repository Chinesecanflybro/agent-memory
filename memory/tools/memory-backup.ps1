<#
  memory-backup.ps1 - Create a timestamped, restorable snapshot of the memory
  metadata layer.

  Import payloads are NOT copied: they are byte-exact copies of external
  originals and are re-creatable using import/PROVENANCE.md. Only the authored
  layer is backed up, plus a full SHA-256 manifest of everything for verification.

  Usage:  powershell -ExecutionPolicy Bypass -File memory-backup.ps1
          powershell -ExecutionPolicy Bypass -File memory-backup.ps1 -Label before-edit
#>
[CmdletBinding()]
param(
  [string]$MemoryRoot = "",
  [string]$Label      = "manual"
)

$ErrorActionPreference = "Stop"

# 插拔式根目录解析：显式参数 > $MEMORY_ROOT > 仓库根的 .memory-root > ./memory
if (-not $MemoryRoot) { $MemoryRoot = $env:MEMORY_ROOT }
if (-not $MemoryRoot) {
  $repoRoot = Split-Path $PSScriptRoot -Parent      # tools/ 的上一层是 memory/，再上才是仓库根
  $repoRoot = Split-Path $repoRoot -Parent
  $cfg = Join-Path $repoRoot ".memory-root"
  if (Test-Path $cfg) {
    $line = (Get-Content $cfg | Where-Object { $_ -and -not $_.StartsWith("#") } | Select-Object -First 1).Trim()
    if ($line) {
      $MemoryRoot = if ([System.IO.Path]::IsPathRooted($line)) { $line } else { Join-Path $repoRoot $line }
    }
  }
}
if (-not $MemoryRoot) { $MemoryRoot = Join-Path (Split-Path $PSScriptRoot -Parent) "." }

if (-not (Test-Path $MemoryRoot)) {
  throw "记忆根目录不存在: $MemoryRoot`n  用 -MemoryRoot、`$env:MEMORY_ROOT 或 .memory-root 指定。"
}

$stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $MemoryRoot "backup\$stamp-$Label"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

# The authored layer: everything except import payloads and previous backups.
$authored = Get-ChildItem -Recurse -File $MemoryRoot |
  Where-Object { $_.FullName -notmatch '\\import\\' -and $_.FullName -notmatch '\\backup\\' }

foreach ($f in $authored) {
  $rel  = $f.FullName.Substring($MemoryRoot.Length).TrimStart('\')
  $dest = Join-Path $backup $rel
  New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
  Copy-Item $f.FullName $dest -Force
}

# Manifest of EVERYTHING under memory\, for later verification.
$manifest = Join-Path $backup "MANIFEST-SHA256.txt"
$all = Get-ChildItem -Recurse -File $MemoryRoot |
  Where-Object { $_.FullName -notmatch '\\backup\\' } | Sort-Object FullName

$lines = foreach ($f in $all) {
  $rel = $f.FullName.Substring($MemoryRoot.Length).TrimStart('\')
  "{0}  {1,10}  {2}" -f (Get-FileHash -Algorithm SHA256 $f.FullName).Hash, $f.Length, $rel
}
$lines | Set-Content -Path $manifest -Encoding UTF8

Write-Host "Backup created        : $backup"
Write-Host ("Authored files copied : {0}" -f $authored.Count)
Write-Host ("Manifest entries      : {0}" -f $all.Count)
Write-Host ("Manifest              : $manifest")
Write-Host ""
Write-Host "Rollback example (restore one file):"
Write-Host ("  Copy-Item '{0}\INDEX.md' '{1}\INDEX.md' -Force" -f $backup, $MemoryRoot)
