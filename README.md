# LuigiOS

LuigiOS is a reproducible, CachyOS-derived COSMIC developer workstation for
modern x86-64-v3 hardware. It combines CachyOS's optimized Arch repositories
and kernels with a focused COSMIC desktop, rollback-capable Btrfs updates,
current developer tooling, decentralized release distribution, and a complete
LuigiOS visual system.

The product contract lives in `product/cachyos/product.json`. Release images
are derived from a pinned revision of the official CachyOS Live ISO project;
the complete pacman dependency closure and every package checksum are recorded
in `sdk/package-lock.json`.

## Build

```sh
./tools/sdk doctor
./tools/sdk bootstrap
./tools/sdk prepare
./tools/sdk fetch
./tools/sdk stage
./tools/sdk validate
./tools/sdk image
```

To refresh repository inputs intentionally:

```sh
sudo pacman -Sy
./tools/sdk lock
./tools/sdk fetch
./tools/sdk prepare
./tools/sdk stage
./tools/sdk image
```

`image-dev` is available for local iteration, but it is intentionally marked
non-release because it resolves against moving repositories.

Release image assembly is unattended after a one-time builder bootstrap. A
rootless Podman container launches a KVM-isolated Arch builder VM, where
`mkarchiso` has the guest-root mount privileges it requires without receiving
host-root privileges. The release boot has no virtual NIC, consumes only the
content-locked package cache, and writes user-owned artifacts to `dist/`. It
does not request host `sudo` or PolicyKit approval. The QEMU runner and official
Arch cloud image are digest/checksum pinned. Tune guest resources with
`LUIGIOS_VM_MEMORY` and `LUIGIOS_VM_CPUS`; progress is recorded in
`.sdk/vm-build.log`.

## Product boundaries

- CachyOS and its x86-64-v3 repositories are the only base.
- COSMIC is the only desktop session and `cosmic-greeter` is the display manager.
- Pacman updates are full-system transactions with Snapper recovery.
- Podman is the default container engine; Rust, LLVM, GCC, mold, sccache, Go,
  Python, Node.js, and a JDK are included.
- UFW is enabled, remote login is disabled, and telemetry is off by default.
- TUF-authorized, content-addressed release distribution is the architectural
  trust model; opt-in BitTorrent v2, HTTPS web seeds, and OCI are byte transports.
- Boot, greeter identity, desktop, terminal, icons, and Code - OSS share the
  LuigiOS visual system under `branding/cosmic-rice`.

Run `./tools/ci-check` before submitting a change.

## SDK and contributions

The SDK is a defining LuigiOS feature alongside decentralized networking.
Today, [`tools/sdk`](tools/sdk) provides the reproducible source, lock, cache,
profile, image, and inspection workflow. The contributor-facing contract and
the non-duplicative customization/deployment stretch plan are documented in
[`docs/SDK.md`](docs/SDK.md).

A contributor can validate a checkout without host-root access:

```sh
./tools/sdk doctor
./tools/sdk validate
./tools/ci-check
```

Release image assembly uses the rootless VM builder described above. Proposed
workstation profiles must support validation and dry-run review before they are
allowed to change a host.
