#!/usr/bin/env bash
# package.sh — build a distributable SteamLED.zip for GitHub Releases.
#
# The zip is what Decky's "Install from URL" downloads.
# After running this, the archive is at out/SteamLED.zip.

set -e

cd "$(dirname "$0")"

if [ ! -f plugin.json ]; then
  echo "ERROR: Run from the project root."
  exit 1
fi

echo "Installing dependencies..."
pnpm install --frozen-lockfile

echo "Building..."
pnpm build

echo "Packaging..."
rm -rf out
mkdir -p out/SteamLED

cp -r dist out/SteamLED/
cp -r py_modules out/SteamLED/
cp main.py plugin.json package.json out/SteamLED/

cd out
zip -r SteamLED.zip SteamLED/
cd ..

echo "Done: out/SteamLED.zip"
