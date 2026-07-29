# LuigiOS visual system

`cosmic-rice` is the installable presentation layer for the CachyOS COSMIC
workstation. It applies:

- LuigiOS boot and Plymouth artwork;
- COSMIC colors, density, panel, dock, wallpaper, and favorites;
- a LuigiOS icon overlay backed by Papirus for broad application coverage;
- terminal typography and appearance;
- a complete Code - OSS color theme merged into existing user settings;
- user imagery for the greeter.

`apply-user.sh` backs up affected user configuration before applying defaults.
`apply-system.sh` requires PolicyKit/root, backs up boot and account state, and
works both from the source tree and the installed `/usr/share/luigios` bundle.

The style is dark, restrained, high-contrast, technically precise, and centered
on the green LuigiOS mark. Network and recovery surfaces use the same vocabulary
without sacrificing recognizable platform iconography.
