#!/usr/bin/env bash
# install-local.sh — build and install SteamLED on the Steam Machine directly.
#
# Requirements:
#   - Run from the project root directory
#   - Decky Loader already installed at ~/homebrew
#   - Internet access (first run fetches nvm + Node)
#
# Usage:
#   bash install-local.sh

set -e

PLUGIN_NAME="SteamLED"
PLUGIN_DIR="$HOME/homebrew/plugins/$PLUGIN_NAME"

cd "$(dirname "$0")"

# ── sanity checks ─────────────────────────────────────────────────────────────

if [ ! -f plugin.json ]; then
  echo "ERROR: Run this script from the SteamLED project root."
  exit 1
fi

if [ ! -d "$HOME/homebrew" ]; then
  echo "ERROR: Decky Loader not found at ~/homebrew. Install Decky first."
  exit 1
fi

if [ ! -d /sys/class/leds ]; then
  echo "WARNING: No LED devices found at /sys/class/leds."
  echo "         The plugin will still install but LEDs won't light up."
fi

# ── Node.js via nvm ───────────────────────────────────────────────────────────

export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  echo "Installing nvm..."
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
fi
# shellcheck source=/dev/null
source "$NVM_DIR/nvm.sh"

NODE_VERSION=20
if ! nvm ls "$NODE_VERSION" | grep -q "v$NODE_VERSION"; then
  echo "Installing Node.js $NODE_VERSION..."
  nvm install "$NODE_VERSION"
fi
nvm use "$NODE_VERSION"

# ── pnpm ──────────────────────────────────────────────────────────────────────

if ! command -v pnpm &>/dev/null; then
  echo "Enabling pnpm via corepack..."
  corepack enable
  corepack prepare pnpm@9 --activate
fi

# ── build ─────────────────────────────────────────────────────────────────────

echo "Installing dependencies..."
pnpm install

echo "Building..."
pnpm build

# ── install ───────────────────────────────────────────────────────────────────

echo "Installing to $PLUGIN_DIR..."
sudo rm -rf "$PLUGIN_DIR"
sudo mkdir -p "$PLUGIN_DIR"

sudo cp -r dist "$PLUGIN_DIR/"
sudo cp -r py_modules "$PLUGIN_DIR/"
sudo cp main.py plugin.json package.json "$PLUGIN_DIR/"

sudo chmod -R 755 "$PLUGIN_DIR"

# ── restart Decky ─────────────────────────────────────────────────────────────

echo "Restarting Decky plugin loader..."
sudo systemctl restart plugin_loader

echo ""
echo "Done! Switch to Game Mode and open the Decky menu to find SteamLED."
echo "If the plugin doesn't appear, check logs with:"
echo "  journalctl -u plugin_loader -f"
