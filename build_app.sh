#!/bin/bash
# Build Bitcoin Compiler macOS App
# This script properly builds the app to prevent double-launch issues

set -e  # Exit on error

echo "======================================"
echo "Bitcoin Compiler - Build Script"
echo "======================================"
echo ""

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "❌ PyInstaller not found!"
    echo ""
    read -p "Install PyInstaller now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📦 Installing PyInstaller..."
        pip3 install pyinstaller
        echo "✅ PyInstaller installed"
    else
        echo "Please install PyInstaller manually: pip3 install pyinstaller"
        exit 1
    fi
fi

echo "✅ PyInstaller found: $(pyinstaller --version)"
echo ""

# Check if spec file exists
if [ ! -f "bitcoin_compiler.spec" ]; then
    echo "⚠️  Warning: bitcoin_compiler.spec not found"
    echo "Building with default settings..."
    echo ""
    
    # Build with command-line flags
    pyinstaller \
        --name "Bitcoin Compiler" \
        --windowed \
        --onedir \
        --noconfirm \
        --clean \
        --osx-bundle-identifier com.bitcointools.compiler \
        compile_bitcoind_gui_fixed.py
else
    echo "📋 Using bitcoin_compiler.spec"
    echo ""
    
    # Build with spec file (recommended)
    pyinstaller --clean --noconfirm bitcoin_compiler.spec
fi

echo ""
echo "======================================"
echo "Build Complete!"
echo "======================================"
echo ""

# Check if build succeeded
if [ -d "dist/Bitcoin Compiler.app" ]; then
    echo "✅ App created successfully"
    echo ""
    echo "Location: dist/Bitcoin Compiler.app"
    echo "Size: $(du -sh "dist/Bitcoin Compiler.app" | cut -f1)"
    echo ""
    
    # Check app structure
    if [ -f "dist/Bitcoin Compiler.app/Contents/MacOS/BitcoinCompiler" ]; then
        echo "✅ Executable found"
        
        # Check if it's actually a binary (not script)
        FILE_TYPE=$(file "dist/Bitcoin Compiler.app/Contents/MacOS/BitcoinCompiler" | grep -o "Mach-O.*executable")
        if [ -n "$FILE_TYPE" ]; then
            echo "✅ Proper Mach-O executable"
        else
            echo "⚠️  Warning: Executable might not be properly compiled"
        fi
    else
        echo "❌ Error: Executable not found"
        exit 1
    fi
    
    # Check Info.plist
    if [ -f "dist/Bitcoin Compiler.app/Contents/Info.plist" ]; then
        echo "✅ Info.plist found"
        
        # Verify critical settings
        LSUIElement=$(plutil -extract LSUIElement raw "dist/Bitcoin Compiler.app/Contents/Info.plist" 2>/dev/null || echo "not set")
        if [ "$LSUIElement" = "0" ] || [ "$LSUIElement" = "false" ]; then
            echo "✅ LSUIElement correctly set (will show in Dock)"
        else
            echo "⚠️  Warning: LSUIElement = $LSUIElement (might cause issues)"
        fi
    fi
    
    echo ""
    echo "======================================"
    echo "Testing App Launch"
    echo "======================================"
    echo ""
    
    read -p "Test launch the app now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🚀 Launching app..."
        echo "(Check if it opens cleanly without double-launch)"
        echo ""
        open "dist/Bitcoin Compiler.app"
        echo ""
        echo "Did the app:"
        echo "  ✅ Open immediately without flashing?"
        echo "  ✅ Stay open (not close and reopen)?"
        echo "  ✅ Show the main window properly?"
        echo ""
        echo "If YES to all three, the build is successful! 🎉"
        echo "If NO to any, see PYINSTALLER_FIX.md for troubleshooting"
    fi
    
    echo ""
    echo "======================================"
    echo "Next Steps"
    echo "======================================"
    echo ""
    echo "To distribute the app:"
    echo ""
    echo "1. TEST on a different Mac (not your dev machine)"
    echo "2. If working, zip it:"
    echo "   cd dist"
    echo "   zip -r Bitcoin-Compiler.zip \"Bitcoin Compiler.app\""
    echo ""
    echo "3. (Optional) Code sign for distribution:"
    echo "   codesign --deep --force --verify --verbose \\"
    echo "     --sign \"Developer ID Application: Your Name\" \\"
    echo "     \"dist/Bitcoin Compiler.app\""
    echo ""
    echo "4. (Optional) Create DMG installer:"
    echo "   # Install create-dmg first: brew install create-dmg"
    echo "   create-dmg --volname \"Bitcoin Compiler\" \\"
    echo "     --window-size 600 400 \\"
    echo "     --app-drop-link 450 185 \\"
    echo "     \"Bitcoin-Compiler.dmg\" \\"
    echo "     \"dist/Bitcoin Compiler.app\""
    echo ""
    
else
    echo "❌ Build failed - app not created"
    echo ""
    echo "Check the output above for errors"
    echo "Common issues:"
    echo "  - Missing dependencies (install with pip)"
    echo "  - Wrong Python version (use Python 3.8+)"
    echo "  - File permissions issues"
    echo ""
    exit 1
fi

echo "Build script complete!"
