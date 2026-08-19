# PkgForge API Reference

## CLI Commands

```
pkgforge convert <file_or_url> [OPTIONS]
pkgforge list
pkgforge remove <package>
pkgforge rollback <package>
pkgforge check-updates
pkgforge gui
pkgforge flatpak-export <app-id> [--list] [--branch stable]
pkgforge appimage-export <file>
pkgforge rpm-to-deb <rpm-file>
pkgforge provenance <package>
pkgforge benchmark [--bench-file <file>] [--quick]
pkgforge sign <package> [--key <gpg-key>]
pkgforge verify <package>
pkgforge graph <package> [--files] [--format ascii|mermaid]
pkgforge audit [--from YYYY-MM-DD] [--to YYYY-MM-DD]
pkgforge scan-image <image>
pkgforge from-source <git-url> [-o output-dir]
```

### Global Options

| Flag | Description |
|------|-------------|
| `-f, --file` | Pre-select files for GUI |
| `-l, --lang` | Language (tr/en) |
| `-t, --theme` | Theme (dark/light/system) |
| `-v, --version` | Show version |
| `--check-deps` | Check system dependencies |
| `--install-deps` | Auto-install missing dependencies |

### Convert Options

| Flag | Description |
|------|-------------|
| `-i, --install` | Install after conversion |
| `-y, --yes` | Skip install confirmation |
| `--dry-run` | Convert only, never install |
| `-o, --output-dir` | Output directory |
| `--to-oci` | Export as OCI container image |
| `--oci-tag` | OCI image tag |
| `--delta` | Use binary delta for download |
| `--verify-build` | Verify reproducible build |
| `--sign` | Auto-sign with GPG |
| `--sign-key` | GPG key path for auto-sign |

## Core Modules

### `core/package_analyzer.py`

```python
from core.package_analyzer import analyze_package
from config import discover_tools

tools = discover_tools()
meta = analyze_package(Path("package.deb"), tools)

# meta.name        — Package name
# meta.version     — Package version
# meta.arch_mapped — Mapped architecture (x86_64, any)
# meta.file_list   — List of files in package
# meta.depends     — List of dependencies
# meta.package_type — "deb" or "rpm"
```

### `core/security.py`

```python
from core.security import (
    validate_mime_type,      # str → raises ValueError if invalid
    validate_file_size,      # (path, min, max_mb) → raises ValueError
    sha256_hash,             # Path → hex str
    check_path_traversal,    # list[str] → list[str] of offending paths
    check_compression_bomb,  # (path, tools) → str | None (warning)
    safe_run,                # subprocess.run wrapper with timeout
    is_valid_package_name,   # str → bool
)
```

### `core/provenance.py`

```python
from core.provenance import create_provenance, save_provenance, load_provenance, verify_provenance

prov = create_provenance(
    source_file=Path("input.deb"),
    source_url="https://example.com/app.deb",
    package_name="myapp",
    package_type="deb",
)
prov_path = save_provenance(prov, Path("output.provenance.json"))
valid, msg = verify_provenance(prov)
```

### `core/dep_graph.py`

```python
from core.dep_graph import build_dep_graph, build_file_dep_graph

# Dependency graph from installed package
graph = build_dep_graph(Path("/var/cache/pacman/pkg/app-1.0.pkg.tar.zst"))
print(graph.to_ascii())    # ASCII tree
print(graph.to_mermaid())  # Mermaid flowchart
stats = graph.stats()      # {total, installed, missing, max_depth}

# File-level shared library graph
graph = build_file_dep_graph(Path("app-1.0.pkg.tar.zst"))
```

### `core/benchmark.py`

```python
from core.benchmark import run_benchmarks

report = run_benchmarks(test_file=Path("test.deb"), quick=False)
print(report.summary())  # Formatted benchmark results
report.passed            # bool
```

### `core/package_signing.py`

```python
from core.package_signing import sign_package, verify_signature

ok, msg = sign_package(Path("package.pkg.tar.zst"))
info = verify_signature(Path("package.pkg.tar.zst"))
# info.valid, info.signer, info.key_id, info.key_fingerprint
```

### `core/malware_scanner.py`

```python
from core.malware_scanner import scan_with_clamav, is_clamav_available

if is_clamav_available():
    ok, msg = scan_with_clamav(Path("package.deb"))
```

### `core/snapshot_manager.py`

```python
from core.snapshot_manager import SnapshotManager, detect_backend

backend = detect_backend()  # "btrfs" | "zfs" | "none"
if backend != "none":
    mgr = SnapshotManager(backend)
    snap_id = mgr.create_snapshot("before-install")
    ok = mgr.rollback(snap_id)
```

### `core/rpm_to_deb_converter.py`

```python
from core.rpm_to_deb_converter import is_rpm_to_deb_available, rpm_to_deb

if is_rpm_to_deb_available():
    ok, msg, deb_path = rpm_to_deb(Path("app.rpm"), Path("/output"))
```

### `core/oci_builder.py`

```python
from core.oci_builder import build_oci_image

ok, msg, oci_path = build_oci_image(
    Path("package.pkg.tar.zst"),
    tools,
    tag="myapp:latest",
)
```

### `core/delta_updater.py`

```python
from core.delta_updater import create_delta, apply_delta, download_with_delta

# Create delta between two files
ok = create_delta(Path("old.deb"), Path("new.deb"), Path("delta.xdelta"))

# Download with delta
file_path, used_delta = download_with_delta(
    url="https://example.com/new.deb",
    dest=Path("/tmp/new.deb"),
    old_file=Path("/tmp/old.deb"),
)
```

### `core/reproducible_build.py`

```python
from core.reproducible_build import verify_reproducible

result = verify_reproducible(Path("package.pkg.tar.zst"), tools)
# result.verified — bool
# result.detail   — description
```

### `core/cli_bridge.py`

```python
from core.cli_bridge import convert_deb_sync, convert_rpm_sync

# Synchronous conversion (for CLI, no Qt event loop needed)
result = convert_deb_sync(
    deb_path=Path("app.deb"),
    output_dir=Path("/output"),
    tools=discover_tools(),
    progress_callback=lambda line: print(line),
)
# result.success — bool
# result.message — str
# result.output_pkg — str (path to .pkg.tar.zst)
```
