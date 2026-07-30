# LuigiOS beta acceptance — 2026-07-29

## Candidate

- ISO: `dist/luigios-2026.07.28-x86_64.iso`
- SHA-256: `01fb57613b16d893e0bb3231935dad7cc6822e50bf0ae363a2baddf8e942204a`
- Size: 7,633,891,328 bytes
- Package roots: 151
- Exact locked package closure: 868
- CachyOS Live ISO source: `5de0e4c3fad800c0f351379989c31b86b65e02fe`

## Automated and virtualized gates

The release build ran in the rootless KVM builder with no virtual NIC. It
verified the complete package cache before invoking `mkarchiso`; the release
therefore did not resolve or download packages from a moving mirror.

The final acceptance install used:

- Q35 chipset and OVMF UEFI;
- KVM and an x86-64 host CPU;
- 8 vCPUs and 8 GiB RAM;
- a newly created 64 GiB NVMe QCOW2 target;
- no virtual network interface;
- erase-disk Btrfs installation;
- a second boot with the ISO removed.

Passed gates:

- ISO structural inspection and SHA-256 verification;
- all nine product-contract tests;
- offline Calamares partition, package, user, locale, Limine, service,
  firewall, snapshot, branding, and cleanup jobs;
- installed Limine kernel entries for CachyOS and CachyOS LTS;
- installed-system boot to the branded COSMIC greeter;
- successful COSMIC login and terminal launch;
- zero failed system units and zero failed user units;
- active `cosmic-greeter` and UFW;
- disabled SSH;
- completed LuigiOS first-boot stamp;
- installed LuigiOS icon theme and Code OSS workstation extension;
- available Podman, Rust, and Code OSS developer commands.

The locale regression pass additionally selected German for the system,
German for the keyboard, Australian English for regional formats, and
Australia/Adelaide for the timezone. The installed system retained all four
choices, booted with zero failed system units, and presented the COSMIC
session in German. The pass also exposed that greetd's PAM boundary discarded
the greeter language. LuigiOS now installs a target-only greeter wrapper which
loads `/etc/locale.conf` at the final process boundary. A rebooted installed
VM confirmed German greeter messages while retaining the independently chosen
Australian date format.

The corrected release ISO was rebuilt offline, structurally inspected, and
boot-smoked to the live COSMIC initial setup and Calamares welcome screen. A
separate clean-media smoke loop caught and eliminated an intermediate
live-only permission regression by keeping the wrapper exclusively in the
installed-target payload.

The final evidence is retained under `.sdk/qa-install/`, including
`rc-install-complete.png`, `rc-greeter.png`, `rc-validation.png`,
`rc-user-validation.png`, the installed QCOW2 disk, OVMF variable store, and
serial logs. Earlier failed loops are retained in timestamped sibling
directories so the fixes remain auditable.

Locale evidence is retained under `.sdk/locale-qa/`; corrected-ISO live-boot
evidence is retained under `.sdk/final-locale-qa/`.

The subsequent setup-flow regression pass found that COSMIC Initial Setup
enumerates only generated locales through `locale -a`; the live image
deliberately generated only `C.UTF-8`, leaving that redundant setup page
empty. LuigiOS now suppresses COSMIC Initial Setup in both the live
environment and Calamares-installed target, and automatically starts
Calamares as the single provisioning path. A pristine boot of the corrected
ISO landed directly on the LuigiOS installer, exposed a populated multilingual
selector, and successfully switched the complete installer UI to German.
Screenshots and VM evidence are retained under `.sdk/language-fix-qa/`.

The final post-install qualification used a new blank 64 GiB QCOW2 disk and a
fresh OVMF variable store. The installer completed its explicit
`Verifying the LuigiOS boot installation` gate, including installed-user rice
seeding, Limine payload hash validation, a closed FAT filesystem check, and a
second payload verification after remount. Two independent cold boots reached
the branded greeter, and both logins produced the complete COSMIC top panel and
dock. The installed system reported no failed system or user units; the
one-shot panel readiness service completed successfully. Final evidence is
retained under `.sdk/postinstall-final2/`, including
`final-boot-greeter.png`, `final-qualified-first-login.png`,
`final-service-checks.png`, `repeat-greeter.png`, and `repeat-login.png`.

## Beta disposition

This candidate is accepted for **VM beta** and is ready for controlled
installation on non-critical bare hardware. It is not yet hardware-qualified.

The first hardware pass must explicitly test:

- Secure Boot policy and signatures;
- AMD, Intel, and NVIDIA graphics paths, including the NVIDIA open modules;
- Wi-Fi, Bluetooth, Ethernet, audio, webcam, and suspend/resume;
- firmware update discovery and application;
- high-DPI and multi-monitor behavior;
- real NVMe/SATA erase installation and Btrfs rollback;
- USB boot compatibility across representative UEFI implementations;
- thermal, scheduler, battery, and performance behavior under sustained load.

Use a backed-up, non-critical machine first. Do not promote this build from
beta until the hardware matrix and rollback/recovery cases are recorded.
