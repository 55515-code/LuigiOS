# Testing

`./tools/ci-check` validates the product contract, dependency lock, scripts, and
legacy-tree removal. `./tools/sdk prepare` exercises the pinned Archiso overlay.

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
