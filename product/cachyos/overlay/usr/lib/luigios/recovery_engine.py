#!/usr/bin/env python3
"""Transactional LuigiOS recovery primitives.

The unprivileged UI only asks this engine for plans. Mutating subcommands must
run as root through PolicyKit or the offline-update systemd unit.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Iterable


DEFAULT_POLICY = pathlib.Path("/usr/share/luigios/recovery-v1.json")
LOCK_PATH = pathlib.Path("/run/lock/luigios-recovery.lock")


class RecoveryError(RuntimeError):
    """An expected recovery safety or execution failure."""


def development_policy_path(engine: pathlib.Path) -> pathlib.Path | None:
    resolved = engine.resolve()
    if len(resolved.parents) <= 6:
        return None
    return resolved.parents[6] / "profiles/recovery-v1.json"


def load_policy(path: pathlib.Path | None = None) -> dict[str, Any]:
    candidate = path or DEFAULT_POLICY
    source_policy = development_policy_path(pathlib.Path(__file__))
    if (
        not candidate.exists()
        and source_policy is not None
        and source_policy.exists()
    ):
        candidate = source_policy
    with candidate.open("r", encoding="utf-8") as stream:
        policy = json.load(stream)
    if policy.get("schema") != 1:
        raise RecoveryError(f"unsupported recovery policy: {candidate}")
    return policy


def atomic_json(path: pathlib.Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = pathlib.Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary_path.unlink()


def atomic_copy(
    source: pathlib.Path, destination: pathlib.Path, mode: int
) -> None:
    if not source.is_file() or source.is_symlink():
        raise RecoveryError(f"required LuigiOS contract file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary_path = pathlib.Path(temporary)
    try:
        with source.open("rb", buffering=0) as input_stream:
            with os.fdopen(descriptor, "wb", buffering=0) as output_stream:
                shutil.copyfileobj(input_stream, output_stream)
                os.fsync(output_stream.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent, os.O_RDONLY | os.O_DIRECTORY
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary_path.unlink()


def exact_symlink(
    root: pathlib.Path, destination_name: str, target: str
) -> None:
    safe_target_parent(root, destination_name)
    destination = rooted(root, destination_name)
    if destination.is_dir() and not destination.is_symlink():
        raise RecoveryError(
            f"refusing to replace directory with contract symlink: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.luigios-{uuid.uuid4().hex}"
    )
    try:
        temporary.symlink_to(target)
        os.replace(temporary, destination)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_root(root: pathlib.Path) -> pathlib.Path:
    root = root.resolve()
    if not root.is_dir():
        raise RecoveryError(f"target root is not a directory: {root}")
    return root


def rooted(root: pathlib.Path, absolute: str) -> pathlib.Path:
    relative = pathlib.PurePosixPath(absolute)
    if not relative.is_absolute() or ".." in relative.parts:
        raise RecoveryError(f"unsafe policy path: {absolute}")
    return root.joinpath(*relative.parts[1:])


def xattrs(path: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        names = os.listxattr(path, follow_symlinks=False)
    except (OSError, NotImplementedError):
        return result
    for name in sorted(names):
        try:
            value = os.getxattr(path, name, follow_symlinks=False)
        except OSError:
            continue
        result[name] = base64.b64encode(value).decode("ascii")
    return result


def entry_metadata(
    path: pathlib.Path,
    relative: pathlib.PurePosixPath,
    hardlink_key: str | None = None,
) -> dict[str, Any]:
    information = path.lstat()
    mode = stat.S_IMODE(information.st_mode)
    record: dict[str, Any] = {
        "path": str(relative),
        "mode": mode,
        "uid": information.st_uid,
        "gid": information.st_gid,
        "mtime_ns": information.st_mtime_ns,
        "xattrs": xattrs(path),
    }
    if stat.S_ISDIR(information.st_mode):
        record["type"] = "directory"
    elif stat.S_ISREG(information.st_mode):
        record["type"] = "file"
        record["size"] = information.st_size
        record["sha256"] = sha256_file(path)
        if hardlink_key:
            record["hardlink_to"] = hardlink_key
    elif stat.S_ISLNK(information.st_mode):
        target = os.readlink(path)
        record["type"] = "symlink"
        record["symlink_target"] = target
        record["sha256"] = hashlib.sha256(
            os.fsencode(target)
        ).hexdigest()
    else:
        raise RecoveryError(f"unsupported special file in settings: {path}")
    return record


def walk_policy_path(
    root: pathlib.Path, absolute: str
) -> Iterable[tuple[pathlib.Path, pathlib.PurePosixPath]]:
    start = rooted(root, absolute)
    if not start.exists() and not start.is_symlink():
        return
    relative = pathlib.PurePosixPath(absolute)
    yield start, relative
    if start.is_dir() and not start.is_symlink():
        for directory, names, files in os.walk(start, followlinks=False):
            names.sort()
            files.sort()
            current = pathlib.Path(directory)
            for name in [*names, *files]:
                source = current / name
                yield source, pathlib.PurePosixPath("/") / source.relative_to(
                    root
                )


def apply_metadata(path: pathlib.Path, record: dict[str, Any]) -> None:
    if record["type"] != "symlink":
        os.chmod(path, record["mode"], follow_symlinks=False)
    with contextlib.suppress(PermissionError):
        os.chown(
            path,
            record["uid"],
            record["gid"],
            follow_symlinks=False,
        )
    with contextlib.suppress(NotImplementedError):
        os.utime(
            path,
            ns=(record["mtime_ns"], record["mtime_ns"]),
            follow_symlinks=False,
        )
    for name, encoded in record["xattrs"].items():
        os.setxattr(
            path,
            name,
            base64.b64decode(encoded),
            follow_symlinks=False,
        )


def copy_entry(
    source: pathlib.Path,
    destination: pathlib.Path,
    record: dict[str, Any],
    hardlink_destination: pathlib.Path | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    if record["type"] == "directory":
        destination.mkdir()
    elif record["type"] == "symlink":
        destination.symlink_to(record["symlink_target"])
    elif hardlink_destination is not None:
        os.link(hardlink_destination, destination)
    else:
        shutil.copyfile(source, destination, follow_symlinks=False)
    apply_metadata(destination, record)


def capture_preservation(
    source_root: pathlib.Path,
    bundle: pathlib.Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    source_root = normalized_root(source_root)
    bundle = bundle.absolute()
    if bundle.exists():
        raise RecoveryError(f"preservation bundle already exists: {bundle}")
    bundle.mkdir(parents=True, mode=0o700)
    os.chmod(bundle, 0o700)
    payload = bundle / "payload"
    payload.mkdir(mode=0o700)

    records: list[dict[str, Any]] = []
    skipped_transient: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    hardlinks: dict[tuple[int, int], tuple[str, pathlib.Path]] = {}
    groups = (
        ("reapply", policy["preservation"]["reapply"]),
        ("retain-for-review", policy["preservation"]["retain_for_review"]),
    )
    for disposition, paths in groups:
        for absolute in paths:
            for source, relative in walk_policy_path(source_root, absolute):
                relative_text = str(relative)
                if relative_text in seen_paths:
                    continue
                seen_paths.add(relative_text)
                information = source.lstat()
                if stat.S_ISSOCK(information.st_mode):
                    skipped_transient.append(
                        {
                            "path": relative_text,
                            "reason": "runtime-unix-socket",
                        }
                    )
                    continue
                hardlink_key = None
                hardlink_destination = None
                if stat.S_ISREG(information.st_mode):
                    inode = (information.st_dev, information.st_ino)
                    if inode in hardlinks:
                        hardlink_key, hardlink_destination = hardlinks[inode]
                    elif information.st_nlink > 1:
                        hardlinks[inode] = (
                            relative_text,
                            rooted(payload, relative_text),
                        )
                record = entry_metadata(source, relative, hardlink_key)
                record["disposition"] = disposition
                destination = rooted(payload, relative_text)
                copy_entry(
                    source,
                    destination,
                    record,
                    hardlink_destination,
                )
                records.append(record)

    for record in reversed(records):
        if record["type"] == "directory":
            apply_metadata(rooted(payload, record["path"]), record)

    manifest = {
        "schema": 1,
        "created_unix_ns": time.time_ns(),
        "source_root": str(source_root),
        "digest": "sha256",
        "entries": records,
        "skipped_transient": skipped_transient,
    }
    atomic_json(bundle / "manifest.json", manifest)
    verification = verify_preservation(bundle)
    if not verification["valid"]:
        raise RecoveryError(
            "new preservation bundle failed verification: "
            + "; ".join(verification["errors"])
        )
    return manifest


def metadata_errors(
    path: pathlib.Path,
    record: dict[str, Any],
    inode_by_source: dict[str, tuple[int, int]],
) -> list[str]:
    errors: list[str] = []
    if not path.exists() and not path.is_symlink():
        return [f"missing {record['path']}"]
    current = entry_metadata(path, pathlib.PurePosixPath(record["path"]))
    for key in (
        "type",
        "mode",
        "uid",
        "gid",
        "mtime_ns",
        "xattrs",
        "size",
        "sha256",
        "symlink_target",
    ):
        if key in record and current.get(key) != record.get(key):
            errors.append(f"{record['path']}: {key} mismatch")
    hardlink_source = record.get("hardlink_to")
    if hardlink_source:
        current_stat = path.stat()
        current_inode = (current_stat.st_dev, current_stat.st_ino)
        if inode_by_source.get(hardlink_source) != current_inode:
            errors.append(f"{record['path']}: hard-link identity mismatch")
    elif record["type"] == "file":
        current_stat = path.stat()
        inode_by_source[record["path"]] = (
            current_stat.st_dev,
            current_stat.st_ino,
        )
    return errors


def verify_preservation(bundle: pathlib.Path) -> dict[str, Any]:
    bundle = bundle.absolute()
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise RecoveryError(f"missing preservation manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = bundle / "payload"
    errors: list[str] = []
    inode_by_source: dict[str, tuple[int, int]] = {}
    for record in manifest.get("entries", []):
        errors.extend(
            metadata_errors(
                rooted(payload, record["path"]),
                record,
                inode_by_source,
            )
        )
    return {
        "valid": not errors,
        "entries": len(manifest.get("entries", [])),
        "errors": errors,
    }


def safe_target_parent(root: pathlib.Path, relative: str) -> None:
    destination = rooted(root, relative)
    current = root
    for component in destination.relative_to(root).parts[:-1]:
        current /= component
        if current.is_symlink():
            raise RecoveryError(
                f"refusing settings restore through symlink: {current}"
            )


def restore_preservation(
    bundle: pathlib.Path,
    target_root: pathlib.Path,
) -> dict[str, Any]:
    target_root = normalized_root(target_root)
    verification = verify_preservation(bundle)
    if not verification["valid"]:
        raise RecoveryError("preservation bundle is not valid")
    manifest = json.loads(
        (bundle / "manifest.json").read_text(encoding="utf-8")
    )
    payload = bundle / "payload"
    restored = 0
    hardlinks: dict[str, pathlib.Path] = {}
    restored_directories: list[dict[str, Any]] = []
    for record in manifest["entries"]:
        if record["disposition"] != "reapply":
            continue
        relative = record["path"]
        safe_target_parent(target_root, relative)
        source = rooted(payload, relative)
        destination = rooted(target_root, relative)
        hardlink_source = record.get("hardlink_to")
        copy_entry(
            source,
            destination,
            record,
            hardlinks.get(hardlink_source),
        )
        if record["type"] == "file" and not hardlink_source:
            hardlinks[relative] = destination
        elif record["type"] == "directory":
            restored_directories.append(record)
        restored += 1
    for record in reversed(restored_directories):
        apply_metadata(rooted(target_root, record["path"]), record)
    return {"restored": restored, "target_root": str(target_root)}


def command(
    arguments: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        env=environment,
    )


def mountpoints_below(path: pathlib.Path) -> list[pathlib.Path]:
    """Read the kernel mount table without following target symlinks."""
    target = str(path.absolute())
    result: list[pathlib.Path] = []
    with pathlib.Path("/proc/self/mountinfo").open(
        "r", encoding="utf-8"
    ) as stream:
        for line in stream:
            fields = line.split()
            if len(fields) < 5:
                continue
            mountpoint = re.sub(
                r"\\([0-7]{3})",
                lambda match: chr(int(match.group(1), 8)),
                fields[4],
            )
            if mountpoint == target or mountpoint.startswith(f"{target}/"):
                result.append(pathlib.Path(mountpoint))
    return sorted(result, key=lambda item: len(item.parts), reverse=True)


def unmount_tree(path: pathlib.Path) -> None:
    """Unmount synchronously; never lazy-detach a recovery target."""
    result = command(["umount", "-R", str(path)], check=False)
    remaining = mountpoints_below(path)
    if remaining:
        detail = (result.stderr or result.stdout).strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise RecoveryError(
            f"recovery target remains mounted at {remaining[0]}{suffix}"
        )


def os_release(root: pathlib.Path) -> dict[str, str]:
    release = rooted(root, "/etc/os-release")
    result: dict[str, str] = {}
    if not release.is_file():
        return result
    for line in release.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip().strip('"')
    return result


def findmnt(target: pathlib.Path) -> dict[str, Any] | None:
    result = command(
        ["findmnt", "--json", "--output", "SOURCE,FSTYPE,FSROOT,TARGET", "-T", str(target)],
        check=False,
    )
    if result.returncode != 0:
        return None
    filesystems = json.loads(result.stdout).get("filesystems", [])
    return filesystems[0] if filesystems else None


def validate_btrfs_device(device: pathlib.Path) -> pathlib.Path:
    requested = str(device)
    resolved = device.resolve(strict=True)
    information = command(
        [
            "lsblk",
            "--json",
            "--paths",
            "--output",
            "PATH,TYPE,FSTYPE",
            str(resolved),
        ]
    )
    devices = json.loads(information.stdout).get("blockdevices", [])
    if len(devices) != 1:
        raise RecoveryError(f"ambiguous recovery device: {requested}")
    entry = devices[0]
    if entry.get("path") != str(resolved):
        raise RecoveryError(f"device identity changed: {requested}")
    if entry.get("type") not in {"part", "crypt", "lvm"}:
        raise RecoveryError(
            f"recovery target must be a partition or mapped volume: {requested}"
        )
    if entry.get("fstype") != "btrfs":
        raise RecoveryError(f"recovery target is not Btrfs: {requested}")
    return resolved


def fstab_unescape(value: str) -> str:
    return re.sub(
        r"\\([0-7]{3})",
        lambda match: chr(int(match.group(1), 8)),
        value,
    )


def fstab_entries(root: pathlib.Path) -> list[dict[str, str]]:
    configuration = rooted(root, "/etc/fstab")
    if not configuration.is_file():
        return []
    entries: list[dict[str, str]] = []
    for line in configuration.read_text(
        encoding="utf-8", errors="strict"
    ).splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) < 4:
            continue
        entries.append(
            {
                "source": fstab_unescape(fields[0]),
                "target": fstab_unescape(fields[1]),
                "fstype": fields[2],
                "options": fields[3],
            }
        )
    return entries


def btrfs_candidates() -> list[pathlib.Path]:
    information = command(
        [
            "lsblk",
            "--json",
            "--paths",
            "--output",
            "PATH,TYPE,FSTYPE",
        ]
    )
    result: list[pathlib.Path] = []

    def visit(entry: dict[str, Any]) -> None:
        if (
            entry.get("fstype") == "btrfs"
            and entry.get("type") in {"part", "crypt", "lvm"}
            and entry.get("path")
        ):
            result.append(pathlib.Path(entry["path"]))
        for child in entry.get("children", []):
            visit(child)

    for block in json.loads(information.stdout).get("blockdevices", []):
        visit(block)
    return sorted(set(result), key=str)


def top_level_luigios_roots(device: pathlib.Path) -> list[str]:
    device = validate_btrfs_device(device)
    base = pathlib.Path("/run/luigios-recovery/discovery")
    base.mkdir(parents=True, exist_ok=True)
    top = pathlib.Path(tempfile.mkdtemp(prefix="target-", dir=base))
    mounted = False
    try:
        command(
            [
                "mount",
                "-o",
                "ro,nosuid,nodev,noexec,subvolid=5",
                str(device),
                str(top),
            ]
        )
        mounted = True
        roots: list[str] = []
        for candidate in sorted(top.iterdir(), key=lambda path: path.name):
            if (
                candidate.is_dir()
                and not candidate.is_symlink()
                and os_release(candidate).get("ID") == "luigios"
            ):
                roots.append(candidate.name)
        return roots
    finally:
        if mounted:
            unmount_tree(top)
        if not mountpoints_below(top):
            with contextlib.suppress(OSError):
                top.rmdir()


def boot_source(root: pathlib.Path) -> str | None:
    entry = next(
        (
            item
            for item in fstab_entries(root)
            if item["target"] == "/boot"
        ),
        None,
    )
    if not entry:
        return None
    source = entry["source"]
    permitted = (
        source.startswith("UUID=")
        or source.startswith("PARTUUID=")
        or source.startswith("LABEL=")
        or source.startswith("/dev/disk/by-")
        or source.startswith("/dev/mapper/")
    )
    if not permitted:
        raise RecoveryError(f"unsafe boot filesystem source in fstab: {source}")
    return source


def limine_active_subvolume(root: pathlib.Path) -> str | None:
    """Return the first top-level Btrfs root selected by Limine."""
    configuration = rooted(root, "/boot/limine.conf")
    if not configuration.is_file():
        return None
    for match in re.finditer(
        r"(?:^|\s)rootflags=subvol=/?([^\s,]+)",
        configuration.read_text(encoding="utf-8", errors="strict"),
    ):
        subvolume = match.group(1).strip("/")
        if subvolume and "/" not in subvolume and subvolume not in {".", ".."}:
            return subvolume
    return None


def live_snapshot_history_subvolume(
    root: pathlib.Path, luigios_roots: list[str]
) -> str | None:
    entry = next(
        (
            item
            for item in fstab_entries(root)
            if item["target"] == "/.snapshots"
        ),
        None,
    )
    if not entry:
        return None
    if entry["fstype"] != "btrfs":
        raise RecoveryError("snapshot history is not a Btrfs mount")
    options = [
        option.split("=", 1)[1].strip("/")
        for option in entry["options"].split(",")
        if option.startswith("subvol=")
    ]
    if len(options) != 1:
        raise RecoveryError("snapshot history has no unique subvolume")
    subvolume = options[0]
    parts = subvolume.split("/")
    if (
        len(parts) != 2
        or parts[1] != ".snapshots"
        or parts[0] not in luigios_roots
    ):
        raise RecoveryError("snapshot history subvolume is outside LuigiOS")
    return subvolume


def offline_repository_ready(root: pathlib.Path) -> bool:
    repository = rooted(root, "/usr/share/luigios/repo")
    database = repository / "luigios-lock.db"
    manifest = rooted(
        root, "/usr/share/luigios/recovery/package-roots"
    )
    if (
        not repository.is_dir()
        or not database.is_file()
        or not manifest.is_file()
        or not shutil.which("bsdtar")
    ):
        return False
    roots = {
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not roots:
        return False
    result = command(
        ["bsdtar", "-xOf", str(database)], check=False
    )
    if result.returncode != 0:
        return False
    records = re.findall(
        r"(?:^|\n)%NAME%\n([^\n]+)\n"
        r"(?:(?!\n%NAME%\n).)*?"
        r"\n%FILENAME%\n([^\n]+)",
        result.stdout,
        re.DOTALL,
    )
    packages = {name: filename for name, filename in records}
    return roots.issubset(packages) and all(
        (repository / packages[name]).is_file() for name in roots
    )


@contextlib.contextmanager
def mounted_live_target(
    device: pathlib.Path,
    subvolume: str,
    policy: dict[str, Any],
    *,
    writable: bool,
):
    require_root()
    device = validate_btrfs_device(device)
    luigios_roots = top_level_luigios_roots(device)
    if (
        not subvolume
        or "/" in subvolume
        or subvolume in {".", ".."}
        or subvolume not in luigios_roots
    ):
        raise RecoveryError(f"invalid LuigiOS root subvolume: {subvolume}")
    base = pathlib.Path("/run/luigios-recovery/live")
    base.mkdir(parents=True, exist_ok=True)
    temporary = pathlib.Path(tempfile.mkdtemp(prefix="target-", dir=base))
    target = temporary / "root"
    target.mkdir()
    mounted = False
    mode = "rw" if writable else "ro"
    try:
        command(
            [
                "mount",
                "-o",
                f"{mode},nosuid,nodev,subvol=/{subvolume}",
                str(device),
                str(target),
            ]
        )
        mounted = True
        media_repository = pathlib.Path(
            "/usr/share/luigios/repo"
        )
        target_repository = rooted(
            target, "/usr/share/luigios/repo"
        )
        if offline_repository_ready(pathlib.Path("/")):
            if target_repository.is_symlink():
                raise RecoveryError(
                    "offline repository mountpoint is a symlink"
                )
            target_repository.mkdir(parents=True, exist_ok=True)
            command(
                [
                    "mount",
                    "--bind",
                    str(media_repository),
                    str(target_repository),
                ]
            )
            command(
                [
                    "mount",
                    "-o",
                    "remount,bind,ro,nosuid,nodev",
                    str(target_repository),
                ]
            )
        history = live_snapshot_history_subvolume(
            target, luigios_roots
        )
        if history:
            destination = rooted(target, "/.snapshots")
            if destination.is_symlink():
                raise RecoveryError(
                    "snapshot history mountpoint is a symlink"
                )
            destination.mkdir(parents=True, exist_ok=True)
            command(
                [
                    "mount",
                    "-o",
                    f"{mode},nosuid,nodev,noexec,subvol=/{history}",
                    str(device),
                    str(destination),
                ]
            )
        for mountpoint, persistent in policy["filesystem"][
            "persistent_subvolumes"
        ].items():
            destination = rooted(target, mountpoint)
            if destination.is_symlink():
                raise RecoveryError(
                    f"persistent mountpoint is a symlink: {mountpoint}"
                )
            destination.mkdir(parents=True, exist_ok=True)
            command(
                [
                    "mount",
                    "-o",
                    f"{mode},nosuid,nodev,subvol=/{persistent}",
                    str(device),
                    str(destination),
                ]
            )
        esp = boot_source(target)
        if esp:
            destination = rooted(target, "/boot")
            if destination.is_symlink():
                raise RecoveryError("boot mountpoint is a symlink")
            destination.mkdir(parents=True, exist_ok=True)
            options = "rw,nodev,nosuid" if writable else "ro,nodev,nosuid"
            command(["mount", "-o", options, esp, str(destination)])
        if writable:
            for source in ("/dev", "/proc", "/sys"):
                destination = rooted(target, source)
                destination.mkdir(parents=True, exist_ok=True)
                command(
                    ["mount", "--bind", source, str(destination)]
                )
            run_directory = rooted(target, "/run")
            run_directory.mkdir(parents=True, exist_ok=True)
            command(
                [
                    "mount",
                    "-t",
                    "tmpfs",
                    "-o",
                    "nosuid,nodev,mode=0755",
                    "tmpfs",
                    str(run_directory),
                ]
            )
        yield target
    finally:
        if mounted:
            unmount_tree(target)
        if not mountpoints_below(target):
            with contextlib.suppress(OSError):
                target.rmdir()
                temporary.rmdir()


def discover_live_targets(policy: dict[str, Any]) -> dict[str, Any]:
    require_root()
    targets: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for device in btrfs_candidates():
        try:
            for subvolume in top_level_luigios_roots(device):
                try:
                    with mounted_live_target(
                        device, subvolume, policy, writable=False
                    ) as root:
                        status = inspect_system(root, policy)
                        active_subvolume = limine_active_subvolume(root)
                    targets.append(
                        {
                            "device": str(device),
                            "subvolume": subvolume,
                            "active": active_subvolume == subvolume,
                            "status": status,
                        }
                    )
                except (RecoveryError, OSError, subprocess.CalledProcessError) as error:
                    errors.append(
                        {
                            "device": str(device),
                            "subvolume": subvolume,
                            "error": str(error),
                        }
                    )
        except (RecoveryError, OSError, subprocess.CalledProcessError) as error:
            errors.append({"device": str(device), "error": str(error)})
    targets.sort(
        key=lambda target: (
            not target["active"],
            target["device"],
            target["subvolume"],
        )
    )
    return {
        "schema": 1,
        "targets": targets,
        "errors": errors,
        "formats_storage": False,
    }


def inspect_system(root: pathlib.Path, policy: dict[str, Any]) -> dict[str, Any]:
    root = normalized_root(root)
    release = os_release(root)
    mount = findmnt(root)
    snapshot_id = None
    for marker in (
        "/var/lib/luigios/recovery/installation-snapshot",
        "/etc/luigios/installation-snapshot",
        "/etc/cachyos/installation-snapshot",
    ):
        installation_snapshot = rooted(root, marker)
        if installation_snapshot.is_file():
            snapshot_id = installation_snapshot.read_text(
                encoding="utf-8"
            ).strip()
            break
    persistent: dict[str, dict[str, Any]] = {}
    for mountpoint, subvolume in policy["filesystem"][
        "persistent_subvolumes"
    ].items():
        path = rooted(root, mountpoint)
        entry = findmnt(path) if path.exists() else None
        persistent[mountpoint] = {
            "expected": f"/{subvolume}",
            "mount": entry,
            "separate": bool(
                entry and entry.get("fsroot") == f"/{subvolume}"
            ),
        }
    blockers: list[str] = []
    if release.get("ID") != "luigios":
        blockers.append("target is not identified as LuigiOS")
    if not mount or mount.get("fstype") != "btrfs":
        blockers.append("root filesystem is not Btrfs")
    if not snapshot_id or not snapshot_id.isdigit():
        blockers.append("permanent installation snapshot is missing")
    missing_subvolumes = [
        path for path, value in persistent.items() if not value["separate"]
    ]
    if missing_subvolumes:
        blockers.append(
            "persistent subvolumes are not separate: "
            + ", ".join(missing_subvolumes)
        )
    package_roots = rooted(
        root, "/usr/share/luigios/recovery/package-roots"
    )
    repository_ready = offline_repository_ready(root)
    return {
        "schema": 1,
        "root": str(root),
        "release": release,
        "mount": mount,
        "installation_snapshot": snapshot_id,
        "persistent_subvolumes": persistent,
        "offline_repository": repository_ready,
        "offline_repository_ready": repository_ready,
        "package_roots": package_roots.is_file(),
        "fresh_start_eligible": not blockers,
        "blockers": blockers,
    }


def make_plan(
    action: str, root: pathlib.Path, policy: dict[str, Any]
) -> dict[str, Any]:
    status = inspect_system(root, policy)
    plan_id = str(uuid.uuid4())
    steps = {
        "safe-upgrade": [
            "resolve a complete update with an isolated package database",
            "download and verify every package before reboot",
            "create a Snapper pre-transaction restore point",
            "apply the full transaction in systemd offline-update mode",
            "verify package database and Limine boot payloads",
            "create the matching post-transaction restore point",
        ],
        "repair": [
            "capture and verify system settings",
            "create a pre-repair restore point",
            "reinstall signed LuigiOS package roots",
            "rebuild and verify initramfs and Limine payloads",
            "verify preserved settings and package database",
        ],
        "fresh-start": [
            "capture and verify safe and quarantined system settings",
            "record persistent subvolume identities",
            "create a pre-Fresh-Start restore point",
            "create a new root from the permanent installation snapshot",
            "reapply safe settings and retain risky overrides for review",
            "verify packages, settings, user-data subvolumes, and boot payloads",
            "add a new boot entry while retaining the previous root",
        ],
    }[action]
    blockers = list(status["blockers"])
    if action == "repair" and not status["offline_repository_ready"]:
        blockers.append(
            "signed repair package pool is unavailable; boot the matching "
            "LuigiOS live medium"
        )
    if action != "fresh-start":
        blockers = [
            item
            for item in blockers
            if not item.startswith("persistent subvolumes")
            and "installation snapshot" not in item
        ]
    return {
        "schema": 1,
        "plan_id": plan_id,
        "action": action,
        "root": str(root.resolve()),
        "steps": steps,
        "formats_storage": False,
        "deletes_previous_root": False,
        "status": status,
        "blockers": blockers,
        "executable": not blockers,
    }


@contextlib.contextmanager
def recovery_lock(path: pathlib.Path = LOCK_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RecoveryError("another recovery transaction is active") from error
        yield


def require_root() -> None:
    if os.geteuid() != 0:
        raise RecoveryError("this operation requires PolicyKit authorization")


def transaction_id(prefix: str) -> str:
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"{prefix}-{timestamp}-{uuid.uuid4().hex[:8]}"


def transaction_directory(root: pathlib.Path, identifier: str) -> pathlib.Path:
    state = rooted(root, "/var/lib/luigios/recovery/transactions")
    state.mkdir(parents=True, exist_ok=True)
    os.chmod(state.parent, 0o700)
    directory = state / identifier
    directory.mkdir(mode=0o700)
    return directory


def log_command(
    arguments: list[str],
    log: pathlib.Path,
    *,
    environment: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = command(arguments, check=False, environment=environment)
    with log.open("a", encoding="utf-8") as stream:
        stream.write("$ " + " ".join(arguments) + "\n")
        stream.write(result.stdout or "")
        stream.write(result.stderr or "")
        stream.flush()
        os.fsync(stream.fileno())
    if check and result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip().splitlines()
        suffix = f": {details[-1][:300]}" if details else ""
        raise RecoveryError(
            f"command failed ({result.returncode}): "
            f"{' '.join(arguments)}{suffix}"
        )
    return result


def snapper_snapshot(
    description: str,
    transaction: str,
    log: pathlib.Path,
    *,
    snapshot_type: str = "single",
    pre_number: str | None = None,
    root: pathlib.Path = pathlib.Path("/"),
) -> str:
    arguments = [
        "snapper",
        "--no-dbus",
        "--root",
        str(root),
        "-c",
        "root",
        "create",
        "--print-number",
        "--type",
        snapshot_type,
        "--description",
        description,
        "--userdata",
        f"important=yes,luigios={transaction}",
    ]
    if pre_number:
        arguments.extend(["--pre-number", pre_number])
    result = log_command(isolated_snapper_command(root, arguments), log)
    snapshot = result.stdout.strip().splitlines()[-1]
    if not snapshot.isdigit():
        raise RecoveryError("Snapper did not return a snapshot number")
    return snapshot


def isolated_snapper_command(
    root: pathlib.Path,
    arguments: list[str],
    *,
    plugin_directory: pathlib.Path = pathlib.Path(
        "/usr/lib/snapper/plugins"
    ),
    empty_directory: pathlib.Path = pathlib.Path(
        "/run/luigios-recovery/empty-snapper-plugins"
    ),
) -> list[str]:
    """Disable host-root-only client plugins for an offline target."""
    if root.resolve() == pathlib.Path("/") or not plugin_directory.is_dir():
        return arguments
    unshare = shutil.which("unshare")
    if not unshare:
        raise RecoveryError(
            "unshare is required to isolate Snapper plugins for live recovery"
        )
    empty_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if empty_directory.is_symlink() or not empty_directory.is_dir():
        raise RecoveryError("unsafe empty Snapper plugin directory")
    script = (
        'mount --bind "$1" "$2" && shift 2 && exec "$@"'
    )
    return [
        unshare,
        "--mount",
        "--propagation",
        "private",
        "--",
        "/bin/sh",
        "-c",
        script,
        "luigios-snapper",
        str(empty_directory),
        str(plugin_directory),
        *arguments,
    ]


def b2sum(path: pathlib.Path) -> str:
    digest = hashlib.blake2b(digest_size=64)
    with path.open("rb", buffering=0) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_boot_payloads(root: pathlib.Path) -> dict[str, Any]:
    configuration = rooted(root, "/boot/limine.conf")
    if not configuration.is_file():
        raise RecoveryError(f"missing Limine configuration: {configuration}")
    checked: list[str] = []
    for line in configuration.read_text(
        encoding="utf-8", errors="strict"
    ).splitlines():
        stripped = line.strip()
        if not (
            stripped.startswith("path:")
            or stripped.startswith("module_path:")
            or stripped.startswith("kernel_path:")
        ):
            continue
        value = stripped.split(":", 1)[1].strip()
        if not value.startswith("boot():/") or "#" not in value:
            continue
        relative, expected = value.removeprefix("boot():/").rsplit("#", 1)
        payload = rooted(root, f"/boot/{relative}")
        if not payload.is_file():
            raise RecoveryError(f"missing Limine payload: {relative}")
        if b2sum(payload) != expected:
            raise RecoveryError(f"Limine payload hash mismatch: {relative}")
        checked.append(relative)
    if not checked:
        raise RecoveryError("Limine configuration has no hashed payloads")
    return {"checked": sorted(set(checked)), "count": len(set(checked))}


def verify_package_database(root: pathlib.Path, log: pathlib.Path) -> None:
    arguments = ["pacman"]
    if root.resolve() != pathlib.Path("/"):
        arguments.extend(["--sysroot", str(root.resolve())])
    arguments.extend(["-Dk"])
    log_command(arguments, log)


def chroot_command(
    root: pathlib.Path, arguments: list[str], log: pathlib.Path
) -> subprocess.CompletedProcess[str]:
    if root.resolve() == pathlib.Path("/"):
        return log_command(arguments, log)
    return log_command(["chroot", str(root.resolve()), *arguments], log)


def boot_regeneration_command(root: pathlib.Path) -> list[str]:
    for command_path in (
        "/usr/bin/limine-mkinitcpio",
        "/usr/local/bin/limine-mkinitcpio",
    ):
        if rooted(root, command_path).is_file():
            return [command_path]
    presets = rooted(root, "/etc/mkinitcpio.d")
    if presets.is_dir() and any(presets.glob("*.preset")):
        return ["/usr/bin/mkinitcpio", "-P"]
    raise RecoveryError(
        "no supported initramfs regeneration path is available"
    )


def regenerate_boot(root: pathlib.Path, log: pathlib.Path) -> None:
    chroot_command(root, boot_regeneration_command(root), log)
    update = rooted(root, "/usr/bin/limine-update")
    if update.exists():
        chroot_command(root, ["/usr/bin/limine-update"], log)
    verify_boot_payloads(root)


def ensure_luigios(root: pathlib.Path) -> None:
    if os_release(root).get("ID") != "luigios":
        raise RecoveryError(f"refusing non-LuigiOS target: {root}")


def reassert_luigios_contract(root: pathlib.Path) -> dict[str, Any]:
    """Restore identity and enablement files owned by the LuigiOS image."""
    root = normalized_root(root)
    copies = {
        "/usr/share/luigios/os-release": ("/usr/lib/os-release", 0o644),
        "/usr/share/luigios/pacman.conf": ("/etc/pacman.conf", 0o644),
    }
    for source_name, (destination_name, mode) in copies.items():
        safe_target_parent(root, destination_name)
        atomic_copy(
            rooted(root, source_name),
            rooted(root, destination_name),
            mode,
        )

    symlinks = {
        "/etc/os-release": "../usr/lib/os-release",
        "/etc/systemd/system/display-manager.service":
            "/usr/lib/systemd/system/cosmic-greeter.service",
        (
            "/etc/systemd/system/multi-user.target.wants/"
            "luigios-firstboot.service"
        ): "/usr/lib/systemd/system/luigios-firstboot.service",
        (
            "/etc/systemd/system/system-update.target.wants/"
            "luigios-offline-update.service"
        ): "/usr/lib/systemd/system/luigios-offline-update.service",
        (
            "/etc/systemd/user/graphical-session-pre.target.wants/"
            "luigios-first-login.service"
        ): "/usr/lib/systemd/user/luigios-first-login.service",
        (
            "/etc/systemd/user/graphical-session.target.wants/"
            "luigios-panel-refresh.service"
        ): "/usr/lib/systemd/user/luigios-panel-refresh.service",
    }
    for destination_name, target in symlinks.items():
        destination = rooted(root, destination_name)
        target_path = (
            rooted(root, target)
            if target.startswith("/")
            else destination.parent / target
        )
        if not target_path.is_file():
            raise RecoveryError(
                f"required LuigiOS contract unit is missing: {target}"
            )
        exact_symlink(root, destination_name, target)

    removed: list[str] = []
    for obsolete in (
        "/etc/systemd/system/luigios-firstboot.service",
        "/etc/systemd/system/multi-user.target.wants/sshd.service",
        (
            "/etc/systemd/system/multi-user.target.wants/"
            "systemd-networkd.service"
        ),
        (
            "/etc/systemd/system/sockets.target.wants/"
            "systemd-networkd.socket"
        ),
        (
            "/etc/systemd/system/multi-user.target.wants/"
            "wpa_supplicant.service"
        ),
    ):
        candidate = rooted(root, obsolete)
        if not candidate.exists() and not candidate.is_symlink():
            continue
        if candidate.is_dir() and not candidate.is_symlink():
            raise RecoveryError(
                f"refusing to remove contract path directory: {candidate}"
            )
        candidate.unlink()
        removed.append(obsolete)

    ensure_luigios(root)
    return {
        "identity": sorted(destination for destination, _mode in copies.values()),
        "symlinks": sorted(symlinks),
        "removed": removed,
    }


def locked_pacman_config(root: pathlib.Path, transaction: pathlib.Path) -> str:
    relative = pathlib.PurePosixPath("/") / transaction.relative_to(root)
    config = transaction / "pacman-recovery.conf"
    config.write_text(
        """[options]
Architecture = auto
CheckSpace
SigLevel = Required DatabaseOptional
LocalFileSigLevel = Optional

[luigios-lock]
Server = file:///usr/share/luigios/repo
""",
        encoding="utf-8",
    )
    os.chmod(config, 0o600)
    return str(relative / config.name)


def package_roots(root: pathlib.Path) -> list[str]:
    manifest = rooted(root, "/usr/share/luigios/recovery/package-roots")
    if not manifest.is_file():
        raise RecoveryError("LuigiOS recovery package manifest is missing")
    roots = [
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not roots:
        raise RecoveryError("LuigiOS recovery package manifest is empty")
    return roots


def repair_system(
    root: pathlib.Path, policy: dict[str, Any]
) -> dict[str, Any]:
    require_root()
    root = normalized_root(root)
    ensure_luigios(root)
    if not offline_repository_ready(root):
        raise RecoveryError(
            "signed repair package pool is unavailable; boot the matching "
            "LuigiOS live medium"
        )
    identifier = transaction_id("repair")
    transaction = transaction_directory(root, identifier)
    log = transaction / "transaction.log"
    result: dict[str, Any] = {
        "schema": 1,
        "transaction": identifier,
        "action": "repair",
        "root": str(root),
        "status": "running",
        "previous_root_retained": True,
        "formatted_storage": False,
    }
    atomic_json(transaction / "result.json", result)
    bundle = transaction / "preservation"
    top = pathlib.Path("/run/luigios-recovery") / identifier / "top"
    mounted: list[pathlib.Path] = []
    boot_backup = transaction / "esp-backup"
    boot_changed = False
    try:
        capture_preservation(root, bundle, policy)
        result["persistent_before"] = {
            path: subvolume_identity(rooted(root, path))
            for path in policy["filesystem"]["persistent_subvolumes"]
        }
        result["pre_snapshot"] = snapper_snapshot(
            "Before LuigiOS system repair",
            identifier,
            log,
            root=root,
        )
        mount = findmnt(root)
        if not mount or mount["fstype"] != "btrfs":
            raise RecoveryError("transactional repair requires a Btrfs root")
        source = mount["source"].split("[", 1)[0]
        old_subvolume = mount["fsroot"].lstrip("/")
        top.mkdir(parents=True)
        log_command(
            ["mount", "-o", "subvolid=5", source, str(top)], log
        )
        new_name = f"@luigios-repair-{identifier.rsplit('-', 1)[-1]}"
        new_root = top / new_name
        if new_root.exists():
            raise RecoveryError(f"repair candidate already exists: {new_name}")
        log_command(
            [
                "btrfs",
                "subvolume",
                "snapshot",
                str(top / old_subvolume),
                str(new_root),
            ],
            log,
        )

        boot_backup.mkdir(mode=0o700)
        log_command(
            [
                "rsync",
                "-aH",
                "--delete",
                f"{rooted(root, '/boot')}/",
                f"{boot_backup}/",
            ],
            log,
        )
        mounted = bind_for_chroot(
            new_root, root, include_repository=True
        )
        boot_changed = True
        transaction_relative = (
            pathlib.PurePosixPath("/") / transaction.relative_to(root)
        )
        candidate_transaction = rooted(
            new_root, str(transaction_relative)
        )
        config = locked_pacman_config(
            new_root, candidate_transaction
        )
        pacman = ["pacman", "--sysroot", str(new_root)]
        log_command([*pacman, "--config", config, "-Sy", "--noconfirm"], log)
        log_command(
            [
                *pacman,
                "--config",
                config,
                "-S",
                "--noconfirm",
                *package_roots(new_root),
            ],
            log,
        )
        overlay = rooted(
            root, "/usr/share/luigios/recovery/target-overlay"
        )
        if not overlay.is_dir():
            raise RecoveryError("LuigiOS recovery overlay is missing")
        log_command(
            [
                "rsync",
                "-aHAX",
                "--numeric-ids",
                f"{overlay}/",
                f"{new_root}/",
            ],
            log,
        )
        result["contract"] = reassert_luigios_contract(new_root)
        restore_preservation(bundle, new_root)
        patch_subvolume_boot(new_root, old_subvolume, new_name)
        verify_package_database(new_root, log)
        regenerate_boot(new_root, log)
        result["previous_boot_entries"] = add_previous_system_boot_entries(
            new_root, new_name, old_subvolume
        )
        limine = rooted(new_root, "/boot/limine.conf").read_text(
            encoding="utf-8"
        )
        if f"rootflags=subvol=/{new_name}" not in limine:
            raise RecoveryError(
                "repaired boot entry does not select the candidate root"
            )
        if f"rootflags=subvol=/{old_subvolume}" not in limine:
            raise RecoveryError(
                "repair has no boot entry for the previous system"
            )
        result["persistent_after"] = {
            path: subvolume_identity(rooted(root, path))
            for path in policy["filesystem"]["persistent_subvolumes"]
        }
        if result["persistent_before"] != result["persistent_after"]:
            raise RecoveryError("a persistent data subvolume changed identity")
        result["preservation"] = verify_preservation(bundle)
        result["boot"] = verify_boot_payloads(new_root)
        result["new_root"] = new_name
        result["previous_root"] = old_subvolume
        result["status"] = "ready-to-reboot"
        result["reboot_required"] = True
    except Exception as error:
        result["status"] = "failed-safe"
        result["error"] = str(error)
        if boot_changed and boot_backup.is_dir():
            log_command(
                [
                    "rsync",
                    "-aH",
                    "--delete",
                    f"{boot_backup}/",
                    f"{rooted(root, '/boot')}/",
                ],
                log,
                check=False,
            )
            result["esp_restored"] = True
        atomic_json(transaction / "result.json", result)
        raise
    finally:
        try:
            cleanup_chroot_and_top(mounted, top)
        except Exception as cleanup_error:
            result["status"] = "failed-safe"
            result["error"] = str(cleanup_error)
            if boot_changed and boot_backup.is_dir():
                log_command(
                    [
                        "rsync",
                        "-aH",
                        "--delete",
                        f"{boot_backup}/",
                        f"{rooted(root, '/boot')}/",
                    ],
                    log,
                    check=False,
                )
                result["esp_restored"] = True
            atomic_json(transaction / "result.json", result)
            raise
    atomic_json(transaction / "result.json", result)
    return result


def stage_upgrade(root: pathlib.Path) -> dict[str, Any]:
    require_root()
    root = normalized_root(root)
    if root.resolve() != pathlib.Path("/"):
        raise RecoveryError("safe upgrades can only be staged by the running OS")
    ensure_luigios(root)
    system_update = pathlib.Path("/system-update")
    if system_update.exists() or system_update.is_symlink():
        raise RecoveryError("another offline update is already staged")
    identifier = transaction_id("upgrade")
    transaction = transaction_directory(root, identifier)
    log = transaction / "transaction.log"
    check_database = transaction / "check-db"
    temporary = transaction / "tmp"
    temporary.mkdir(mode=0o700)
    environment = dict(os.environ)
    environment.update(
        {
            "CHECKUPDATES_DB": str(check_database),
            "TMPDIR": str(temporary),
        }
    )
    result = log_command(
        ["checkupdates", "--download", "--nocolor"],
        log,
        environment=environment,
        check=False,
    )
    if result.returncode == 2:
        value = {
            "schema": 1,
            "transaction": identifier,
            "action": "safe-upgrade",
            "status": "no-updates",
            "updates": [],
            "reboot_required": False,
        }
        atomic_json(transaction / "result.json", value)
        return value
    if result.returncode != 0:
        raise RecoveryError("unable to resolve and download the full update")
    updates = [
        line for line in result.stdout.splitlines() if line.strip()
    ]
    pending = {
        "schema": 1,
        "transaction": identifier,
        "action": "safe-upgrade",
        "status": "staged",
        "updates": updates,
        "reboot_required": True,
    }
    atomic_json(transaction / "pending.json", pending)
    os.symlink(str(transaction), system_update)
    return pending


def offline_upgrade() -> dict[str, Any]:
    require_root()
    system_update = pathlib.Path("/system-update")
    if not system_update.is_symlink():
        raise RecoveryError("no LuigiOS offline update is staged")
    transaction = system_update.resolve(strict=True)
    pending = json.loads(
        (transaction / "pending.json").read_text(encoding="utf-8")
    )
    if pending.get("action") != "safe-upgrade":
        raise RecoveryError("invalid offline update transaction")
    identifier = pending["transaction"]
    log = transaction / "transaction.log"
    # Remove the trigger before changing packages so a failure cannot loop.
    system_update.unlink()
    result = dict(pending)
    result["status"] = "running"
    atomic_json(transaction / "result.json", result)
    pre_snapshot = None
    try:
        pre_snapshot = snapper_snapshot(
            "Before LuigiOS offline upgrade",
            identifier,
            log,
            snapshot_type="pre",
        )
        result["pre_snapshot"] = pre_snapshot
        staged_sync = transaction / "check-db/sync"
        if not staged_sync.is_dir():
            raise RecoveryError("staged package database is missing")
        log_command(
            [
                "rsync",
                "-a",
                "--delete",
                f"{staged_sync}/",
                "/var/lib/pacman/sync/",
            ],
            log,
        )
        log_command(["pacman", "-Su", "--noconfirm"], log)
        verify_package_database(pathlib.Path("/"), log)
        regenerate_boot(pathlib.Path("/"), log)
        result["post_snapshot"] = snapper_snapshot(
            "After LuigiOS offline upgrade",
            identifier,
            log,
            snapshot_type="post",
            pre_number=pre_snapshot,
        )
        result["boot"] = verify_boot_payloads(pathlib.Path("/"))
        result["status"] = "complete"
        result["reboot_required"] = True
    except Exception as error:
        result["error"] = str(error)
        result["status"] = "rolling-back"
        atomic_json(transaction / "result.json", result)
        if pre_snapshot:
            try:
                log_command(
                    [
                        "snapper",
                        "--no-dbus",
                        "-c",
                        "root",
                        "undochange",
                        f"{pre_snapshot}..0",
                    ],
                    log,
                )
                regenerate_boot(pathlib.Path("/"), log)
                result["status"] = "rolled-back"
            except Exception as rollback_error:
                result["status"] = "rollback-required"
                result["rollback_error"] = str(rollback_error)
        atomic_json(transaction / "result.json", result)
        raise RecoveryError(
            f"offline update failed; recovery status: {result['status']}"
        ) from error
    atomic_json(transaction / "result.json", result)
    return result


def patch_subvolume_boot(
    new_root: pathlib.Path,
    old_subvolume: str,
    new_subvolume: str,
) -> None:
    fstab = rooted(new_root, "/etc/fstab")
    if not fstab.is_file():
        raise RecoveryError("Fresh Start root has no fstab")
    output: list[str] = []
    root_replaced = False
    root_spec = None
    root_options: list[str] = []
    for line in fstab.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[1] == "/":
            options = fields[3].split(",")
            replaced: list[str] = []
            for option in options:
                if option in (
                    f"subvol={old_subvolume}",
                    f"subvol=/{old_subvolume.lstrip('/')}",
                ):
                    replaced.append(f"subvol=/{new_subvolume.lstrip('/')}")
                    root_replaced = True
                else:
                    replaced.append(option)
            fields[3] = ",".join(replaced)
            root_spec = fields[0]
            root_options = replaced
            line = "\t".join(fields)
        output.append(line)
    if not root_replaced or not root_spec:
        raise RecoveryError("unable to identify the root subvolume in fstab")
    snapshot_options = [
        (
            f"subvol=/{old_subvolume.lstrip('/')}/.snapshots"
            if option.startswith("subvol=")
            else option
        )
        for option in root_options
    ]
    if not any(
        len(line.split()) >= 2 and line.split()[1] == "/.snapshots"
        for line in output
    ):
        output.append(
            "\t".join(
                [
                    root_spec,
                    "/.snapshots",
                    "btrfs",
                    ",".join(snapshot_options),
                    "0",
                    "0",
                ]
            )
        )
    fstab.write_text("\n".join(output) + "\n", encoding="utf-8")
    cmdline = rooted(new_root, "/etc/kernel/cmdline")
    if not cmdline.is_file():
        raise RecoveryError("Fresh Start root has no kernel command line")
    text = cmdline.read_text(encoding="utf-8")
    variants = (
        f"subvol={old_subvolume}",
        f"subvol=/{old_subvolume.lstrip('/')}",
    )
    for variant in variants:
        if variant in text:
            text = text.replace(
                variant, f"subvol=/{new_subvolume.lstrip('/')}"
            )
            break
    else:
        raise RecoveryError("kernel command line has no root subvolume")
    cmdline.write_text(text, encoding="utf-8")
    rooted(new_root, "/.snapshots").mkdir(parents=True, exist_ok=True)


PREVIOUS_BOOT_BEGIN = "### LuigiOS previous system begin"
PREVIOUS_BOOT_END = "### LuigiOS previous system end"


def add_previous_system_boot_entries(
    root: pathlib.Path,
    current_subvolume: str,
    previous_subvolume: str,
) -> int:
    """Add writable previous-root entries using the verified current payloads."""
    configuration = rooted(root, "/boot/limine.conf")
    if not configuration.is_file():
        raise RecoveryError("Fresh Start root has no Limine configuration")
    text = configuration.read_text(encoding="utf-8", errors="strict")
    marked = re.compile(
        rf"\n?{re.escape(PREVIOUS_BOOT_BEGIN)}.*?"
        rf"{re.escape(PREVIOUS_BOOT_END)}\n?",
        re.DOTALL,
    )
    text = marked.sub("\n", text).rstrip() + "\n"
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if line.startswith("//linux-")
    ]
    blocks: list[str] = []
    current_variants = (
        f"rootflags=subvol=/{current_subvolume.lstrip('/')}",
        f"rootflags=subvol={current_subvolume.lstrip('/')}",
    )
    previous_flag = (
        f"rootflags=subvol=/{previous_subvolume.lstrip('/')}"
    )
    for start in starts:
        end = start + 1
        while end < len(lines) and not lines[end].startswith("/"):
            end += 1
        block = lines[start:end]
        replaced = 0
        cloned: list[str] = []
        for line in block:
            for variant in current_variants:
                if variant in line:
                    line = line.replace(variant, previous_flag)
                    replaced += 1
            cloned.append(line)
        if replaced != 1:
            continue
        kernel = block[0].removeprefix("//")
        cloned[0] = f"//Previous system - {kernel}"
        blocks.append("\n".join(cloned))
    if not blocks:
        raise RecoveryError(
            "unable to create a boot entry for the previous system"
        )
    section = "\n".join(
        [
            PREVIOUS_BOOT_BEGIN,
            "/+LuigiOS Previous System",
            (
                "comment: Writable system retained immediately before "
                "LuigiOS Fresh Start"
            ),
            *blocks,
            PREVIOUS_BOOT_END,
        ]
    )
    configuration.write_text(
        text.rstrip() + "\n\n" + section + "\n",
        encoding="utf-8",
    )
    return len(blocks)


def snapshot_history_subvolume(
    root: pathlib.Path, current_root_subvolume: str
) -> str:
    for entry in fstab_entries(root):
        if entry["target"] != "/.snapshots":
            continue
        for option in entry["options"].split(","):
            if not option.startswith("subvol="):
                continue
            subvolume = option.split("=", 1)[1].strip("/")
            suffix = "/.snapshots"
            if subvolume.endswith(suffix):
                history = subvolume[: -len(suffix)]
                if history and "/" not in history:
                    return history
        raise RecoveryError("invalid snapshot-history subvolume in fstab")
    return current_root_subvolume


def subvolume_identity(path: pathlib.Path) -> str:
    result = command(["btrfs", "subvolume", "show", str(path)])
    for line in result.stdout.splitlines():
        if line.strip().startswith("Subvolume ID:"):
            return line.split(":", 1)[1].strip()
    raise RecoveryError(f"could not determine subvolume ID: {path}")


def bind_for_chroot(
    new_root: pathlib.Path,
    source_root: pathlib.Path = pathlib.Path("/"),
    *,
    include_repository: bool = False,
) -> list[pathlib.Path]:
    mounted: list[pathlib.Path] = []
    target_sources = [
        "/boot",
        "/home",
        "/root",
        "/srv",
        "/var/cache",
        "/var/lib/luigios",
        "/var/log",
        "/var/tmp",
    ]
    if include_repository:
        target_sources.append("/usr/share/luigios/repo")
    host_sources = ["/dev", "/proc", "/sys"]
    try:
        for absolute in target_sources + host_sources:
            source = (
                rooted(source_root, absolute)
                if absolute in target_sources
                else pathlib.Path(absolute)
            )
            destination = rooted(new_root, absolute)
            destination.mkdir(parents=True, exist_ok=True)
            command(["mount", "--bind", str(source), str(destination)])
            mounted.append(destination)
        run_directory = rooted(new_root, "/run")
        run_directory.mkdir(parents=True, exist_ok=True)
        command(
            [
                "mount",
                "-t",
                "tmpfs",
                "-o",
                "nosuid,nodev,mode=0755",
                "tmpfs",
                str(run_directory),
            ]
        )
        mounted.append(run_directory)
    except Exception:
        unmount_chroot(mounted)
        raise
    return mounted


def unmount_chroot(mounted: list[pathlib.Path]) -> None:
    errors: list[Exception] = []
    for path in reversed(mounted):
        try:
            unmount_tree(path)
        except Exception as error:
            errors.append(error)
    if errors:
        raise errors[0]


def cleanup_chroot_and_top(
    mounted: list[pathlib.Path], top: pathlib.Path
) -> None:
    cleanup_error: Exception | None = None
    try:
        unmount_chroot(mounted)
    except Exception as error:
        cleanup_error = error
    if top.is_mount() or mountpoints_below(top):
        try:
            unmount_tree(top)
        except Exception as error:
            cleanup_error = error
    remaining = mountpoints_below(top)
    if remaining:
        raise RecoveryError(
            f"recovery candidate remains mounted at {remaining[0]}"
        ) from cleanup_error


def fresh_start(
    root: pathlib.Path, policy: dict[str, Any]
) -> dict[str, Any]:
    require_root()
    root = normalized_root(root)
    status = inspect_system(root, policy)
    if not status["fresh_start_eligible"]:
        raise RecoveryError("; ".join(status["blockers"]))
    identifier = transaction_id("fresh-start")
    transaction = transaction_directory(root, identifier)
    log = transaction / "transaction.log"
    result: dict[str, Any] = {
        "schema": 1,
        "transaction": identifier,
        "action": "fresh-start",
        "status": "running",
        "previous_root_retained": True,
        "formatted_storage": False,
    }
    atomic_json(transaction / "result.json", result)
    bundle = transaction / "preservation"
    top = pathlib.Path("/run/luigios-recovery") / identifier / "top"
    mounted: list[pathlib.Path] = []
    boot_backup = transaction / "esp-backup"
    boot_changed = False
    try:
        capture_preservation(root, bundle, policy)
        result["persistent_before"] = {
            path: subvolume_identity(rooted(root, path))
            for path in policy["filesystem"]["persistent_subvolumes"]
        }
        log_command(
            ["btrfs", "device", "stats", "-c", str(root)], log
        )
        log_command(
            ["btrfs", "scrub", "start", "-B", "-r", str(root)], log
        )
        result["pre_snapshot"] = snapper_snapshot(
            "Before LuigiOS Fresh Start", identifier, log, root=root
        )
        if root.resolve() == pathlib.Path("/") and shutil.which(
            "limine-snapper-sync"
        ):
            log_command(["limine-snapper-sync"], log)

        mount = status["mount"]
        source = mount["source"].split("[", 1)[0]
        old_subvolume = mount["fsroot"].lstrip("/")
        history_subvolume = snapshot_history_subvolume(
            root, old_subvolume
        )
        top.mkdir(parents=True)
        log_command(
            ["mount", "-o", "subvolid=5", source, str(top)], log
        )
        source_snapshot = (
            top
            / history_subvolume
            / ".snapshots"
            / status["installation_snapshot"]
            / "snapshot"
        )
        log_command(
            ["btrfs", "subvolume", "show", str(source_snapshot)], log
        )
        new_name = f"@luigios-fresh-{identifier.rsplit('-', 1)[-1]}"
        new_root = top / new_name
        if new_root.exists():
            raise RecoveryError(f"Fresh Start root already exists: {new_name}")
        log_command(
            [
                "btrfs",
                "subvolume",
                "snapshot",
                str(source_snapshot),
                str(new_root),
            ],
            log,
        )
        restore_preservation(bundle, new_root)
        patch_subvolume_boot(new_root, old_subvolume, new_name)
        verify_package_database(new_root, log)

        boot_backup.mkdir(mode=0o700)
        log_command(
            [
                "rsync",
                "-aH",
                "--delete",
                f"{rooted(root, '/boot')}/",
                f"{boot_backup}/",
            ],
            log,
        )
        mounted = bind_for_chroot(new_root, root)
        boot_changed = True
        regenerate_boot(new_root, log)
        result["previous_boot_entries"] = add_previous_system_boot_entries(
            new_root, new_name, old_subvolume
        )
        limine = rooted(new_root, "/boot/limine.conf").read_text(
            encoding="utf-8"
        )
        expected_rootflag = f"rootflags=subvol=/{new_name}"
        if expected_rootflag not in limine:
            raise RecoveryError(
                "new Limine entry does not select the Fresh Start root"
            )
        previous_rootflag = f"rootflags=subvol=/{old_subvolume}"
        if previous_rootflag not in limine:
            raise RecoveryError(
                "Limine has no boot entry for the previous system"
            )
        result["persistent_after"] = {
            path: subvolume_identity(rooted(root, path))
            for path in policy["filesystem"]["persistent_subvolumes"]
        }
        if result["persistent_before"] != result["persistent_after"]:
            raise RecoveryError("a persistent data subvolume changed identity")
        result["new_root"] = new_name
        result["preservation"] = verify_preservation(bundle)
        result["boot"] = verify_boot_payloads(new_root)
        result["status"] = "ready-to-reboot"
        result["reboot_required"] = True
    except Exception as error:
        result["status"] = "failed-safe"
        result["error"] = str(error)
        if boot_changed and boot_backup.is_dir():
            log_command(
                [
                    "rsync",
                    "-aH",
                    "--delete",
                    f"{boot_backup}/",
                    f"{rooted(root, '/boot')}/",
                ],
                log,
                check=False,
            )
            result["esp_restored"] = True
        atomic_json(transaction / "result.json", result)
        raise
    finally:
        try:
            cleanup_chroot_and_top(mounted, top)
        except Exception as cleanup_error:
            result["status"] = "failed-safe"
            result["error"] = str(cleanup_error)
            if boot_changed and boot_backup.is_dir():
                log_command(
                    [
                        "rsync",
                        "-aH",
                        "--delete",
                        f"{boot_backup}/",
                        f"{rooted(root, '/boot')}/",
                    ],
                    log,
                    check=False,
                )
                result["esp_restored"] = True
            atomic_json(transaction / "result.json", result)
            raise
    atomic_json(transaction / "result.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="LuigiOS transactional recovery engine"
    )
    result.add_argument("--policy", type=pathlib.Path)
    subcommands = result.add_subparsers(dest="command", required=True)

    status = subcommands.add_parser("status")
    status.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/"))
    status.add_argument("--device", type=pathlib.Path)
    status.add_argument("--subvolume")

    plan = subcommands.add_parser("plan")
    plan.add_argument(
        "action", choices=("safe-upgrade", "repair", "fresh-start")
    )
    plan.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/"))
    plan.add_argument("--device", type=pathlib.Path)
    plan.add_argument("--subvolume")

    subcommands.add_parser("discover-targets")

    preserve = subcommands.add_parser("preserve")
    preserve.add_argument("--source", type=pathlib.Path, required=True)
    preserve.add_argument("--bundle", type=pathlib.Path, required=True)

    verify = subcommands.add_parser("verify-preservation")
    verify.add_argument("--bundle", type=pathlib.Path, required=True)

    restore = subcommands.add_parser("restore-settings")
    restore.add_argument("--bundle", type=pathlib.Path, required=True)
    restore.add_argument("--target", type=pathlib.Path, required=True)

    stage = subcommands.add_parser("stage-upgrade")
    stage.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/"))

    subcommands.add_parser("offline-upgrade")

    repair = subcommands.add_parser("repair")
    repair.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/"))
    repair.add_argument("--device", type=pathlib.Path)
    repair.add_argument("--subvolume")

    fresh = subcommands.add_parser("fresh-start")
    fresh.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/"))
    fresh.add_argument("--device", type=pathlib.Path)
    fresh.add_argument("--subvolume")
    return result


def validate_pkexec_scope(options: argparse.Namespace) -> None:
    """Keep the PolicyKit entry point limited to product workflows.

    The same engine exposes low-level preservation helpers for root-owned
    services and qualification. A desktop user authorized for recovery must
    not be able to turn those helpers or an alternate policy into a generic
    privileged file copier.
    """
    if "PKEXEC_UID" not in os.environ:
        return
    if options.policy is not None:
        raise RecoveryError("PolicyKit recovery cannot use an alternate policy")
    allowed = {
        "discover-targets",
        "plan",
        "repair",
        "fresh-start",
        "stage-upgrade",
    }
    if options.command not in allowed:
        raise RecoveryError(
            f"command is not available through PolicyKit: {options.command}"
        )
    root = getattr(options, "root", pathlib.Path("/"))
    if root != pathlib.Path("/"):
        raise RecoveryError("PolicyKit recovery cannot select an alternate root")


@contextlib.contextmanager
def selected_root(
    options: argparse.Namespace,
    policy: dict[str, Any],
    *,
    writable: bool,
):
    device = getattr(options, "device", None)
    subvolume = getattr(options, "subvolume", None)
    if bool(device) != bool(subvolume):
        raise RecoveryError("--device and --subvolume must be used together")
    if device:
        if getattr(options, "root", pathlib.Path("/")) != pathlib.Path("/"):
            raise RecoveryError("--root cannot be combined with --device")
        with mounted_live_target(
            device, subvolume, policy, writable=writable
        ) as root:
            yield root
    else:
        yield options.root


def main(arguments: list[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    try:
        validate_pkexec_scope(options)
        policy = load_policy(options.policy)
        if options.command == "status":
            with selected_root(options, policy, writable=False) as root:
                value = inspect_system(root, policy)
        elif options.command == "plan":
            with selected_root(options, policy, writable=False) as root:
                value = make_plan(options.action, root, policy)
            if options.device:
                value["device"] = str(options.device)
                value["subvolume"] = options.subvolume
                value["root"] = "live-media target"
        elif options.command == "discover-targets":
            value = discover_live_targets(policy)
        elif options.command == "preserve":
            require_root()
            with recovery_lock():
                value = capture_preservation(
                    options.source, options.bundle, policy
                )
        elif options.command == "verify-preservation":
            value = verify_preservation(options.bundle)
        elif options.command == "restore-settings":
            require_root()
            with recovery_lock():
                value = restore_preservation(
                    options.bundle, options.target
                )
        elif options.command == "stage-upgrade":
            with recovery_lock():
                value = stage_upgrade(options.root)
        elif options.command == "offline-upgrade":
            with recovery_lock():
                value = offline_upgrade()
        elif options.command == "repair":
            with recovery_lock():
                with selected_root(options, policy, writable=True) as root:
                    value = repair_system(root, policy)
        elif options.command == "fresh-start":
            with recovery_lock():
                with selected_root(options, policy, writable=True) as root:
                    value = fresh_start(root, policy)
        else:
            raise AssertionError(options.command)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    except (RecoveryError, OSError, subprocess.CalledProcessError) as error:
        print(
            json.dumps(
                {"error": str(error), "type": type(error).__name__},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
