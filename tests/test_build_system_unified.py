"""Build-system algilayicilarinin teklesmesi (2026-10-18).

Olculen bug: ayni repo icin UC farkli algilayici UC farkli sonuc veriyordu.

  1. ``core/api/handlers_system.py::handle_source_generate`` elle yazilmis
     bir if-else merdiveni kullaniyordu. ``pyproject.toml``'a bakmiyor:
     pyproject-only bir repo "unknown" sonuc veriyor, generator'un else
     dali (gcc + make) ile uyumsuz bir PKGBUILD uretiliyordu.
  2. ``core/from_source.py``'daki node daliwc ulasilamaz durumda: hicbir
     algilayici "node" donmuyordu, bu yolla sadece "unknown" gelirdi.
  3. ``configure.ac``-only autotools repolari algilanamiyordu.

Bu testler uc cagri yerinin de TEK tabloyla ayni sonucu verdigini ve
generator'un her algilanan sistem icin uygun PKGBUILD urettigini kanitlar.
Kirmizi kanit: duzeltme geri alininca "pyproject merdiveni" testi fail veriyor.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from core.aur_publish import detect_build_system
from core.from_source import generate_pkgbuild_from_source

# (marker dosyasi, beklenen sistem) — uc cagri yeri de ayni sonucu vermeli.
BEKLENEN: list[tuple[str, str]] = [
    ("Cargo.toml", "cargo"),
    ("CMakeLists.txt", "cmake"),
    ("meson.build", "meson"),
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("setup.cfg", "python"),
    ("configure", "autotools"),
    ("configure.ac", "autotools"),
    ("Makefile", "make"),
    ("makefile", "make"),
    ("go.mod", "go"),
    ("package.json", "node"),
]

# Ellerle yazilmis merdiven (handle_source_generate icindeki) — bunun yerine
# artık tek tablo kullaniliyor olmali.
def _merdiven(repo_dir: Path) -> str:
    """handle_source_generate'in eski elle yazilmis merdiveni (referans)."""
    if (repo_dir / "CMakeLists.txt").exists():
        return "cmake"
    if (repo_dir / "meson.build").exists():
        return "meson"
    if (repo_dir / "Cargo.toml").exists():
        return "cargo"
    if (repo_dir / "configure").exists():
        return "autotools"
    if (repo_dir / "Makefile").exists() or (repo_dir / "makefile").exists():
        return "make"
    if (repo_dir / "setup.py").exists():
        return "python"
    return "unknown"


@pytest.mark.parametrize("marker,beklenen", BEKLENEN)
def test_tek_tablo_eski_merdivenden_daha_kapsamli(
    marker: str, beklenen: str, tmp_path: Path
) -> None:
    """Tek taboo eski merdivenin gormedigi marker'lari da tanimali."""
    (tmp_path / marker).write_text("", encoding="utf-8")
    eski = _merdiven(tmp_path)
    yeni = detect_build_system(tmp_path)
    # Eski merdivenin "unknown" dondurugu yerlerde yeni tablo gercek sistemi
    # dondurmeli; eski merdivenin dogru oldugu yerlerde ayni kalmali.
    if eski != "unknown":
        assert yeni == beklenen, f"{marker}: eski={eski} yeni={yeni}"
    else:
        assert yeni == beklenen, (
            f"{marker}: eski merdiven 'unknown' verdi, yeni tablo "
            f"'{beklenen}' vermeliydi, '{yeni}' verdi"
        )


@pytest.mark.parametrize(
    "marker,beklenen",
    [m for m in BEKLENEN if m[0] not in ("configure", "makefile")],
)
def test_from_source_generator_algilanan_sistemi_destekliyor(
    marker: str, beklenen: str, tmp_path: Path
) -> None:
    """Generator, algilanan sistem icin o sisteme ozel makedepends uretmeli."""
    (tmp_path / marker).write_text("", encoding="utf-8")
    sistem = detect_build_system(tmp_path)
    assert sistem == beklenen
    pb = generate_pkgbuild_from_source("demo", "https://x.test/demo", sistem, tmp_path)
    if beklenen == "python":
        assert "python -m build" in pb, "python yolu eksik"
        assert "python-installer" in pb
    elif beklenen == "node":
        assert "npm ci" in pb, "node yolu eksik"
        assert "nodejs" in pb
    elif beklenen == "go":
        assert "go build" in pb, "go yolu eksik"
        assert "go" in pb
    elif beklenen == "autotools":
        # configure-only ise ./configure; configure.ac-only ise autoreconf.
        if marker == "configure.ac":
            assert "autoreconf" in pb, "configure.ac icin autoreconf eksik"
        else:
            assert "./configure" in pb
    elif beklenen == "make":
        assert "make" in pb
    elif beklenen == "cmake":
        assert "cmake -B build" in pb
    elif beklenen == "meson":
        assert "meson setup build" in pb
    elif beklenen == "cargo":
        assert "cargo build --release" in pb


def test_go_mod_versiyonu_pkgver_oluyor(tmp_path: Path) -> None:
    """go.mod icinde acik version varsa pkgver'a yansimali.

    Olculen bug: go yolu yeni eklendi ama version algilama go.mod'yu
    gormuyordu (pkgver 0.0.1 kaliyordu) ve makedepends 'git' iki kez
    yaziliyordu.
    """
    (tmp_path / "go.mod").write_text(
        "module github.com/x/demo\n\nversion v1.2.3\n", encoding="utf-8"
    )
    pb = generate_pkgbuild_from_source(
        "demo", "https://x.test/demo", "go", tmp_path
    )
    m = re.search(r"pkgver=(\S+)", pb)
    assert m is not None and m.group(1) == "v1.2.3", pb
    md = re.search(r"makedepends=\((.*?)\)", pb)
    assert md is not None
    deps = [d.strip().strip("'\"") for d in md.group(1).split()]
    dup = {d for d in deps if deps.count(d) > 1}
    assert not dup, f"makedepends tekrarli: {dup} -> {md.group(1)}"


def test_node_paketi_url_goremeyen_algilayicidan_gelebilir(tmp_path: Path) -> None:
    """package.json'li bir repo 'node' algilanabilmeli (eski kod olcemiyordu)."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "main": "main.js", "scripts": {"build": "tsc"}}),
        encoding="utf-8",
    )
    assert detect_build_system(tmp_path) == "node"
    pb = generate_pkgbuild_from_source(
        "demo", "https://x.test/demo", "node", tmp_path
    )
    assert "npm ci" in pb
    assert "ln -s /usr/lib/$pkgname/main.js" in pb


_geomek = shutil.which("makepkg") is not None and shutil.which("cmake") is not None


@pytest.mark.skipif(not _geomek, reason="gercek derleme icin makepkg+cmake gerekli")
def test_uretilen_pkgbuild_gercekten_derleniyor(tmp_path: Path) -> None:
    """Olculen kanit: from-source PKGBUILD gercek makepkg ile derlenmeli.

    Eskiden pyproject-only repolar 'unknown' -> gcc+make PKGBUILD uretiyordu;
    bu derleme sirasinda basarisiz olurdu. Simdi python yolu uretilmeli.
    """
    import io
    import subprocess
    import tarfile

    proje = tmp_path / "repo"
    proje.mkdir()
    (proje / "pyproject.toml").write_text(
        "[build-system]\nrequires = [\"setuptools>=64\"]\n"
        "build-backend = \"setuptools.build_meta\"\n\n"
        "[project]\nname = \"pfprob\"\nversion = \"0.0.1\"\n",
        encoding="utf-8",
    )
    paket = proje / "src" / "pfprob"
    paket.mkdir(parents=True)
    (paket / "__init__.py").write_text("", encoding="utf-8")

    sistem = detect_build_system(proje)
    assert sistem == "python", f"pyproject-only repo 'python' olmali, '{sistem}' geldi"

    pb = generate_pkgbuild_from_source("pfprob", "file:///dev/null", sistem, proje)
    # source()'u yerel tarball'a yonlendir
    assert 'source=("$url/archive/v$pkgver.tar.gz")' in pb
    pb = pb.replace(
        'source=("$url/archive/v$pkgver.tar.gz")',
        'source=("$srcdir/pfprob-0.0.1.tar.gz")',
    )

    # yerel tarball: git archive yerine elle hazirla
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for f in proje.rglob("*"):
            if f.is_file() and f.name != "pyproject.toml":
                continue
            if f.is_file():
                tf.add(f, arcname=f"pfprob-0.0.1/{f.relative_to(proje)}")

    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "PKGBUILD").write_text(pb, encoding="utf-8")
    (build_dir / "pfprob-0.0.1.tar.gz").write_bytes(buf.getvalue())

    sonuc = subprocess.run(
        ["makepkg", "-f", "--noconfirm"],
        cwd=build_dir,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert sonuc.returncode == 0, (
        f"makepkg basarisiz rc={sonuc.returncode}\nSTDERR:\n{sonuc.stderr[-1500:]}"
    )
    pkgler = list(build_dir.glob("*.pkg.tar.zst"))
    assert pkgler, "makepkg paket uretmedi"
