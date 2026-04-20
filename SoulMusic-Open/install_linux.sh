#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  install_linux.sh  —  SoulMusic system installer for Linux
#
#  Modes
#    System install (sudo / root):
#      • Copies source to /opt/SoulMusic
#      • Writes launcher to /usr/local/bin/soulmusic
#      • Installs .desktop to /usr/share/applications/
#
#    User install (no sudo):
#      • Copies source to ~/.local/share/SoulMusic
#      • Writes launcher to ~/.local/bin/soulmusic
#      • Installs .desktop to ~/.local/share/applications/
#
#  Usage:
#    chmod +x install_linux.sh
#    sudo bash install_linux.sh          # system install (recommended)
#    bash install_linux.sh --user        # user install (no root required)
#    bash install_linux.sh --uninstall   # remove system install
#    bash install_linux.sh --user --uninstall  # remove user install
#
#  Run from the repository root directory.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="SoulMusic"
APP_BINARY="soul_gui.py"
APP_VERSION="1.0.0"

USER_INSTALL=false
UNINSTALL=false

for arg in "$@"; do
    case "$arg" in
        --user)        USER_INSTALL=true ;;
        --uninstall)   UNINSTALL=true ;;
    esac
done

# ── Paths ────────────────────────────────────────────────────────────────────
if [[ "$USER_INSTALL" == true ]]; then
    INSTALL_DIR="$HOME/.local/share/$APP_NAME"
    BIN_DIR="$HOME/.local/bin"
    DESKTOP_DIR="$HOME/.local/share/applications"
else
    INSTALL_DIR="/opt/$APP_NAME"
    BIN_DIR="/usr/local/bin"
    DESKTOP_DIR="/usr/share/applications"
fi

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RESET='\033[0m'
step()  { echo -e "\n${CYAN}[${APP_NAME}] $*${RESET}"; }
ok()    { echo -e "  ${GREEN}[OK]  $*${RESET}"; }
warn()  { echo -e "  ${YELLOW}[WARN] $*${RESET}"; }
fail()  { echo -e "  ${RED}[ERR] $*${RESET}"; exit 1; }

# ── Uninstall path ───────────────────────────────────────────────────────────
if [[ "$UNINSTALL" == true ]]; then
    step "Uninstalling $APP_NAME"
    [[ -d "$INSTALL_DIR" ]]         && rm -rf "$INSTALL_DIR"     && ok "Removed $INSTALL_DIR"
    [[ -f "$BIN_DIR/soulmusic" ]]   && rm -f  "$BIN_DIR/soulmusic" && ok "Removed $BIN_DIR/soulmusic"
    [[ -f "$DESKTOP_DIR/soulmusic.desktop" ]] && \
        rm -f "$DESKTOP_DIR/soulmusic.desktop" && ok "Removed desktop entry"
    command -v update-desktop-database &>/dev/null && \
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    echo ""
    echo -e "${GREEN}$APP_NAME uninstalled.${RESET}"
    exit 0
fi

# ── 1. Prerequisites ─────────────────────────────────────────────────────────
step "Checking prerequisites"

if ! command -v python3 &>/dev/null; then
    fail "python3 not found.\n  Ubuntu/Debian: sudo apt-get install python3\n  Fedora: sudo dnf install python3"
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10) ]]; then
    fail "Python $PY_VER detected. SoulMusic requires Python ≥ 3.10."
fi
ok "Python $PY_VER"

if ! python3 -m pip --version &>/dev/null; then
    fail "pip not found. Run: python3 -m ensurepip --upgrade"
fi
ok "pip available"

# ── 2. Install Python dependencies ──────────────────────────────────────────
step "Installing Python packages (PySide6, numpy)"
PIP_FLAGS=""
[[ "$USER_INSTALL" == true ]] && PIP_FLAGS="--user"
python3 -m pip install $PIP_FLAGS --quiet PySide6 numpy || \
    fail "pip install failed. Check your network connection."
ok "PySide6 and numpy installed"

echo "  Optional packages (skip if not needed):"
echo "    pip install $PIP_FLAGS pyserial sounddevice matplotlib"

# ── 3. Copy project files ────────────────────────────────────────────────────
step "Installing $APP_NAME to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy all source files — exclude build artefacts and caches
rsync -a --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude 'dist/' \
    --exclude 'build/' \
    --exclude 'installer/' \
    --exclude '*.spec' \
    --exclude '*.iss' \
    --exclude '*.exe' \
    --exclude '*.ps1' \
    --exclude 'SoulPlan.md' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/" 2>/dev/null || {
    # rsync not available — fall back to cp
    cp -r "$SCRIPT_DIR/acoustic"  "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/detection" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/flight"    "$INSTALL_DIR/"
    cp    "$SCRIPT_DIR/soul_gui.py" "$INSTALL_DIR/"
    cp    "$SCRIPT_DIR/test_harness.py" "$INSTALL_DIR/" 2>/dev/null || true
    cp    "$SCRIPT_DIR/bench_test.py"   "$INSTALL_DIR/" 2>/dev/null || true
}

# Ensure plugins directory exists (MODULE LOADER auto-discover target)
mkdir -p "$INSTALL_DIR/plugins"
touch "$INSTALL_DIR/plugins/.gitkeep" 2>/dev/null || true

ok "Files installed to $INSTALL_DIR"

# ── 4. Create launcher script ────────────────────────────────────────────────
step "Creating launcher: $BIN_DIR/soulmusic"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/soulmusic" <<EOF
#!/usr/bin/env bash
# SoulMusic launcher — generated by install_linux.sh
export QT_ENABLE_HIGHDPI_SCALING=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1
exec python3 "$INSTALL_DIR/soul_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/soulmusic"
ok "Launcher created"

# Warn if BIN_DIR is not in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH."
    echo "       Add this to your ~/.bashrc or ~/.zshrc:"
    echo "         export PATH=\"$BIN_DIR:\$PATH\""
fi

# ── 5. Install desktop entry ─────────────────────────────────────────────────
step "Installing desktop launcher"
mkdir -p "$DESKTOP_DIR"

DESKTOP_ICON="utilities-terminal"
# Use project icon if one exists
[[ -f "$INSTALL_DIR/assets/icon.png" ]] && DESKTOP_ICON="$INSTALL_DIR/assets/icon.png"

cat > "$DESKTOP_DIR/soulmusic.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=SoulMusic
GenericName=Acoustic Counter-UAS Platform
Comment=MEMS gyroscope resonance research and counter-UAS test control
Exec=$BIN_DIR/soulmusic %F
Icon=$DESKTOP_ICON
Terminal=false
Categories=Science;Engineering;
Keywords=drone;counter-uas;mems;acoustic;resonance;
StartupNotify=true
EOF

command -v update-desktop-database &>/dev/null && \
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null && \
    ok "Desktop database updated" || warn "update-desktop-database not found — .desktop may not appear immediately"
ok "Desktop entry installed: $DESKTOP_DIR/soulmusic.desktop"

# ── 6. Verify installation ───────────────────────────────────────────────────
step "Verifying installation"
python3 -c "
import sys, os
sys.path.insert(0, '$INSTALL_DIR')
try:
    import acoustic.resonance
    import detection.acoustic_detect
    import flight.telemetry
    print('  [OK]  Core modules import cleanly')
except ImportError as e:
    print(f'  [WARN] Import check: {e}')
" 2>&1 || warn "Module verification produced warnings (non-fatal)"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════${RESET}"
echo -e "${GREEN}  SoulMusic $APP_VERSION installed successfully.${RESET}"
echo -e "${GREEN}══════════════════════════════════════════${RESET}"
echo ""
echo "  Run from terminal : soulmusic"
echo "  Run directly      : python3 $INSTALL_DIR/soul_gui.py"
echo "  Run tests         : python3 $INSTALL_DIR/test_harness.py"
echo "  Uninstall         : bash $SCRIPT_DIR/install_linux.sh ${USER_INSTALL:+--user }--uninstall"
echo ""
echo -e "${YELLOW}  USE AT YOUR OWN RISK. Verify local regulations before deployment.${RESET}"
