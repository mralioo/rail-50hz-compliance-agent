#!/usr/bin/env bash
# One-time setup for Craftsman's live FreeCAD GUI mode (docs/CRAFTSMAN_AGENT.md).
# `pixi install` alone isn't enough - two gaps in the conda-forge xpra/Xvfb
# packages need fixing up by hand, both confirmed hands-on:
#
# 1. conda-forge's `xorg-xvfb-server` package installs its xkeyboard-config
#    data under share/xkeyboard-config-2/ instead of the share/X11/xkb/
#    layout Xvfb actually looks for at runtime (a file-collision "clobber"
#    with another package's partial share/X11/xkb/ - only Xvfb's own
#    `compiled` cache dir survives there, the real keycodes/symbols/rules/
#    etc are missing) - Xvfb fails immediately with "Keyboard initialization
#    failed" until these are symlinked into place.
# 2. conda-forge's `xpra` package ships the server only, not the HTML5
#    client (`--html=on` 404s on every path with no bundled www/ dir) -
#    the client is a separate, non-packaged repo that has to be vendored.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> pixi install (xpra + Xvfb + xkeyboard-config, no sudo required)"
pixi install

ENV_DIR=".pixi/envs/default"
XKB_SRC="$ENV_DIR/share/xkeyboard-config-2"
XKB_DST="$ENV_DIR/share/X11/xkb"

echo "==> fixing Xvfb's xkeyboard-config path"
mkdir -p "$XKB_DST"
for d in compat geometry keycodes rules symbols types; do
  if [ -e "$XKB_SRC/$d" ] && [ ! -e "$XKB_DST/$d" ]; then
    ln -s "../../xkeyboard-config-2/$d" "$XKB_DST/$d"
    echo "   linked $d"
  fi
done

WWW_DIR="$ENV_DIR/share/xpra/www"
if [ ! -f "$WWW_DIR/connect.html" ]; then
  echo "==> vendoring the xpra-html5 client (not on conda-forge)"
  TMP_CLONE="$(mktemp -d)"
  git clone --depth 1 https://github.com/Xpra-org/xpra-html5.git "$TMP_CLONE"
  mkdir -p "$WWW_DIR"
  cp -r "$TMP_CLONE/html5/." "$WWW_DIR/"
  rm -rf "$TMP_CLONE"
else
  echo "==> xpra-html5 client already present, skipping"
fi

echo "==> done. XPRA_PATH=$(pwd)/$ENV_DIR/bin/xpra"
