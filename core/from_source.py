"""PkgForge — From-Source PKGBUILD Generation.

Auto-detects build system (cmake/meson/cargo/autotools/make/python),
extracts version from multiple sources, detects license, and generates
a complete PKGBUILD with proper dependency specification.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _extract_version_from_cargo(repo_dir: Path) -> str | None:
    """Extract version from Cargo.toml."""
    cargo_toml = repo_dir / "Cargo.toml"
    if not cargo_toml.exists():
        return None
    try:
        text = cargo_toml.read_text(encoding="utf-8", errors="ignore")
        # Match [package] section version = "1.2.3"
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except OSError:
        pass
    return None


def _extract_version_from_cmake(repo_dir: Path) -> str | None:
    """Extract version from CMakeLists.txt."""
    cmake = repo_dir / "CMakeLists.txt"
    if not cmake.exists():
        return None
    try:
        text = cmake.read_text(encoding="utf-8", errors="ignore")
        # project(name VERSION 1.2.3 ...)
        match = re.search(
            r'project\s*\([^)]*VERSION\s+([\d.]+)', text, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        # set(VERSION "1.2.3")
        match = re.search(
            r'set\s*\(\s*\w*VERSION\w*\s+["\']?([\d.]+)["\']?', text, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
    except OSError:
        pass
    return None


def _extract_version_from_meson(repo_dir: Path) -> str | None:
    """Extract version from meson.build."""
    meson = repo_dir / "meson.build"
    if not meson.exists():
        return None
    try:
        text = meson.read_text(encoding="utf-8", errors="ignore")
        # project('name', 'c', version: '1.2.3')
        match = re.search(r"version\s*:\s*['\"]([^'\"]+)['\"]", text)
        if match:
            return match.group(1).strip()
    except OSError:
        pass
    return None


def _extract_version_from_pyproject(repo_dir: Path) -> str | None:
    """Extract version from pyproject.toml."""
    pyproject = repo_dir / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        # [tool.poetry] version = "1.2.3"
        # or [project] version = "1.2.3"
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except OSError:
        pass
    return None


def _extract_version_from_file(repo_dir: Path) -> str | None:
    """Try extracting version from VERSION, version.txt, etc."""
    for vf in [
        repo_dir / "VERSION",
        repo_dir / "version.txt",
        repo_dir / "VERSION.txt",
        repo_dir / ".version",
        repo_dir / "version",
    ]:
        if vf.exists():
            try:
                v = vf.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[0].strip()
                if v:
                    return v
            except OSError:
                pass
    return None


def _detect_license(repo_dir: Path) -> str:
    """Detect license from LICENSE/COPYING files."""
    license_patterns = {
        "GPL-3.0-or-later": ["GPL-3", "GNU GENERAL PUBLIC LICENSE, Version 3"],
        "GPL-2.0-or-later": ["GPL-2", "GNU GENERAL PUBLIC LICENSE, Version 2"],
        "MIT": ["MIT License", "MIT LICENSE", "Permission is hereby granted, free of charge"],
        "Apache-2.0": ["Apache License, Version 2.0", "Apache-2.0"],
        "BSD-2-Clause": ["BSD 2-Clause", "Redistribution and use in source and binary forms"],
        "BSD-3-Clause": ["BSD 3-Clause"],
        "LGPL-2.1-or-later": ["LGPL-2.1", "GNU LESSER GENERAL PUBLIC LICENSE"],
        "LGPL-3.0-or-later": ["LGPL-3", "GNU LESSER GENERAL PUBLIC LICENSE, Version 3"],
        "MPL-2.0": ["Mozilla Public License", "MPL-2.0"],
        "ISC": ["ISC License", "ISC LICENSE"],
        "Zlib": ["zlib License"],
        "Unlicense": ["Unlicense", "This is free and unencumbered software"],
    }

    license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENSE.MD",
        "COPYING", "COPYING.txt", "COPYING.md",
    ]

    for lf_name in license_files:
        lf = repo_dir / lf_name
        if lf.exists():
            try:
                content = lf.read_text(encoding="utf-8", errors="ignore")[:2000]
                for spdx_id, patterns in license_patterns.items():
                    for pattern in patterns:
                        if pattern.lower() in content.lower():
                            return spdx_id
            except OSError:
                pass

    # Also check Cargo.toml for Rust projects
    cargo = repo_dir / "Cargo.toml"
    if cargo.exists():
        try:
            text = cargo.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'license\s*=\s*["\']([^"\']+)["\']', text)
            if match:
                return match.group(1).strip()
        except OSError:
            pass

    # Check package.json for JS projects
    pkg_json = repo_dir / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text(encoding="utf-8", errors="ignore"))
            lic = data.get("license", "")
            if isinstance(lic, str) and lic:
                return lic
        except (OSError, ValueError):
            pass

    return "GPL-3.0-or-later"  # safe default


def _detect_python_package(repo_dir: Path) -> bool:
    """Check if this is a Python package."""
    return (
        (repo_dir / "setup.py").exists()
        or (repo_dir / "setup.cfg").exists()
        or (repo_dir / "pyproject.toml").exists()
    )


def _detect_node_package(repo_dir: Path) -> bool:
    """Check if this is a Node.js package."""
    pkg_json = repo_dir / "package.json"
    if not pkg_json.exists():
        return False
    try:
        import json
        data = json.loads(pkg_json.read_text(encoding="utf-8", errors="ignore"))
        return "scripts" in data or "main" in data or "bin" in data
    except (OSError, ValueError):
        return False


def _detect_binary_name(repo_dir: Path, proj_name: str) -> str:
    """Try to detect the main binary name from the project."""
    # Check Cargo.toml for [[bin]] or [package] name
    cargo = repo_dir / "Cargo.toml"
    if cargo.exists():
        try:
            text = cargo.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
            if match:
                return match.group(1).strip()
        except OSError:
            pass

    # Check CMakeLists.txt for executable()
    cmake = repo_dir / "CMakeLists.txt"
    if cmake.exists():
        try:
            text = cmake.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'add_executable\s*\(\s*(\w+)', text)
            if match:
                return match.group(1).strip()
        except OSError:
            pass

    # Check package.json bin field
    pkg_json = repo_dir / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text(encoding="utf-8", errors="ignore"))
            bin_field = data.get("bin", {})
            if isinstance(bin_field, dict) and bin_field:
                return next(iter(bin_field.keys()))
            elif isinstance(bin_field, str):
                return bin_field
        except (OSError, ValueError):
            pass

    return proj_name


def generate_pkgbuild_from_source(
    name: str,
    repo_url: str,
    build_system: str,
    repo_dir: Path,
) -> str:
    """Generate a complete PKGBUILD from source repository.

    Detects version from Cargo.toml/CMakeLists.txt/meson.build/pyproject.toml/VERSION files.
    Detects license from LICENSE/COPYING files.
    Generates proper makedepends based on build system.
    """
    # Version detection (priority order)
    version = (
        _extract_version_from_cargo(repo_dir)
        or _extract_version_from_cmake(repo_dir)
        or _extract_version_from_meson(repo_dir)
        or _extract_version_from_pyproject(repo_dir)
        or _extract_version_from_file(repo_dir)
        or "0.0.1"
    )

    # License detection
    license_id = _detect_license(repo_dir)

    # Description from README
    description = f"{name} — kaynaktan derlenen paket"
    for readme_name in ["README.md", "README.rst", "README", "readme.md"]:
        readme = repo_dir / readme_name
        if readme.exists():
            try:
                for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    # Skip markdown headers, image links, badges
                    if not line:
                        continue
                    if line.startswith(("#", "!", "[", "<", "---", "===")):
                        continue
                    if line.startswith("![") or line.startswith("[!["):
                        continue
                    if len(line) > 15 and len(line) < 120:
                        description = line
                        break
            except OSError:
                pass
            break

    # Escape for PKGBUILD single quotes
    description = description.replace("'", "'\\''")

    # Build system detection and makedepends
    makedepends_base = ["git"]
    if build_system == "cmake":
        makedepends_base.extend(["cmake", "gcc"])
        build_cmds = (
            "    cmake -B build -DCMAKE_INSTALL_PREFIX=/usr \\\n"
            "          -DCMAKE_BUILD_TYPE=Release\n"
            "    cmake --build build"
        )
        install_cmds = '    DESTDIR="$pkgdir" cmake --install build'
    elif build_system == "meson":
        makedepends_base.extend(["meson", "gcc"])
        build_cmds = (
            "    meson setup build --prefix=/usr --buildtype=release\n"
            "    meson compile -C build"
        )
        install_cmds = '    DESTDIR="$pkgdir" meson install -C build'
    elif build_system == "cargo":
        makedepends_base.extend(["rust", "cargo"])
        binary_name = _detect_binary_name(repo_dir, name)
        build_cmds = "    cargo build --release --locked"
        install_cmds = f'    install -Dm755 target/release/{binary_name} \\\n        "$pkgdir/usr/bin/{binary_name}"'
    elif build_system == "autotools":
        makedepends_base.extend(["gcc", "autoconf", "automake"])
        build_cmds = (
            "    ./configure --prefix=/usr --sysconfdir=/etc\n"
            "    make"
        )
        install_cmds = '    make DESTDIR="$pkgdir" install'
    elif build_system == "python":
        makedepends_base.extend(["python-build", "python-installer", "python-setuptools"])
        build_cmds = "    python -m build --wheel --no-isolation"
        install_cmds = '    python -m installer --destdir="$pkgdir" dist/*.whl'
    elif _detect_node_package(repo_dir):
        makedepends_base.extend(["nodejs", "npm"])
        build_cmds = "    npm ci\n    npm run build"
        install_cmds = (
            '    mkdir -p "$pkgdir/usr/lib/$pkgname"\n'
            '    cp -r dist/* "$pkgdir/usr/lib/$pkgname/"\n'
            '    mkdir -p "$pkgdir/usr/bin"\n'
            f'    ln -s /usr/lib/$pkgname/main.js "$pkgdir/usr/bin/$pkgname"'
        )
    else:
        makedepends_base.append("gcc")
        build_cmds = "    make"
        install_cmds = '    make DESTDIR="$pkgdir" install'

    makedepends_str = " ".join(f"'{d}'" for d in makedepends_base)

    # Generate source URL — try multiple patterns
    source_line = f'        "$url/archive/v$pkgver.tar.gz"'

    pkgbuild = f"""# Maintainer: PkgForge <noreply@pkgforge.app>

pkgname={name}
pkgver={version}
pkgrel=1
pkgdesc='{description}'
arch=('x86_64')
url='{repo_url}'
license=('{license_id}')
depends=()
makedepends=({makedepends_str})

source=("$url/archive/v$pkgver.tar.gz")
sha256sums=('SKIP')

prepare() {{
    cd "$pkgname-$pkgver" || cd "$srcdir/$pkgname-$pkgver"
}}

build() {{
    cd "$pkgname-$pkgver" || cd "$srcdir/$pkgname-$pkgver"

{build_cmds}
}}

package() {{
    cd "$pkgname-$pkgver" || cd "$srcdir/$pkgname-$pkgver"

{install_cmds}
}}
"""
    return pkgbuild
