#!/bin/sh
# SPDX-License-Identifier: MIT
# Build and test the local backport from already authenticated source archives.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir=${SOURCE_DIR:-"$root/.build/source"}
work=${WORK_DIR:-"$root/.build/work"}

for file in \
  gnome-keyring_46.1.orig.tar.xz \
  gnome-keyring_46.1-2ubuntu0.2.debian.tar.xz \
  gnome-keyring_46.1-2ubuntu0.2.dsc
do
  test -f "$source_dir/$file" || {
    printf '%s\n' "missing authenticated source input: $source_dir/$file" >&2
    exit 1
  }
done

rm -rf "$work"
mkdir -p "$work"
cp "$source_dir"/gnome-keyring_46.1* "$work/"
cd "$work"

cat <<'CHECKSUMS' | sha256sum --check --strict
b1d3ae9132ff2f8b3f25a190790892968e3d0acf952a487e40f644a8550ce3f6  gnome-keyring_46.1.orig.tar.xz
8ba42f582bbad08b90161325da3cc60d6962929d9c9c9e8d25742d5e1806c171  gnome-keyring_46.1-2ubuntu0.2.debian.tar.xz
4478823a8403d4aa41861a706596ea2dbeb8b1144efdc5880349d80a6844c1de  gnome-keyring_46.1-2ubuntu0.2.dsc
CHECKSUMS

dpkg-source -x gnome-keyring_46.1-2ubuntu0.2.dsc build
install -m 0644 "$root/patches/0001-escape-multiline-textual-secrets.patch" \
  build/debian/patches/0008-secret-textual-escape-multiline-secrets.patch
printf '%s\n' '0008-secret-textual-escape-multiline-secrets.patch' >> build/debian/patches/series

cd build
python3 - <<'PY'
from pathlib import Path
p = Path("debian/changelog")
old = p.read_text(encoding="utf-8")
entry = """gnome-keyring (46.1-2ubuntu0.2+local1) noble; urgency=medium

  * d/p: Escape multiline textual secrets in passwordless keyrings.
    Local backport of GNOME MR !111.

 -- Local GNOME Keyring Backport <noreply@invalid>  Fri, 28 Aug 2026 00:00:00 +0000

"""
p.write_text(entry + old, encoding="utf-8")
PY
DEB_BUILD_OPTIONS=${DEB_BUILD_OPTIONS:-} dpkg-buildpackage -b -uc -us

mkdir -p "$root/dist"
rm -f "$root/dist"/*.deb
mv ../gnome-keyring_46.1-2ubuntu0.2+local1_*.deb "$root/dist/"
dpkg-deb -f "$root/dist/gnome-keyring_46.1-2ubuntu0.2+local1_amd64.deb" \
  Package Version Architecture
sha256sum "$root/dist"/*.deb
