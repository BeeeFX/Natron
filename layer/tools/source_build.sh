#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of the layer of this Natron fork (see FORK.md at the repository root).
#
# Builds Natron from this checkout with Niik-l's own build scripts (tools/win-build), run unchanged except for
# where MSYS2 lives and how many jobs at once. See layer/README.md, "Building from source".
#
# Run inside the MSYS2 MINGW64 shell of the MSYS2 that holds the packages (layer/tools/msys2_snapshot.py):
#
#   MSYS2_ROOT=/c/Users/<you>/.singerie/tools/natron-build/msys64 \
#   NATRON_ROOT=/c/Users/<you>/.singerie/tools/natron-build JOBS=4 \
#   bash layer/tools/source_build.sh [phase ...]   # default: 02-patch fixes 03-cycles 04-natron 05-plugins 06-install strip
#
# NATRON_ROOT is the folder holding this checkout as Natron/ and its siblings (cycles/, openfx-misc/, openfx-io/,
# openfx-arena/, natron-plugins/, wgpu/), cloned at the refs of tools/win-build/config.sh. Phases 00 (pacman -Syu and
# the newest packages) and 01 (clone) are left out on purpose: the packages come from the dated snapshot instead.
set -euo pipefail
: "${MSYS2_ROOT:?set MSYS2_ROOT to the MSYS2 folder (Unix form, e.g. /c/.../msys64)}"
: "${NATRON_ROOT:?set NATRON_ROOT to the folder holding Natron/ and its siblings}"
JOBS="${JOBS:-4}"
SRC="$NATRON_ROOT/Natron/tools/win-build"
RUN="$NATRON_ROOT/win-build-run"
[ -f "$SRC/build-all.sh" ] || { echo "no $SRC/build-all.sh"; exit 1; }
[ -x "$MSYS2_ROOT/mingw64/bin/gcc.exe" ] || { echo "no gcc in $MSYS2_ROOT/mingw64/bin"; exit 1; }

WIN_ROOT="$(cygpath -m "$MSYS2_ROOT")"   # e.g. C:/Users/<you>/.../msys64
rm -rf "$RUN"; mkdir -p "$RUN"
cp -r "$SRC/." "$RUN/"
# Niik-l's scripts name MSYS2's default folder; point them at this one. Nothing else in them changes.
sed -i -e "s#/c/msys64#${MSYS2_ROOT}#g" -e "s#C:/msys64#${WIN_ROOT}#g" "$RUN"/*.sh
sed -i -e "s#^JOBS=.*#JOBS=\"${JOBS}\"#" -e "s#^NATRON_JOBS=.*#NATRON_JOBS=\"${JOBS}\"#" "$RUN/config.sh"
export NATRON_ROOT

# "strip" (ours, after 06-install): the staged programs and plug-ins without their debug information, as BUILDING.md
# advises for handing a build on (Natron.exe goes from about 1.9 GB to the size of Niik-l's release); the copies in
# Natron/build-qt6 keep theirs for crash backtraces.
strip_install() {
  local I="$NATRON_ROOT/Natron-install"
  "$MSYS2_ROOT/mingw64/bin/strip.exe" --strip-debug "$I/App/Natron.exe" "$I/Renderer/NatronRenderer.exe" \
    "$I"/Plugins/OFX/Natron/*.ofx.bundle/Contents/Win64/*.ofx
  ls -la "$I/App/Natron.exe" "$I/Renderer/NatronRenderer.exe"
}

# "fixes" (ours, after 02-patch): build fixes for the dated MSYS2 packages that are newer than Niik-l's PC had
# (layer/patches/fixes/<repository>-<what>.patch, applied in the sibling repository the name starts with; skipped
# when already applied). Not core patches: they touch the plug-ins' sources, not Natron's.
apply_fixes() {
  local fix repo
  for fix in "$NATRON_ROOT"/Natron/layer/patches/fixes/*.patch; do
    [ -f "$fix" ] || continue
    case "$(basename "$fix")" in openfx-io-*) repo=openfx-io ;; openfx-misc-*) repo=openfx-misc ;;
      openfx-arena-*) repo=openfx-arena ;; cycles-*) repo=cycles ;;
      *) echo "which repository is $(basename "$fix") for?"; return 1 ;; esac
    if git -C "$NATRON_ROOT/$repo" apply --reverse --check "$fix" 2>/dev/null; then
      echo "$repo: $(basename "$fix") already applied"
    else
      git -C "$NATRON_ROOT/$repo" apply "$fix" && echo "$repo: applied $(basename "$fix")"
    fi
  done
}

# Niik-l's 07-verify is left out of the default: it starts NatronRenderer with the PC user's own home and Natron
# settings (Natron records switches in the registry for every PyPlug it loads); the layer's smoke test checks the
# packaged build instead, with a throwaway home and the settings compared before and after.
phases=("$@")
[ ${#phases[@]} -gt 0 ] || phases=(02-patch fixes 03-cycles 04-natron 05-plugins 06-install strip)
mkdir -p "$NATRON_ROOT/logs"
for ph in "${phases[@]}"; do
  start=$(date +%s)
  echo "==== $ph ($(date +%H:%M:%S))"
  if [ "$ph" = strip ]; then
    strip_install > "$NATRON_ROOT/logs/strip.log" 2>&1 || { echo "FAILED: strip"; cat "$NATRON_ROOT/logs/strip.log"; exit 1; }
  elif [ "$ph" = fixes ]; then
    apply_fixes > "$NATRON_ROOT/logs/fixes.log" 2>&1 || { echo "FAILED: fixes"; cat "$NATRON_ROOT/logs/fixes.log"; exit 1; }
  else
    bash "$RUN/$ph.sh" > "$NATRON_ROOT/logs/$ph.log" 2>&1 || { echo "FAILED: $ph, see $NATRON_ROOT/logs/$ph.log"; tail -30 "$NATRON_ROOT/logs/$ph.log"; exit 1; }
  fi
  echo "==== $ph done in $(( $(date +%s) - start ))s"
done
