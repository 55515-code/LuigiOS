#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="luigios"
iso_label="LUIGIOS_$(date --date="@${SOURCE_DATE_EPOCH:?}" +%Y%m)"
iso_publisher="LuigiOS <https://github.com/LuigiOS>"
iso_application="LuigiOS CachyOS COSMIC Developer Workstation"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:?}" +%Y.%m.%d)"
install_dir="arch"
buildmodes=('iso')
bootmodes=('uefi.systemd-boot')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86' '-b' '1M' '-Xdict-size' '1M')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/etc/gshadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/etc/polkit-1/rules.d"]="0:0:750"
  ["/etc/sudoers.d"]="0:0:750"
  ["/etc/sudoers.d/g_wheel"]="0:0:440"
  ["/usr/lib/luigios/firstboot"]="0:0:755"
  ["/usr/lib/luigios/install-target"]="0:0:755"
  ["/usr/bin/luigios-network"]="0:0:755"
  ["/usr/local/bin/calamares-online.sh"]="0:0:755"
)
