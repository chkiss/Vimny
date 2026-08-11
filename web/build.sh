#!/usr/bin/env bash
# Fetch everything the browser build serves, and build the Vimny wheel.
#
# Nothing here is committed: web/vendor/ is gitignored, because it is 20-odd MB
# of other people's release artifacts. Run this once after a clone, and again
# whenever Vimny's own version changes.
#
#   ./web/build.sh
#   ./web/serve.py          # then open http://localhost:8000
set -euo pipefail

PYODIDE_VERSION="314.0.4"
XTERM_VERSION="6.0.0"
FIT_VERSION="0.11.0"
DEJAVU_VERSION="2.37"
SYMBOLA_FILE="Symbola-13.otf"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/web/vendor"
WHEELS="$VENDOR/wheels"

mkdir -p "$VENDOR" "$WHEELS"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ── Pyodide ───────────────────────────────────────────────────────────────────
# `pyodide-core` is the cut-down bundle: interpreter, stdlib, and nothing else.
# The full one carries scipy and friends, none of which Vimny asks for.
if [ ! -f "$VENDOR/pyodide/pyodide.js" ]; then
  echo "→ pyodide $PYODIDE_VERSION"
  curl -fsSL -o "$TMP/pyodide.tar.bz2" \
    "https://github.com/pyodide/pyodide/releases/download/${PYODIDE_VERSION}/pyodide-core-${PYODIDE_VERSION}.tar.bz2"
  tar -xjf "$TMP/pyodide.tar.bz2" -C "$TMP"
  rm -rf "$VENDOR/pyodide"
  mv "$TMP/pyodide" "$VENDOR/pyodide"
else
  echo "→ pyodide $PYODIDE_VERSION (cached)"
fi

# ── xterm.js ──────────────────────────────────────────────────────────────────
# The terminal emulator. Vimny's shim emits ordinary ANSI, so this is what turns
# escape sequences back into a screen.
fetch_npm () {           # fetch_npm <package> <version> <file> <dest>
  local pkg="$1" ver="$2" file="$3" dest="$4"
  [ -f "$dest" ] && { echo "→ $pkg (cached)"; return; }
  echo "→ $pkg $ver"
  curl -fsSL -o "$TMP/pkg.tgz" "https://registry.npmjs.org/${pkg}/-/$(basename "$pkg")-${ver}.tgz"
  tar -xzf "$TMP/pkg.tgz" -C "$TMP"
  mkdir -p "$(dirname "$dest")"
  cp "$TMP/package/$file" "$dest"
  rm -rf "$TMP/package"
}

fetch_npm "@xterm/xterm"      "$XTERM_VERSION" "lib/xterm.js"          "$VENDOR/xterm/xterm.js"
fetch_npm "@xterm/xterm"      "$XTERM_VERSION" "css/xterm.css"         "$VENDOR/xterm/xterm.css"
fetch_npm "@xterm/addon-fit"  "$FIT_VERSION"   "lib/addon-fit.js"      "$VENDOR/xterm/addon-fit.js"

# ── Fonts ─────────────────────────────────────────────────────────────────────
# Vimny's dungeons are built out of runes from the chess, card, dice, planetary
# and alchemical blocks. A terminal player has a font they chose; a visitor gets
# whatever their browser calls "monospace", which mostly does not cover those.
# So subset the three faces it takes to cover the game and ship them.
FONTS="$VENDOR/fonts"
FONT_SRC="$VENDOR/font-src"
if [ ! -f "$FONTS/fonts.css" ]; then
  mkdir -p "$FONT_SRC"
  echo "→ dejavu $DEJAVU_VERSION"
  curl -fsSL -o "$TMP/dejavu.zip" \
    "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_${DEJAVU_VERSION//./_}/dejavu-fonts-ttf-${DEJAVU_VERSION}.zip"
  unzip -qo "$TMP/dejavu.zip" -d "$TMP"
  cp "$TMP/dejavu-fonts-ttf-${DEJAVU_VERSION}/ttf/DejaVuSansMono.ttf" \
     "$TMP/dejavu-fonts-ttf-${DEJAVU_VERSION}/ttf/DejaVuSans.ttf" "$FONT_SRC/"

  echo "→ symbola $SYMBOLA_FILE"
  curl -fsSL -o "$FONT_SRC/Symbola.otf" \
    "https://github.com/ChiefMikeK/ttf-symbola/raw/master/$SYMBOLA_FILE"

  echo "→ subsetting"
  python3 "$ROOT/web/subset_fonts.py" "$FONT_SRC" "$FONTS"
  rm -rf "$FONT_SRC"          # 12 MB of sources for ~40 KB of output
else
  echo "→ fonts (cached)"
fi

# ── Wheels ────────────────────────────────────────────────────────────────────
# Vimny itself, plus wcwidth (pure Python, and the only thing the shim's
# `length()` wants). blessed is NOT here: it imports termios, which is why the
# shim exists.
echo "→ vimny wheel"
rm -f "$WHEELS"/*.whl
( cd "$ROOT" && rm -rf build *.egg-info && python3 -m build --wheel --outdir "$WHEELS" >/dev/null )

echo "→ wcwidth wheel"
python3 -m pip download wcwidth --no-deps --only-binary=:all: -q -d "$WHEELS"

# The `build` id is what the service worker keys its cache on: a new one throws
# the old cache away wholesale, so a rebuild can never leave a visitor running
# yesterday's boot.py against today's wheel.
cat > "$VENDOR/manifest.json" <<EOF
{
  "pyodide": "$PYODIDE_VERSION",
  "xterm": "$XTERM_VERSION",
  "build": "$(date -u +%Y%m%dT%H%M%SZ)",
  "wheels": [$(cd "$WHEELS" && ls *.whl | sed 's/.*/"&"/' | paste -sd,)]
}
EOF

echo
echo "Vendored into web/vendor:"
du -sh "$VENDOR"/* | sed 's/^/  /'
echo
echo "Now run:  ./web/serve.py"
