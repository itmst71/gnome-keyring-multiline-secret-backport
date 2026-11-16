#!/bin/sh
# SPDX-License-Identifier: MIT
# Build the selected target in Docker; never install the resulting package.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 -B "$root/scripts/backport.py" container "$@"
