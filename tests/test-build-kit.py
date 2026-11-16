#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline tests of the public build entrypoint; no desktop/keyring access."""

import json
import importlib.util
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("backport", ROOT / "scripts/backport.py")
assert SPEC is not None and SPEC.loader is not None
KIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KIT)


class TargetContractTests(unittest.TestCase):
    def test_noble_target_retains_pinned_source(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/backport.py"), "info", "ubuntu24.04"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        target = json.loads(result.stdout)
        self.assertEqual(target["source_version"], "46.1-2ubuntu0.2")
        self.assertEqual(target["suite"], "noble")
        self.assertEqual(target["architecture"], "amd64")
        self.assertEqual(target["local_version"], "46.1-2ubuntu0.2+local1")

    def test_resolute_has_separate_authenticated_target(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/backport.py"), "info", "ubuntu26.04"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        target = json.loads(result.stdout)
        self.assertEqual(target["source_version"], "50.0-1")
        self.assertEqual(target["suite"], "resolute")
        self.assertEqual(target["local_version"], "50.0-1ubuntu0.0+local1")
        self.assertNotEqual(target["base_image"], KIT.load_target("ubuntu24.04")["base_image"])
        self.assertEqual(len(target["files"]), 3)
        self.assertTrue((ROOT / target["signer_key"]).is_file())

    @unittest.skipUnless(shutil.which("dpkg"), "version-order check requires dpkg")
    def test_local_packages_do_not_outrank_next_ubuntu_security_revision(self):
        next_revisions = {"ubuntu24.04": "46.1-2ubuntu0.3", "ubuntu26.04": "50.0-1ubuntu0.1"}
        for name, next_revision in next_revisions.items():
            with self.subTest(target=name):
                target = KIT.load_target(name)
                for lower, upper in ((target["source_version"], target["local_version"]),
                                     (target["local_version"], next_revision)):
                    result = subprocess.run(["dpkg", "--compare-versions", lower, "lt", upper],
                                            timeout=10)
                    self.assertEqual(result.returncode, 0, f"expected {lower} < {upper}")

    def test_unknown_target_is_rejected(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/backport.py"), "info", "../other"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_tampered_source_is_rejected_before_signature_check(self):
        with tempfile.TemporaryDirectory() as directory:
            target = json.loads((ROOT / "targets/ubuntu24.04.json").read_text())
            for name in target["files"]:
                (Path(directory) / name).write_bytes(b"not the pinned source")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/backport.py"), "verify",
                 "ubuntu24.04", "--source-dir", directory],
                capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checksum mismatch", result.stderr)

    def test_source_fetch_retries_connection_resets_with_a_bound(self):
        data = b"synthetic source input"
        target = {"files": {"fixture.tar.xz": hashlib.sha256(data).hexdigest()},
                  "source_base": "https://example.invalid/source"}
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)

            def download(command, **kwargs):
                Path(command[command.index("--output") + 1]).write_bytes(data)

            with mock.patch.object(KIT.subprocess, "run", side_effect=download) as run:
                with mock.patch.object(KIT, "authenticated_source") as authenticate:
                    KIT.fetch_source(target, source_dir)
            command = run.call_args.args[0]
            self.assertIn("--retry-all-errors", command)
            self.assertEqual(command[command.index("--retry") + 1], "2")
            self.assertEqual(run.call_args.kwargs["timeout"], 600)
            authenticate.assert_called_once_with(target, source_dir)
            self.assertEqual((source_dir / "fixture.tar.xz").read_bytes(), data)

    def test_build_cannot_disable_package_tests(self):
        for variable in ("DEB_BUILD_OPTIONS", "DEB_BUILD_PROFILES"):
            with self.subTest(variable=variable):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/backport.py"),
                     "build", "ubuntu24.04"],
                    env={**os.environ, variable: "parallel=2 nocheck"},
                    capture_output=True, text=True, timeout=10,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("nocheck is not allowed", result.stderr)

    def test_package_publication_never_overwrites_existing_output(self):
        self.assertTrue(callable(getattr(KIT, "publish_package", None)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "built.deb"
            source.write_bytes(b"new package")
            destination = root / "output"
            destination.mkdir()
            existing = destination / source.name
            existing.write_bytes(b"old package")
            with self.assertRaises(FileExistsError):
                KIT.publish_package(source, destination)
            self.assertEqual(existing.read_bytes(), b"old package")
            self.assertEqual(source.read_bytes(), b"new package")

    def test_package_publication_preserves_sibling_targets(self):
        self.assertTrue(callable(getattr(KIT, "publish_package", None)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "built.deb"
            source.write_bytes(b"new package")
            sibling = root / "dist" / "other" / "old.deb"
            sibling.parent.mkdir(parents=True)
            sibling.write_bytes(b"old package")
            destination = root / "dist" / "selected"
            published = KIT.publish_package(source, destination)
            self.assertEqual(published.read_bytes(), source.read_bytes())
            self.assertEqual(sibling.read_bytes(), b"old package")

    def test_wrong_distribution_is_rejected(self):
        self.assertTrue(callable(getattr(KIT, "check_build_environment", None)))
        target = KIT.load_target("ubuntu24.04")
        with mock.patch.dict(os.environ, {"DEB_BUILD_OPTIONS": "", "DEB_BUILD_PROFILES": ""}):
            with mock.patch.object(KIT.platform, "freedesktop_os_release",
                                   return_value={"ID": "ubuntu", "VERSION_ID": "99.99"}):
                with self.assertRaisesRegex(ValueError, "wrong build distribution"):
                    KIT.check_build_environment(target)

    def test_container_build_separates_target_paths_and_disables_build_network(self):
        self.assertTrue(callable(getattr(KIT, "container_build", None)))
        with tempfile.TemporaryDirectory(prefix="build kit ") as directory:
            root = Path(directory)
            target = KIT.load_target("ubuntu24.04")
            with mock.patch.object(KIT, "ROOT", root), mock.patch.object(KIT.subprocess, "run") as run:
                KIT.container_build(target, root / "dist" / target["id"])
            commands = [call.args[0] for call in run.call_args_list]
            image_build = commands[0]
            self.assertEqual(image_build[:2], ["docker", "build"])
            self.assertIn("BASE_IMAGE=" + target["base_image"], image_build)
            self.assertIn("SUITE=noble", image_build)
            self.assertEqual(run.call_args_list[0].kwargs["timeout"], 45 * 60)
            containers = [command for command in commands if command[:2] == ["docker", "run"]]
            self.assertEqual(len(containers), 2)
            self.assertIn("--network=none", containers[1])
            self.assertIn(str(root) + ":/work:ro", containers[1])
            self.assertIn(str(root / ".build" / "ubuntu24.04") + ":/build:rw", containers[1])
            self.assertIn("ubuntu24.04", containers[1])

    def test_container_provisions_the_callers_uid_and_gid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = KIT.load_target("ubuntu24.04")
            with mock.patch.object(KIT, "ROOT", root), \
                    mock.patch.object(KIT.os, "getuid", return_value=1001), \
                    mock.patch.object(KIT.os, "getgid", return_value=1002), \
                    mock.patch.object(KIT.subprocess, "run") as run:
                KIT.container_build(target, root / "dist")
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn("BUILD_UID=1001", commands[0])
            self.assertIn("BUILD_GID=1002", commands[0])
            image = commands[0][commands[0].index("--tag") + 1]
            self.assertTrue(image.endswith("-uid1001-gid1002"))
            for command in commands:
                if command[:2] == ["docker", "run"]:
                    self.assertIn("1001:1002", command)
                    self.assertIn(image, command)


class DocumentationTests(unittest.TestCase):
    def test_readme_introduction_explains_failure_prevention_and_limit(self):
        introduction = (ROOT / "README.md").read_text().split("## ", 1)[0].lower()
        for phrase in ("passwordless", "multiline", "next", "does not repair"):
            self.assertIn(phrase, introduction)

    def test_japanese_translation_matches_commands_and_structure(self):
        japanese = ROOT / "README.ja.md"
        self.assertTrue(japanese.is_file(), "full Japanese README is required")
        english_text = (ROOT / "README.md").read_text()
        japanese_text = japanese.read_text()
        self.assertIn("[日本語](README.ja.md)", english_text)
        self.assertIn("[English (canonical)](README.md)", japanese_text)
        self.assertIn("English takes precedence", english_text)
        self.assertIn("英語版を優先", japanese_text)
        self.assertEqual(re.findall(r"^(#+) ", english_text, re.M),
                         re.findall(r"^(#+) ", japanese_text, re.M))
        self.assertEqual(re.findall(r"^```[^\n]*\n.*?^```", english_text, re.M | re.S),
                         re.findall(r"^```[^\n]*\n.*?^```", japanese_text, re.M | re.S))


if __name__ == "__main__":
    unittest.main()
