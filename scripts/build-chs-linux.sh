#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
workspace_dir="$(cd -- "$repo_dir/../.." && pwd)"

source "$workspace_dir/build-env.sh"

# The workspace devkitPro portlibs contain png.h.  Debian's runtime libpng is
# sufficient for the host-side graphics tools even when libpng-dev is absent.
host_lib_dir="$repo_dir/.local/host-libs/lib"
mkdir -p "$host_lib_dir"
if [[ ! -e "$host_lib_dir/libpng.so" ]]; then
    libpng_runtime="$(ldconfig -p 2>/dev/null | awk '/libpng16\.so\.16 / { print $NF; exit }')"
    if [[ -z "$libpng_runtime" || ! -e "$libpng_runtime" ]]; then
        echo "libpng16 runtime not found; install libpng16/libpng-dev first" >&2
        exit 1
    fi
    ln -s "$libpng_runtime" "$host_lib_dir/libpng.so"
fi

export CPATH="$DEVKITPRO/portlibs/armv4t/include${CPATH:+:$CPATH}"
export LIBRARY_PATH="$host_lib_dir${LIBRARY_PATH:+:$LIBRARY_PATH}"

make -C "$repo_dir" -j"$(nproc)" modern
