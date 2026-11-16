#!/bin/sh
# SPDX-License-Identifier: MIT
# Fetch and authenticate the explicitly selected target. No default target.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 -B "$root/scripts/backport.py" fetch "$@"
