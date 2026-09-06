"""PkgForge — Debian/RPM ad eslestirme ve derleme-cikti sonlandirma yardimcilari.

Bu modulun iki gorevi vardir:

1. Dagitimlar arasi ad cevirisi (Debian ``Depends`` adlari ve lisans
   metinleri → Arch karsiliklari). Yalnizca ``config.py`` icindeki
   kanitlanmis eslestirmeler kullanilir; bilinmeyen adlar ``None`` doner
   ve cagiran tarafca durustca "cozulemedi" olarak raporlanir (tahmin yok).
2. Basarili derleme sonrasi calisma agaci temizligi: uretilen
   ``.pkg.tar.*`` cikti dizini kokune tasinir, ``src/`` + ``pkg/``
   kaldirilir, ``PKGBUILD`` inceleme icin saklanir.

Saf fonksiyonlar agirliktadir; dosya yazan iki yardimci tum
hatalari yutar ve ``None`` doner (donusum asla temizlik yuzunden
basarisiz sayilmaz).
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from config import DEB_DEP_MAP, DEB_LICENSE_MAP

log = logging.getLogger(__name__)

_VERSION_SPLIT_RE = re.compile(r"[><=()]")


def debian_dep_to_arch(dep: str) -> str | None:
    """Map a Debian dependency token to its Arch package name.

    Version constraints (``libc6 (>= 2.34)``) and multiarch qualifiers
    (``libc6:amd64``) are stripped before lookup. Returns ``None`` when
    the name is unknown or empty so callers report it honestly instead
    of guessing.
    """
    name = _VERSION_SPLIT_RE.split(dep, maxsplit=1)[0].strip()
    name = name.split(":")[0].strip()
    if not name:
        return None
    return DEB_DEP_MAP.get(name.lower())


def arch_license(license_text: str, pkgname: str) -> str:
    """Resolve upstream license text to a PKGBUILD ``license=()`` entry.

    Known Debian-ish tokens map to SPDX identifiers (namcap-clean).
    Unknown or empty input yields ``LicenseRef-<pkg>-unknown`` — also
    namcap-clean (``LicenseRef-`` prefix) and honest about provenance.
    Never returns the bare ``custom`` token, which namcap ≥3.6 flags
    as ``unknown-spdx-license-identifier``.
    """
    text = (license_text or "").lower()
    for token, spdx in DEB_LICENSE_MAP.items():
        if token and token in text:
            return spdx
    safe = re.sub(r"[^A-Za-z0-9._+-]", "-", pkgname.strip()) or "unknown"
    return f"LicenseRef-{safe}-unknown"


LICENSE_STUB_TEMPLATE = """\
Upstream license: UNKNOWN (converted package)
Package: {pkgname}

This Arch package was automatically converted from a foreign
(.deb/.rpm) archive whose license metadata could not be determined.
The original work remains under its upstream license; this file is
only a provenance placeholder so the package declares an explicit,
machine-readable license field.

If you are the upstream author, please report the correct license to
the packager so this placeholder can be replaced.
"""


def write_license_stub(src_root: Path, pkgname: str) -> Path | None:
    """Install an honest UNKNOWN license stub into the extracted tree.

    Writes ``usr/share/licenses/<pkg>/UNKNOWN`` under *src_root* so the
    built package satisfies namcap's ``license-file-missing`` check for
    ``LicenseRef-`` identifiers. Returns the stub path, or ``None`` on
    any filesystem error (caller must proceed without the stub).
    """
    try:
        target_dir = src_root / "usr" / "share" / "licenses" / pkgname
        target_dir.mkdir(parents=True, exist_ok=True)
        stub = target_dir / "UNKNOWN"
        stub.write_text(
            LICENSE_STUB_TEMPLATE.format(pkgname=pkgname), encoding="utf-8"
        )
        return stub
    except OSError as exc:
        log.warning("Lisans stub yazilamadi (%s): %s", pkgname, exc)
        return None


def finalize_build_output(build_dir: Path, output_dir: Path) -> Path | None:
    """Move the built artifact to *output_dir* root and clean the tree.

    - ``build_dir`` altinda ``.pkg.tar.*`` aranir (``.sig``/``.json`` haric).
    - Bulunan ilk urun *output_dir* kokune tasinir (ayni isim varsa uzerine
      yazilir — ``makepkg -f`` semantigi ile tutarli).
    - ``src/`` ve ``pkg/`` silinir; ``PKGBUILD`` inceleme icin saklanir;
      bosen ``pkgout/`` kaldirilir.
    - Hata durumunda ``None`` doner; tasma basarili sayilmaz ama donusum
      sonucu degismez (cagiran eski yolu kullanmaya devam edebilir).
    """
    try:
        candidates = sorted(
            p
            for p in build_dir.rglob("*.pkg.tar.*")
            if p.is_file()
            and ".pkg.tar" in p.name
            and not p.name.endswith((".sig", ".json"))
        )
        if not candidates:
            return None
        artifact = candidates[0]
        output_dir.mkdir(parents=True, exist_ok=True)
        final_path = output_dir / artifact.name
        if artifact.resolve() != final_path.resolve():
            if final_path.exists():
                final_path.unlink()
            shutil.move(str(artifact), str(final_path))
        else:
            final_path = artifact
        for sub in ("src", "pkg"):
            shutil.rmtree(build_dir / sub, ignore_errors=True)
        pkgout = build_dir / "pkgout"
        try:
            pkgout.rmdir()  # yalnizca bossa; doluysa sessizce birak
        except OSError:
            pass
        return final_path
    except OSError as exc:
        log.warning("Derleme ciktisi sonlandirilamadi (%s): %s", build_dir, exc)
        return None
