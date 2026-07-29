import json
import fnmatch
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProductContract(unittest.TestCase):
    def test_identity_and_version_agree(self):
        product = json.loads((ROOT / "product/cachyos/product.json").read_text())
        self.assertEqual(product["version"], (ROOT / "VERSION").read_text().strip())
        self.assertEqual(product["base"]["distribution"], "CachyOS")
        self.assertEqual(product["base"]["microarchitecture"], "x86-64-v3")
        self.assertEqual(product["desktop"], {
            "session": "cosmic",
            "display_manager": "cosmic-greeter",
            "exclusive": True,
        })

    def test_package_roots_have_no_forbidden_payload(self):
        packages = {
            line.split("#", 1)[0].strip()
            for line in (ROOT / "product/cachyos/packages.x86_64").read_text().splitlines()
            if line.split("#", 1)[0].strip()
        }
        patterns = [
            line.strip().lower()
            for line in (ROOT / "product/cachyos/forbidden-packages.txt").read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        rejected = sorted(
            package for package in packages
            if any(
                fnmatch.fnmatchcase(package.lower(), pattern)
                for pattern in patterns
            )
        )
        self.assertEqual(rejected, [])
        self.assertIn("cosmic-session", packages)
        self.assertIn("cosmic-greeter", packages)
        self.assertIn("plymouth", packages)
        self.assertNotIn("cachyos-hello", packages)
        self.assertNotIn("cachyos-packageinstaller", packages)
        self.assertNotIn("limine-entry-tool", packages)

    def test_release_is_content_locked(self):
        lock = json.loads((ROOT / "sdk/package-lock.json").read_text())
        roots = {
            line.split("#", 1)[0].strip()
            for line in (ROOT / "product/cachyos/packages.x86_64").read_text().splitlines()
            if line.split("#", 1)[0].strip()
        }
        records = {item["name"]: item for item in lock["packages"]}
        self.assertLess(100, len(records))
        self.assertLessEqual(roots, records.keys())
        self.assertTrue(all(len(item["sha256"]) == 64 for item in records.values()))
        sdk = (ROOT / "tools/sdk").read_text()
        release_repo = sdk[
            sdk.index("configure_locked_repo()"):
            sdk.index("verify_release_cache()")
        ]
        self.assertIn('exec "${ROOT}/tools/rootless-image"', sdk)
        self.assertNotIn(".luigios-upstream-pacman.conf", release_repo)
        self.assertIn(
            "--network=none",
            (ROOT / "tools/rootless-image").read_text(),
        )
        self.assertIn(
            "Architecture = x86_64 x86_64_v2 x86_64_v3",
            sdk,
        )
        self.assertIn("pacman-key --populate archlinux cachyos", sdk)
        self.assertIn(
            "@sha256:",
            (ROOT / "sdk/Containerfile").read_text(),
        )

    def test_decentralized_transport_cannot_authorize(self):
        product = json.loads((ROOT / "product/cachyos/product.json").read_text())
        self.assertTrue(product["decentralized_networking"]["defining_feature"])
        policy = json.loads((ROOT / "profiles/distribution-v2.json").read_text())
        self.assertEqual(policy["authority"]["metadata"], "tuf")
        self.assertFalse(policy["authority"]["transport_can_authorize"])
        self.assertFalse(policy["transports"]["seeding_default"])
        self.assertFalse(policy["privacy"]["stable_device_identifier"])
        self.assertFalse(policy["cache"]["scan_arbitrary_user_files"])
        unit = (
            ROOT
            / "product/cachyos/overlay/usr/lib/systemd/system/luigios-peer.service"
        ).read_text()
        self.assertIn("User=luigios-peer", unit)
        self.assertIn(
            "ExecStartPre=/usr/bin/cp /etc/luigios/peer/settings.json "
            "/var/lib/luigios-peer/settings.json",
            unit,
        )
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("NoNewPrivileges=yes", unit)
        settings = json.loads(
            (
                ROOT
                / "product/cachyos/overlay/etc/luigios/peer/settings.json"
            ).read_text()
        )
        self.assertFalse(settings["dht-enabled"])
        self.assertFalse(settings["pex-enabled"])
        self.assertFalse(settings["port-forwarding-enabled"])
        self.assertFalse(settings["rpc-enabled"])
        services = json.loads((ROOT / "product/cachyos/services.json").read_text())
        self.assertNotIn("luigios-peer.service", services["enabled"])

    def test_rice_is_installable_and_complete(self):
        rice = ROOT / "branding/cosmic-rice"
        required = [
            rice / "apply-user.sh",
            rice / "apply-system.sh",
            rice / "luigios-dark.ron",
            rice / "icon-theme/index.theme",
            rice / "vscode-theme/package.json",
            rice / "plymouth/luigios.plymouth",
            ROOT / "tools/inspect-image",
        ]
        self.assertTrue(all(path.is_file() for path in required))

    def test_installer_is_single_path_and_offline_capable(self):
        installer = ROOT / "product/cachyos/archiso/calamares"
        settings = (installer / "settings_online.conf").read_text().lower()
        self.assertNotIn("packages@", settings)
        self.assertNotIn("netinstall", settings)
        self.assertNotIn("update-mirrorlist", settings)
        self.assertNotIn("- zfs", settings)
        self.assertNotIn("- grubcfg", settings)

        partition = (installer / "partition.conf").read_text()
        self.assertIn('defaultFileSystemType: "btrfs"', partition)
        self.assertIn('availableFileSystemTypes: [ "btrfs" ]', partition)

        bootloader = (installer / "packagechooser_bootloader.conf").read_text()
        self.assertIn("limine", bootloader.lower())
        self.assertNotIn("grub", bootloader.lower())

        initialization = (
            installer / "shellprocess_initialize_pacman.conf"
        ).read_text()
        self.assertNotIn("update-mirrorlist", initialization)
        self.assertNotIn("rate-mirrors", initialization)

    def test_live_boot_is_modern_and_branded(self):
        profile = (
            ROOT / "product/cachyos/archiso/profiledef.sh"
        ).read_text()
        self.assertIn("bootmodes=('uefi.systemd-boot')", profile)
        self.assertNotIn("bios.syslinux", profile)
        self.assertNotIn("uefi.grub", profile)
        entries = ROOT / "product/cachyos/archiso/efiboot/loader/entries"
        rendered = "\n".join(
            path.read_text() for path in sorted(entries.glob("*.conf"))
        )
        self.assertIn("LuigiOS Live - Stable kernel", rendered)
        self.assertIn("LuigiOS Live - Performance kernel", rendered)
        self.assertIn("LuigiOS Live - Safe graphics", rendered)
        self.assertNotIn("CachyOS", rendered)

    def test_installer_service_policy_matches_product(self):
        services = json.loads((ROOT / "product/cachyos/services.json").read_text())
        module = (
            ROOT / "product/cachyos/archiso/calamares/services-systemd.conf"
        ).read_text()
        for unit in services["enabled"]:
            self.assertIn(f'name: "{unit}"', module)
        for unit in services["disabled"]:
            self.assertIn(f'name: "{unit}"', module)
            self.assertIn(
                f'name: "{unit}", action: "disable"',
                module,
            )
        self.assertIn('name: "luigios-peer.service", action: "disable"', module)

    def test_legacy_implementation_trees_are_absent(self):
        for relative in ("prototype", "third_party/bua", "product/package", "product/patches"):
            path = ROOT / relative
            files = list(path.rglob("*")) if path.exists() else []
            self.assertEqual([item for item in files if item.is_file()], [])


if __name__ == "__main__":
    unittest.main()
