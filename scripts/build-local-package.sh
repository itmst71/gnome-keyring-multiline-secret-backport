#!/bin/sh
# SPDX-License-Identifier: MIT
# Run inside the matching Ubuntu builder; tests cannot be disabled.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 -B "$root/scripts/backport.py" build "$@"
