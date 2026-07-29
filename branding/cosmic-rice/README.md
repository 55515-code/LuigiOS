# LuigiOS COSMIC Workstation Rice

This package applies the LuigiOS visual identity to a CachyOS COSMIC
workstation from boot menu through desktop. It deliberately keeps native
COSMIC interaction patterns and accessibility while replacing the visual
identity.

## Design

- OLED black and charcoal surfaces (`#000000`, `#121416`, `#1A1A1A`)
- LuigiOS green (`#22C55E`) only for focus, selection, progress, and health
- Inter for interface text and JetBrains Mono Nerd Font for developer surfaces
- restrained 8–12 px radii, compact panel, and an intelligent-hide dock
- mascot artwork only in the wallpaper; boot and greeter use the core mark
- LuigiOS icon layer over Papirus Dark and COSMIC fallbacks, with coherent
  green folders and original core application/launcher glyphs

## Apply and roll back

Run `./apply-user.sh` as the desktop user. Run `./apply-system.sh` through
PolicyKit to install the boot, greeter, and account artwork. Both scripts create
timestamped backups under `~/.local/state/luigios-rice/backups` and
`/var/lib/luigios-rice/backups`.

`rollback-user.sh BACKUP_DIRECTORY` restores a user backup. System backups are
plain file trees and can be restored from a rescue shell.

The system script updates the initramfs after installing the Plymouth theme.
The Limine menu remains fully usable and its kernel entries are not modified.
COSMIC Terminal uses the global LuigiOS palette with JetBrains Mono Nerd Font,
96% opacity, visible pane boundaries, and bright-bold ANSI rendering.

The icon layer inherits Papirus Dark for broad application, action, device,
and MIME coverage, then overrides the visible OS identity. It does not modify
the packaged Papirus or COSMIC themes. COSMIC, GTK 3, GTK 4, and the GNOME
interface icon setting are updated together so native and compatibility apps
resolve the same theme.

Code - OSS receives the local `LuigiOS Workstation` extension with a matching
editor/terminal palette and purpose-built file icons. Existing unrelated user
settings are preserved through a JSON object merge. The deployed settings use
JetBrains Mono, accessible contrast, semantic highlighting, restrained motion,
green Git-added/focus states, blue modified states, amber warnings, and red
errors. Reload the Code window once after applying.
