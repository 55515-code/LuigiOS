import importlib.util
import json
import os
import pathlib
import socket
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE_PATH = (
    ROOT
    / "product/cachyos/overlay/usr/lib/luigios/recovery_engine.py"
)
SPEC = importlib.util.spec_from_file_location("recovery_engine", ENGINE_PATH)
ENGINE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ENGINE)
POLICY = json.loads((ROOT / "profiles/recovery-v1.json").read_text())


class PreservationContract(unittest.TestCase):
    def build_source(self, base):
        source = base / "source"
        (source / "etc/NetworkManager/system-connections").mkdir(
            parents=True
        )
        (source / "etc/pacman.d").mkdir(parents=True)
        (source / "var/lib/bluetooth").mkdir(parents=True)
        (source / "etc/hostname").write_text("luigios-dev\n")
        (source / "etc/locale.conf").write_text("LANG=en_US.UTF-8\n")
        (source / "etc/pacman.conf").write_text("[custom]\n")
        connection = (
            source
            / "etc/NetworkManager/system-connections/development.nmconnection"
        )
        connection.write_text("[connection]\nid=Development Wi-Fi\n")
        connection.chmod(0o600)
        hardlink = connection.with_name("development-copy.nmconnection")
        os.link(connection, hardlink)
        (source / "etc/localtime").symlink_to(
            "../usr/share/zoneinfo/America/New_York"
        )
        try:
            os.setxattr(connection, "user.luigios-test", b"preserved")
        except OSError:
            pass
        return source

    def test_capture_verify_restore_and_quarantine(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            source = self.build_source(base)
            bundle = base / "bundle"
            manifest = ENGINE.capture_preservation(
                source, bundle, POLICY
            )

            verification = ENGINE.verify_preservation(bundle)
            self.assertTrue(verification["valid"], verification["errors"])
            self.assertEqual(bundle.stat().st_mode & 0o777, 0o700)
            records = {
                record["path"]: record for record in manifest["entries"]
            }
            self.assertEqual(
                records["/etc/pacman.conf"]["disposition"],
                "retain-for-review",
            )
            self.assertEqual(
                records["/etc/hostname"]["disposition"], "reapply"
            )

            first = (
                bundle
                / "payload/etc/NetworkManager/system-connections/"
                "development.nmconnection"
            )
            second = first.with_name("development-copy.nmconnection")
            self.assertEqual(first.stat().st_ino, second.stat().st_ino)

            target = base / "target"
            (target / "etc").mkdir(parents=True)
            (target / "etc/pacman.conf").write_text("[luigios]\n")
            restored = ENGINE.restore_preservation(bundle, target)
            self.assertGreater(restored["restored"], 0)
            self.assertEqual(
                (target / "etc/hostname").read_text(), "luigios-dev\n"
            )
            self.assertEqual(
                (target / "etc/pacman.conf").read_text(), "[luigios]\n"
            )
            restored_first = (
                target
                / "etc/NetworkManager/system-connections/"
                "development.nmconnection"
            )
            restored_second = restored_first.with_name(
                "development-copy.nmconnection"
            )
            self.assertEqual(
                restored_first.stat().st_ino,
                restored_second.stat().st_ino,
            )
            self.assertEqual(
                os.readlink(target / "etc/localtime"),
                "../usr/share/zoneinfo/America/New_York",
            )

    def test_tampering_is_detected_before_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            source = self.build_source(base)
            bundle = base / "bundle"
            ENGINE.capture_preservation(source, bundle, POLICY)
            (bundle / "payload/etc/hostname").write_text("tampered\n")

            verification = ENGINE.verify_preservation(bundle)
            self.assertFalse(verification["valid"])
            self.assertTrue(
                any("sha256 mismatch" in item for item in verification["errors"])
            )
            target = base / "target"
            target.mkdir()
            with self.assertRaises(ENGINE.RecoveryError):
                ENGINE.restore_preservation(bundle, target)

    def test_transient_unix_sockets_are_audited_and_not_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            source = self.build_source(base)
            gnupg = source / "etc/pacman.d/gnupg"
            gnupg.mkdir()
            socket_path = gnupg / "S.dirmngr"
            listener = socket.socket(socket.AF_UNIX)
            try:
                listener.bind(str(socket_path))
                manifest = ENGINE.capture_preservation(
                    source, base / "bundle", POLICY
                )
            finally:
                listener.close()

            self.assertEqual(
                manifest["skipped_transient"],
                [
                    {
                        "path": "/etc/pacman.d/gnupg/S.dirmngr",
                        "reason": "runtime-unix-socket",
                    }
                ],
            )
            self.assertFalse(
                (base / "bundle/payload/etc/pacman.d/gnupg/S.dirmngr").exists()
            )

    def test_unexpected_non_socket_special_files_still_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            source = self.build_source(base)
            special = source / "etc/pacman.d/unexpected-fifo"
            os.mkfifo(special)
            with self.assertRaisesRegex(
                ENGINE.RecoveryError, "unsupported special file"
            ):
                ENGINE.capture_preservation(source, base / "bundle", POLICY)


class RecoveryPlanContract(unittest.TestCase):
    def test_policykit_scope_excludes_low_level_file_operations(self):
        allowed = ENGINE.parser().parse_args(["fresh-start"])
        blocked = ENGINE.parser().parse_args(
            [
                "restore-settings",
                "--bundle",
                "/tmp/bundle",
                "--target",
                "/",
            ]
        )
        alternate_policy = ENGINE.parser().parse_args(
            ["--policy", "/tmp/untrusted.json", "fresh-start"]
        )
        alternate_root = ENGINE.parser().parse_args(
            ["fresh-start", "--root", "/tmp/target"]
        )
        with mock.patch.dict(os.environ, {"PKEXEC_UID": "1000"}):
            ENGINE.validate_pkexec_scope(allowed)
            with self.assertRaisesRegex(
                ENGINE.RecoveryError, "not available through PolicyKit"
            ):
                ENGINE.validate_pkexec_scope(blocked)
            with self.assertRaisesRegex(
                ENGINE.RecoveryError, "alternate policy"
            ):
                ENGINE.validate_pkexec_scope(alternate_policy)
            with self.assertRaisesRegex(
                ENGINE.RecoveryError, "alternate root"
            ):
                ENGINE.validate_pkexec_scope(alternate_root)

    def test_installed_engine_does_not_require_checkout_parent_depth(self):
        self.assertIsNone(
            ENGINE.development_policy_path(
                pathlib.Path("/usr/lib/luigios/recovery_engine.py")
            )
        )
        self.assertEqual(
            ENGINE.development_policy_path(ENGINE_PATH),
            ROOT / "profiles/recovery-v1.json",
        )

    def test_repair_reasserts_luigios_identity_and_unit_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            share = root / "usr/share/luigios"
            vendor_system = root / "usr/lib/systemd/system"
            vendor_user = root / "usr/lib/systemd/user"
            share.mkdir(parents=True)
            vendor_system.mkdir(parents=True)
            vendor_user.mkdir(parents=True)
            (share / "os-release").write_text(
                'ID=luigios\nNAME="LuigiOS"\n'
            )
            (share / "pacman.conf").write_text("[luigios-lock]\n")
            for unit in (
                "cosmic-greeter.service",
                "luigios-firstboot.service",
                "luigios-offline-update.service",
            ):
                (vendor_system / unit).write_text("[Unit]\n")
            for unit in (
                "luigios-first-login.service",
                "luigios-panel-refresh.service",
            ):
                (vendor_user / unit).write_text("[Unit]\n")
            (root / "etc/systemd/system").mkdir(parents=True)
            (root / "etc/systemd/system/luigios-firstboot.service").write_text(
                "obsolete\n"
            )

            result = ENGINE.reassert_luigios_contract(root)

            self.assertEqual(
                (root / "usr/lib/os-release").read_text(),
                'ID=luigios\nNAME="LuigiOS"\n',
            )
            self.assertEqual(
                os.readlink(root / "etc/os-release"),
                "../usr/lib/os-release",
            )
            self.assertEqual(
                os.readlink(
                    root / "etc/systemd/system/display-manager.service"
                ),
                "/usr/lib/systemd/system/cosmic-greeter.service",
            )
            self.assertFalse(
                (root / "etc/systemd/system/luigios-firstboot.service").exists()
            )
            self.assertIn("/usr/lib/os-release", result["identity"])

    def test_fresh_start_requires_and_reports_persistent_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "etc/cachyos").mkdir(parents=True)
            (root / "etc/os-release").write_text(
                'ID=luigios\nNAME="LuigiOS"\n'
            )
            (root / "etc/cachyos/installation-snapshot").write_text("7\n")
            (root / "usr/share/luigios/repo").mkdir(parents=True)
            (root / "usr/share/luigios/recovery").mkdir(parents=True)
            (
                root / "usr/share/luigios/recovery/package-roots"
            ).write_text("base\n")
            for mountpoint in POLICY["filesystem"][
                "persistent_subvolumes"
            ]:
                ENGINE.rooted(root, mountpoint).mkdir(
                    parents=True, exist_ok=True
                )

            expected = {
                str(ENGINE.rooted(root, mountpoint)): f"/{subvolume}"
                for mountpoint, subvolume in POLICY["filesystem"][
                    "persistent_subvolumes"
                ].items()
            }

            def fake_findmnt(path):
                resolved = str(path)
                if resolved == str(root):
                    return {
                        "source": "/dev/mapper/root[/@]",
                        "fstype": "btrfs",
                        "fsroot": "/@",
                        "target": str(root),
                    }
                return {
                    "source": f"/dev/mapper/root[{expected[resolved]}]",
                    "fstype": "btrfs",
                    "fsroot": expected[resolved],
                    "target": resolved,
                }

            with mock.patch.object(ENGINE, "findmnt", side_effect=fake_findmnt):
                plan = ENGINE.make_plan("fresh-start", root, POLICY)
            self.assertTrue(plan["executable"], plan["blockers"])
            self.assertFalse(plan["formats_storage"])
            self.assertFalse(plan["deletes_previous_root"])
            self.assertIn("retaining the previous root", plan["steps"][-1])

    def test_policy_forbids_hardware_cutover_before_qualification(self):
        hardware = POLICY["hardware_cutover"]
        self.assertFalse(hardware["allowed_before_vm_qualification"])
        self.assertTrue(hardware["require_explicit_confirmation"])
        self.assertTrue(hardware["require_external_backup"])

    def test_fresh_start_retargets_root_and_keeps_snapshot_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "etc/kernel").mkdir(parents=True)
            (root / "etc/fstab").write_text(
                "UUID=ROOT / btrfs defaults,subvol=/@,compress=zstd 0 0\n"
                "UUID=ROOT /home btrfs defaults,subvol=/@home 0 0\n"
            )
            (root / "etc/kernel/cmdline").write_text(
                "root=UUID=ROOT rw rootflags=subvol=@ quiet\n"
            )
            ENGINE.patch_subvolume_boot(root, "@", "@luigios-fresh-test")
            fstab = (root / "etc/fstab").read_text()
            cmdline = (root / "etc/kernel/cmdline").read_text()
            self.assertIn("subvol=/@luigios-fresh-test", fstab)
            self.assertIn("subvol=/@/.snapshots", fstab)
            self.assertIn(
                "rootflags=subvol=/@luigios-fresh-test", cmdline
            )
            self.assertIn("subvol=/@home", fstab)
            self.assertEqual(
                ENGINE.snapshot_history_subvolume(
                    root, "@luigios-fresh-test"
                ),
                "@",
            )
            ENGINE.patch_subvolume_boot(
                root,
                "@luigios-fresh-test",
                "@luigios-fresh-second",
            )
            self.assertEqual(
                ENGINE.snapshot_history_subvolume(
                    root, "@luigios-fresh-second"
                ),
                "@",
            )

    def test_limine_active_subvolume_ignores_snapshot_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "boot").mkdir()
            (root / "boot/limine.conf").write_text(
                "/+LuigiOS\n"
                "//linux-cachyos\n"
                "  cmdline: rootflags=subvol=/@luigios-fresh-current rw\n"
                "/-Snapshots\n"
                "//3\n"
                "  cmdline: rootflags=subvol=/@/.snapshots/3/snapshot rw\n"
            )
            self.assertEqual(
                ENGINE.limine_active_subvolume(root),
                "@luigios-fresh-current",
            )

    def test_live_snapshot_history_stays_on_a_known_luigios_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "etc").mkdir()
            fstab = root / "etc/fstab"
            fstab.write_text(
                "UUID=ROOT /.snapshots btrfs "
                "defaults,subvol=/@/.snapshots 0 0\n"
            )
            self.assertEqual(
                ENGINE.live_snapshot_history_subvolume(
                    root, ["@", "@luigios-fresh-current"]
                ),
                "@/.snapshots",
            )
            fstab.write_text(
                "UUID=ROOT /.snapshots btrfs "
                "defaults,subvol=/untrusted/.snapshots 0 0\n"
            )
            with self.assertRaisesRegex(
                ENGINE.RecoveryError, "outside LuigiOS"
            ):
                ENGINE.live_snapshot_history_subvolume(root, ["@"])

    def test_offline_snapper_isolates_host_root_only_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            root = base / "target"
            plugins = base / "plugins"
            empty = base / "empty"
            root.mkdir()
            plugins.mkdir()
            arguments = ["snapper", "--root", str(root), "create"]
            wrapped = ENGINE.isolated_snapper_command(
                root,
                arguments,
                plugin_directory=plugins,
                empty_directory=empty,
            )
            self.assertIn("--mount", wrapped)
            self.assertIn(str(empty), wrapped)
            self.assertIn(str(plugins), wrapped)
            self.assertEqual(wrapped[-len(arguments) :], arguments)
            self.assertTrue(empty.is_dir())

    def test_repair_plan_requires_a_complete_signed_media_pool(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "usr/share/luigios/repo").mkdir(parents=True)
            (root / "usr/share/luigios/recovery").mkdir(parents=True)
            (
                root / "usr/share/luigios/recovery/package-roots"
            ).write_text("base\n")
            self.assertFalse(ENGINE.offline_repository_ready(root))

    def test_repair_builds_a_transactional_candidate_root(self):
        source = ENGINE_PATH.read_text()
        repair = source[
            source.index("def repair_system(") :
            source.index("def stage_upgrade(")
        ]
        self.assertIn('"btrfs",\n                "subvolume",\n                "snapshot"', repair)
        self.assertIn("@luigios-repair-", repair)
        self.assertIn("previous_root_retained", repair)
        self.assertIn("include_repository=True", repair)
        self.assertIn('result["status"] = "ready-to-reboot"', repair)
        self.assertNotIn('f"{root}/",', repair)

    def test_previous_system_boot_entries_are_writable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "boot").mkdir()
            configuration = root / "boot/limine.conf"
            configuration.write_text(
                "/+LuigiOS\n"
                "//linux-cachyos-lts\n"
                "  path: boot():/vmlinuz-lts#known\n"
                "  cmdline: rootflags=subvol=/@luigios-fresh-current rw\n"
                "//linux-cachyos\n"
                "  path: boot():/vmlinuz#known\n"
                "  cmdline: rootflags=subvol=/@luigios-fresh-current rw\n"
                "/-Snapshots\n"
                "//3\n"
                "  cmdline: rootflags=subvol=/@/.snapshots/3/snapshot rw\n"
            )
            self.assertEqual(
                ENGINE.add_previous_system_boot_entries(
                    root, "@luigios-fresh-current", "@"
                ),
                2,
            )
            first = configuration.read_text()
            self.assertIn("/+LuigiOS Previous System", first)
            self.assertEqual(first.count("rootflags=subvol=/@ rw"), 2)
            self.assertEqual(
                first.count(ENGINE.PREVIOUS_BOOT_BEGIN), 1
            )
            self.assertEqual(
                ENGINE.add_previous_system_boot_entries(
                    root, "@luigios-fresh-current", "@"
                ),
                2,
            )
            second = configuration.read_text()
            self.assertEqual(
                second.count(ENGINE.PREVIOUS_BOOT_BEGIN), 1
            )
            self.assertEqual(second.count("rootflags=subvol=/@ rw"), 2)

    def test_boot_payload_hashes_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "boot").mkdir()
            payload = root / "boot/vmlinuz-test"
            payload.write_bytes(b"known boot payload")
            expected = ENGINE.b2sum(payload)
            (root / "boot/limine.conf").write_text(
                "/LuigiOS\n"
                "  protocol: linux\n"
                f"  path: boot():/vmlinuz-test#{expected}\n"
            )
            report = ENGINE.verify_boot_payloads(root)
            self.assertEqual(report["count"], 1)
            payload.write_bytes(b"corrupt")
            with self.assertRaises(ENGINE.RecoveryError):
                ENGINE.verify_boot_payloads(root)

    def test_boot_regeneration_uses_the_installed_boot_stack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "usr/bin").mkdir(parents=True)
            limine = root / "usr/bin/limine-mkinitcpio"
            limine.write_text("#!/bin/sh\n")
            self.assertEqual(
                ENGINE.boot_regeneration_command(root),
                ["/usr/bin/limine-mkinitcpio"],
            )

            limine.unlink()
            presets = root / "etc/mkinitcpio.d"
            presets.mkdir(parents=True)
            (presets / "linux-luigios.preset").write_text(
                "ALL_kver=/boot/vmlinuz\n"
            )
            self.assertEqual(
                ENGINE.boot_regeneration_command(root),
                ["/usr/bin/mkinitcpio", "-P"],
            )

            (presets / "linux-luigios.preset").unlink()
            with self.assertRaisesRegex(
                ENGINE.RecoveryError, "no supported initramfs"
            ):
                ENGINE.boot_regeneration_command(root)

    def test_engine_has_no_format_or_previous_root_delete_command(self):
        source = ENGINE_PATH.read_text()
        forbidden = (
            "mkfs.",
            "wipefs",
            "btrfs subvolume delete",
            "shutil.rmtree(new_root",
        )
        self.assertFalse(
            any(command in source for command in forbidden),
            "recovery engine contains a destructive storage primitive",
        )

    def test_installer_layout_and_offline_update_are_static_contracts(self):
        mount = (
            ROOT / "product/cachyos/archiso/calamares/mount.conf"
        ).read_text()
        for subvolume in (
            "@home",
            "@root",
            "@srv",
            "@cache",
            "@luigios-state",
            "@log",
            "@tmp",
        ):
            self.assertIn(f"subvolume: /{subvolume}", mount)
        unit = (
            ROOT
            / "product/cachyos/overlay/usr/lib/systemd/system/"
            "luigios-offline-update.service"
        ).read_text()
        self.assertIn("ConditionPathIsSymbolicLink=/system-update", unit)
        self.assertIn("SuccessAction=reboot", unit)
        self.assertIn("FailureAction=reboot", unit)
        self.assertIn("offline-upgrade", unit)
        sdk = (ROOT / "tools/sdk").read_text()
        self.assertIn(
            "system-update.target.wants/luigios-offline-update.service",
            sdk,
        )

    def test_live_media_requires_an_exact_device_and_subvolume_pair(self):
        parser = ENGINE.parser()
        discovered = parser.parse_args(["discover-targets"])
        self.assertEqual(discovered.command, "discover-targets")
        selected = parser.parse_args(
            [
                "plan",
                "fresh-start",
                "--device",
                "/dev/mapper/luigios",
                "--subvolume",
                "@",
            ]
        )
        self.assertEqual(selected.subvolume, "@")
        incomplete = parser.parse_args(
            [
                "plan",
                "fresh-start",
                "--device",
                "/dev/mapper/luigios",
            ]
        )
        with self.assertRaisesRegex(
            ENGINE.RecoveryError, "must be used together"
        ):
            with ENGINE.selected_root(
                incomplete, POLICY, writable=False
            ):
                pass

    def test_live_repair_mounts_runtime_filesystems_for_package_hooks(self):
        source = ENGINE_PATH.read_text()
        mounted_target = source[
            source.index("def mounted_live_target(") :
            source.index("def discover_live_targets(")
        ]
        self.assertIn(
            'for source in ("/dev", "/proc", "/sys")',
            mounted_target,
        )
        self.assertIn('["mount", "--bind", source', mounted_target)
        self.assertIn('"tmpfs"', mounted_target)
        self.assertIn("unmount_tree(target)", mounted_target)
        self.assertNotIn("TemporaryDirectory", mounted_target)

    def test_recovery_never_lazy_unmounts_or_recursively_deletes_a_target(self):
        source = ENGINE_PATH.read_text()
        unmount = source[
            source.index("def unmount_tree(") :
            source.index("def os_release(")
        ]
        mounted_target = source[
            source.index("def mounted_live_target(") :
            source.index("def discover_live_targets(")
        ]
        self.assertNotIn('"-l"', unmount)
        self.assertNotIn("shutil.rmtree", mounted_target)
        self.assertIn("mountpoints_below(target)", mounted_target)
        self.assertNotIn('"--rbind"', source)
        self.assertNotIn('"--make-rslave"', source)

    def test_live_media_fstab_parser_accepts_only_stable_boot_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "etc").mkdir()
            (root / "etc/fstab").write_text(
                "UUID=ROOT / btrfs defaults,subvol=/@ 0 0\n"
                "PARTUUID=abcd-01 /boot vfat defaults,umask=0077 0 2\n"
            )
            self.assertEqual(ENGINE.boot_source(root), "PARTUUID=abcd-01")
            (root / "etc/fstab").write_text(
                "/tmp/untrusted.img /boot vfat loop 0 0\n"
            )
            with self.assertRaisesRegex(
                ENGINE.RecoveryError, "unsafe boot filesystem"
            ):
                ENGINE.boot_source(root)

    def test_live_recovery_ui_uses_authorized_read_only_discovery(self):
        ui = (
            ROOT
            / "product/cachyos/overlay/usr/bin/luigios-recovery"
        ).read_text()
        self.assertIn('["discover-targets"], privileged=True', ui)
        self.assertIn('"--device"', ui)
        self.assertIn('"--subvolume"', ui)
        self.assertIn(
            "RecoveryApplication().run(GTK_ARGUMENTS)", ui
        )
        self.assertIn(
            'argument for argument in sys.argv if argument != "--live"',
            ui,
        )


if __name__ == "__main__":
    unittest.main()
