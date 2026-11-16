# GNOME Keyring multiline textual-secret backport

**English (canonical)** | [日本語](README.ja.md)

English takes precedence if the translations differ.

**Why this exists:** affected GNOME Keyring versions can write an unreadable
keyring when an application stores a **multiline secret in a passwordless
keyring**. It may still work in the current session, then fail to load at the
next login or daemon start, making saved credentials appear to have disappeared.
This kit builds a narrowly patched Ubuntu package that escapes those values
correctly to prevent that corruption. **It does not repair an already damaged
keyring or recover missing credentials.**

> **Unofficial local backport kit for Ubuntu 24.04 and 26.04.** It is not affiliated with GNOME or Ubuntu, does not distribute binaries, and is not an official security update.

One repository maintains the shared patch, tests and build tooling; explicit
target profiles separate the Ubuntu source versions and build environments.
Build for your own system. Do not use a package built for a different Ubuntu
release or treat somebody else's build as a trusted release artifact.

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

## Targets and pinned inputs

| Target | Ubuntu | Source version | Local package version |
|---|---|---|---|
| `ubuntu24.04` | 24.04 / noble | `46.1-2ubuntu0.2` | `46.1-2ubuntu0.2+local1` |
| `ubuntu26.04` | 26.04 / resolute | `50.0-1` | `50.0-1ubuntu0.0+local1` |

Only **amd64** is qualified. An Ubuntu release's support lifetime does not mean
every later source revision is covered by this patch.

The [24.04 profile](targets/ubuntu24.04.json) and
[26.04 profile](targets/ubuntu26.04.json) are the authoritative lists of source
URLs, SHA-256 hashes, signer fingerprints, base-image digests and snapshot dates.
The shared fetch/build code verifies all three source hashes and the signed
`.dsc` using only the selected public signer key in a temporary keyring. It
repeats authentication on the copied build inputs before extraction.

Build inputs are pinned; **byte-for-byte reproducible output is not claimed**.
Targets have separate caches, work directories and output directories. Existing
packages are never overwritten and failed build directories are retained.

> The minimal base image has no CA certificate bundle. The Dockerfile disables
> HTTPS peer verification only for the first package-index update and
> installation of `ca-certificates`; APT signature verification remains active.
> All subsequent snapshot fetches use normal TLS verification.

## Rebuild and package test

Prerequisites: Linux, Python 3.10 or later, Docker with a working daemon, and
network access for image/dependency/source downloads. Run from the repository
root as your normal user; the package build runs as that user's UID/GID.

```sh
# Select the target explicitly; there is no default.
sh scripts/build.sh ubuntu24.04
sh scripts/build.sh ubuntu26.04
```

Each command builds its pinned container, authenticates the source, applies
the shared patch and runs `dpkg-buildpackage -b -uc -us -j4`, including the
distribution's package test suite and the added multiline round-trip test.
`nocheck` is rejected. The package-build container has no network, the checkout
is mounted read-only, and no desktop session bus or real keyring is mounted.
Nothing is installed on the host and no service is restarted.

Only the resulting `gnome-keyring` package is copied to `dist/<target>/`.
Other build outputs and logs remain under `.build/<target>/work/`.
Do not commit, publish or upload generated files. Inspect the package:

```sh
dpkg-deb -f dist/ubuntu26.04/gnome-keyring_50.0-1ubuntu0.0+local1_amd64.deb \
  Package Version Architecture
sha256sum dist/ubuntu26.04/*.deb
```

For a rebuild without overwriting an earlier package, use a new output directory:

```sh
sh scripts/build.sh ubuntu26.04 --dist-dir "$PWD/dist/ubuntu26.04-rerun"
```

The lower-level `scripts/fetch-source.sh` and `scripts/build-local-package.sh`
also require a target; their old no-argument invocation is no longer supported.
Use `python3 scripts/backport.py --help` for source/work/output path options.
The direct build command refuses a mismatched Ubuntu release or architecture.

## Tests and publication checks

The offline build-tool and bilingual-documentation tests require Python; the
version-order check additionally uses `dpkg` and is skipped when it is absent.
Run the publication check on a source-only tree, before creating `.build/` or
`dist/`; it deliberately rejects generated/private material even when ignored
by Git. CI runs this check before building both targets in a matrix; configured
CI is not a claim that a particular unpublished commit has passed hosted CI.

```sh
python3 -B tests/test-build-kit.py -v
python3 -B tests/verify-public-tree.py
```

The standalone C check uses a fixed non-secret multiline value. It requires a
C compiler and GLib development files, is independent of Secret Service, and
does not access a keyring. Run it in either matching builder:

```sh
# Expected RED: raw GKeyFile writing aborts on a reload attempt.
test_dir=$(mktemp -d)
ulimit -c 0
gcc -std=c11 -Wall -Wextra -Werror tests/test-keyfile-multiline-roundtrip.c \
  $(pkg-config --cflags --libs glib-2.0) -o "$test_dir/keyfile-test-raw"
"$test_dir/keyfile-test-raw"

# GREEN: the escaping writer round-trips the same value.
gcc -std=c11 -Wall -Wextra -Werror -DUSE_ESCAPING_WRITER \
  tests/test-keyfile-multiline-roundtrip.c \
  $(pkg-config --cflags --libs glib-2.0) -o "$test_dir/keyfile-test-escaped"
"$test_dir/keyfile-test-escaped"
```

The raw test is deliberately expected to fail. Run the escaped test only after
observing that RED result. These tests do not establish persistence across a
real desktop logout/login.

## Installation and rollback

Installation is deliberately manual. Preserve a private backup of your existing
keyrings first, inspect your package, and use **only the matching Ubuntu target**.
Example for Ubuntu 26.04:

```sh
sudo apt install ./dist/ubuntu26.04/gnome-keyring_50.0-1ubuntu0.0+local1_amd64.deb
```

Use a normal logout/login so the desktop session starts the installed daemon.
A user-service restart in an already running session is not equivalent to a
fresh desktop login and is not an appropriate persistence proof.

To return to Ubuntu's documented base version when it remains available
(this restores the affected writer, not damaged data):

```sh
sudo apt install --reinstall --allow-downgrades gnome-keyring=50.0-1
```

For 24.04, use its table entry and corresponding `dist/ubuntu24.04/` package.
The local versions sort above their base packages but below the next ordinary
Ubuntu security revisions (`46.1-2ubuntu0.3` and `50.0-1ubuntu0.1`, respectively).
These are ordering examples, not claims that those revisions are available.
The 26.04 `ubuntu0.0+local1` suffix deliberately avoids `50.0-1+local1`, which
would incorrectly outrank `50.0-1ubuntu0.1`. Not every possible official rebuild
necessarily sorts above a local suffix: inspect `apt-cache policy gnome-keyring`
and rebase when needed. An official update or OS upgrade can also replace the
fix with an affected version. **Recheck after package or distribution upgrades.**
Do not place the package on an indefinite hold and block security updates.
Before adding a source revision, check whether the official source already
contains the fix, then update the target pins and rerun the complete package
tests. Keep both maintained targets in the same reviewed change when shared
tooling or the patch changes. Existing corruption needs a separate recovery
procedure; do not delete a keyring merely because it is absent from the UI.

## Publication boundary

Never add keyring files, credentials, private keys, cookies, database dumps,
network captures, D-Bus logs, source download caches, build directories, or
package artifacts to this repository. The `.gitignore` excludes common local
outputs, and `tests/verify-public-tree.py` rejects unapproved files and personal
filesystem paths.

See [NOTICE](NOTICE) for upstream attribution and [LICENSE](LICENSE) for the
per-file license allocation. Contribution and reporting boundaries are in
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
