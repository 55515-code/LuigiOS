#!/usr/bin/env bash
set -euo pipefail

rice_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${rice_dir}/../branding/assets" ]]; then
    bundle_root="$(cd -- "${rice_dir}/.." && pwd)"
else
    bundle_root="$(cd -- "${rice_dir}/../.." && pwd)"
fi
state_root="${XDG_STATE_HOME:-${HOME}/.local/state}/luigios-rice"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="${state_root}/backups/${stamp}"
cosmic="${XDG_CONFIG_HOME:-${HOME}/.config}/cosmic"
wallpaper_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/backgrounds/LuigiOS"
icon_root="${XDG_DATA_HOME:-${HOME}/.local/share}/icons"
icon_theme="${icon_root}/LuigiOS"
code_user="${XDG_CONFIG_HOME:-${HOME}/.config}/Code - OSS/User"
code_extension="${HOME}/.vscode-oss/extensions/luigios.luigios-workstation-theme-1.0.0"
cosmic_locale=(
    env
    -u LC_ALL -u LC_ADDRESS -u LC_CTYPE -u LC_IDENTIFICATION
    -u LC_MEASUREMENT -u LC_MONETARY -u LC_NAME -u LC_NUMERIC
    -u LC_PAPER -u LC_TELEPHONE -u LC_TIME
    LANG=en-US LANGUAGE=en-US
)

mkdir -p "${backup}" "${wallpaper_dir}"
if [[ -d "${cosmic}" ]]; then
    cp -a "${cosmic}" "${backup}/cosmic"
fi
for gtk_version in 3.0 4.0; do
    gtk_settings="${XDG_CONFIG_HOME:-${HOME}/.config}/gtk-${gtk_version}/settings.ini"
    [[ -f "${gtk_settings}" ]] &&
        cp -a "${gtk_settings}" "${backup}/gtk-${gtk_version}-settings.ini"
done
if [[ -d "${icon_theme}" ]]; then
    cp -a "${icon_theme}" "${backup}/LuigiOS-icon-theme"
fi
if [[ -f "${code_user}/settings.json" ]]; then
    cp -a "${code_user}/settings.json" "${backup}/code-settings.json"
fi
if [[ -d "${code_extension}" ]]; then
    cp -a "${code_extension}" "${backup}/code-theme-extension"
fi
"${cosmic_locale[@]}" cosmic-settings appearance export \
    "${backup}/theme.ron" >/dev/null 2>&1 || true

install -m 0644 \
    "${bundle_root}/branding/assets/desktop/wallpapers/luigios/1920x1080.png" \
    "${wallpaper_dir}/luigios-workstation.png"

rm -rf "${icon_theme:?}"
install -d -m 0755 \
    "${icon_theme}/scalable/apps" \
    "${icon_theme}/scalable/places" \
    "${icon_theme}/scalable/status" \
    "${icon_theme}/symbolic/apps"
install -m 0644 "${rice_dir}/icon-theme/index.theme" "${icon_theme}/index.theme"
install -m 0644 "${rice_dir}"/icon-theme/scalable/apps/*.svg \
    "${icon_theme}/scalable/apps/"
install -m 0644 "${rice_dir}"/icon-theme/symbolic/apps/*.svg \
    "${icon_theme}/symbolic/apps/"

link_icon() {
    local target="$1" source="$2"
    ln -s "${source}" "${icon_theme}/scalable/apps/${target}.svg"
}
link_icon com.system76.CosmicAppLibrary luigios.svg
link_icon com.system76.CosmicAppList luigios.svg
link_icon com.system76.CosmicPanelAppButton luigios.svg
link_icon com.system76.CosmicInitialSetup luigios.svg
link_icon com.system76.CosmicFiles luigios-files.svg
link_icon com.system76.CosmicTerm luigios-terminal.svg
link_icon com.system76.CosmicEdit luigios-edit.svg
link_icon com.system76.CosmicSettings luigios-settings.svg
link_icon com.system76.CosmicStore luigios-store.svg
link_icon com.system76.CosmicLauncher luigios-launcher.svg
link_icon com.system76.CosmicPanelLauncherButton luigios-launcher.svg
link_icon com.system76.CosmicWorkspaces luigios-workspaces.svg
link_icon com.system76.CosmicAppletWorkspaces luigios-workspaces.svg
link_icon com.system76.CosmicPanelWorkspacesButton luigios-workspaces.svg
link_icon com.system76.CosmicPlayer luigios-player.svg
link_icon com.system76.CosmicScreenshot luigios-screenshot.svg

for symbolic_name in \
    com.system76.CosmicAppLibrary-symbolic \
    com.system76.CosmicAppList-symbolic \
    com.system76.CosmicPanelAppButton-symbolic; do
    ln -s luigios-symbolic.svg \
        "${icon_theme}/symbolic/apps/${symbolic_name}.svg"
done

# Papirus supplies comprehensive application, action, MIME, and device
# coverage. Promote its green folder family into the LuigiOS override layer.
for source in /usr/share/icons/Papirus-Dark/64x64/places/folder-green*.svg; do
    [[ -f "${source}" ]] || continue
    target="$(basename "${source}")"
    target="${target/folder-green/folder}"
    install -m 0644 "${source}" "${icon_theme}/scalable/places/${target}"
done
gtk-update-icon-cache -f -t "${icon_theme}" >/dev/null

if ! command -v jq >/dev/null 2>&1; then
    echo "jq is required to preserve and merge Code - OSS settings" >&2
    exit 1
fi
rm -rf "${code_extension:?}"
install -d -m 0755 "${code_extension}"
cp -a "${rice_dir}/vscode-theme/." "${code_extension}/"
mkdir -p "${code_user}"
if [[ ! -f "${code_user}/settings.json" ]]; then
    printf '{}\n' >"${code_user}/settings.json"
fi
merged_settings="$(mktemp "${code_user}/.luigios-settings.XXXXXX")"
jq -s '.[0] * .[1]' \
    "${code_user}/settings.json" \
    "${rice_dir}/vscode-theme/settings.json" >"${merged_settings}"
chmod 0644 "${merged_settings}"
mv "${merged_settings}" "${code_user}/settings.json"

write_cosmic() {
    local component="$1" key="$2" value="$3"
    local directory="${cosmic}/${component}/v1"
    mkdir -p "${directory}"
    printf '%s' "${value}" >"${directory}/${key}"
}

# COSMIC 1.4 still probes the v1 light and dark stores while the active theme
# is v2. Complete the legacy stores from packaged defaults to prevent noisy
# partial-overlay failures without duplicating generated theme data.
for theme_mode in Dark Light; do
    legacy_list_button="/usr/share/cosmic/com.system76.CosmicTheme.${theme_mode}/v1/list_button"
    if [[ -f "${legacy_list_button}" ]]; then
        install -Dm0644 "${legacy_list_button}" \
            "${cosmic}/com.system76.CosmicTheme.${theme_mode}/v1/list_button"
    fi
done
"${cosmic_locale[@]}" cosmic-settings appearance import \
    "${rice_dir}/luigios-dark.ron"

write_cosmic com.system76.CosmicBackground all \
"(
    output: \"all\",
    source: Path(\"${wallpaper_dir}/luigios-workstation.png\"),
    filter_by_theme: false,
    rotation_frequency: 300,
    filter_method: Lanczos,
    scaling_mode: Zoom,
    sampling_method: Alphanumeric,
)"
write_cosmic com.system76.CosmicBackground same-on-all "true"

write_cosmic com.system76.CosmicPanel.Panel anchor_gap "true"
write_cosmic com.system76.CosmicPanel.Panel expand_to_edges "false"
write_cosmic com.system76.CosmicPanel.Panel border_radius "12"
write_cosmic com.system76.CosmicPanel.Panel margin "6"
write_cosmic com.system76.CosmicPanel.Panel padding "2"
write_cosmic com.system76.CosmicPanel.Panel opacity "0.92"
write_cosmic com.system76.CosmicPanel.Panel size "S"
write_cosmic com.system76.CosmicPanel.Panel spacing "4"
write_cosmic com.system76.CosmicPanel.Dock autohide "OnOverlap"
write_cosmic com.system76.CosmicPanel.Dock border_radius "20"
write_cosmic com.system76.CosmicPanel.Dock margin "6"
write_cosmic com.system76.CosmicPanel.Dock padding "4"
write_cosmic com.system76.CosmicPanel.Dock opacity "0.92"
write_cosmic com.system76.CosmicPanel.Dock size "M"
write_cosmic com.system76.CosmicPanel.Dock spacing "4"

write_cosmic com.system76.CosmicTk interface_density "Compact"
write_cosmic com.system76.CosmicTk header_size "Compact"
write_cosmic com.system76.CosmicTk apply_theme_global "true"
write_cosmic com.system76.CosmicTk icon_theme '"LuigiOS"'

for gtk_version in 3.0 4.0; do
    gtk_settings="${XDG_CONFIG_HOME:-${HOME}/.config}/gtk-${gtk_version}/settings.ini"
    mkdir -p "$(dirname "${gtk_settings}")"
    if [[ ! -f "${gtk_settings}" ]]; then
        printf '[Settings]\ngtk-icon-theme-name=LuigiOS\n' >"${gtk_settings}"
    elif grep -q '^gtk-icon-theme-name=' "${gtk_settings}"; then
        sed -i 's/^gtk-icon-theme-name=.*/gtk-icon-theme-name=LuigiOS/' "${gtk_settings}"
    else
        printf 'gtk-icon-theme-name=LuigiOS\n' >>"${gtk_settings}"
    fi
done
gsettings set org.gnome.desktop.interface icon-theme 'LuigiOS' 2>/dev/null || true

write_cosmic com.system76.CosmicTerm app_theme "Dark"
write_cosmic com.system76.CosmicTerm font_name '"JetBrainsMono Nerd Font"'
write_cosmic com.system76.CosmicTerm font_size "14"
write_cosmic com.system76.CosmicTerm opacity "96"
write_cosmic com.system76.CosmicTerm show_headerbar "true"
write_cosmic com.system76.CosmicTerm show_pane_borders "true"
write_cosmic com.system76.CosmicTerm use_bright_bold "true"
write_cosmic com.system76.CosmicTerm syntax_theme_dark '"COSMIC Dark"'

write_cosmic com.system76.CosmicAppList favorites '[
    "com.system76.CosmicFiles",
    "com.system76.CosmicTerm",
    "com.visualstudio.code.oss",
    "io.github.cromite.cromite",
    "com.system76.CosmicEdit",
    "com.system76.CosmicSettings",
    "com.system76.CosmicStore",
]'

echo "LuigiOS COSMIC rice applied."
echo "Backup: ${backup}"
echo "Reload Code - OSS and log out/in if a running shell component does not refresh."
touch "${state_root}/applied-v1"
