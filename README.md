# PkgForge

> **Modern, Sandboxed `.deb` and `.rpm` Package Converter & Lifecycle Manager for Arch Linux & CachyOS**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-449%20passed-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-41%25-yellow)](#)
[![mypy](https://img.shields.io/badge/mypy-0%20errors-brightgreen)](#)
[![Security](https://img.shields.io/badge/bandit-0%20high-brightgreen)](#)

**PkgForge** converts Debian (`.deb`) and RedHat (`.rpm`) packages into Arch Linux compatible `.pkg.tar.zst` packages. It features a **high-speed pure Python native converter**, **Bubblewrap sandbox isolation**, **full Headless CLI**, **PyQt6 GUI**, **URL direct downloading**, **package lifecycle management (uninstall & rollback)**, and **upstream update tracking**.

---

## 🎯 Key Features

- **⚡ Fast Pure Python Native Converter**: Converts `.deb` packages directly into `PKGBUILD` and `.pkg.tar.zst` in seconds without slow external scripts.
- **🛡️ 12 Security Layers & Bubblewrap Sandbox**: Executes `makepkg` and conversions inside isolated `bwrap` sandboxes with strict MIME, GPG, SHA-256, Path Traversal, and **ClamAV malware scanning** checks.
- **💻 Dual Interface (Headless CLI + PyQt6 GUI)**: CLI runs without PyQt6 or a display server. GUI mode requires PyQt6 (`sudo pacman -S python-pyqt6`).
- **🌐 Direct URL Conversion**: Download and convert packages directly from HTTP/HTTPS links (`pkgforge convert https://...`).
- **📸 Atomic Snapshot Rollback**: Automatically takes Btrfs/ZFS filesystem snapshots before installation for instant atomic rollback.
- **🐳 OCI Container Export**: Convert any `.deb`/`.rpm` to a portable OCI container image (`pkgforge convert --to-oci`).
- **📦 Binary Delta Updates**: Use xdelta3 to download only the diff for faster updates (`pkgforge convert --delta`).
- **⏪ Lifecycle & Rollback Management**: Uninstall converted packages via `pacman -R` or rollback to previous saved backups stored in `~/.config/pkgforge/backups/`.
- **📡 Upstream Auto-Tracker**: Compares stored `ETag`/`Last-Modified` headers against current values to detect actual content changes.
- **🔀 Cross-Check Engine**: Compares versions across Local files, AUR, and Flatpak using pacman's `vercmp` to recommend the newest release.

---

## 🚀 Quick Installation

### Option 1: Automated System Installer (Recommended)

Clone the repository and run the automated system installer:

```bash
git clone https://github.com/goun7/pkgforge.git
cd pkgforge
sudo ./scripts/install.sh
```

This installs:
- The application tree to `/usr/lib/pkgforge`
- Executable wrapper to `/usr/local/bin/pkgforge`
- Desktop shortcut to `/usr/share/applications/pkgforge.desktop`
- SVG application icon to `/usr/share/icons/hicolor/scalable/apps/pkgforge.svg`
- Polkit policy to `/usr/share/polkit-1/actions/org.pkgforge.app.policy`
- Shell completion scripts for **Bash** and **Zsh**

To uninstall:
```bash
sudo ./scripts/uninstall.sh
```

---

### Option 2: pip / wheel

```bash
pip install dist/pkgforge-1.1.0-py3-none-any.whl   # after: python -m build --wheel
# or from a checkout:
pip install .
```

> **AUR note:** An AUR package is planned but **not yet published**. Until it
> exists, use Option 1 (installer script) or Option 2 (pip/wheel).

---

## 💻 CLI Usage

PkgForge includes a complete headless CLI interface (no PyQt6 required for CLI):

```bash
# Core conversion
pkgforge convert package.deb                    # Convert DEB → Arch
pkgforge convert package.rpm --install           # Convert + install
pkgforge convert https://example.com/pkg.deb    # Convert from URL
pkgforge convert package.deb --to-oci            # Export as OCI container
pkgforge convert package.deb --delta             # Binary delta download
pkgforge convert package.deb --sign              # Auto-sign with GPG
pkgforge convert package.deb --resolve-deps      # Auto-resolve missing deps
pkgforge convert package.deb --verify-build      # Reproducible build check

# Package lifecycle
pkgforge list                                    # Conversion history
pkgforge remove package-name                     # Uninstall package
pkgforge rollback package-name                   # Restore backup
pkgforge check-updates                           # Check upstream updates
pkgforge check-updates --watch                   # Watch mode (polls every 5min)

# Cross-conversion
pkgforge rpm-to-deb package.rpm                  # RPM → DEB
pkgforge flatpak-export org.mozilla.firefox      # Flatpak → DEB
pkgforge appimage-export app.AppImage            # AppImage → DEB
pkgforge from-source https://github.com/repo     # Generate PKGBUILD from source

# Security & Analysis
pkgforge quality package.pkg.tar.zst             # Quality score (A-F)
pkgforge abi-check package.pkg.tar.zst           # GLIBC/GLIBCXX symbol check
pkgforge scan-image image.tar                    # OCI image security scan
pkgforge sign package.pkg.tar.zst                # GPG sign package
pkgforge verify package.pkg.tar.zst              # Verify GPG signature
pkgforge provenance package.pkg.tar.zst          # SLSA provenance check

# System Management
pkgforge health                                  # Health dashboard
pkgforge graph package-name                      # Dependency graph
pkgforge audit                                   # Audit trail + anomaly detection
pkgforge snapshot-cleanup --install              # Auto-cleanup old snapshots
pkgforge benchmark --quick                       # Performance benchmarks
pkgforge publish package.pkg.tar.zst             # Publish to AUR
pkgforge verify-rollback                         # Test rollback mechanism
pkgforge --clear-cache                           # Clear offline cache

# GUI (requires PyQt6)
pkgforge gui
```

---

## 🖼️ GUI Features

Launch the graphical interface via `pkgforge gui` or your application launcher:

- **Drag-and-Drop Drop Zone**: Drop `.deb` or `.rpm` files directly onto the app.
- **Multi-Package Queue Sidebar**: Process multiple packages sequentially.
- **🌐 Link Input Dialog**: Click the globe icon to paste package URLs.
- **📋 History & Package Manager**: Click the clipboard icon to view converted packages, uninstall (`pacman -R`), or rollback (`pacman -U`).
- **📡 Upstream Update Check**: Click the antenna icon to scan for package updates.
- **🌙 Dark/Light Theme Support**: Automatic Breeze / KDE dark and light mode adaptation.

---

## 🔒 Security Architecture

PkgForge runs a layered set of checks before installing any converted archive.
We are deliberate about what each layer *does* and *does not* guarantee — a
converter can never make a genuinely malicious package safe, so the goal is to
**surface risk and require review**, not to promise absolute safety.

| # | Security Layer | Description |
|---|----------------|-------------|
| 1 | **MIME Type Validation** | Strict `file --mime-type` checking for genuine `.deb` / `.rpm` archives |
| 2 | **GPG Signature Detection** | Detects embedded signatures (presence check — **not** a trust-chain verification, since third-party packages are rarely signed against a known keyring) |
| 3 | **SHA-256 Integrity** | Computes the file hash; for URL downloads it is **verified** against a caller-supplied checksum when provided |
| 4 | **Path Traversal & Symlink Shield** | Rejects archives containing `../` escapes and extracted symlinks that point outside the build tree |
| 5 | **HTTPS-Only Downloads** | URL downloads require HTTPS by default (plain `http://` is opt-in via the `allow_insecure_http` setting) to prevent MITM tampering |
| 6 | **Bubblewrap Sandbox** | Runs `makepkg` inside restricted `bwrap` container mounts with `--unshare-net` |
| 7 | **Namcap Static Analysis** | Runs Arch Linux `namcap` static analysis (quality/packaging lint) |
| 8 | **Dependency Resolution** | Resolves required packages and shared libraries dynamically via `pacman -Fq` |
| 9 | **File Conflict Detection** | Scans the system via `pacman -Qo` to prevent file collisions |
| 10 | **Shared Library Audit** | `ldd` analysis to detect missing ELF shared objects and glibc requirements |
| 11 | **Polkit Privilege Gate** | Privileged installation runs exclusively via `pkexec`, with an explicit confirmation step (`--yes` to bypass in CLI) |
| 12 | **Orphan Cleanup GC** | Automated purge of stale `/tmp/pkgforge_*` directories on startup |

> ⚠️ **Trust note:** The sandbox protects the *build* step. The final
> `pacman -U` installs files onto your real system as root. Always review the
> compatibility report and the file list before installing packages from
> untrusted sources.

---

## 🧪 Running Tests

To run the automated test suite (449 tests, requires dev dependencies):

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q --timeout=120
```

Current status: **449 passed, 12 skipped** · **47% line coverage** on `core/` ·
CI gate enforces ≥35%.

---

## 📜 License

Distributed under the **GNU General Public License v3.0 or later** (GPL-3.0-or-later). See [LICENSE](LICENSE) for details.
