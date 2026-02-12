#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import requests
import multiprocessing
import shutil
import re
import platform
import time
import hashlib

# ================== PYINSTALLER COMPATIBILITY ==================
def is_pyinstaller():
    """Check if running as PyInstaller bundle"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def get_base_path():
    """Get base path for resources (works with PyInstaller)"""
    if is_pyinstaller():
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return sys._MEIPASS
    return os.path.abspath(".")

# Set base path for resources
BASE_PATH = get_base_path()

# Fix macOS app bundle issues
if is_pyinstaller() and platform.system() == 'Darwin':
    # Prevent double-launch on macOS
    os.environ['APP_STARTED'] = '1'

# ================== FIX GUI APP PATH ==================
os.environ["PATH"] = (
    "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:"
    + os.path.expanduser("~/.cargo/bin")
)

# ================== CONFIG ==================
BITCOIN_API = "https://api.github.com/repos/bitcoin/bitcoin/releases"
BITCOIN_REPO = "https://github.com/bitcoin/bitcoin.git"
ELECTRS_API = "https://api.github.com/repos/romanz/electrs/releases"
ELECTRS_REPO = "https://github.com/romanz/electrs.git"
DEFAULT_BUILD_DIR = os.path.expanduser("~/Downloads/bitcoin_builds")

# ================== ARCHITECTURE DETECTION ==================
def get_architecture():
    """Detect if running on Apple Silicon or Intel Mac"""
    machine = platform.machine()
    if machine == "arm64":
        return "apple_silicon"
    elif machine == "x86_64":
        return "intel"
    else:
        return "unknown"

ARCH = get_architecture()

# ================== HOMEBREW DETECTION ==================
def find_brew():
    """Find Homebrew installation (Apple Silicon or Intel Mac)"""
    for path in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
        if os.path.isfile(path):
            return path
    return None

BREW = find_brew()

# Determine Homebrew prefix based on architecture
if BREW:
    if "/opt/homebrew" in BREW:
        BREW_PREFIX = "/opt/homebrew"
    else:
        BREW_PREFIX = "/usr/local"
else:
    BREW_PREFIX = None

# ================== SHA256 VERIFICATION ==================
def calculate_sha256(filepath, chunk_size=8192):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        log(f"❌ Error calculating SHA256: {e}\n")
        return None

def verify_git_commit(repo_dir, expected_tag):
    """Verify git repository is at the expected tag/commit"""
    try:
        # Get current commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            log(f"⚠️  Could not get commit hash\n")
            return False
        
        current_commit = result.stdout.strip()
        
        # Get commit hash for the tag
        result = subprocess.run(
            ["git", "rev-list", "-n", "1", expected_tag],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            log(f"⚠️  Could not get tag commit hash\n")
            return False
        
        tag_commit = result.stdout.strip()
        
        if current_commit == tag_commit:
            log(f"✓ Git repository verified at {expected_tag}\n")
            log(f"  Commit: {current_commit[:16]}...\n")
            return True
        else:
            log(f"⚠️  Repository commit mismatch!\n")
            log(f"  Current: {current_commit[:16]}...\n")
            log(f"  Expected: {tag_commit[:16]}...\n")
            return False
            
    except Exception as e:
        log(f"⚠️  Error verifying git commit: {e}\n")
        return False

def verify_source_integrity(repo_dir, project_name, version):
    """Verify source code integrity using git commit verification"""
    log(f"\n🔐 Verifying {project_name} source integrity...\n")
    
    if verify_git_commit(repo_dir, version):
        log(f"✓ {project_name} source integrity verified!\n")
        return True
    else:
        log(f"⚠️  {project_name} source verification failed\n")
        response = messagebox.askyesno(
            "Source Verification Warning",
            f"{project_name} source code could not be verified.\n\n"
            f"This could indicate:\n"
            f"• Network issues during clone\n"
            f"• Repository corruption\n"
            f"• Unexpected git state\n\n"
            f"Continue anyway? (Not recommended)"
        )
        return response

# ================== OPTIMIZATION FLAGS ==================
def get_optimization_flags(use_aggressive=False):
    """Get compiler optimization flags based on architecture and settings"""
    flags = {}
    
    if ARCH == "apple_silicon":
        # Apple Silicon (M1/M2/M3) optimizations
        base_flags = [
            "-mcpu=apple-m1",  # or apple-m2 for newer chips
            "-O2",              # Safe optimization level
            "-fomit-frame-pointer",
            "-fno-common",
        ]
        
        if use_aggressive:
            # Aggressive optimizations (may break some code)
            aggressive_flags = [
                "-O3",           # Maximum optimization
                "-flto",         # Link-time optimization
                "-march=armv8.5-a+fp16+crypto+dotprod",
            ]
            flags['CFLAGS'] = ' '.join(base_flags + aggressive_flags)
            flags['CXXFLAGS'] = ' '.join(base_flags + aggressive_flags)
            flags['LDFLAGS'] = '-flto'
        else:
            flags['CFLAGS'] = ' '.join(base_flags)
            flags['CXXFLAGS'] = ' '.join(base_flags)
            flags['LDFLAGS'] = ''
            
    elif ARCH == "intel":
        # Intel Mac optimizations
        base_flags = [
            "-march=native",    # Optimize for current CPU
            "-O2",              # Safe optimization level
            "-fomit-frame-pointer",
            "-fno-common",
        ]
        
        if use_aggressive:
            # Aggressive optimizations
            aggressive_flags = [
                "-O3",           # Maximum optimization
                "-flto",         # Link-time optimization
                "-mtune=native",
            ]
            flags['CFLAGS'] = ' '.join(base_flags + aggressive_flags)
            flags['CXXFLAGS'] = ' '.join(base_flags + aggressive_flags)
            flags['LDFLAGS'] = '-flto'
        else:
            flags['CFLAGS'] = ' '.join(base_flags)
            flags['CXXFLAGS'] = ' '.join(base_flags)
            flags['LDFLAGS'] = ''
    else:
        # Unknown architecture - use safe defaults
        flags['CFLAGS'] = '-O2'
        flags['CXXFLAGS'] = '-O2'
        flags['LDFLAGS'] = ''
    
    return flags

def get_rust_optimization_flags(use_aggressive=False):
    """Get Rust/Cargo optimization flags"""
    flags = {}
    
    if use_aggressive:
        # Aggressive Rust optimizations
        # Note: When using LTO, we must enable embed-bitcode
        flags['RUSTFLAGS'] = '-C opt-level=3 -C target-cpu=native'
        flags['CARGO_PROFILE_RELEASE_LTO'] = 'fat'
        flags['CARGO_PROFILE_RELEASE_OPT_LEVEL'] = '3'
        flags['CARGO_PROFILE_RELEASE_EMBED_BITCODE'] = 'yes'
    else:
        # Standard release optimizations
        flags['RUSTFLAGS'] = '-C opt-level=2 -C target-cpu=native'
        flags['CARGO_PROFILE_RELEASE_OPT_LEVEL'] = '2'
    
    return flags

# ================== GUI HELPERS ==================
def log(msg):
    """Thread-safe logging to GUI text widget"""
    # Only log if the widget exists (GUI is initialized)
    try:
        if 'log_text' in globals() and log_text.winfo_exists():
            log_text.after(0, lambda: (
                log_text.insert("end", msg),
                log_text.see("end")
            ))
    except:
        # Silently fail during initialization
        pass

def set_progress(val):
    """Thread-safe progress bar update"""
    progress.after(0, lambda: progress_var.set(val))

def run_command(cmd, cwd=None, env=None):
    """Execute shell command and log output in real-time"""
    log(f"\n$ {cmd}\n")
    if env is None:
        env = os.environ.copy()
    
    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )
    
    for line in process.stdout:
        log(line)
    
    process.wait()
    
    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")
    
    return process.returncode

# ================== VERSION LOGIC ==================
def parse_version(tag):
    """Parse version number from git tag"""
    # Remove 'v' prefix if present
    tag = tag.lstrip('v')
    m = re.match(r"(\d+)\.(\d+)", tag)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def use_cmake(version):
    """Determine if version uses CMake (v25+) or Autotools"""
    major, _ = parse_version(version)
    return major >= 25

def get_bitcoin_versions():
    """Fetch latest Bitcoin Core releases from GitHub"""
    try:
        r = requests.get(BITCOIN_API, timeout=10)
        r.raise_for_status()
        
        # Collect all non-RC versions
        all_versions = []
        for rel in r.json():
            tag = rel["tag_name"]
            # Skip release candidates
            if "rc" in tag.lower():
                continue
            all_versions.append(tag)
            if len(all_versions) == 20:  # Get more to filter from
                break
        
        # Group by major.minor version, keeping only the latest patch
        version_groups = {}
        for tag in all_versions:
            # Parse version (e.g., "v29.3" -> (29, 3))
            major, minor = parse_version(tag)
            key = f"{major}.{minor}"
            
            if key not in version_groups:
                version_groups[key] = []
            version_groups[key].append(tag)
        
        # For each major.minor, keep only the highest patch version
        filtered_versions = []
        for key in sorted(version_groups.keys(), key=lambda x: tuple(map(int, x.split('.'))), reverse=True):
            # Sort versions in this group and take the first (latest)
            group = sorted(version_groups[key], key=lambda v: parse_version(v), reverse=True)
            filtered_versions.append(group[0])
            if len(filtered_versions) == 5:  # Only keep 5 versions
                break
        
        log(f"Found {len(filtered_versions)} Bitcoin versions (latest patch only)\n")
        return filtered_versions
    except Exception as e:
        log(f"Failed to fetch Bitcoin versions: {e}\n")
        # Return empty list on failure, don't show error dialog during init
        return []

def get_electrs_versions():
    """Fetch latest Electrs releases from GitHub"""
    try:
        r = requests.get(ELECTRS_API, timeout=10)
        r.raise_for_status()
        versions = []
        for rel in r.json():
            tag = rel["tag_name"]
            # Skip release candidates
            if "rc" in tag.lower():
                continue
            versions.append(tag)
            if len(versions) == 3:  # Only keep 3 versions
                break
        log(f"Found {len(versions)} Electrs versions\n")
        return versions
    except Exception as e:
        log(f"Failed to fetch Electrs versions: {e}\n")
        # Return empty list on failure, don't show error dialog during init
        return []

# ================== ENVIRONMENT SETUP ==================
def setup_build_environment(use_aggressive_opts=False):
    """Setup environment variables for building"""
    env = os.environ.copy()
    
    if not BREW_PREFIX:
        log("⚠️  Warning: Homebrew prefix not detected, using defaults\n")
    
    # Build comprehensive PATH
    path_components = []
    
    # Add Homebrew to PATH
    if BREW_PREFIX:
        path_components.append(f"{BREW_PREFIX}/bin")
    
    # Add common Homebrew locations
    path_components.extend([
        "/opt/homebrew/bin",
        "/usr/local/bin"
    ])
    
    # Add Cargo/Rust paths (multiple possible locations)
    rust_paths = [
        os.path.expanduser("~/.cargo/bin"),
        f"{BREW_PREFIX}/bin" if BREW_PREFIX else None,
    ]
    for rust_path in rust_paths:
        if rust_path and os.path.isdir(rust_path):
            path_components.append(rust_path)
    
    # Add LLVM for Electrs
    llvm_paths = [
        f"{BREW_PREFIX}/opt/llvm/bin" if BREW_PREFIX else None,
        "/opt/homebrew/opt/llvm/bin",
        "/usr/local/opt/llvm/bin"
    ]
    for llvm_path in llvm_paths:
        if llvm_path and os.path.isdir(llvm_path):
            path_components.append(llvm_path)
    
    # Add existing PATH
    path_components.append(env.get('PATH', ''))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for p in path_components:
        if p and p not in seen:
            seen.add(p)
            unique_paths.append(p)
    
    env["PATH"] = ":".join(unique_paths)
    
    # LLVM setup for Electrs
    llvm_lib_paths = [
        f"{BREW_PREFIX}/opt/llvm" if BREW_PREFIX else None,
        "/opt/homebrew/opt/llvm",
        "/usr/local/opt/llvm"
    ]
    for llvm_prefix in llvm_lib_paths:
        if llvm_prefix and os.path.isdir(llvm_prefix):
            env["LIBCLANG_PATH"] = f"{llvm_prefix}/lib"
            env["DYLD_LIBRARY_PATH"] = f"{llvm_prefix}/lib"
            break
    
    # Add optimization flags
    opt_flags = get_optimization_flags(use_aggressive_opts)
    for key, value in opt_flags.items():
        if value:  # Only set non-empty values
            env[key] = value
            log(f"  {key}: {value}\n")
    
    # Note: Berkeley DB is NOT configured here as it's only needed for legacy wallet support
    # For running a Bitcoin node (bitcoind), wallet support is disabled in the build
    
    return env

# ================== DEPENDENCY CHECKER ==================
def check_rust_installation():
    """Comprehensive Rust/Cargo check and installation"""
    log("\n=== Checking Rust Toolchain ===\n")
    
    # Possible Rust installation paths
    rust_paths = [
        os.path.expanduser("~/.cargo/bin"),
        f"{BREW_PREFIX}/bin" if BREW_PREFIX else None,
        "/usr/local/bin",
        "/opt/homebrew/bin"
    ]
    rust_paths = [p for p in rust_paths if p]  # Remove None values
    
    # Check if rustc is accessible
    rustc_found = False
    cargo_found = False
    rustc_path = None
    cargo_path = None
    
    for path in rust_paths:
        rustc_candidate = os.path.join(path, "rustc")
        cargo_candidate = os.path.join(path, "cargo")
        
        if os.path.isfile(rustc_candidate) and not rustc_found:
            # Test if it works
            result = subprocess.run(
                [rustc_candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                rustc_found = True
                rustc_path = rustc_candidate
                log(f"✓ rustc found at: {rustc_path}\n")
                log(f"  Version: {result.stdout.strip()}\n")
        
        if os.path.isfile(cargo_candidate) and not cargo_found:
            result = subprocess.run(
                [cargo_candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                cargo_found = True
                cargo_path = cargo_candidate
                log(f"✓ cargo found at: {cargo_path}\n")
                log(f"  Version: {result.stdout.strip()}\n")
    
    # If not found, install Rust via Homebrew
    if not rustc_found or not cargo_found:
        log("\n❌ Rust toolchain not found or incomplete!\n")
        log("Installing Rust via Homebrew...\n")
        
        try:
            # First, check if rust formula exists
            result = subprocess.run(
                [BREW, "info", "rust"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                log("📦 Installing rust from Homebrew...\n")
                run_command(f"{BREW} install rust")
                
                # Verify installation
                log("\nVerifying Rust installation...\n")
                time.sleep(2)  # Give it a moment
                
                # Check again
                for path in rust_paths:
                    rustc_candidate = os.path.join(path, "rustc")
                    cargo_candidate = os.path.join(path, "cargo")
                    
                    if os.path.isfile(rustc_candidate):
                        result = subprocess.run(
                            [rustc_candidate, "--version"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        if result.returncode == 0:
                            log(f"✓ rustc installed successfully: {result.stdout.strip()}\n")
                            rustc_found = True
                            break
                
                for path in rust_paths:
                    cargo_candidate = os.path.join(path, "cargo")
                    if os.path.isfile(cargo_candidate):
                        result = subprocess.run(
                            [cargo_candidate, "--version"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        if result.returncode == 0:
                            log(f"✓ cargo installed successfully: {result.stdout.strip()}\n")
                            cargo_found = True
                            break
                
                if not rustc_found or not cargo_found:
                    log("⚠️  Rust installation may have succeeded but binaries not found in PATH\n")
                    log("You may need to restart the app or your terminal\n")
                    messagebox.showwarning(
                        "Rust Installation",
                        "Rust was installed but may not be in PATH.\n\n"
                        "Please:\n"
                        "1. Close and reopen this app\n"
                        "2. OR manually add ~/.cargo/bin to your PATH"
                    )
            else:
                log("❌ Rust formula not found in Homebrew\n")
                log("Attempting alternative installation method...\n")
                messagebox.showerror(
                    "Rust Installation Failed",
                    "Could not install Rust via Homebrew.\n\n"
                    "Please install manually:\n"
                    "1. Visit https://rustup.rs\n"
                    "2. Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\n"
                    "3. Restart this app"
                )
                
        except Exception as e:
            log(f"❌ Failed to install Rust: {e}\n")
            messagebox.showerror(
                "Installation Error",
                f"Failed to install Rust: {e}\n\n"
                "Please install manually from https://rustup.rs"
            )
    
    return rustc_found and cargo_found

def check_dependencies():
    """Check and install required system dependencies"""
    def task():
        try:
            log("\n=== Checking System Dependencies ===\n")
            
            if not BREW:
                log("❌ Homebrew not found!\n")
                log("Please install Homebrew from https://brew.sh\n")
                messagebox.showerror("Missing Dependency", "Homebrew not found! Please install from https://brew.sh")
                return

            log(f"✓ Homebrew found at: {BREW}\n")
            log(f"  Homebrew prefix: {BREW_PREFIX}\n")

            # Required Homebrew packages (excluding rust, we check that separately)
            # Note: berkeley-db@4 is only needed for wallet support, not for running a node
            # Added git to the list of required packages
            brew_packages = [
                "automake", "libtool", "pkg-config", "boost",
                "miniupnpc", "zeromq", "sqlite", "python", "cmake", "llvm", "libevent", "rocksdb", "rust", "git"
            ]

            log("\nChecking Homebrew packages...\n")
            missing = []
            for pkg in brew_packages:
                result = subprocess.run(
                    [BREW, "list", pkg],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode != 0:
                    log(f"  ❌ {pkg} - not installed\n")
                    missing.append(pkg)
                else:
                    log(f"  ✓ {pkg}\n")

            if missing:
                log(f"\n⚠️  Missing Homebrew packages: {', '.join(missing)}\n")
                
                # Create a simple, safe message for the dialog
                try:
                    pkg_count = len(missing)
                    pkg_list = ', '.join(missing[:5])  # Show first 5 packages
                    if pkg_count > 5:
                        pkg_list += f", and {pkg_count - 5} more"
                    
                    message = (
                        f"Found {pkg_count} missing package{'s' if pkg_count > 1 else ''}:\n\n"
                        f"{pkg_list}\n\n"
                        f"Install all missing packages now?"
                    )
                    
                    install_deps = messagebox.askyesno("Install Missing Dependencies", message)
                except Exception as e:
                    log(f"⚠️  Error showing dialog: {e}\n")
                    # Fallback: ask in a simpler way
                    install_deps = messagebox.askyesno(
                        "Install Dependencies",
                        f"Install {len(missing)} missing packages?"
                    )
                
                if install_deps:
                    for pkg in missing:
                        log(f"\n📦 Installing {pkg}...\n")
                        try:
                            run_command(f"{BREW} install {pkg}")
                            log(f"✓ {pkg} installed successfully\n")
                        except Exception as e:
                            log(f"❌ Failed to install {pkg}: {e}\n")
                            try:
                                messagebox.showerror("Installation Failed", f"Failed to install {pkg}")
                            except:
                                log("⚠️  Could not show error dialog\n")
                else:
                    log("\n⚠️  Dependencies not installed. Compilation may fail.\n")
            else:
                log("\n✓ All Homebrew packages are installed!\n")

            # Comprehensive Rust check
            rust_ok = check_rust_installation()
            
            if rust_ok:
                log("\n✓ Rust toolchain is ready!\n")
            else:
                log("\n⚠️  Rust toolchain needs attention (see messages above)\n")

            log("\n=== Dependency Check Complete ===\n")
            
            if rust_ok:
                messagebox.showinfo(
                    "Dependency Check",
                    "✅ All dependencies are installed and ready!\n\n"
                    "You can now proceed with compilation."
                )
            else:
                messagebox.showwarning(
                    "Dependency Check",
                    "⚠️  Some dependencies need attention.\n\n"
                    "Check the log for details.\n"
                    "You may need to restart the app after installing Rust."
                )

        except Exception as e:
            log(f"\n❌ Error during dependency check: {e}\n")
            import traceback
            log(traceback.format_exc() + "\n")
            messagebox.showerror("Error", f"Dependency check failed: {e}")

    threading.Thread(target=task, daemon=True).start()

def refresh_bitcoin_versions():
    """Refresh Bitcoin version list in dropdown"""
    log("\n📡 Fetching Bitcoin versions from GitHub...\n")
    versions = get_bitcoin_versions()
    if versions:
        bitcoin_combo.configure(values=versions)
        # Always set to the first (newest) version
        bitcoin_version_var.set(versions[0])
        log(f"✓ Loaded {len(versions)} Bitcoin versions (selected: {versions[0]})\n")
    else:
        log("⚠️  Could not fetch Bitcoin versions (check internet connection)\n")
        messagebox.showwarning("Network Error", "Could not fetch Bitcoin versions. Check your internet connection.")

def refresh_electrs_versions():
    """Refresh Electrs version list in dropdown"""
    log("\n📡 Fetching Electrs versions from GitHub...\n")
    versions = get_electrs_versions()
    if versions:
        electrs_combo.configure(values=versions)
        # Always set to the first (newest) version
        electrs_version_var.set(versions[0])
        log(f"✓ Loaded {len(versions)} Electrs versions (selected: {versions[0]})\n")
    else:
        log("⚠️  Could not fetch Electrs versions (check internet connection)\n")
        messagebox.showwarning("Network Error", "Could not fetch Electrs versions. Check your internet connection.")

def initial_version_load():
    """Load versions after GUI is ready"""
    def task():
        refresh_bitcoin_versions()
        refresh_electrs_versions()
    threading.Thread(target=task, daemon=True).start()

# ================== GLOBAL GUI VARIABLES ==================
# These will be set by create_gui()
root = None
target_var = None
cores_var = None
build_dir_var = None
bitcoin_version_var = None
electrs_version_var = None
bitcoin_combo = None
electrs_combo = None
log_text = None
progress_var = None
progress = None
compile_btn = None
bitcoin_status = None
electrs_status = None
aggressive_opts_var = None

# ================== BUILD FUNCTIONS ==================
def copy_binaries(src_dir, dest_dir, binary_files):
    """Copy compiled binaries to destination directory"""
    os.makedirs(dest_dir, exist_ok=True)
    copied = []
    
    log(f"Copying binaries to: {dest_dir}\n")
    
    for binary in binary_files:
        if os.path.exists(binary):
            try:
                dest = os.path.join(dest_dir, os.path.basename(binary))
                shutil.copy2(binary, dest)
                # Make executable
                os.chmod(dest, 0o755)
                copied.append(dest)
                log(f"✓ Copied: {os.path.basename(binary)} → {dest}\n")
            except Exception as e:
                log(f"⚠️  Failed to copy {os.path.basename(binary)}: {e}\n")
        else:
            log(f"⚠️  Binary not found (skipping): {binary}\n")
    
    if not copied:
        log(f"❌ WARNING: No binaries were copied!\n")
    
    return copied

def compile_bitcoin_source(version, build_dir, cores, use_aggressive_opts=False):
    """Compile Bitcoin Core from source using git clone"""
    try:
        log(f"\n{'='*60}\n")
        log(f"COMPILING BITCOIN CORE {version}\n")
        log(f"{'='*60}\n")
        log(f"Architecture: {ARCH.upper()}\n")
        log(f"Optimization: {'AGGRESSIVE (O3 + LTO)' if use_aggressive_opts else 'STANDARD (O2)'}\n")
        log(f"{'='*60}\n")
        
        version_clean = version.lstrip('v')
        src_dir = os.path.join(build_dir, f"bitcoin-{version_clean}")
        
        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        
        # Clone or update source from GitHub
        if not os.path.exists(src_dir):
            log(f"\n📥 Cloning Bitcoin Core repository...\n")
            run_command(
                f"git clone --depth 1 --branch {version} {BITCOIN_REPO} {src_dir}",
                cwd=build_dir
            )
            log(f"✓ Source cloned to {src_dir}\n")
        else:
            log(f"✓ Source directory already exists: {src_dir}\n")
            log(f"📥 Updating to {version}...\n")
            run_command(f"git fetch --depth 1 origin tag {version}", cwd=src_dir)
            run_command(f"git checkout {version}", cwd=src_dir)
            log(f"✓ Updated to {version}\n")

        # Verify source integrity
        if not verify_source_integrity(src_dir, "Bitcoin Core", version):
            log("❌ User cancelled due to verification failure\n")
            raise RuntimeError("Source verification failed")

        # Setup environment with optimization flags
        env = setup_build_environment(use_aggressive_opts)
        
        log(f"\nEnvironment setup:\n")
        log(f"  PATH: {env['PATH'][:150]}...\n")
        if 'CFLAGS' in env:
            log(f"  CFLAGS: {env['CFLAGS']}\n")
        if 'CXXFLAGS' in env:
            log(f"  CXXFLAGS: {env['CXXFLAGS']}\n")
        if 'LDFLAGS' in env and env['LDFLAGS']:
            log(f"  LDFLAGS: {env['LDFLAGS']}\n")
        log(f"  Building node-only (wallet support disabled)\n")
        
        # Determine build method
        if use_cmake(version):
            log(f"\n🔨 Building with CMake (Bitcoin Core {version})...\n")
            build_subdir = os.path.join(src_dir, "build")
            
            cmake_cmd = f"cmake -B build -DENABLE_WALLET=OFF -DENABLE_IPC=OFF"
            log(f"\n⚙️  Configuring (wallet support disabled for node-only build)...\n")
            run_command(cmake_cmd, cwd=src_dir, env=env)
            
            log(f"\n🔧 Compiling with {cores} cores...\n")
            run_command(f"cmake --build build -j{cores}", cwd=src_dir, env=env)
            
            # Binary locations for CMake build
            build_subdir = os.path.join(src_dir, "build")
            binary_dir = os.path.join(build_subdir, "bin")
            binaries = [
                os.path.join(binary_dir, "bitcoind"),
                os.path.join(binary_dir, "bitcoin-cli"),
                os.path.join(binary_dir, "bitcoin-tx"),
                os.path.join(binary_dir, "bitcoin-wallet"),
                os.path.join(binary_dir, "bitcoin-util"),
            ]
            
        else:
            log(f"\n🔨 Building with Autotools (Bitcoin Core {version})...\n")
            
            # Configure options - disable wallet support for node-only build
            config_opts = [
                "--disable-wallet",  # Disable wallet (no Berkeley DB needed)
                "--disable-gui",     # Disable GUI
            ]
            
            config_cmd = f"./configure {' '.join(config_opts)}"
            
            log(f"\n⚙️  Running autogen.sh...\n")
            run_command("./autogen.sh", cwd=src_dir, env=env)
            
            log(f"\n⚙️  Configuring (wallet support disabled for node-only build)...\n")
            run_command(config_cmd, cwd=src_dir, env=env)
            
            log(f"\n🔧 Compiling with {cores} cores...\n")
            run_command(f"make -j{cores}", cwd=src_dir, env=env)
            
            # Binary locations for Autotools build
            binary_dir = os.path.join(src_dir, "bin")
            binaries = [
                os.path.join(binary_dir, "bitcoind"),
                os.path.join(binary_dir, "bitcoin-cli"),
                os.path.join(binary_dir, "bitcoin-tx"),
                os.path.join(binary_dir, "bitcoin-wallet"),
            ]
        
        # Copy binaries to output directory
        log(f"\n📋 Collecting binaries...\n")
        output_dir = os.path.join(build_dir, "binaries", f"bitcoin-{version_clean}")
        copied = copy_binaries(src_dir, output_dir, binaries)
        
        if not copied:
            log(f"⚠️  Warning: No binaries were copied. Checking what exists...\n")
            for binary in binaries:
                exists = "✓" if os.path.exists(binary) else "❌"
                log(f"  {exists} {binary}\n")
        
        log(f"\n{'='*60}\n")
        log(f"✅ BITCOIN CORE {version} COMPILED SUCCESSFULLY!\n")
        log(f"{'='*60}\n")
        log(f"\n📍 Binaries location: {output_dir}\n")
        log(f"   Found {len(copied)} binaries\n\n")
        
        return output_dir

    except Exception as e:
        log(f"\n❌ Error compiling Bitcoin: {e}\n")
        import traceback
        log(f"\nFull traceback:\n{traceback.format_exc()}\n")
        raise

def compile_electrs_source(version, build_dir, cores, use_aggressive_opts=False):
    """Compile Electrs from source using git clone"""
    try:
        log(f"\n{'='*60}\n")
        log(f"COMPILING ELECTRS {version}\n")
        log(f"{'='*60}\n")
        log(f"Architecture: {ARCH.upper()}\n")
        log(f"Optimization: {'AGGRESSIVE (O3 + LTO)' if use_aggressive_opts else 'STANDARD (O2)'}\n")
        log(f"{'='*60}\n")
        
        # Setup environment with LLVM and Rust optimization flags
        env = setup_build_environment(use_aggressive_opts)
        
        # Add Rust-specific optimization flags
        rust_flags = get_rust_optimization_flags(use_aggressive_opts)
        for key, value in rust_flags.items():
            if value:
                env[key] = value
                log(f"  {key}: {value}\n")
        
        # Verify Rust is available before proceeding
        log("\n🔍 Verifying Rust installation...\n")
        cargo_check = subprocess.run(
            ["cargo", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        if cargo_check.returncode != 0:
            error_msg = (
                "❌ Cargo not found in PATH!\n\n"
                "Electrs requires Rust/Cargo to compile.\n\n"
                "Please:\n"
                "1. Click 'Check & Install Dependencies' button\n"
                "2. Ensure Rust is installed\n"
                "3. Restart this application\n\n"
                f"Current PATH: {env['PATH'][:200]}...\n"
            )
            log(error_msg)
            messagebox.showerror("Rust Not Found", error_msg)
            raise RuntimeError("Cargo not found - cannot compile Electrs")
        
        log(f"✓ Cargo found: {cargo_check.stdout.strip()}\n")
        
        rustc_check = subprocess.run(
            ["rustc", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        if rustc_check.returncode == 0:
            log(f"✓ Rustc found: {rustc_check.stdout.strip()}\n")
        else:
            log("⚠️  Warning: rustc check failed, but cargo found. Proceeding...\n")
        
        version_clean = version.lstrip('v')
        src_dir = os.path.join(build_dir, f"electrs-{version_clean}")
        
        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        
        # Clone or update source from GitHub
        if not os.path.exists(src_dir):
            log(f"\n📥 Cloning Electrs repository...\n")
            run_command(
                f"git clone --depth 1 --branch {version} {ELECTRS_REPO} {src_dir}",
                cwd=build_dir,
                env=env
            )
            log(f"✓ Source cloned to {src_dir}\n")
        else:
            log(f"✓ Source directory already exists: {src_dir}\n")
            log(f"📥 Updating to {version}...\n")
            run_command(f"git fetch --depth 1 origin tag {version}", cwd=src_dir, env=env)
            run_command(f"git checkout {version}", cwd=src_dir, env=env)
            log(f"✓ Updated to {version}\n")
        
        # Verify source integrity
        if not verify_source_integrity(src_dir, "Electrs", version):
            log("❌ User cancelled due to verification failure\n")
            raise RuntimeError("Source verification failed")
        
        log(f"\n🔧 Building with Cargo ({cores} jobs)...\n")
        log(f"Environment details:\n")
        log(f"  PATH: {env['PATH'][:150]}...\n")
        if 'LIBCLANG_PATH' in env:
            log(f"  LIBCLANG_PATH: {env['LIBCLANG_PATH']}\n")
        if 'RUSTFLAGS' in env:
            log(f"  RUSTFLAGS: {env['RUSTFLAGS']}\n")
        
        run_command(f"cargo build --release --jobs {cores}", cwd=src_dir, env=env)
        
        # Copy binary
        log(f"\n📋 Collecting binaries...\n")
        binary = os.path.join(src_dir, "target", "release", "electrs")
        
        if not os.path.exists(binary):
            raise RuntimeError(f"Electrs binary not found at expected location: {binary}")
        
        output_dir = os.path.join(build_dir, "binaries", f"electrs-{version_clean}")
        copied = copy_binaries(src_dir, output_dir, [binary])
        
        log(f"\n{'='*60}\n")
        log(f"✅ ELECTRS {version} COMPILED SUCCESSFULLY!\n")
        log(f"{'='*60}\n")
        log(f"\n📍 Binary location: {output_dir}/electrs\n\n")
        
        return output_dir

    except Exception as e:
        log(f"\n❌ Error compiling Electrs: {e}\n")
        import traceback
        log(f"\nFull traceback:\n{traceback.format_exc()}\n")
        raise

def compile_selected():
    """Main compilation function triggered by GUI button"""
    target = target_var.get()
    cores = cores_var.get()
    build_dir = build_dir_var.get()
    bitcoin_ver = bitcoin_version_var.get()
    electrs_ver = electrs_version_var.get()
    use_aggressive = aggressive_opts_var.get()

    def task():
        try:
            set_progress(0)
            compile_btn.config(state="disabled")
            
            # Show warning if aggressive optimizations are enabled
            if use_aggressive:
                response = messagebox.askyesno(
                    "Aggressive Optimizations Enabled",
                    "⚠️  WARNING: You have enabled aggressive optimizations (O3 + LTO)\n\n"
                    "These flags may:\n"
                    "• Increase build time significantly\n"
                    "• Potentially introduce bugs or instability\n"
                    "• May not work with all versions\n\n"
                    "Recommended for advanced users only.\n\n"
                    "Continue with aggressive optimizations?",
                    icon='warning'
                )
                if not response:
                    log("\n❌ User cancelled compilation due to aggressive optimization warning\n")
                    return
            
            # Validate versions are loaded
            if target in ["Bitcoin", "Both"]:
                if not bitcoin_ver or bitcoin_ver == "Loading...":
                    messagebox.showerror("Error", "Please wait for Bitcoin versions to load, or click Refresh")
                    return
            
            if target in ["Electrs", "Both"]:
                if not electrs_ver or electrs_ver == "Loading...":
                    messagebox.showerror("Error", "Please wait for Electrs versions to load, or click Refresh")
                    return
            
            output_dirs = []
            
            if target in ["Bitcoin", "Both"]:
                set_progress(10)
                output_dir = compile_bitcoin_source(bitcoin_ver, build_dir, cores, use_aggressive)
                output_dirs.append(output_dir)
                set_progress(50)
            
            if target in ["Electrs", "Both"]:
                set_progress(60 if target == "Both" else 10)
                output_dir = compile_electrs_source(electrs_ver, build_dir, cores, use_aggressive)
                output_dirs.append(output_dir)
                set_progress(100)
            
            set_progress(100)
            
            msg = f"✅ {target} compilation completed successfully!\n\n"
            msg += "Binaries saved to:\n"
            for d in output_dirs:
                msg += f"• {d}\n"
            
            messagebox.showinfo("Compilation Complete", msg)
            
        except Exception as e:
            log(f"\n❌ Compilation failed: {e}\n")
            messagebox.showerror("Compilation Failed", str(e))
        finally:
            compile_btn.config(state="normal")
            set_progress(0)

    threading.Thread(target=task, daemon=True).start()

# ================== GUI ==================
def create_gui():
    """Create and configure the main GUI window"""
    global root, target_var, cores_var, build_dir_var, bitcoin_version_var, electrs_version_var
    global bitcoin_combo, electrs_combo, log_text, progress_var, progress, compile_btn
    global bitcoin_status, electrs_status, aggressive_opts_var
    
    root = tk.Tk()
    root.title("Bitcoin & Electrs Compiler for macOS")
    root.geometry("900x850")
    
    # Prevent window from being created multiple times
    root.protocol("WM_DELETE_WINDOW", lambda: root.quit())
    
    # macOS specific: bring to front
    if platform.system() == 'Darwin':
        try:
            root.lift()
            root.attributes('-topmost', True)
            root.after_idle(root.attributes, '-topmost', False)
        except:
            pass
    
    # Header
    header = ttk.Label(
        root,
        text="Bitcoin Core & Electrs Compiler",
        font=("Arial", 16, "bold")
    )
    header.pack(pady=10)
    
    # Architecture info
    arch_text = f"Architecture: {ARCH.upper()}" + (
        " (Apple Silicon)" if ARCH == "apple_silicon" else " (Intel Mac)" if ARCH == "intel" else ""
    )
    arch_label = ttk.Label(root, text=arch_text, font=("Arial", 10))
    arch_label.pack()
    
    # Dependency check button
    dep_frame = ttk.Frame(root)
    dep_frame.pack(pady=10)
    ttk.Label(dep_frame, text="Step 1:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    ttk.Button(
        dep_frame,
        text="Check & Install Dependencies",
        command=check_dependencies
    ).pack(side="left")
    
    # Separator
    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=10)
    
    # Target selection
    target_frame = ttk.LabelFrame(root, text="Step 2: Select What to Compile", padding=10)
    target_frame.pack(fill="x", padx=20, pady=5)
    
    ttk.Label(target_frame, text="Target:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    target_var = tk.StringVar(value="Bitcoin")
    target_combo = ttk.Combobox(
        target_frame,
        values=["Bitcoin", "Electrs", "Both"],
        textvariable=target_var,
        state="readonly",
        width=15
    )
    target_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
    
    # CPU cores
    ttk.Label(target_frame, text="CPU Cores:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
    cores_var = tk.IntVar(value=max(1, multiprocessing.cpu_count() - 1))
    cores_spinbox = ttk.Spinbox(
        target_frame,
        from_=1,
        to=multiprocessing.cpu_count(),
        textvariable=cores_var,
        width=5
    )
    cores_spinbox.grid(row=0, column=3, sticky="w", padx=5, pady=5)
    ttk.Label(
        target_frame,
        text=f"(max: {multiprocessing.cpu_count()})",
        font=("Arial", 9)
    ).grid(row=0, column=4, sticky="w", padx=2, pady=5)
    
    # Build directory
    ttk.Label(target_frame, text="Build Directory:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    build_dir_var = tk.StringVar(value=DEFAULT_BUILD_DIR)
    build_entry = ttk.Entry(target_frame, textvariable=build_dir_var, width=40)
    build_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
    ttk.Button(
        target_frame,
        text="Browse",
        command=lambda: build_dir_var.set(filedialog.askdirectory(initialdir=build_dir_var.get()))
    ).grid(row=1, column=4, padx=5, pady=5)
    
    # Optimization options
    opt_frame = ttk.LabelFrame(root, text="Step 2.5: Optimization Settings", padding=10)
    opt_frame.pack(fill="x", padx=20, pady=5)
    
    aggressive_opts_var = tk.BooleanVar(value=False)
    aggressive_check = ttk.Checkbutton(
        opt_frame,
        text="⚡ Enable Aggressive Optimizations (O3 + LTO) - May break code, use with caution!",
        variable=aggressive_opts_var
    )
    aggressive_check.pack(anchor="w", padx=5, pady=5)
    
    opt_info = ttk.Label(
        opt_frame,
        text="ℹ️  Standard build uses O2 optimizations. Aggressive mode adds O3 and Link-Time Optimization.\n"
             "   Aggressive optimizations may significantly increase compile time and could introduce bugs.",
        font=("Arial", 9),
        foreground="gray"
    )
    opt_info.pack(anchor="w", padx=5, pady=(0, 5))
    
    # Version selection
    version_frame = ttk.LabelFrame(root, text="Step 3: Select Versions", padding=10)
    version_frame.pack(fill="x", padx=20, pady=5)
    
    # Bitcoin version
    ttk.Label(version_frame, text="Bitcoin Version:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    bitcoin_version_var = tk.StringVar(value="Loading...")
    bitcoin_combo = ttk.Combobox(
        version_frame,
        values=["Loading..."],
        textvariable=bitcoin_version_var,
        state="readonly",
        width=20
    )
    bitcoin_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
    ttk.Button(
        version_frame,
        text="Refresh",
        command=lambda: threading.Thread(target=refresh_bitcoin_versions, daemon=True).start()
    ).grid(row=0, column=2, padx=5, pady=5)
    
    # Electrs version
    ttk.Label(version_frame, text="Electrs Version:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    electrs_version_var = tk.StringVar(value="Loading...")
    electrs_combo = ttk.Combobox(
        version_frame,
        values=["Loading..."],
        textvariable=electrs_version_var,
        state="readonly",
        width=20
    )
    electrs_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
    ttk.Button(
        version_frame,
        text="Refresh",
        command=lambda: threading.Thread(target=refresh_electrs_versions, daemon=True).start()
    ).grid(row=1, column=2, padx=5, pady=5)
    
    # Progress bar
    progress_frame = ttk.Frame(root)
    progress_frame.pack(fill="x", padx=20, pady=10)
    ttk.Label(progress_frame, text="Progress:").pack(anchor="w")
    progress_var = tk.DoubleVar()
    progress = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
    progress.pack(fill="x", pady=5)
    
    # Log terminal
    log_frame = ttk.LabelFrame(root, text="Build Log", padding=5)
    log_frame.pack(fill="both", expand=True, padx=20, pady=5)
    
    log_text_frame = tk.Frame(log_frame)
    log_text_frame.pack(fill="both", expand=True)
    
    log_text = tk.Text(
        log_text_frame,
        height=15,
        wrap="none",
        bg="#1e1e1e",
        fg="#00ff00",
        font=("Courier", 10)
    )
    log_text.pack(side="left", fill="both", expand=True)
    
    scrollbar_y = ttk.Scrollbar(log_text_frame, command=log_text.yview)
    scrollbar_y.pack(side="right", fill="y")
    log_text.config(yscrollcommand=scrollbar_y.set)
    
    scrollbar_x = ttk.Scrollbar(log_frame, orient="horizontal", command=log_text.xview)
    scrollbar_x.pack(fill="x")
    log_text.config(xscrollcommand=scrollbar_x.set)
    
    # Compile button
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)
    compile_btn = ttk.Button(
        button_frame,
        text="🚀 Start Compilation",
        command=compile_selected
    )
    compile_btn.pack()
    
    # Status bar
    status_frame = ttk.Frame(root)
    status_frame.pack(fill="x", side="bottom")
    status_text = (
        f"System: macOS {platform.mac_ver()[0]} | "
        f"Arch: {ARCH} | "
        f"Homebrew: {BREW_PREFIX if BREW_PREFIX else 'Not Found'} | "
        f"CPUs: {multiprocessing.cpu_count()}"
    )
    status_label = ttk.Label(
        status_frame,
        text=status_text,
        relief="sunken",
        anchor="w"
    )
    status_label.pack(fill="x")
    
    # Initial log message
    log("=" * 60 + "\n")
    log("Bitcoin Core & Electrs Compiler\n")
    log("=" * 60 + "\n")
    log(f"System: macOS {platform.mac_ver()[0]}\n")
    log(f"Architecture: {ARCH}\n")
    log(f"Homebrew: {BREW_PREFIX if BREW_PREFIX else 'Not Found'}\n")
    log(f"CPU Cores: {multiprocessing.cpu_count()}\n")
    if is_pyinstaller():
        log(f"Running as: PyInstaller Bundle\n")
    log("=" * 60 + "\n\n")
    log("🔧 Features:\n")
    log("  • Architecture-specific optimizations\n")
    log("  • SHA256 source verification\n")
    log("  • Optional aggressive O3 + LTO optimizations\n\n")
    log("👉 Click 'Check & Install Dependencies' to begin\n\n")
    log("📝 Note: Both Bitcoin and Electrs now pull source from GitHub\n")
    log("🔐 Note: Source integrity is verified using git commit hashes\n\n")
    
    # Load versions after GUI is ready
    root.after(100, initial_version_load)
    
    return root

# ================== MAIN ==================
def main():
    """Main entry point with exception handling"""
    global root
    
    try:
        # Create the GUI
        root = create_gui()
        
        # Start the GUI event loop
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        # Log any uncaught exceptions
        error_msg = f"Fatal error: {e}\n"
        print(error_msg, file=sys.stderr)
        import traceback
        traceback.print_exc()
        
        # Try to show error dialog if possible
        try:
            messagebox.showerror(
                "Fatal Error",
                f"Application crashed:\n\n{e}\n\nCheck console for details."
            )
        except:
            pass
        
        sys.exit(1)

if __name__ == "__main__":
    # Prevent re-execution in frozen apps
    if is_pyinstaller():
        multiprocessing.freeze_support()
    
    main()
