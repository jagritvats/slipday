#!/bin/sh
# Downloads the official LOLA files Slipday uses and builds data/dem/ from them.
# This is now a thin wrapper: scripts/fetch_on_your_machine.sh downloads everything into data/reference/
# (the folder scripts/prepare_dem.py and LOCAL_PASS.md use; an earlier version of this script saved into
# lola_nasa/ instead, which did not match the instructions).  Run from the repository root.
set -u
sh scripts/fetch_on_your_machine.sh || exit 1
python3 scripts/prepare_dem.py data/reference
