# LuigiOS recovery and Fresh Start

LuigiOS recovery is a transactional product feature, not a destructive
installer shortcut. The authoritative contract is
[`profiles/recovery-v1.json`](../profiles/recovery-v1.json).

## Safety invariants

- Recovery and upgrade never format a partition.
- `/home` remains an independent Btrfs subvolume and is never copied over
  during root recovery.
- `/root`, `/srv`, caches, logs, temporary state, and LuigiOS transaction state
  are also independent subvolumes.
- Every operation creates an inspectable plan and a pre-change restore point.
- Fresh Start creates a new root from the permanent installation snapshot. It
  does not mutate or delete the previous root.
- Boot configuration changes only after package, filesystem, preservation, and
  boot-payload verification succeeds.
- A failed transaction remains available for diagnosis and the old root stays
  bootable.

A Btrfs snapshot is a local rollback mechanism, not a backup. Hardware failure
can damage both a subvolume and its snapshots, so physical installation still
requires an independently verified backup.

## Recovery modes

### Safe Upgrade

The Recovery Center uses `checkupdates` with an isolated package database to
show and download one complete Arch/CachyOS transaction. The approved
transaction runs through systemd's offline-update target with Snapper pre/post
restore points. Partial upgrades are rejected.

### Repair

Repair reinstalls the signed LuigiOS package roots from the release's locked
offline repository, preserves pacman's backup-managed configuration, rebuilds
initramfs and Limine payloads, and verifies the resulting boot entry. It can run
against the installed system or a mounted LuigiOS target from live media.

### Fresh Start

Calamares creates a permanent post-install snapshot after the account, locale,
bootloader, services, and LuigiOS defaults exist. Fresh Start creates a new
writable root from that snapshot while the persistent data subvolumes remain
unchanged.

User files and user-space configuration stay in `/home` without a copy/move
step. Identity, locale, timezone, host, fstab/crypttab, and encrypted network
credentials are captured with ownership, modes, timestamps, symlink targets,
extended attributes, and SHA-256 content digests before they are reapplied.

System overrides that could reproduce the failure—custom pacman configuration,
systemd overrides, kernel tuning, sudoers, SSH host configuration, PolicyKit,
and udev rules—are retained in the root-only transaction bundle for review
instead of being silently activated in the fresh root.

### Live-media targeting

The live Recovery Center first requests PolicyKit authorization for read-only
discovery. The engine considers only Btrfs partitions or mapped volumes,
temporarily mounts their top level read-only with `nosuid`, `nodev`, and
`noexec`, and reports only root subvolumes whose `os-release` identifies
LuigiOS. If more than one root exists, the operator must choose the exact
device and subvolume.

Planning remounts that exact pair read-only. An approved Repair or Fresh Start
remounts the same pair writable, attaches only the declared persistent
subvolumes and the stable UUID/PARTUUID/LABEL boot filesystem from its fstab,
then unmounts the complete target when the transaction ends. Device and
subvolume arguments are an inseparable pair; recovery never guesses from
partition ordering and contains no formatting primitive.

## Qualification gate

No real workstation installation is permitted until all of these pass:

1. deterministic preservation-manifest and failure-injection tests;
2. rootless container simulations for planning and archive verification;
3. disposable Btrfs tests covering distinct user IDs, ACLs, xattrs, symlinks,
   sparse files, hard links, Unicode names, and interrupted transactions;
4. repeated UEFI VM upgrades, package-repair runs, Fresh Start cutovers,
   previous-root rollback, greeter login, and user-data hash comparison;
5. cold-boot tests with the ISO removed and zero failed system/user units.

The physical cutover is a separate operation with an external backup,
machine-readable before/after manifests, and explicit approval.

## QA tooling

### Functional tests (`./tools/qa/functional-test`)

Runs a rootless QEMU boot smoke test against a built ISO. Checks UEFI boot,
Cromite availability, default-browser configuration, recovery UI presence,
previous-root boot entries, recovery QA disk cleanup, and the recovery
simulation (`tools/recovery-sim`). Requires `/dev/kvm`, `qemu-system-x86_64`,
`jq`, and `socat`. Accepts `--image PATH` and `--report PATH`. By default
selects the latest `dist/luigios-*.iso` and writes a JSON report to
`.sdk/functional-test-report.json`.

### Recovery VM tests (`./tools/qa/run-recovery-btrfs-vm`)

Runs the destructive Btrfs recovery test inside a rootless QEMU VM. The VM
bootstraps via cloud-init and runs `tools/qa/recovery-btrfs-vm` against a
disposable disk tagged with serial `LUIGIOS_RECOVERY_QA`. Preserves the QA disk
when `LUIGIOS_KEEP_SUCCESSFUL_QA_DISKS=1`.

### Hardware tests (`./tools/qa/hardware-test`)

Runs a hardware boot and installation test from a specified ISO against a real
disk device. **DESTRUCTIVE**: erases the target device. Requires rootless Podman,
`/dev/kvm`, and the `luigios-qemu-runner` image passed through `--device`.
Accepts `--image PATH`, `--device PATH`, `--report PATH`, and `--keep-disk`.

## Upstream basis

- Calamares supports distribution-defined modules and branding:
  <https://calamares.io/about/>
- systemd defines the offline-update boot protocol:
  <https://www.freedesktop.org/software/systemd/man/latest/systemd.offline-updates.html>
- pacman's `--sysroot` operates on mounted guest systems:
  <https://man.archlinux.org/man/pacman.8.en>
- `checkupdates` safely uses a separate sync database and can pre-download a
  full update:
  <https://man.archlinux.org/man/extra/pacman-contrib/checkupdates.8.en>
- Btrfs documents subvolume boundaries and atomic root rollback:
  <https://btrfs.readthedocs.io/en/latest/btrfs-subvolume.html>
- Snapper documents pre/post snapshots, undo, and rollback:
  <https://man.archlinux.org/man/extra/snapper/snapper.8.en>
