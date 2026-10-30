#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
#
# Installs exactly the MSYS2 packages of a lock file written by msys2_snapshot.py (the MINGW64 packages as they
# stood on a release's day), from the folder they were downloaded to. Run inside that MSYS2's shell:
#
#   bash layer/tools/msys2_install.sh <lock file> <package folder>
#
# Each package's SHA-256 is checked against the lock file, and pacman checks its signature against MSYS2's keys when
# pacman.conf says LocalFileSigLevel = Required (layer/README.md, "Building from source"). pacman answers "skip" by
# itself (--noconfirm) when a package's dependency is missing, so every package is checked afterwards: the script
# fails if one wasn't installed.
set -euo pipefail
LOCK="${1:?lock file}"
CACHE="${2:?package folder}"
files=()
while read -r name ver sum file; do
  case "$name" in \#*|"") continue ;; esac
  echo "$sum  $CACHE/$file" | sha256sum -c --quiet - || { echo "checksum mismatch: $file"; exit 1; }
  pacman -Q "$name" 2>/dev/null | grep -qx "$name $ver" || files+=("$CACHE/$file")
done < "$LOCK"
echo "${#files[@]} packages to install"
[ ${#files[@]} -eq 0 ] || pacman -U --noconfirm "${files[@]}"
missing=0
while read -r name ver sum file; do
  case "$name" in \#*|"") continue ;; esac
  pacman -Q "$name" 2>/dev/null | grep -qx "$name $ver" || { echo "NOT INSTALLED: $name $ver"; missing=1; }
done < "$LOCK"
[ "$missing" = 0 ] && echo "every package of $(basename "$LOCK") is installed"
exit "$missing"
