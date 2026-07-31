# Roadmap

## Qualification

- Completed: build and structurally inspect the first locked ISO.
- Completed: clean offline VM installation, repeated cold boots, greeter login,
  and complete COSMIC panel/dock validation.
- Completed: guarded disposable-VM Btrfs Fresh Start, preservation, tamper
  rejection, previous-root retention, and unchanged user-data verification.
- Completed: `tools/qa/functional-test` UEFI boot smoke, recovery sim, and
  Cromite/default-browser gating.
- Completed: `tools/qa/hardware-test` runner for destructive bare-metal boot and
  installation qualification.
- Next: exercise full offline upgrades, package repair, Fresh Start cutover,
  previous-root rollback, and recovery from UEFI live media.
- Validate AMD, Intel, and NVIDIA graphics on representative hardware.
- Exercise suspend, Bluetooth, Wi-Fi, audio, firmware updates, containers,
  compilers, Code - OSS, and the complete COSMIC first-login experience.

## Release

- Completed: beta build pipeline with `LUIGIOS_BETA=1` producing
  `luigios-beta-*.iso` via `.github/workflows/beta.yml`.
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

## Transactional recovery

- Implemented: one LuigiOS Recovery Center in the installed OS and live image.
- Implemented: stage full upgrades through systemd's offline-update target with Snapper
  pre/post restore points and Limine recovery entries.
- Implemented: repair package and boot payloads from the signed, locked release repository.
- Implemented: build Fresh Start roots from the permanent installation snapshot while
  preserving user-data subvolumes in place.
- Implemented and VM-tested: hash and verify preserved system settings before
  any boot cutover.
- Implemented and VM-tested: retain the previous root through cutover.
- Next: qualify the new root through repeated cold-boot, login,
  service, package, and user-data integrity checks.
