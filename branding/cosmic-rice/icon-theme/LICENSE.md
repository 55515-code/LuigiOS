# Icon licensing

The original LuigiOS icons in `scalable/apps` and `symbolic/apps` are part of
the LuigiOS brand artwork and are licensed under CC BY-SA 4.0, matching
`branding/LICENSES/CC-BY-SA-4.0.txt`.

The deployed theme inherits the separately installed Papirus Dark, COSMIC, and
hicolor themes. No third-party icon files are committed here. At deployment
time, `apply-user.sh` promotes the locally installed Papirus green folder
variants into the user-local generated theme. Papirus is distributed under
GPL-3.0; its local package license remains authoritative.
