# GNOME Keyring multiline textual-secret backport

> **Unofficial local backport kit for Ubuntu 24.04.** It is not affiliated with GNOME or Ubuntu, does not distribute binaries, and is not an official security update.

This repository documents and rebuilds a narrowly scoped patch for the Ubuntu
`gnome-keyring` source version `46.1-2ubuntu0.2`. It is intended for local,
operator-controlled builds only. Verify the exact source package and build a
package for your own system; do not treat a package built by somebody else as a
trusted release artifact.

## Scope

The affected UTF-8 textual-secret writer used `g_key_file_set_value()`. Newline
characters were therefore emitted as an invalid GKeyFile value, which could
make a textual keyring fail to load at a later daemon start.

[`patches/0001-escape-multiline-textual-secrets.patch`](patches/0001-escape-multiline-textual-secrets.patch)
is equivalent in behavior to [GNOME gnome-keyring MR !111](https://gitlab.gnome.org/GNOME/gnome-keyring/-/merge_requests/111):

- replace the UTF-8 writer's `g_key_file_set_value()` call with
  `g_key_file_set_string()`;
- add GNOME's focused multiline write/reload/read regression coverage.

The only production runtime logic change is that API replacement. The patch
also registers the upstream-style regression test; it does not change the
binary-secret path, Secret Service protocol, keyring encryption, or daemon
startup/unlock behavior.

This repository intentionally contains no owner-local D-Bus or Secret Service
integration helper. Its synthetic GLib test proves serialization semantics only;
it is not evidence about any particular user's keyring or session persistence.

## Pinned inputs

| Input | Value |
|---|---|
| Ubuntu source version | `46.1-2ubuntu0.2` |
| Original source SHA-256 | `b1d3ae9132ff2f8b3f25a190790892968e3d0acf952a487e40f644a8550ce3f6` |
| Debian delta SHA-256 | `8ba42f582bbad08b90161325da3cc60d6962929d9c9c9e8d25742d5e1806c171` |
| Signed `.dsc` SHA-256 | `4478823a8403d4aa41861a706596ea2dbeb8b1144efdc5880349d80a6844c1de` |
| Source signer fingerprint | `BC27F8FEF77F7207A7BA08BE0D0246F38220EDA6` |
| Docker base image | `ubuntu@sha256:1e0a86e57d247923571b75e0aaf48a1449cf8c543d51fb3e07a4a7d7bfa79316` |
| Ubuntu snapshot | `20260828T000000Z` |

`scripts/fetch-source.sh` downloads only over HTTPS, verifies all three hashes,
and validates the signed Debian source control file with the pinned public
source-signer key. The Docker image uses a digest-pinned base and a timestamped
Ubuntu snapshot rather than a floating image tag or live package indices.

> The minimal base image has no CA certificate bundle. The Dockerfile disables
> HTTPS peer verification only for the first package-index update and
> installation of `ca-certificates`; APT signature verification remains active.
> All subsequent snapshot fetches use normal TLS verification.

## Rebuild and package test

These commands require Docker access. They create a neutral local package with
version suffix `+local1` but do **not** install it.

```sh
# Build the disposable, pinned Ubuntu builder.
docker build --pull --no-cache \
  -t gnome-keyring-local-builder:ubuntu24.04 \
  container

# Fetch and authenticate the exact Ubuntu source package inputs.
docker run --rm \
  -v "$PWD:/work:rw" -w /work \
  gnome-keyring-local-builder:ubuntu24.04 \
  sh scripts/fetch-source.sh

# Apply the patch and run Debian's package test suite.
docker run --rm \
  -v "$PWD:/work:rw" -w /work \
  --user "$(id -u):$(id -g)" \
  gnome-keyring-local-builder:ubuntu24.04 \
  sh scripts/build-local-package.sh
```

The build script runs `dpkg-buildpackage -b -uc -us`; do not use a package
built with `DEB_BUILD_OPTIONS=nocheck`. It writes locally generated packages to
an ignored `dist/` directory. Do not commit, publish, or upload those files.
Inspect the locally generated package before using it:

```sh
dpkg-deb -f dist/gnome-keyring_46.1-2ubuntu0.2+local1_amd64.deb \
  Package Version Architecture
sha256sum dist/*.deb
```

## Synthetic regression check

The included check uses a fixed non-secret multiline value. It is independent
of Secret Service and does not access a keyring.

```sh
# Expected RED: raw GKeyFile writing aborts on a reload attempt.
gcc -std=c11 -Wall -Wextra -Werror tests/test-keyfile-multiline-roundtrip.c \
  $(pkg-config --cflags --libs glib-2.0) -o /tmp/keyfile-test-raw
/tmp/keyfile-test-raw

# GREEN: the escaping writer round-trips the same value.
gcc -std=c11 -Wall -Wextra -Werror -DUSE_ESCAPING_WRITER \
  tests/test-keyfile-multiline-roundtrip.c \
  $(pkg-config --cflags --libs glib-2.0) -o /tmp/keyfile-test-escaped
/tmp/keyfile-test-escaped

# Assert that this repository remains a minimal, safe publication tree.
python3 tests/verify-public-tree.py
```

The first command is deliberately expected to fail. Run the second and third
commands only after observing that RED result.

## Installation and rollback

Installation is deliberately manual and outside this repository's support
scope. On a compatible Ubuntu system, after inspecting your local package:

```sh
sudo dpkg -i dist/gnome-keyring_46.1-2ubuntu0.2+local1_amd64.deb
```

Use a normal logout/login so the desktop session starts the installed daemon.
A user-service restart in an already running session is not equivalent to a
fresh desktop login and is not an appropriate persistence proof.

To return to Ubuntu's documented base version when it remains available:

```sh
sudo apt install --reinstall --allow-downgrades gnome-keyring=46.1-2ubuntu0.2
```

A later official Ubuntu revision such as `46.1-2ubuntu0.3` sorts above the
local `+local1` package and can replace it through normal APT upgrade. Do not
place the package on hold. Before applying this patch to another Ubuntu source
revision, confirm that the official source has not already adopted the fix and
re-run the complete package test suite.

## Publication boundary

Never add keyring files, credentials, private keys, cookies, database dumps,
network captures, D-Bus logs, source download caches, build directories, or
package artifacts to this repository. The `.gitignore` excludes common local
outputs, and `tests/verify-public-tree.py` rejects unapproved files and personal
filesystem paths.

See [NOTICE](NOTICE) for upstream attribution and [LICENSE](LICENSE) for the
per-file license allocation. Contribution and reporting boundaries are in
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
