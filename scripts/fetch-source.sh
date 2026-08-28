#!/bin/sh
# SPDX-License-Identifier: MIT
# Fetch and authenticate precisely the Ubuntu source package this backport targets.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out=${1:-"$root/.build/source"}
base=https://launchpad.net/ubuntu/+archive/primary/+files
mkdir -p "$out"
cd "$out"

for file in \
  gnome-keyring_46.1.orig.tar.xz \
  gnome-keyring_46.1-2ubuntu0.2.debian.tar.xz \
  gnome-keyring_46.1-2ubuntu0.2.dsc
do
  curl --fail --location --proto '=https' --tlsv1.2 --remote-name "$base/$file"
done

cat <<'CHECKSUMS' | sha256sum --check --strict
b1d3ae9132ff2f8b3f25a190790892968e3d0acf952a487e40f644a8550ce3f6  gnome-keyring_46.1.orig.tar.xz
8ba42f582bbad08b90161325da3cc60d6962929d9c9c9e8d25742d5e1806c171  gnome-keyring_46.1-2ubuntu0.2.debian.tar.xz
4478823a8403d4aa41861a706596ea2dbeb8b1144efdc5880349d80a6844c1de  gnome-keyring_46.1-2ubuntu0.2.dsc
CHECKSUMS

key="$root/keys/gnome-keyring-46.1-source-signer.asc"
expected_fpr=BC27F8FEF77F7207A7BA08BE0D0246F38220EDA6
actual_fpr=$(gpg --batch --show-keys --with-colons "$key" | awk -F: '$1 == "fpr" { print $10; exit }')
[ "$actual_fpr" = "$expected_fpr" ] || {
  printf '%s\n' "unexpected source signer fingerprint: $actual_fpr" >&2
  exit 1
}
gpg --batch --yes --dearmor --output "$out/source-signer.gpg" "$key"
gpgv --keyring "$out/source-signer.gpg" "$out/gnome-keyring_46.1-2ubuntu0.2.dsc"
