# Security and privacy reporting

This repository distributes source patches and local build instructions only;
it does not operate a service or accept credential-bearing test data.

## Do not publish sensitive data

Never open a public issue or pull request containing a keyring, password,
token, cookie, private key, account identifier, raw D-Bus capture, package from
a personal system, or unredacted filesystem path. Use a synthetic reproduction
that demonstrates the issue without secret material.

## Reporting a repository-specific concern

After the public repository is created, use GitHub Private Vulnerability
Reporting if it has been enabled in the repository's Security settings. Until
then, do not send sensitive details through a public issue. A redacted public
issue that identifies only the affected file and impact is sufficient to start
a coordination channel.

For a vulnerability in GNOME Keyring itself, follow the upstream project's
current reporting guidance rather than treating this local backport repository
as the upstream security authority.
