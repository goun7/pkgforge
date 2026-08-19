# PkgForge

> **Modern, Sandboxed `.deb` and `.rpm` Package Converter & Lifecycle Manager for Arch Linux & CachyOS**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Build Status](https://img.shields.io/badge/tests-39%20passed-brightgreen)](tests/)

**PkgForge** converts Debian (`.deb`) and RedHat (`.rpm`) packages into Arch Linux compatible `.pkg.tar.zst` packages. It features a **high-speed pure Python native converter**, **Bubblewrap sandbox isolation**, **full Headless CLI**, **PyQt6 GUI**, **URL direct downloading**, **package lifecycle management (uninstall & rollback)**, and **upstream update tracking**.

---

## 🎯 Key Features

- **⚡ Fast Pure Python Native Converter**: Converts `.deb` packages directly into `PKGBUILD` and `.pkg.tar.zst` in seconds without slow external scripts.
- **🛡️ 11 Security Layers & Bubblewrap Sandbox**: Executes `makepkg` and conversions inside isolated `bwrap` sandboxes with strict MIME, GPG, SHA-256, and Path Traversal checks.
- **💻 Dual Interface (Headless CLI + PyQt6 GUI)**: Seamless operation in terminal or rich graphical desktop mode.
- **🌐 Direct URL Conversion**: Download and convert packages directly from HTTP/HTTPS links (`pkgforge convert https://...`).
- **⏪ Lifecycle & Rollback Management**: Uninstall converted packages via `pacman -R` or rollback to previous saved backups stored in `~/.config/pkgforge/backups/`.
- **📡 Upstream Auto-Tracker**: Lightweight HTTP header inspector (`ETag` / `Last-Modified`) to check if installed packages have new releases.
- **🔀 Cross-Check Engine**: Compares versions across Local files, AUR, and Flatpak using pacman's `vercmp` to recommend the newest release.

---

## 🚀 Quick Installation

### Option 1: Automated System Installer (Recommended)

Clone the repository and run the automated system installer:

```bash
git clone https://github.com/pkgforge/pkgforge.git
cd pkgforge
sudo ./scripts/install.sh
```

This installs:
- Executable binary wrapper to `/usr/local/bin/pkgforge`
- Desktop shortcut to `/usr/share/applications/org.pkgforge.app.desktop`
- SVG application icon to `/usr/share/icons/hicolor/scalable/apps/pkgforge.svg`
- Shell completion scripts for **Bash** and **Zsh**

To uninstall:
```bash
sudo ./scripts/uninstall.sh
```

---

### Option 2: AUR Package (`pkgforge-git`)

If installing via an AUR helper:

```bash
paru -S pkgforge-git
# or
yay -S pkgforge-git
```

---

## 💻 CLI Usage

PkgForge includes a complete headless CLI interface:

```bash
# Convert a local package
pkgforge convert package.deb

# Convert and automatically install
pkgforge convert package.deb --install

# Convert directly from a URL
pkgforge convert https://example.com/software_amd64.deb --install

# List conversion and installation history
pkgforge list

# Uninstall an installed package
pkgforge remove package-name

# Rollback a package to its previous saved backup
pkgforge rollback package-name

# Check saved package URLs for upstream updates
pkgforge check-updates

# Launch GUI interface from terminal
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

To run the automated test suite (39 unit tests):

```bash
python -m unittest discover -s tests
```

---

## 📜 License

Distributed under the **GNU General Public License v3.0 or later** (GPL-3.0-or-later). See [LICENSE](LICENSE) for details.
