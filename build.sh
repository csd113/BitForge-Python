#!/bin/bash

set -e

APP_NAME="Bitcoin Electrs Compiler"
SPEC_FILE="BitcoinElectrsCompiler.spec"
DIST_DIR="dist"
BUILD_DIR="build"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Building: $APP_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Clean old builds
rm -rf "$BUILD_DIR" "$DIST_DIR"

echo "🧹 Cleaned previous builds"

# Run PyInstaller using spec file
pyinstaller "$SPEC_FILE" --clean --noconfirm

echo "📦 Build complete"

APP_PATH="$DIST_DIR/$APP_NAME.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: App bundle not found!"
    exit 1
fi

echo "🔏 Codesigning app..."

codesign --deep --force --verify --verbose \
    --sign - \
    "$APP_PATH"

echo "✅ Codesign complete"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 SUCCESS"
echo "App located at:"
echo "$APP_PATH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
