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

## Current status

LuigiOS is an early VM-beta project, not a general end-user release. The
current source produces a locked CachyOS/COSMIC image and has passed clean
offline installation, repeated cold boot and login, product-contract tests,
and guarded Btrfs recovery testing in disposable virtual machines.

Physical hardware support is not yet qualified. Use non-critical hardware or a
disposable VM, keep an independently verified backup, and report results in
the [hardware qualification tracker][qualification].

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

Recovery, safe upgrades, and the data-preserving Fresh Start contract are
documented in [`docs/RECOVERY.md`](docs/RECOVERY.md). These workflows never
format an installed system. Preservation, tamper rejection, Btrfs root
cutover, and unchanged persistent-subvolume identity have passed the guarded
disposable-VM test; physical-machine recovery remains blocked on the remaining
UEFI and hardware qualification gates.

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

## Community

- Coordinate development and testing in the [LuigiOS Discord][discord].
- Claim a focused contribution lane in the [qualification tracker][qualification].
- Use [GitHub Discussions][discussions] for proposals and longer-form community
  conversations.
- Read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md),
  and [`SECURITY.md`](SECURITY.md) before participating.

LuigiOS welcomes developers, testers, technical writers, designers, and
accessibility contributors. The project does not distribute games, console
firmware, BIOS files, keys, or other proprietary payloads.

[discord]: https://discord.gg/BDfCJPUeVG
[discussions]: https://github.com/55515-code/LuigiOS/discussions
[qualification]: https://github.com/55515-code/LuigiOS/issues/12
