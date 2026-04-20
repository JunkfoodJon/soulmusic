#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  build_installer_linux.sh  —  Full SoulMusic Linux release build
#
#  Steps
#    1. Verify prerequisites (Python ≥ 3.10, pip, PyInstaller)
#    2. Optionally install Qt xcb runtime dependencies (Debian/Ubuntu/Fedora)
#    3. Clean previous build artefacts
#    4. Run PyInstaller  →  dist/SoulMusic/
#    5. Create a portable .tar.gz archive  →  dist/SoulMusic-linux-x86_64.tar.gz
#
#  Usage:
#    chmod +x build_installer_linux.sh
#    ./build_installer_linux.sh [--skip-deps] [--arch arm64]
#
#  Run from the repository root directory.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="SoulMusic"
SPEC_FILE="SoulMusic-linux.spec"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"
ARCHIVE_NAME="SoulMusic-linux-$(uname -m).tar.gz"
SKIP_DEPS=false
ARCH="$(uname -m)"

# ── Parse args ─────────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --skip-deps)  SKIP_DEPS=true ;;
        --arch=*)     ARCH="${arg#--arch=}" ;;
    esac
done

# ── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'
step()  { echo -e "\n${CYAN}[${APP_NAME}] $*${RESET}"; }
ok()    { echo -e "  ${GREEN}[OK]  $*${RESET}"; }
fail()  { echo -e "  ${RED}[ERR] $*${RESET}"; exit 1; }

# ── 1. Prerequisites ────────────────────────────────────────────────────────
step "Checking prerequisites"

# Python
if ! command -v python3 &>/dev/null; then
    fail "python3 not found. Install with: sudo apt-get install python3  OR  sudo dnf install python3"
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10) ]]; then
    fail "Python $PY_VER detected. SoulMusic requires Python ≥ 3.10."
fi
ok "Python $PY_VER"

# pip
if ! python3 -m pip --version &>/dev/null; then
    fail "pip not found. Install with: python3 -m ensurepip --upgrade"
fi
ok "pip OK"

# PyInstaller
if ! python3 -m PyInstaller --version &>/dev/null; then
    step "Installing PyInstaller"
    python3 -m pip install --quiet pyinstaller || fail "PyInstaller install failed."
fi
ok "PyInstaller $(python3 -m PyInstaller --version)"

# ── 2. System Qt dependencies (Debian/Ubuntu/Fedora) ───────────────────────
if [[ "$SKIP_DEPS" == false ]]; then
    step "Checking Qt runtime libraries"
    if command -v apt-get &>/dev/null; then
        QT_PKGS=(
            libxcb-icccm4 libxcb-image0 libxcb-keysyms1
            libxcb-randr0 libxcb-render-util0 libxcb-xinerama0
            libxcb-xkb1 libxkbcommon-x11-0 libegl1 libgl1-mesa-glx
            libdbus-1-3 libglib2.0-0
        )
        MISSING_PKGS=()
        for pkg in "${QT_PKGS[@]}"; do
            dpkg -s "$pkg" &>/dev/null || MISSING_PKGS+=("$pkg")
        done
        if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
            echo "  Installing missing Qt libraries: ${MISSING_PKGS[*]}"
            sudo apt-get install -y "${MISSING_PKGS[@]}" || \
                echo "  Warning: could not install some Qt libraries. Build may still succeed."
        fi
        ok "Qt runtime libraries ready (apt)"
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y -q \
            xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil \
            libxkbcommon-x11 mesa-libEGL mesa-libGL dbus-libs glib2 \
            2>/dev/null || echo "  Warning: dnf Qt install skipped."
        ok "Qt runtime libraries ready (dnf)"
    else
        echo "  Skipping system Qt deps — unknown package manager. Install manually if needed."
    fi
fi

# ── 3. Clean previous artefacts ─────────────────────────────────────────────
step "Cleaning previous build artefacts"
rm -rf "$DIST_DIR/$APP_NAME" "$BUILD_DIR/$APP_NAME"
ok "Cleaned dist/$APP_NAME and build/$APP_NAME"

# ── 4. Run PyInstaller ──────────────────────────────────────────────────────
step "Running PyInstaller (this takes 60–180 seconds)"
python3 -m PyInstaller "$SPEC_FILE" --noconfirm || fail "PyInstaller build failed."

BINARY="$DIST_DIR/$APP_NAME/$APP_NAME"
if [[ ! -f "$BINARY" ]]; then
    fail "Expected binary not found at: $BINARY"
fi
chmod +x "$BINARY"
ok "Binary built: $BINARY"

# ── 5. Create portable archive ───────────────────────────────────────────────
step "Creating portable archive: $ARCHIVE_NAME"
cd "$DIST_DIR"
tar -czf "$ARCHIVE_NAME" "$APP_NAME/"
ok "Archive: $DIST_DIR/$ARCHIVE_NAME  ($(du -sh "$ARCHIVE_NAME" | cut -f1))"
cd "$SCRIPT_DIR"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════${RESET}"
echo -e "${GREEN}  SoulMusic Linux build complete.${RESET}"
echo -e "${GREEN}══════════════════════════════════════════${RESET}"
echo ""
echo "  Portable binary : dist/$APP_NAME/$APP_NAME"
echo "  Archive         : dist/$ARCHIVE_NAME"
echo ""
echo "  To install system-wide: sudo bash install_linux.sh"
echo "  To run directly       : dist/$APP_NAME/$APP_NAME"
