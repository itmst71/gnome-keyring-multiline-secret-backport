# SPDX-License-Identifier: MIT
# Shared disposable builder. scripts/build.sh supplies the selected target pins.
ARG BASE_IMAGE=ubuntu@sha256:1e0a86e57d247923571b75e0aaf48a1449cf8c543d51fb3e07a4a7d7bfa79316
FROM ${BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG UBUNTU_SNAPSHOT=20260828T000000Z
ARG SUITE=noble

RUN rm -f /etc/apt/sources.list.d/* \
 && printf '%s\n' \
      "deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}/ ${SUITE} main universe" \
      "deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}/ ${SUITE}-updates main universe" \
      > /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false \
      -o Acquire::https::Verify-Peer=false \
      -o Acquire::https::Verify-Host=false update \
 && apt-get -o Acquire::Check-Valid-Until=false \
      -o Acquire::https::Verify-Peer=false \
      -o Acquire::https::Verify-Host=false \
      install -y --no-install-recommends ca-certificates \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      curl \
      dbus \
      debhelper \
      dh-sequence-gnome \
      docbook-xml \
      docbook-xsl \
      fakeroot \
      gnupg \
      ubuntu-keyring \
      libgck-1-dev \
      libgcr-3-dev \
      libgcrypt20-dev \
      libglib2.0-dev \
      libglib2.0-doc \
      libp11-kit-dev \
      libpam0g-dev \
      libselinux1-dev \
      libsystemd-dev \
      libtasn1-6-dev \
      libtasn1-bin \
      meson \
      openssh-client \
      python3 \
      systemd-dev \
      xsltproc \
 && rm -rf /var/lib/apt/lists/*

# D-Bus requires an NSS entry, not just Docker's numeric --user mapping.
# Add only missing container-local identities; never mount host account files.
ARG BUILD_UID=1000
ARG BUILD_GID=1000
RUN case "$BUILD_UID" in ''|*[!0-9]*) exit 1;; esac \
 && case "$BUILD_GID" in ''|*[!0-9]*) exit 1;; esac \
 && { getent group "$BUILD_GID" >/dev/null \
      || printf 'backport-builder-%s:x:%s:\n' "$BUILD_GID" "$BUILD_GID" >> /etc/group; } \
 && { getent passwd "$BUILD_UID" >/dev/null \
      || printf 'backport-builder-%s:x:%s:%s:Local build user:/build/home:/bin/false\n' \
           "$BUILD_UID" "$BUILD_UID" "$BUILD_GID" >> /etc/passwd; } \
 && getent passwd "$BUILD_UID" >/dev/null \
 && getent group "$BUILD_GID" >/dev/null

WORKDIR /work
