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

## SDK and contributor experience

- Treat `tools/sdk` as a stable, documented product interface.
- Add a guided `sdk init` workflow that creates a user-owned customization
  project without modifying the LuigiOS source checkout.
- Define declarative workstation profiles for packages, services, COSMIC
  settings, terminal and editor defaults, and organization policy.
- Add schema validation, dry-run plans, diffs, and rollback metadata before a
  profile can touch a workstation or image.
- Support rootless container and VM test deployments before host application.
- Produce machine-readable build, deployment, and QA reports.
- Provide templates and a one-command contributor check that match CI.
- Keep image construction, host customization, and fleet deployment as
  separate SDK surfaces sharing one profile model.
