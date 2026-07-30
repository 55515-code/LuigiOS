#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! -d "$1/cosmic" ]]; then
    echo "usage: $0 BACKUP_DIRECTORY" >&2
    exit 2
fi
cosmic="${XDG_CONFIG_HOME:-${HOME}/.config}/cosmic"
rollback="${cosmic}.luigios-rollback-$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -d "${cosmic}" ]]; then
    mv "${cosmic}" "${rollback}"
fi
cp -a "$1/cosmic" "${cosmic}"
for gtk_version in 3.0 4.0; do
    saved="$1/gtk-${gtk_version}-settings.ini"
    live="${XDG_CONFIG_HOME:-${HOME}/.config}/gtk-${gtk_version}/settings.ini"
    [[ -f "${saved}" ]] && install -Dm0644 "${saved}" "${live}"
done
icon_theme="${XDG_DATA_HOME:-${HOME}/.local/share}/icons/LuigiOS"
rm -rf "${icon_theme:?}"
if [[ -d "$1/LuigiOS-icon-theme" ]]; then
    cp -a "$1/LuigiOS-icon-theme" "${icon_theme}"
fi
code_user="${XDG_CONFIG_HOME:-${HOME}/.config}/Code - OSS/User"
code_extension="${HOME}/.vscode-oss/extensions/luigios.luigios-workstation-theme-1.0.0"
if [[ -f "$1/code-settings.json" ]]; then
    install -Dm0644 "$1/code-settings.json" "${code_user}/settings.json"
fi
rm -rf "${code_extension:?}"
if [[ -d "$1/code-theme-extension" ]]; then
    cp -a "$1/code-theme-extension" "${code_extension}"
fi
echo "Restored COSMIC configuration from $1"
echo "Replaced configuration retained at ${rollback}"
