# Releasing

1. Update the CachyOS commit and `SOURCE_DATE_EPOCH` intentionally.
2. Refresh pacman databases, run `tools/sdk lock`, and review every dependency change.
3. Run `tools/sdk fetch` and verify the content-addressed cache.
4. Run `tools/ci-check`, `tools/sdk prepare`, and `tools/sdk stage`.
5. Build with `tools/sdk image`; release mode rejects an unstaged or stale
   package lock. Rootless Podman launches a KVM-isolated Arch builder VM, so
   `mkarchiso` receives guest-root mount privileges but no host-root authority.
   The first run downloads and verifies the pinned Arch cloud image and
   provisions the reusable VM. Release assembly then boots without a virtual
   NIC and uses only the locked package cache. Follow `.sdk/vm-build.log` for
   progress; tune the guest with `LUIGIOS_VM_MEMORY` and `LUIGIOS_VM_CPUS`.
   Run `tools/sdk inspect` to validate identity, boot payloads,
   legacy-path absence, and write the ISO checksum.
6. Test live boot, installation, updates, rollback, COSMIC, development tools,
   peer opt-in/off behavior, confinement, and the complete visual system.
7. Generate SHA-256 checksums, SPDX JSON with Syft, SLSA provenance, and a
   Sigstore bundle. Publish them with source revision, package lock, and QA report.
8. Promote an existing artifact digest between channels; do not rebuild it.

Until the TUF client and signing ceremony are qualified, pacman repository
signatures remain the installation authority and decentralized delivery remains
an isolated transport preview.
