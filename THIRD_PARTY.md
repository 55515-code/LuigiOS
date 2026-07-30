# Third-party components

LuigiOS consumes released packages from CachyOS and Arch Linux repositories;
the exact dependency closure, source repository, version, filename, and SHA-256
digest are recorded in `sdk/package-lock.json`.

The image profile derives from the official CachyOS Live ISO commit pinned in
`sdk/versions.env`. COSMIC, Papirus, Transmission, Syncthing, Sigstore, Syft,
Skopeo, Podman, and other components retain their upstream licenses and marks.
LuigiOS does not imply endorsement by those projects.
