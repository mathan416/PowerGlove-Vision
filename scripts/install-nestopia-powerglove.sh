#!/usr/bin/env bash
# Build and install the separately named evidence-gated Nestopia core on RetroPie.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
destination=${1:-"$root/build/nestopia-powerglove-retropie"}
target=/opt/retropie/libretrocores/lr-nestopia-powerglove

if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' "Run this installer with sudo on the RetroPie cabinet." >&2
  exit 1
fi

core=$("$root/scripts/build-nestopia-powerglove.sh" "$destination")
case "$core" in
  *.so) ;;
  *) printf '%s\n' "The native core must be built on the Linux RetroPie host." >&2; exit 1 ;;
esac
install -d -m 0755 "$target"
install -m 0644 "$core" "$target/nestopia_powerglove_libretro.so"
install -m 0644 "$destination/source/COPYING" "$target/COPYING"
install -m 0644 "$root/native/nestopia-powerglove/README.md" "$target/README.md"
printf '%s\n' "Installed $target/nestopia_powerglove_libretro.so"
printf '%s\n' "Use configure-super-glove-ball-core.py to opt one ROM into native mode or restore FCEUmm."
