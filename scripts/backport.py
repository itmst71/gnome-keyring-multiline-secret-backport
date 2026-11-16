#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Explicit, version-pinned targets for the local backport build kit."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("ubuntu24.04", "ubuntu26.04")


def load_target(name):
    if name not in TARGETS:
        raise ValueError("unsupported target")
    return json.loads((ROOT / "targets" / (name + ".json")).read_text())


def verify_hashes(target, source_dir):
    for name, expected in target["files"].items():
        path = source_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing regular source input: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"checksum mismatch: {name}")


@contextmanager
def authenticated_source(target, source_dir):
    verify_hashes(target, source_dir)
    with tempfile.TemporaryDirectory(prefix="backport-gpg-") as directory:
        home = Path(directory)
        key = ROOT / target["signer_key"]
        gpg = ["gpg", "--homedir", str(home), "--no-options", "--batch"]
        listing = subprocess.run(
            gpg + ["--show-keys", "--with-colons", str(key)],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.splitlines()
        fingerprints = [line.split(":")[9] for line in listing if line.startswith("fpr:")]
        if (sum(line.startswith("pub:") for line in listing) != 1
                or not fingerprints or fingerprints[0] != target["signer_fingerprint"]):
            raise ValueError("unexpected source signer fingerprint")
        keyring = home / "signer.gpg"
        subprocess.run(gpg + ["--dearmor", "--output", str(keyring), str(key)],
                       check=True, timeout=30)
        dsc = source_dir / f"gnome-keyring_{target['source_version']}.dsc"
        subprocess.run(["gpgv", "--homedir", str(home), "--keyring", str(keyring), str(dsc)],
                       check=True, timeout=30)
        yield keyring


def check_build_environment(target):
    for name in ("DEB_BUILD_OPTIONS", "DEB_BUILD_PROFILES"):
        if "nocheck" in os.environ.get(name, "").split():
            raise ValueError("nocheck is not allowed: package tests are required")
    release = platform.freedesktop_os_release()
    if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != target["os_version"]:
        raise ValueError("wrong build distribution; use the selected pinned container")
    architecture = subprocess.run(
        ["dpkg", "--print-architecture"], capture_output=True, text=True,
        check=True, timeout=10,
    ).stdout.strip()
    if architecture != target["architecture"]:
        raise ValueError("wrong build architecture; only amd64 is qualified")


def publish_package(source, destination):
    """Copy privately, then link into place atomically without overwriting."""
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".publish-", dir=destination) as temporary:
        with source.open("rb") as input_file:
            shutil.copyfileobj(input_file, temporary)
        temporary.flush()
        os.fsync(temporary.fileno())
        os.chmod(temporary.name, 0o644)
        output = destination / source.name
        os.link(temporary.name, output)
    return output


def fetch_source(target, source_dir):
    source_dir.mkdir(parents=True, exist_ok=True)
    for name, expected in target["files"].items():
        destination = source_dir / name
        if destination.exists() or destination.is_symlink():
            if (destination.is_symlink() or not destination.is_file()
                    or hashlib.sha256(destination.read_bytes()).hexdigest() != expected):
                raise ValueError(f"checksum mismatch or unsafe cached input: {name}")
            continue
        with tempfile.TemporaryDirectory(prefix="fetch-", dir=source_dir) as directory:
            downloaded = Path(directory) / name
            subprocess.run([
                "curl", "--fail", "--show-error", "--location", "--proto", "=https",
                "--proto-redir", "=https", "--tlsv1.2", "--connect-timeout", "20",
                "--max-time", "180", "--max-filesize", "33554432", "--retry", "2",
                "--retry-all-errors",
                "--output", str(downloaded), target["source_base"] + "/" + name,
            ], check=True, timeout=600)
            if hashlib.sha256(downloaded.read_bytes()).hexdigest() != expected:
                raise ValueError(f"checksum mismatch: {name}")
            publish_package(downloaded, source_dir)
    with authenticated_source(target, source_dir):
        print("source_authentication=passed", flush=True)


def build_package(target, source_dir, work_root, dist_dir):
    check_build_environment(target)
    verify_hashes(target, source_dir)
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="build-", dir=work_root))
    print(f"build_work={work}", flush=True)
    for name in target["files"]:
        shutil.copyfile(source_dir / name, work / name)
    with authenticated_source(target, work):
        # Exact hashes and the pinned signer were checked above, on these copies.
        # Avoid dpkg's differing global-keyring interfaces across Ubuntu releases.
        subprocess.run(["dpkg-source", "--no-check", "-x",
                        f"gnome-keyring_{target['source_version']}.dsc", "build"],
                       cwd=work, check=True, timeout=120)
    build = work / "build"
    patch_name = "local-multiline-textual-secrets.patch"
    patch = build / "debian/patches" / patch_name
    with patch.open("xb") as output:
        output.write((ROOT / "patches/0001-escape-multiline-textual-secrets.patch").read_bytes())
    series = build / "debian/patches/series"
    with series.open("a") as output:
        output.write("\n" + patch_name + "\n")
    changelog = build / "debian/changelog"
    entry = (
        f"gnome-keyring ({target['local_version']}) {target['suite']}; urgency=medium\n\n"
        "  * Escape multiline textual secrets in passwordless keyrings.\n"
        "    Local backport of GNOME MR !111 with write/read regression coverage.\n\n"
        f" -- Local GNOME Keyring Backport <noreply@invalid>  {target['changelog_date']}\n\n"
    )
    changelog.write_text(entry + changelog.read_text())
    subprocess.run(["dpkg-buildpackage", "-b", "-uc", "-us", "-j4"],
                   cwd=build, check=True, timeout=1800)
    package = work / f"gnome-keyring_{target['local_version']}_{target['architecture']}.deb"
    metadata = subprocess.run(
        ["dpkg-deb", "--show", "--showformat=${Package}\t${Version}\t${Architecture}", str(package)],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout
    expected = f"gnome-keyring\t{target['local_version']}\t{target['architecture']}"
    if metadata != expected:
        raise ValueError("built package metadata does not match selected target")
    published = publish_package(package, dist_dir)
    print(metadata, flush=True)
    print(f"{hashlib.sha256(published.read_bytes()).hexdigest()}  {published}", flush=True)


def container_build(target, dist_dir):
    cache = ROOT / ".build" / target["id"]
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "tmp").mkdir(exist_ok=True)
    (cache / "home").mkdir(exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    image = "gnome-keyring-local-builder:" + target["id"]
    subprocess.run([
        "docker", "build", "--pull", "--platform", "linux/amd64",
        "--build-arg", "BASE_IMAGE=" + target["base_image"],
        "--build-arg", "SUITE=" + target["suite"],
        "--build-arg", "UBUNTU_SNAPSHOT=" + target["snapshot"],
        "--tag", image, str(ROOT / "container"),
    ], check=True, timeout=1800)
    for action in ("fetch", "build"):
        name = "backport-" + target["id"] + "-" + uuid.uuid4().hex[:12]
        command = [
            "docker", "run", "--rm", "--name", name, "--platform", "linux/amd64",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--env", "HOME=/build/home", "--env", "TMPDIR=/build/tmp",
            "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "LC_ALL=C.UTF-8",
            "--volume", str(ROOT) + ":/work:ro",
            "--volume", str(cache) + ":/build:rw",
            "--volume", str(dist_dir) + ":/dist:rw",
        ]
        if action == "build":
            command.append("--network=none")
        command += [image, "python3", "-B", "/work/scripts/backport.py", action,
                    target["id"], "--source-dir", "/build/source",
                    "--work-root", "/build/work", "--dist-dir", "/dist"]
        try:
            subprocess.run(command, check=True, timeout=2400)
        finally:
            # Also contains a timed-out/interrupted attached Docker client.
            subprocess.run(["docker", "rm", "--force", name], timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("info", "verify", "fetch", "build", "container"))
    parser.add_argument("target", choices=TARGETS)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--dist-dir", type=Path)
    args = parser.parse_args()
    target = load_target(args.target)
    if args.action == "info":
        print(json.dumps(target, indent=2))
        return
    source_dir = (args.source_dir or ROOT / ".build" / args.target / "source").resolve()
    if args.action == "verify":
        with authenticated_source(target, source_dir):
            print("source_authentication=passed")
    elif args.action == "fetch":
        fetch_source(target, source_dir)
    elif args.action == "build":
        work_root = (args.work_root or ROOT / ".build" / args.target / "work").resolve()
        dist_dir = (args.dist_dir or ROOT / "dist" / args.target).resolve()
        build_package(target, source_dir, work_root, dist_dir)
    else:
        if args.source_dir or args.work_root:
            parser.error("container uses target-isolated source/work directories")
        container_build(target, (args.dist_dir or ROOT / "dist" / args.target).resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"backport: {exc}", file=sys.stderr)
        raise SystemExit(1)
