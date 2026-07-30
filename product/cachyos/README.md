# CachyOS product layer

This directory is the complete active LuigiOS base contract.

- `product.json` defines the supported architecture and workstation behavior.
- `packages.x86_64` contains only direct package roots. The generated lock
  resolves and hashes the full dependency closure.
- `forbidden-packages.txt` prevents desktop and product-scope regressions.
- `services.json` is the allowlist for enabled system services.
- `archiso/` overrides the pinned official CachyOS live profile.
- `overlay/` contains auditable files copied into the image root.

`./tools/sdk prepare` creates a clean Archiso profile from the pinned upstream
commit and these files. `./tools/sdk lock` generates the content-addressed
package closure. A release build requires a complete verified package cache;
an unlocked rolling-repository build is development-only.
