# nviu installer for Windows.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/NehemiahAklil/neoviu/master/install.ps1 | iex"
#
# To pass options, download the script first:
#   .\install.ps1 [-Ref <branch|tag|commit>] [-Extras "standard,tui"] [-Local] [-Remote] [-Editable]
param(
    [string]$Ref = "master",
    [string]$Extras = "standard,tui",
    [switch]$Local,
    [switch]$Remote,
    [switch]$Editable
)
$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/NehemiahAklil/neoviu.git"
$FallbackExtras = "download,lxml,discord,tui"

function Info($msg) { Write-Host "==> $msg" -ForegroundColor Blue }
function Warn($msg) { Write-Host "warning: $msg" -ForegroundColor Yellow }
function Die($msg) { Write-Host "error: $msg" -ForegroundColor Red; exit 1 }

# A checkout next to this script; empty when run through `irm | iex`.
$ScriptDir = if ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { "" }
$IsCheckout = $ScriptDir -and (Test-Path (Join-Path $ScriptDir "pyproject.toml")) -and
    (Select-String -Path (Join-Path $ScriptDir "pyproject.toml") -Pattern '^name = "nviu"' -Quiet)

$Mode = if ($Local) { "local" } elseif ($Remote) { "remote" } elseif ($IsCheckout) { "local" } else { "remote" }
if ($Mode -eq "local" -and -not $IsCheckout) { Die "-Local needs to be run from an nviu checkout" }

Write-Host "Installing nviu" -ForegroundColor White

# --- uv ---
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Info "Installing uv (https://docs.astral.sh/uv/)"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Die "uv was installed but isn't on PATH; open a new terminal and rerun this script"
    }
}
Info "Using $(uv --version)"

if ($Mode -eq "remote" -and -not (Get-Command git -ErrorAction SilentlyContinue)) {
    Die "git is required to install from GitHub; install it with 'winget install Git.Git' and retry"
}

function Get-Spec($extras) {
    $suffix = if ($extras) { "[$extras]" } else { "" }
    if ($Mode -eq "local") { "$ScriptDir$suffix" } else { "nviu$suffix @ git+$RepoUrl@$Ref" }
}

function Try-Install($extras) {
    $spec = Get-Spec $extras
    $uvArgs = @("tool", "install", "--force", "--reinstall", "--python", ">=3.11")
    if ($Editable -and $Mode -eq "local") { $uvArgs += "--editable" }
    Info "uv $($uvArgs -join ' ') `"$spec`""
    & uv @uvArgs $spec
    return $LASTEXITCODE -eq 0
}

if ($Mode -eq "local") { Info "Source: local checkout at $ScriptDir" } else { Info "Source: $RepoUrl ($Ref)" }

if (-not (Try-Install $Extras)) {
    if ($Extras -and $Extras -ne $FallbackExtras) {
        Warn "install with extras [$Extras] failed; retrying with [$FallbackExtras]"
        if (-not (Try-Install $FallbackExtras)) {
            Warn "retrying with no extras"
            if (-not (Try-Install "")) { Die "installation failed; see the uv output above" }
        }
    } else {
        Die "installation failed; see the uv output above"
    }
}

uv tool update-shell *> $null
$BinDir = (uv tool dir --bin).Trim()
$env:Path = "$BinDir;$env:Path"
if (-not (Get-Command nviu -ErrorAction SilentlyContinue)) { Die "nviu was installed to $BinDir but can't be run; add that directory to PATH" }
Info "Installed: $(nviu --version)"

# Before the rename, this project installed as the viu-media package with a
# `viu` command. Leave it alone (it may be upstream Viu) but point it out.
if (uv tool list 2>$null | Select-String -Pattern '^viu-media ' -Quiet) {
    Write-Host ""
    Warn "an older 'viu-media' install (the 'viu' command) is still present."
    Write-Host "  nviu replaces it and has copied its settings. Remove it with: uv tool uninstall viu-media"
}

$missing = @()
if (-not (Get-Command mpv -ErrorAction SilentlyContinue)) { $missing += "mpv (required for streaming)" }
if (-not (Get-Command fzf -ErrorAction SilentlyContinue)) { $missing += "fzf (fuzzy-finder UI)" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { $missing += "ffmpeg (downloads)" }
if (-not (Get-Command chafa -ErrorAction SilentlyContinue)) { $missing += "chafa (image previews)" }
if ($missing.Count -gt 0) {
    Write-Host ""
    Warn "these optional tools weren't found:"
    $missing | ForEach-Object { Write-Host "    - $_" }
    Write-Host "  Install them with: scoop install mpv fzf ffmpeg chafa"
}

Write-Host ""
Write-Host "Done! Open a new terminal and run 'nviu --help' to get started." -ForegroundColor White
