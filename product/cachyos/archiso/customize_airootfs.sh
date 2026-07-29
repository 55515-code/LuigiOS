#!/usr/bin/env bash
set -euo pipefail

installer=/usr/share/luigios/calamares
install -Dm0644 /usr/share/luigios/os-release /usr/lib/os-release
ln -sfn ../usr/lib/os-release /etc/os-release
install -Dm0644 "${installer}/settings_online.conf" \
    /usr/share/calamares/settings_online.conf
for module in \
    packagechooser_bootloader.conf \
    pacstrap.conf \
    partition.conf \
    services-systemd.conf \
    shellprocess_initialize_pacman.conf \
    shellprocess_luigios.conf
do
    install -Dm0644 "${installer}/${module}" \
        "/etc/calamares/modules/${module}"
done

# limine-mkinitcpio-hook intentionally replaces Arch's normal mkinitcpio ALPM
# hook for installed systems. A live Archiso has no mounted ESP, so that hook
# cannot create the initramfs that mkarchiso subsequently collects. Keep the
# Limine integration in the target package set, but restore the stock hook and
# build the live initramfs explicitly after the package transaction.
rm -f /etc/pacman.d/hooks/80-limine-efi-deploy.hook \
    /etc/pacman.d/hooks/90-mkinitcpio-install.hook
live_kernel=
while IFS= read -r pkgbase_file; do
    if [[ "$(<"${pkgbase_file}")" == linux-cachyos-lts ]]; then
        live_kernel="$(dirname "${pkgbase_file}")/vmlinuz"
        break
    fi
done < <(find /usr/lib/modules -mindepth 2 -maxdepth 2 -name pkgbase -type f)
[[ -n "${live_kernel}" && -r "${live_kernel}" ]] || {
    echo "unable to locate the locked linux-cachyos-lts kernel" >&2
    exit 1
}
install -Dm0644 "${live_kernel}" /boot/vmlinuz-linux-cachyos-lts
mkinitcpio -P
