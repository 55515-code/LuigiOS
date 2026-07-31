# Testing

`./tools/ci-check` validates the product contract, dependency lock, scripts, and
legacy-tree removal. `./tools/sdk prepare` exercises the pinned Archiso overlay.
`./tools/validate-cromite` validates the Cromite browser integration across
manifest, lock file, apply-user.sh, firstboot, and profile desktop entry.

Release qualification additionally covers:

- two clean builds and extracted filesystem-manifest comparison;
- live and installed UEFI boot, Btrfs layout, full upgrades, snapshots, rollback;
- AMD, Intel, and NVIDIA graphics; audio, Wi-Fi, Bluetooth, suspend, firmware;
- COSMIC greeter/session, icons, wallpaper, terminal, Code - OSS, accessibility;
- Podman, Distrobox, Rust, C/C++, Python, Node.js, Go, Java, debuggers, sccache;
- peer disabled by default, explicit enable/disable, DHT/privacy controls,
  metered/battery policy, cache quotas, service confinement, and corrupt objects;
- package signature and future TUF failure modes: expiry, rollback, freeze,
  mix-and-match, wrong length/hash, compromised mirror, and unavailable peers.

## Automated QA scripts

- `./tools/qa/functional-test` — rootless QEMU boot smoke test against a built ISO.
  Checks UEFI boot, Cromite, default-browser config, recovery UI, previous-root
  entries, and recovery sim. Requires `/dev/kvm`, `qemu-system-x86_64`, `jq`,
  `socat`.
- `./tools/qa/run-recovery-btrfs-vm` — disposable Btrfs recovery VM test via
  rootless Podman. Destructive to a synthetic disk.
- `./tools/qa/hardware-test` — bare-metal boot and installation test against a
  real disk device. **Destructive**; requires rootless Podman and
  `luigios-qemu-runner`.
- `./tools/qa/qmp` — minimal QMP client for VM input/screenshot/send-key ops
  used by functional and hardware QA scripts.
