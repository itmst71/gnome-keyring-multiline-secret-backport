# Contributing

This repository is intentionally narrow: one shared local backport with explicit
Ubuntu source targets, pinned source verification/build steps, and
synthetic regression checks. It is not a general GNOME Keyring fork or a
binary-package distribution channel.

## Before opening an issue or pull request

- Do not include keyrings, passwords, tokens, cookies, private keys, account
  identifiers, package artifacts built on a personal system, or private logs.
  Use a synthetic fixture and redact paths and hostnames.
- Check whether the reported Ubuntu source revision already includes the
  upstream fix.
- Describe the exact source version, the deterministic reproduction or build
  failure, and the check you ran.
- For non-trivial changes, open an issue first and wait for a maintainer to
  confirm the problem and scope. Scope confirmation is not a promise to merge.

Small documentation corrections and broken links may be submitted directly.
Maintainer-owned work may use direct commits and is not required to follow the
external issue-first process.

## Pull-request expectations

A proposed change should be small, independently reviewable, and include:

1. a focused test that was observed failing before the change and passing after;
2. the command output or other reproducible evidence actually obtained;
3. an explicit statement of what was not tested;
4. a negative scan confirming that no secrets, private data, or machine-local
   paths are included.

Keep `README.md` canonical in English and update the full Japanese translation
in `README.ja.md` in the same change. Explain the problem and the limits before
the build details; preserve identical commands and target versions in both files.
Shared tooling/patch changes must pass builds for both maintained targets. New
source revisions require new reviewed source hashes, signer verification and
matching Ubuntu build-environment pins; do not silently float a target.

Review, merge, support, and release timing are best-effort. This project may
reject changes that expand the target source scope, introduce networked runtime
behavior, or weaken its publication boundary.
