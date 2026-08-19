"""Inspect the compatibility report for the converted test package."""
from pathlib import Path

from config import discover_tools
from core.package_analyzer import analyze_package
from core.compatibility_checker import run_compatibility_checks

tools = discover_tools()
pkg = Path("utest/out/native_build/pkgout/hello-1.0.0-1-x86_64.pkg.tar.zst")
meta = analyze_package(Path("utest/hello_1.0.0-1_amd64.deb"), tools)
report = run_compatibility_checks(pkg, meta.file_list, meta.depends, tools)
print(f"grade={report.grade} overall={report.overall.value}")
for c in report.checks:
    print(f"[{c.severity.value}] {c.name}: {c.message}")
    for d in c.details[:5]:
        print(f"    - {d}")
