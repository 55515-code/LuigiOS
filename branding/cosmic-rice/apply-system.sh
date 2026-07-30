#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run through PolicyKit: pkexec $0" >&2
    exit 1
fi
rice_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${rice_dir}/../branding/assets" ]]; then
    bundle_root="$(cd -- "${rice_dir}/.." && pwd)"
else
    bundle_root="$(cd -- "${rice_dir}/../.." && pwd)"
fi
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="/var/lib/luigios-rice/backups/${stamp}"
mkdir -p "${backup}"

[[ -f /etc/plymouth/plymouthd.conf ]] &&
    cp -a /etc/plymouth/plymouthd.conf "${backup}/plymouthd.conf"
[[ -f /boot/limine.conf ]] && cp -a /boot/limine.conf "${backup}/limine.conf"
[[ -d /var/lib/AccountsService/users ]] &&
    cp -a /var/lib/AccountsService/users "${backup}/accounts-users"

install -d -m 0755 /usr/share/plymouth/themes/luigios
install -m 0644 "${rice_dir}/plymouth/luigios.plymouth" \
    /usr/share/plymouth/themes/luigios/luigios.plymouth
install -m 0644 "${rice_dir}/plymouth/luigios.script" \
    /usr/share/plymouth/themes/luigios/luigios.script
install -m 0644 "${bundle_root}/branding/assets/core/luigios-symbolic.svg" \
    /usr/share/plymouth/themes/luigios/logo.svg
rsvg-convert -w 176 -h 176 \
    /usr/share/plymouth/themes/luigios/logo.svg \
    -o /usr/share/plymouth/themes/luigios/logo.png

install -d -m 0755 /etc/plymouth
if [[ ! -f /etc/plymouth/plymouthd.conf ]]; then
    printf '[Daemon]\nTheme=luigios\n' >/etc/plymouth/plymouthd.conf
elif grep -q '^Theme=' /etc/plymouth/plymouthd.conf; then
    sed -i 's/^Theme=.*/Theme=luigios/' /etc/plymouth/plymouthd.conf
else
    printf 'Theme=luigios\n' >>/etc/plymouth/plymouthd.conf
fi

install -d -m 0755 /boot/luigios
install -m 0644 \
    "${bundle_root}/branding/assets/boot/boot-logo-1280x800.png" \
    /boot/luigios/boot-menu.png

if [[ -f /boot/limine.conf ]]; then
    sed -i '/^# BEGIN LUIGIOS RICE$/,/^# END LUIGIOS RICE$/d' /boot/limine.conf
    {
        printf '\n# BEGIN LUIGIOS RICE\n'
        cat "${rice_dir}/limine-branding.conf"
        printf '# END LUIGIOS RICE\n'
    } >>/boot/limine.conf
fi

install -d -m 0700 /var/lib/AccountsService/users
install -d -m 0755 /var/lib/AccountsService/icons
while IFS=: read -r account _ uid _; do
    (( uid >= 1000 && uid < 60000 )) || continue
    account_file="/var/lib/AccountsService/users/${account}"
    account_icon="/var/lib/AccountsService/icons/${account}"
    install -m 0644 "${bundle_root}/branding/assets/community/avatar-512.png" \
        "${account_icon}"
    if [[ ! -f "${account_file}" ]]; then
        printf '[User]\nSystemAccount=false\n' >"${account_file}"
    fi
    if grep -q '^Icon=' "${account_file}"; then
        sed -i "s|^Icon=.*|Icon=${account_icon}|" "${account_file}"
    else
        printf 'Icon=%s\n' "${account_icon}" >>"${account_file}"
    fi
done </etc/passwd

if command -v limine-mkinitcpio >/dev/null 2>&1; then
    limine-mkinitcpio
else
    mkinitcpio -P
fi
echo "LuigiOS system rice applied. Backup: ${backup}"
