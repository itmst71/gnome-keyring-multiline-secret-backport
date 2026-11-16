#!/usr/bin/env python3
"""Fail closed if the public source tree is not the intentionally minimal set."""

from __future__ import annotations

import re
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FILES = {
    ".github/workflows/build.yml",
    ".gitignore",
    "CONTRIBUTING.md",
    "LICENSE",
    "LICENSES/LGPL-2.1-or-later.txt",
    "LICENSES/MIT.txt",
    "NOTICE",
    "README.md",
    "README.ja.md",
    "SECURITY.md",
    "container/Dockerfile",
    "keys/gnome-keyring-46.1-source-signer.asc",
    "keys/gnome-keyring-50.0-source-signer.asc",
    "patches/0001-escape-multiline-textual-secrets.patch",
    "scripts/build-local-package.sh",
    "scripts/backport.py",
    "scripts/build.sh",
    "scripts/fetch-source.sh",
    "targets/ubuntu24.04.json",
    "targets/ubuntu26.04.json",
    "tests/test-build-kit.py",
    "tests/test-keyfile-multiline-roundtrip.c",
    "tests/verify-public-tree.py",
}
FORBIDDEN_PATH_PARTS = {
    ".build",
    ".work",
    "artifacts",
    "dist",
    "source",
    "live-" + "secret-service-roundtrip.c",
    "test-live-" + "test-safety.py",
}
FORBIDDEN_TEXT = (
    b"/" + b"home/",
    b"live-" + b"secret-service-roundtrip",
    b"test-live-" + b"test-safety",
    b"+it" + b"mst",
)
FORBIDDEN_SUFFIXES = (".deb", ".keyring", ".jsonl", ".state")


def fail(message: str) -> None:
    raise AssertionError(message)


def published_files() -> set[str]:
    result: set[str] = set()
    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            fail(f"symlink is not allowed: {relative}")
        if path.is_dir():
            if relative.name in FORBIDDEN_PATH_PARTS:
                fail(f"forbidden directory: {relative}")
            continue
        if not path.is_file():
            fail(f"non-regular entry: {relative}")
        if relative.name in FORBIDDEN_PATH_PARTS or relative.suffix in FORBIDDEN_SUFFIXES:
            fail(f"forbidden publication file: {relative}")
        result.add(relative.as_posix())
    return result


def assert_text_hygiene(files: set[str]) -> None:
    for relative in files:
        data = (ROOT / relative).read_bytes()
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            fail(f"non-UTF-8 public file: {relative}: {exc}")
        for marker in FORBIDDEN_TEXT:
            if marker in data:
                fail(f"forbidden text marker {marker!r} in {relative}")


def assert_relative_markdown_links(files: set[str]) -> None:
    link = re.compile(r"\[[^]]+\]\(([^)#]+)(?:#[^)]*)?\)")
    for relative in files:
        if not relative.endswith(".md") and relative != "LICENSE":
            continue
        text = (ROOT / relative).read_text(encoding="utf-8")
        for target in link.findall(text):
            if "://" in target or target.startswith("mailto:"):
                continue
            resolved = (ROOT / relative).parent / target
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                fail(f"markdown link escapes repository: {relative} -> {target}")
            if not resolved.is_file():
                fail(f"markdown link target is missing: {relative} -> {target}")


def main() -> None:
    files = published_files()
    if files != EXPECTED_FILES:
        missing = sorted(EXPECTED_FILES - files)
        extra = sorted(files - EXPECTED_FILES)
        fail(f"unexpected public scope; missing={missing}; extra={extra}")

    assert_text_hygiene(files)
    assert_relative_markdown_links(files)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())
    for required in (
        "Unofficial",
        "not affiliated with GNOME or Ubuntu",
        "does not distribute binaries",
        "46.1-2ubuntu0.2",
        "50.0-1",
        "English takes precedence",
        "+local1",
        "GNOME gnome-keyring MR !111",
    ):
        if required not in normalized_readme:
            fail(f"README missing required scope statement: {required}")

    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    if "LGPL-2.0-or-later" not in notice or "Stefan Walter" not in notice:
        fail("NOTICE lacks upstream attribution and patch license")

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "License allocation" not in license_text:
        fail("LICENSE lacks license allocation")
    lgpl = (ROOT / "LICENSES/LGPL-2.1-or-later.txt").read_text(encoding="utf-8")
    if "GNU LESSER GENERAL PUBLIC LICENSE" not in lgpl or "Version 2.1" not in lgpl:
        fail("LGPL text is missing or wrong version")
    mit = (ROOT / "LICENSES/MIT.txt").read_text(encoding="utf-8")
    if "MIT License" not in mit:
        fail("MIT license text is missing")

    patch = (ROOT / "patches/0001-escape-multiline-textual-secrets.patch").read_text(
        encoding="utf-8"
    )
    old = "-\t\t\tg_key_file_set_value (file, identifier, \"secret\", (gchar*)secret);"
    new = "+\t\t\tg_key_file_set_string (file, identifier, \"secret\", (gchar*)secret);"
    if patch.count(old) != 1 or patch.count(new) != 1:
        fail("patch does not contain exactly the intended production replacement")

    for relative in ("scripts/fetch-source.sh", "scripts/build-local-package.sh", "scripts/build.sh"):
        mode = (ROOT / relative).stat().st_mode
        if not mode & stat.S_IXUSR:
            fail(f"script is not owner-executable: {relative}")

    print("public_tree_contract=passed")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"public_tree_contract=failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
