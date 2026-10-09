#!/usr/bin/env bash
# nviu installer for Linux, macOS, and Termux.
#
#   curl -fsSL https://raw.githubusercontent.com/NehemiahAklil/neoviu/master/install.sh | bash
#
# Run from a clone (./install.sh) to install that checkout instead of GitHub.
# Options (pass after `bash -s --` when piping):
#   --ref <branch|tag|commit>  install a specific git ref (default: master)
#   --extras <list>            comma-separated extras (default: standard,tui)
#   --local                    install the checkout this script lives in
#   --remote                   install from GitHub even when run from a clone
#   --editable                 with --local, install in editable mode (for development)
#   -h, --help                 show this help
set -euo pipefail

REPO_URL="https://github.com/NehemiahAklil/neoviu.git"
REF="master"
EXTRAS="standard,tui"
# Extras to try when the requested set fails to build (dbus-python, which
# [standard] pulls in on Linux, needs system headers).
FALLBACK_EXTRAS="download,lxml,discord,tui"
MODE="auto"
EDITABLE=0

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '\033[34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die() {
  printf '\033[31merror:\033[0m %s\n' "$*" >&2
  exit 1
}

usage() {
  sed -n '2,13p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
  --ref) REF="${2:?--ref needs a value}"; shift 2 ;;
  --extras) EXTRAS="${2-}"; shift 2 ;;
  --local) MODE="local"; shift ;;
  --remote) MODE="remote"; shift ;;
  --editable) EDITABLE=1; shift ;;
  -h | --help) usage ;;
  *) die "unknown option: $1 (see --help)" ;;
  esac
done

# Locate a checkout next to this script. When piped through curl, BASH_SOURCE
# is empty or not a file, so this stays empty and we install from GitHub.
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
is_checkout() { [ -n "$SCRIPT_DIR" ] && grep -q '^name = "nviu"' "$SCRIPT_DIR/pyproject.toml" 2>/dev/null; }

if [ "$MODE" = "auto" ]; then
  if is_checkout; then MODE="local"; else MODE="remote"; fi
fi
if [ "$MODE" = "local" ] && ! is_checkout; then
  die "--local needs to be run from an nviu checkout"
fi

IS_TERMUX=0
if [ -n "${TERMUX_VERSION-}" ] || [ -d /data/data/com.termux ]; then IS_TERMUX=1; fi

bold "Installing nviu"

# --- uv --------------------------------------------------------------------
# uv also downloads a suitable Python (3.11+) when the system one is too old.
if ! command -v uv >/dev/null 2>&1; then
  if [ "$IS_TERMUX" = 1 ]; then
    info "Installing uv with pkg"
    pkg install -y uv || die "could not install uv; run 'pkg install uv' and retry"
  else
    info "Installing uv (https://docs.astral.sh/uv/)"
    if command -v curl >/dev/null 2>&1; then
      curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://astral.sh/uv/install.sh | sh
    else
      die "neither curl nor wget is available; install uv manually: https://docs.astral.sh/uv/"
    fi
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  fi
  command -v uv >/dev/null 2>&1 || die "uv was installed but isn't on PATH; open a new shell and rerun this script"
fi
info "Using $(uv --version)"

if [ "$MODE" = "remote" ] && ! command -v git >/dev/null 2>&1; then
  die "git is required to install from GitHub; install git and retry"
fi

# --- install -----------------------------------------------------------------
spec_for() {
  local extras="$1" suffix=""
  [ -n "$extras" ] && suffix="[$extras]"
  if [ "$MODE" = "local" ]; then
    printf '%s%s' "$SCRIPT_DIR" "$suffix"
  else
    printf 'nviu%s @ git+%s@%s' "$suffix" "$REPO_URL" "$REF"
  fi
}

try_install() {
  local spec
  spec="$(spec_for "$1")"
  local args=(tool install --force --reinstall --python ">=3.11")
  if [ "$EDITABLE" = 1 ] && [ "$MODE" = "local" ]; then args+=(--editable); fi
  info "uv ${args[*]} \"$spec\""
  uv "${args[@]}" "$spec"
}

if [ "$MODE" = "local" ]; then
  info "Source: local checkout at $SCRIPT_DIR"
else
  info "Source: $REPO_URL ($REF)"
fi

if ! try_install "$EXTRAS"; then
  if [ "$EXTRAS" != "$FALLBACK_EXTRAS" ] && [ -n "$EXTRAS" ]; then
    warn "install with extras [$EXTRAS] failed; retrying with [$FALLBACK_EXTRAS]"
    warn "(desktop notifications need dbus headers on Linux, e.g. 'sudo apt install libdbus-1-dev pkg-config')"
    try_install "$FALLBACK_EXTRAS" || {
      warn "retrying with no extras"
      try_install "" || die "installation failed; see the uv output above"
    }
  else
    die "installation failed; see the uv output above"
  fi
fi

uv tool update-shell >/dev/null 2>&1 || true
BIN_DIR="$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")"
export PATH="$BIN_DIR:$PATH"

if ! command -v nviu >/dev/null 2>&1; then
  die "nviu was installed to $BIN_DIR but can't be run; add that directory to PATH"
fi
info "Installed: $(nviu --version)"

# Before the rename, this project installed as the viu-media package with a
# `viu` command. Leave it alone (it may be upstream Viu) but point it out.
if uv tool list 2>/dev/null | grep -q '^viu-media '; then
  echo
  warn "an older 'viu-media' install (the 'viu' command) is still present."
  echo "  nviu replaces it and has copied its settings. Remove it with: uv tool uninstall viu-media"
fi

# --- external tools ----------------------------------------------------------
missing=()
command -v mpv >/dev/null 2>&1 || missing+=("mpv (required for streaming)")
command -v fzf >/dev/null 2>&1 || missing+=("fzf (fuzzy-finder UI)")
command -v ffmpeg >/dev/null 2>&1 || missing+=("ffmpeg (downloads)")
if ! command -v chafa >/dev/null 2>&1 && ! command -v kitten >/dev/null 2>&1; then
  missing+=("chafa (image previews)")
fi

if [ ${#missing[@]} -gt 0 ]; then
  echo
  warn "these optional tools weren't found:"
  for m in "${missing[@]}"; do printf '    - %s\n' "$m"; done
  if [ "$IS_TERMUX" = 1 ]; then hint="pkg install fzf ffmpeg chafa   (install mpv from the Play Store)"
  elif command -v brew >/dev/null 2>&1; then hint="brew install mpv fzf ffmpeg chafa"
  elif command -v pacman >/dev/null 2>&1; then hint="sudo pacman -S mpv fzf ffmpeg chafa"
  elif command -v apt-get >/dev/null 2>&1; then hint="sudo apt install mpv fzf ffmpeg chafa"
  elif command -v dnf >/dev/null 2>&1; then hint="sudo dnf install mpv fzf ffmpeg chafa"
  elif command -v zypper >/dev/null 2>&1; then hint="sudo zypper install mpv fzf ffmpeg chafa"
  else hint=""; fi
  [ -n "$hint" ] && printf '  Install them with: %s\n' "$hint"
fi

echo
bold "Done! Run 'nviu --help' to get started."
case ":$PATH:" in
*":$BIN_DIR:"*) ;;
*) echo "Open a new terminal (or run: export PATH=\"$BIN_DIR:\$PATH\") so 'nviu' is on your PATH." ;;
esac
