#!/bin/bash
# Example: Convert a .deb package to .pkg.tar.zst
# Usage: bash examples/convert_deb.sh

set -e

echo "=== PkgForge DEB Conversion Example ==="

# Basic conversion
echo "1. Basic conversion:"
pkgforge convert example_1.0.0_amd64.deb

# Conversion with install
echo "2. Convert and install:"
pkgforge convert example_1.0.0_amd64.deb --install --yes

# Dry run (analyze without converting)
echo "3. Dry run:"
pkgforge convert example_1.0.0_amd64.deb --dry-run

# Custom output directory
echo "4. Custom output:"
pkgforge convert example_1.0.0_amd64.deb --output-dir /tmp/output

# With security signing
echo "5. Signed conversion:"
pkgforge convert example_1.0.0_amd64.deb --sign

# From URL
echo "6. Convert from URL:"
pkgforge convert https://example.com/package_1.0_amd64.deb --install

echo "Done!"
