#!/usr/bin/env bash
set -euo pipefail

APP=erza
REPO="ryangerardwilson/erza"
APP_HOME="$HOME/.${APP}"
INSTALL_DIR="$APP_HOME/bin"
APP_DIR="$APP_HOME/app"
VENV_DIR="$APP_HOME/venv"
PUBLIC_BIN_DIR="$HOME/.local/bin"
PUBLIC_LAUNCHER="$PUBLIC_BIN_DIR/${APP}"
INTERNAL_LAUNCHER="$INSTALL_DIR/${APP}"
LATEST_VERSION_CACHE=""

usage() {
  cat <<EOF
${APP} Installer

Usage: install.sh [options]

Options:
  -h                         Show this help and exit
  -v [<version>]             Print the latest release version, or install a specific one
  -u                         Upgrade to the latest release only when newer
  -n                         Compatibility alias; installer never edits shell startup files

      --help                 Compatibility alias for -h
      --version [<version>]  Compatibility alias for -v
      --upgrade              Compatibility alias for -u
      --no-modify-path       Compatibility alias for -n
EOF
}

requested_version=${VERSION:-}
show_latest=false
upgrade=false
no_modify_path=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -v|--version)
      if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
        requested_version="${2#v}"
        shift 2
      else
        show_latest=true
        shift
      fi
      ;;
    -u|--upgrade)
      upgrade=true
      shift
      ;;
    -n|--no-modify-path)
      no_modify_path=true
      shift
      ;;
    *)
      echo "Warning: Unknown option '$1'" >&2
      shift
      ;;
  esac
done

print_message() {
  printf '%b\n' "$2"
}

die() {
  print_message error "$1"
  exit 1
}

detect_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf 'python3\n'
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf 'python\n'
    return 0
  fi
  die "Python is required but was not found"
}

installed_command_path() {
  if command -v "${APP}" >/dev/null 2>&1; then
    command -v "${APP}"
    return 0
  fi
  if [[ -x "${INTERNAL_LAUNCHER}" ]]; then
    printf '%s\n' "${INTERNAL_LAUNCHER}"
    return 0
  fi
  if [[ -x "${PUBLIC_LAUNCHER}" ]]; then
    printf '%s\n' "${PUBLIC_LAUNCHER}"
    return 0
  fi
  return 1
}

read_installed_version() {
  local installed_cmd
  installed_cmd="$(installed_command_path)" || return 0
  "$installed_cmd" -v 2>/dev/null || true
}

get_latest_version() {
  command -v curl >/dev/null 2>&1 || die "'curl' is required but not installed."
  if [[ -z "$LATEST_VERSION_CACHE" ]]; then
    local release_url
    local tag
    release_url="$(curl -fsSL -o /dev/null -w "%{url_effective}" "https://github.com/${REPO}/releases/latest" || true)"
    tag="${release_url##*/}"
    tag="${tag#v}"
    if [[ -z "$tag" || "$tag" == "latest" || "$tag" == "releases" ]]; then
      LATEST_VERSION_CACHE="0.0.0"
    else
      LATEST_VERSION_CACHE="$tag"
    fi
  fi
  printf '%s\n' "$LATEST_VERSION_CACHE"
}

write_internal_launcher() {
  mkdir -p "$INSTALL_DIR"
  cat > "${INTERNAL_LAUNCHER}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "${VENV_DIR}/bin/python" "${APP_DIR}/main.py" "\$@"
EOF
  chmod 755 "${INTERNAL_LAUNCHER}"
}

write_public_launcher() {
  if [[ -e "$PUBLIC_LAUNCHER" && ! -L "$PUBLIC_LAUNCHER" && ! -f "$PUBLIC_LAUNCHER" ]]; then
    die "Refusing to overwrite non-file launcher: $PUBLIC_LAUNCHER"
  fi

  if [[ -L "$PUBLIC_LAUNCHER" ]]; then
    local resolved
    resolved="$(readlink -f "$PUBLIC_LAUNCHER" 2>/dev/null || true)"
    if [[ "$resolved" != "${INTERNAL_LAUNCHER}" ]]; then
      die "Refusing to overwrite existing symlink launcher: $PUBLIC_LAUNCHER"
    fi
  elif [[ -f "$PUBLIC_LAUNCHER" ]] && ! grep -Fq '# Managed by rgw_cli_contract local-bin launcher' "$PUBLIC_LAUNCHER" 2>/dev/null; then
    die "Refusing to overwrite existing launcher: $PUBLIC_LAUNCHER"
  fi

  mkdir -p "$PUBLIC_BIN_DIR"
  cat > "${PUBLIC_LAUNCHER}" <<EOF
#!/usr/bin/env bash
# Managed by rgw_cli_contract local-bin launcher
set -euo pipefail
exec "${INTERNAL_LAUNCHER}" "\$@"
EOF
  chmod 755 "${PUBLIC_LAUNCHER}"
}

print_manual_shell_steps() {
  if [[ ":$PATH:" != *":$PUBLIC_BIN_DIR:"* ]]; then
    print_message info "Manually add to ~/.bashrc if needed: export PATH=$PUBLIC_BIN_DIR:\$PATH"
    print_message info "Reload your shell: source ~/.bashrc"
  fi
}

install_ref() {
  local ref="$1"
  local python_bin
  local tmp_dir
  local archive
  local repo_root
  local url

  python_bin="$(detect_python)"
  command -v curl >/dev/null 2>&1 || die "'curl' is required but not installed."
  command -v tar >/dev/null 2>&1 || die "'tar' is required but not installed."

  if [[ "$ref" == "0.0.0" ]]; then
    url="https://github.com/${REPO}/archive/refs/heads/main.tar.gz"
  else
    url="https://github.com/${REPO}/archive/refs/tags/v${ref}.tar.gz"
  fi

  tmp_dir="$(mktemp -d)"
  archive="$tmp_dir/${APP}.tar.gz"
  trap 'rm -rf "$tmp_dir"' RETURN

  curl -fsSL "$url" -o "$archive" || die "Unable to download ${url}"
  tar -xzf "$archive" -C "$tmp_dir"
  repo_root="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [[ -n "$repo_root" && -d "$repo_root/app" ]] || die "Downloaded archive did not contain app/"

  rm -rf "$APP_DIR" "$VENV_DIR"
  mkdir -p "$APP_HOME"
  mv "$repo_root/app" "$APP_DIR"

  if [[ "$ref" != "0.0.0" ]]; then
    printf '__version__ = "%s"\n' "$ref" > "$APP_DIR/_version.py"
  fi

  "$python_bin" -m venv "$VENV_DIR"
  write_internal_launcher
  write_public_launcher
  trap - RETURN
  rm -rf "$tmp_dir"
}

if $show_latest; then
  [[ "$upgrade" == false && -z "$requested_version" ]] || die "-v (no arg) cannot be combined with other options"
  get_latest_version
  exit 0
fi

if $upgrade; then
  [[ -z "$requested_version" ]] || die "-u cannot be combined with -v <version>"
  requested_version="$(get_latest_version)"
  installed_version="$(read_installed_version)"
  installed_version="${installed_version#v}"
  if [[ -n "$installed_version" && "$installed_version" == "$requested_version" ]]; then
    write_public_launcher || true
    print_manual_shell_steps
    print_message info "${APP} version ${requested_version} already installed"
    exit 0
  fi
fi

specific_version="${requested_version:-$(get_latest_version)}"
install_ref "$specific_version"
print_manual_shell_steps
print_message info "Run: ${APP} -h"
