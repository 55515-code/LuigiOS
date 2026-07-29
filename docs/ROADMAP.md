# Roadmap

## Qualification

- Build the first locked ISO from a clean CachyOS workstation.
- Boot-test UEFI and legacy paths in virtual machines.
- Install to Btrfs and verify rollback after an interrupted package transaction.
- Validate AMD, Intel, and NVIDIA graphics on representative hardware.
- Exercise suspend, Bluetooth, Wi-Fi, audio, firmware updates, containers,
  compilers, Code - OSS, and the complete COSMIC first-login experience.

## Release

- Rebuild twice from the same lock and compare extracted filesystem manifests.
- Publish the ISO checksum, dependency lock, source revision, and QA report.
- Document the intentional exceptions if container metadata prevents a
  bit-identical outer ISO while file payloads remain identical.
