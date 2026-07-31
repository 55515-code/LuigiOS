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
        self.assertIn("python-toml", packages)
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
        self.assertNotIn(
            "sed -n '/^\\[cachyos-v3\\]$/,$p'",
            release_repo,
        )
        self.assertIn(
            'ln -s luigios-lock.db.tar.zst "${live_repo}/luigios-lock.db"',
            release_repo,
        )
        self.assertIn(
            "Server = file:///usr/share/luigios/repo",
            release_repo,
        )
        self.assertIn(
            "--network=none",
            (ROOT / "tools/rootless-image").read_text(),
        )
        self.assertIn(
            '"${ROOT}/tools/sdk" prepare',
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
        self.assertTrue(product["sdk"]["defining_feature"])
        self.assertTrue(product["sdk"]["rootless_first"])
        self.assertEqual(product["sdk"]["entrypoint"], "tools/sdk")
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
        self.assertIn(
            "bash /usr/share/luigios/cosmic-rice/apply-system.sh",
            (
                ROOT / "product/cachyos/overlay/usr/lib/luigios/firstboot"
            ).read_text(),
        )
        first_login = (
            ROOT
            / "product/cachyos/overlay/usr/lib/systemd/user/"
            "luigios-first-login.service"
        ).read_text()
        self.assertIn(
            "/usr/bin/bash /usr/share/luigios/cosmic-rice/apply-user.sh",
            first_login,
        )
        self.assertIn("Before=graphical-session-pre.target", first_login)
        self.assertIn("WantedBy=graphical-session-pre.target", first_login)
        panel_refresh_unit = (
            ROOT
            / "product/cachyos/overlay/usr/lib/systemd/user/"
            "luigios-panel-refresh.service"
        ).read_text()
        self.assertIn("After=graphical-session.target", panel_refresh_unit)
        self.assertIn(
            "ExecStart=/usr/lib/luigios/refresh-cosmic-panel",
            panel_refresh_unit,
        )
        panel_refresh = (
            ROOT
            / "product/cachyos/overlay/usr/lib/luigios/"
            "refresh-cosmic-panel"
        )
        self.assertTrue(panel_refresh.stat().st_mode & 0o111)
        panel_refresh_text = panel_refresh.read_text()
        self.assertIn("org.freedesktop.Notifications", panel_refresh_text)
        self.assertIn("/org/freedesktop/Notifications", panel_refresh_text)
        self.assertIn("sleep 5", panel_refresh_text)
        self.assertIn('kill -TERM "${panel_pid}"', panel_refresh_text)
        self.assertIn(
            "ExecStart=/usr/bin/bash /usr/lib/luigios/firstboot",
            (
                ROOT
                / "product/cachyos/overlay/usr/lib/systemd/system/"
                "luigios-firstboot.service"
            ).read_text(),
        )

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

        self.assertNotIn("packagechooser@bootloader", settings)
        self.assertNotIn("modify_mk_hook", settings)
        self.assertNotIn("reset_mk_hook", settings)
        self.assertNotIn("\n      - initcpio\n", settings)
        self.assertNotIn("\n      - initcpiocfg\n", settings)
        self.assertNotIn("\n      - plymouthcfg\n", settings)
        self.assertNotIn("\n      - displaymanager\n", settings)
        self.assertIn("shellprocess@limine_initramfs", settings)
        self.assertIn("shellprocess@finalize_target", settings)
        self.assertIn(
            'install -m 0644 "${calamares}/shellprocess_finalize_target.conf"',
            (ROOT / "tools/sdk").read_text(),
        )
        limine_initramfs = (
            installer / "shellprocess_limine_initramfs.conf"
        ).read_text()
        self.assertIn(
            "bash /usr/share/luigios/cosmic-rice/apply-system.sh",
            limine_initramfs,
        )
        self.assertNotIn("--seed-all-users", limine_initramfs)
        apply_user = (
            ROOT / "branding/cosmic-rice/apply-user.sh"
        ).read_text()
        self.assertIn("--seed-all-users", apply_user)
        self.assertIn('runuser -u "${account}" -- env', apply_user)
        self.assertIn('install -d -m 0750 -o "${uid}" -g "${gid}"', apply_user)
        self.assertIn(
            "write_cosmic com.system76.CosmicPanel entries",
            apply_user,
        )
        install_target = (
            ROOT / "product/cachyos/overlay/usr/lib/luigios/install-target"
        ).read_text()
        self.assertIn("/etc/kernel/cmdline", install_target)
        self.assertIn("root=UUID=", install_target)
        self.assertIn(
            "install -Dm0755 \\\n"
            "    /usr/share/luigios/target-root/usr/lib/luigios/"
            "cosmic-greeter-start",
            install_target,
        )
        self.assertIn(
            "install -Dm0755 \\\n"
            "    /usr/lib/luigios/refresh-cosmic-panel",
            install_target,
        )
        profiledef = (
            ROOT / "product/cachyos/archiso/profiledef.sh"
        ).read_text()
        self.assertIn(
            '["/usr/share/luigios/target-root/usr/lib/luigios/'
            'cosmic-greeter-start"]="0:0:755"',
            profiledef,
        )
        greeter_config = (
            ROOT
            / "product/cachyos/target-overlay/etc/greetd/"
            "cosmic-greeter.toml"
        ).read_text()
        self.assertIn(
            'command = "/usr/lib/luigios/cosmic-greeter-start"',
            greeter_config,
        )
        greeter_start = (
            ROOT
            / "product/cachyos/target-overlay/usr/lib/luigios/"
            "cosmic-greeter-start"
        )
        self.assertTrue(greeter_start.stat().st_mode & 0o111)
        greeter_start_text = greeter_start.read_text()
        self.assertIn(". /etc/locale.conf", greeter_start_text)
        self.assertIn("exec /usr/bin/cosmic-greeter-start", greeter_start_text)
        self.assertLess(
            settings.index("shellprocess@luigios"),
            settings.index("shellprocess@limine_initramfs"),
        )
        self.assertLess(
            settings.index("shellprocess@cleanup_calamares"),
            settings.index("shellprocess@finalize_target"),
        )
        self.assertLess(
            settings.index("shellprocess@finalize_target"),
            settings.index("\n      - umount"),
        )
        finalize_target = (
            ROOT / "product/cachyos/overlay/usr/lib/luigios/finalize-target"
        )
        self.assertTrue(finalize_target.stat().st_mode & 0o111)
        finalize_text = finalize_target.read_text()
        self.assertIn("seed_target_users", finalize_text)
        self.assertIn('chroot "${target}" /usr/bin/runuser', finalize_text)
        self.assertIn("no regular installed user was available", finalize_text)
        self.assertIn("verify_limine_payloads", finalize_text)
        self.assertIn('fsck.fat -a "${esp_source}"', finalize_text)
        self.assertIn('umount "${boot_mount}"', finalize_text)
        self.assertIn(
            '["/usr/lib/luigios/finalize-target"]="0:0:755"',
            profiledef,
        )
        self.assertIn(
            '["/usr/lib/luigios/refresh-cosmic-panel"]="0:0:755"',
            profiledef,
        )
        self.assertIn(
            '["/usr/share/luigios/target-root/usr/lib/luigios/'
            'refresh-cosmic-panel"]="0:0:755"',
            profiledef,
        )
        self.assertIn(
            "graphical-session-pre.target.wants/luigios-first-login.service",
            install_target,
        )
        self.assertIn(
            "graphical-session-pre.target.wants/luigios-first-login.service",
            (ROOT / "tools/sdk").read_text(),
        )
        self.assertIn(
            "graphical-session.target.wants/luigios-panel-refresh.service",
            install_target,
        )
        self.assertIn(
            "graphical-session.target.wants/luigios-panel-refresh.service",
            (ROOT / "tools/sdk").read_text(),
        )
        self.assertIn(
            "'bootloader: limine'",
            (ROOT / "tools/sdk").read_text(),
        )
        customize = (
            ROOT / "product/cachyos/archiso/customize_airootfs.sh"
        ).read_text()
        self.assertIn(
            "/etc/xdg/autostart/com.system76.CosmicInitialSetup.desktop",
            customize,
        )
        self.assertIn("Hidden=true", customize)
        self.assertIn(
            "/etc/xdg/autostart/luigios-installer.desktop",
            customize,
        )
        target_initial_setup = (
            ROOT
            / "product/cachyos/target-overlay/etc/xdg/autostart/"
            "com.system76.CosmicInitialSetup.desktop"
        ).read_text()
        self.assertIn("Hidden=true", target_initial_setup)
        self.assertIn(
            'libcalamares.job.configuration.get("bootloader")',
            customize,
        )

        initialization = (
            installer / "shellprocess_initialize_pacman.conf"
        ).read_text()
        self.assertNotIn("update-mirrorlist", initialization)
        self.assertNotIn("rate-mirrors", initialization)
        self.assertIn(
            "cp /etc/pacman.conf ${ROOT}/etc/pacman.conf",
            initialization,
        )
        self.assertIn(
            "mount --bind /usr/share/luigios/repo "
            "${ROOT}/usr/share/luigios/repo",
            initialization,
        )

    def test_live_boot_is_modern_and_branded(self):
        profile = (
            ROOT / "product/cachyos/archiso/profiledef.sh"
        ).read_text()
        self.assertIn("bootmodes=('uefi.systemd-boot')", profile)
        self.assertIn("'-comp' 'zstd'", profile)
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
        customize = (
            ROOT / "product/cachyos/archiso/customize_airootfs.sh"
        ).read_text()
        self.assertIn("/usr/bin/mkinitcpio -P", customize)
        self.assertNotIn("archiso_pxe", customize)
        installer_entry = (
            ROOT / "product/cachyos/archiso/luigios-installer.desktop"
        ).read_text()
        self.assertIn("Name=LuigiOS Setup & Recovery", installer_entry)
        self.assertIn("Exec=/usr/bin/luigios-recovery --live", installer_entry)
        self.assertIn("Icon=luigios-recovery", installer_entry)
        launcher = (
            ROOT
            / "product/cachyos/archiso/calamares/calamares-online.sh"
        ).read_text()
        self.assertIn("pkexec-wrapper /usr/local/libexec/luigios-calamares", launcher)
        self.assertEqual(
            (
                ROOT / "product/cachyos/overlay/etc/hostname"
            ).read_text().strip(),
            "luigios",
        )
        partition = (
            ROOT / "product/cachyos/archiso/calamares/partition.conf"
        ).read_text()
        self.assertIn('userSwapChoices: [ "none" ]', partition)
        self.assertEqual(partition.count('userSwapChoices: [ "none" ]'), 1)
        settings = (
            ROOT / "product/cachyos/archiso/calamares/settings_online.conf"
        ).read_text()
        self.assertNotIn("packagechooser@bootloader", settings)
        self.assertIn('efiBootloaderId: "luigios"', customize)
        self.assertNotIn("initialSwapChoice: none", partition)

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
