#!/usr/bin/env bash
set -euo pipefail

installer=/usr/share/luigios/calamares
install -Dm0644 /usr/share/luigios/os-release /usr/lib/os-release
ln -sfn ../usr/lib/os-release /etc/os-release

# Calamares is LuigiOS' single provisioning flow. COSMIC Initial Setup derives
# its language list from generated locales (`locale -a`), which is intentionally
# minimal in the live image, and duplicates the installer account/locale pages.
# Suppress that package autostart and launch the branded installer directly.
cat >/etc/xdg/autostart/com.system76.CosmicInitialSetup.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=COSMIC Initial Setup
Hidden=true
EOF
install -Dm0644 /usr/share/applications/luigios-installer.desktop \
    /etc/xdg/autostart/luigios-installer.desktop

install -Dm0644 "${installer}/settings_online.conf" \
    /usr/share/calamares/settings_online.conf
for module in \
    pacstrap.conf \
    partition.conf \
    services-systemd.conf \
    shellprocess_finalize_target.conf \
    shellprocess_initialize_pacman.conf \
    shellprocess_limine_initramfs.conf \
    shellprocess_luigios.conf
do
    install -Dm0644 "${installer}/${module}" \
        "/etc/calamares/modules/${module}"
done

# LuigiOS supports one installer path and one bootloader. Avoid the redundant
# single-item package chooser, teach CachyOS' pacstrap module to consume the
# explicit profile setting, and make the installed Limine identity explicit.
pacstrap_module=/usr/lib/calamares/modules/pacstrap/main.py
python - "${pacstrap_module}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
old = 'bootloader = libcalamares.globalstorage.value("packagechooser_bootloader")'
new = (
    'bootloader = (libcalamares.job.configuration.get("bootloader") or '
    'libcalamares.globalstorage.value("packagechooser_bootloader"))'
)
if source.count(old) != 1:
    raise SystemExit(f"unexpected CachyOS pacstrap bootloader API in {path}")
path.write_text(source.replace(old, new))
PY
sed -i \
    -e 's/efiBootloaderId: "cachyos"/efiBootloaderId: "luigios"/' \
    -e 's#limineSplashLogo: .*#limineSplashLogo: "/usr/share/luigios/branding/assets/boot/boot-logo-1280x800.png"#' \
    /etc/calamares/modules/bootloader.conf

# limine-mkinitcpio-hook intentionally replaces Arch's normal mkinitcpio ALPM
# hook for installed systems. A live Archiso has no mounted ESP, so that hook
# cannot create the initramfs that mkarchiso subsequently collects. Keep the
# Limine integration in the target package set, but restore the stock hook and
# build the live initramfs explicitly after the package transaction.
rm -f /etc/pacman.d/hooks/80-limine-efi-deploy.hook \
    /etc/pacman.d/hooks/90-mkinitcpio-install.hook \
    /etc/boot/hooks/pre.d/10-limine-reset-enroll \
    /etc/boot/hooks/post.d/90-limine-enroll-config
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
# The CachyOS Limine package places an installed-system wrapper in
# /usr/local/bin. The live image has no ESP, so invoke the real generator.
# LuigiOS does not offer PXE boot; omit its optional NFS/NBD/memdisk hooks.
cat >/etc/mkinitcpio.conf.d/archiso.conf <<'EOF'
HOOKS=(base udev microcode modconf archiso archiso_loop_mnt block filesystems keyboard)
EOF
/usr/bin/mkinitcpio -P
