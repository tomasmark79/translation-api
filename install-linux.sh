#!/usr/bin/env bash
# Copyright (C) 2026 Tomáš Mark
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash install-linux.sh [--update | --uninstall] [--service]

Install from this checkout for the current user, without sudo.
  --update     Upgrade an existing installation from this checkout.
  --service    Enable and start a user systemd service (also with --update).
  --uninstall  Remove the installation and its service; preserve configuration.
  --help       Show this help.

Requires Linux, Python 3.11+, venv and pip. Ollama and its model are separate.
The installer never pulls Git changes; run git pull before --update.
EOF
}

die() { echo "Error: $*" >&2; exit 1; }
action=install
service=false
for arg in "$@"; do
    case "$arg" in
        --help|-h) usage; exit 0 ;;
        --update|--uninstall)
            [[ "$action" == install ]] || die "Choose either --update or --uninstall."
            action=${arg#--} ;;
        --service) service=true ;;
        *) die "Unknown option: $arg (see --help)." ;;
    esac
done
[[ "$(uname -s)" == Linux ]] || die "This installer is for Linux."
[[ "$EUID" -ne 0 ]] || die "Run as your regular user, without sudo."
[[ "$action" != uninstall || "$service" == false ]] || die "--uninstall cannot be combined with --service."

data_dir=${XDG_DATA_HOME:-$HOME/.local/share}/translation-api
config_dir=${XDG_CONFIG_HOME:-$HOME/.config}/translation-api
bin_dir=$HOME/.local/bin
launcher=$bin_dir/translation-api
unit_dir=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
unit=$unit_dir/translation-api.service
marker='# Managed by translation-api/install-linux.sh'

# Refuse to replace files belonging to another deployment method.
for path in "$data_dir" "$config_dir" "$bin_dir" "$unit_dir"; do
    [[ "$path" == /* && "$path" != *$'\n'* && "$path" != *$'\r'* ]] || die "Installation paths must be absolute and contain no newlines."
    [[ "$path" != *'$'* ]] || die "Python packaging does not support dollar signs in installation paths: $path"
done
[[ ! -L "$data_dir" ]] || die "Installation directory must not be a symlink: $data_dir"
if [[ -e "$data_dir" ]]; then
    [[ -f "$data_dir/.installer-owned" ]] || die "Unmanaged installation directory: $data_dir"
fi
for path in "$launcher" "$unit"; do
    if [[ -e "$path" || -L "$path" ]]; then
        [[ -f "$path" && ! -L "$path" ]] && file_header=$(head -n 2 "$path") || die "Unmanaged file: $path"
        [[ "$file_header" == *"$marker"* ]] || die "Unmanaged file: $path"
    fi
done

if [[ -f "$unit" || "$service" == true ]]; then
    command -v systemctl >/dev/null || die "systemctl is required for the user service."
    systemctl --user show-environment >/dev/null || die "No user systemd session; run from a regular login session."
    if [[ ! -f "$unit" ]] && systemctl --user cat translation-api.service >/dev/null 2>&1; then
        die "An existing user service belongs to another installation method. Disable and remove it through its original configuration first."
    fi
fi

if [[ "$action" == uninstall ]]; then
    if [[ -f "$unit" ]]; then
        systemctl --user disable --now translation-api.service
        rm -- "$unit"
        systemctl --user daemon-reload
    fi
    rm -f -- "$launcher"
    if [[ -d "$data_dir" ]]; then rm -rf -- "$data_dir"; fi
    echo "Uninstalled. Configuration preserved at $config_dir."
    exit 0
fi

[[ "$action" != update || -f "$data_dir/.installer-owned" ]] || die "No existing installation; run without --update first."
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -f "$source_dir/pyproject.toml" && -f "$source_dir/server.py" ]] || die "Run the installer from a complete translation-api checkout."
if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    die "Python 3.11+ is required. See docs/deployment.md for distribution packages."
fi

mkdir -p -- "$data_dir"
touch "$data_dir/.installer-owned"
if [[ ! -x "$data_dir/venv/bin/python" ]]; then
    python3 -m venv "$data_dir/venv" || die "Cannot create venv. Install the distribution packages listed in docs/deployment.md and retry."
fi
"$data_dir/venv/bin/python" -m pip install --upgrade "$source_dir"
"$data_dir/venv/bin/python" -I -m server --version

mkdir -p -- "$bin_dir" "$config_dir"
if [[ ! -e "$config_dir/arguments" ]]; then
    cat > "$config_dir/arguments" <<'EOF'
--host
127.0.0.1
--port
5001
--model
translategemma:4b
--ollama-url
http://127.0.0.1:11434
EOF
fi

# Bash quoting keeps spaces and shell characters in user paths literal.
{
    printf '#!/usr/bin/env bash\n%s\nset -euo pipefail\n' "$marker"
    printf 'arguments_file=%q\nexecutable=%q\n' "$config_dir/arguments" "$data_dir/venv/bin/python"
    cat <<'EOF'
arguments=()
if [[ -f "$arguments_file" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" == \#* ]] || arguments+=("$line")
    done < "$arguments_file"
fi
exec "$executable" -I -m server "${arguments[@]}" "$@"
EOF
} > "$launcher"
chmod +x "$launcher"

if [[ "$service" == true ]]; then
    mkdir -p -- "$unit_dir"
    # systemd has its own quoting, specifier and environment expansion rules.
    exec_path=${launcher//\\/\\\\}
    exec_path=${exec_path//\"/\\\"}
    exec_path=${exec_path//%/%%}
    exec_path=${exec_path//\$/\$\$}
    cat > "$unit" <<EOF
$marker
[Unit]
Description=Local translation API backed by Ollama

[Service]
ExecStart="$exec_path"
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable translation-api.service
    systemctl --user restart translation-api.service
elif [[ -f "$unit" ]] && systemctl --user is-active --quiet translation-api.service; then
    systemctl --user restart translation-api.service
fi

echo "Installed: $launcher"
echo "Configuration: $config_dir/arguments (one argument per line; no shell quoting)."
case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *) printf 'Add to your shell profile: export PATH="$HOME/.local/bin:$PATH"\n' ;;
esac
echo 'Ollama must be running with the configured model: ollama pull translategemma:4b'
echo 'Start with translation-api, then check: curl http://127.0.0.1:5001/health'
if [[ -f "$unit" ]]; then
    echo 'Service logs: journalctl --user -u translation-api.service -n 50'
fi
