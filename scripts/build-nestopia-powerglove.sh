#!/usr/bin/env bash
# Build the isolated evidence-gated Nestopia PowerGlove research core.
set -eu

revision=5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
destination=${1:-"$root/build/nestopia-powerglove"}
source_dir="$destination/source"

mkdir -p "$destination"
if [ ! -d "$source_dir/.git" ]; then
  git clone https://github.com/libretro/nestopia.git "$source_dir"
fi
if ! git -C "$source_dir" cat-file -e "$revision^{commit}" 2>/dev/null; then
  git -C "$source_dir" fetch --depth 1 origin "$revision"
fi
if git -C "$source_dir" apply --reverse --check "$root/native/nestopia-powerglove/nestopia-powerglove.patch" 2>/dev/null; then
  git -C "$source_dir" apply --reverse "$root/native/nestopia-powerglove/nestopia-powerglove.patch"
fi
if ! git -C "$source_dir" diff --quiet || ! git -C "$source_dir" diff --cached --quiet; then
  printf '%s\n' "The isolated Nestopia source has unrelated tracked changes; use a new build directory." >&2
  exit 1
fi
git -C "$source_dir" checkout --detach "$revision"
git -C "$source_dir" apply --check "$root/native/nestopia-powerglove/nestopia-powerglove.patch"
git -C "$source_dir" apply "$root/native/nestopia-powerglove/nestopia-powerglove.patch"
make -C "$source_dir/libretro" -j"${JOBS:-2}" >&2

core=$(find "$source_dir/libretro" -maxdepth 1 -type f \( -name 'nestopia_libretro.so' -o -name 'nestopia_libretro.dylib' \) -print | head -n 1)
test -n "$core"
cp "$core" "$destination/nestopia_powerglove_libretro.${core##*.}"
printf '%s\n' "$destination/nestopia_powerglove_libretro.${core##*.}"
