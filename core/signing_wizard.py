"""Tur-55 B7: Sigstore / PGP onboarding wizard.

Interaktif sihirbaz: kullanıcıya üç seçenek sunar (PGP, Sigstore,
skip) ve her biri için somut adımları yazdırır. Otomatik ortamda
(TTY yok) tam çevrimdışı modda çalışır ve tüm adımları metin olarak
döner — bu da wizard'ı CI ve testlerde deterministik yapar.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.package_signing import is_gpg_available
from core.sigstore import get_sigstore_status
from i18n import tr


@dataclass
class WizardStep:
    """One concrete onboarding step."""

    order: int
    title: str
    command: str
    rationale: str = ""


@dataclass
class WizardResult:
    """Full wizard output: status of tools + chosen method + steps."""

    method: str  # "pgp" | "sigstore" | "skip"
    tools_available: dict = field(default_factory=dict)
    steps: list[WizardStep] = field(default_factory=list)
    config_path: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [asdict(s) for s in self.steps]
        return d


def _env_status() -> dict:
    """Snapshot of available signing tools in current environment."""
    return {
        "gpg": {"available": is_gpg_available(),
                "path": shutil.which("gpg") or ""},
        "sigstore": get_sigstore_status(),
    }


def _pgp_steps() -> list[WizardStep]:
    return [
        WizardStep(1, tr("signing.setup.pgp_step1"),
                   "gpg --full-generate-key"),
        WizardStep(2, tr("signing.setup.pgp_step2"),
                   "gpg --list-keys  # not alin"),
        WizardStep(3, tr("signing.setup.pgp_step3"),
                   "gpg --armor --export <KEY_ID> > pkgforge.pub"),
        WizardStep(4, "Sign a package",
                   "pkgforge sign my-pkg.pkg.tar.zst --key <KEY_ID>"),
    ]


def _sigstore_steps() -> list[WizardStep]:
    return [
        WizardStep(1, tr("signing.setup.sigstore_step1"),
                   "go install github.com/sigstore/cosign/v2/cmd/cosign@latest"),
        WizardStep(2, "Login to OIDC provider (GitHub/Google)",
                   "cosign login ghcr.io  # token from env"),
        WizardStep(3, tr("signing.setup.sigstore_step2"),
                   "cosign sign-blob --yes my-pkg.pkg.tar.zst"),
        WizardStep(4, tr("signing.setup.sigstore_step3"),
                   "cosign verify-blob --certificate-identity-regexp=.* "
                   "--certificate-oidc-issuer-regexp=.* my-pkg.pkg.tar.zst"),
    ]


def _write_persist(result: WizardResult, path: Path) -> Path:
    """Save the wizard output to a JSON config for later reuse."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path


def run_wizard(method: str = "auto",
               persist_to: Path | None = None) -> WizardResult:
    """Run the wizard non-interactively (or interactively when method='auto'
    and stdin is a TTY).

    Args:
        method: "pgp" | "sigstore" | "skip" | "auto".
                "auto" picks PGP if gpg is available, else Sigstore if
                cosign is available, else "skip".
        persist_to: optional path to write a JSON config the user can
                    reuse later (e.g. for `pkgforge sign` defaults).

    Returns:
        WizardResult with tool status + chosen method + steps.
    """
    env = _env_status()
    chosen = method
    if method == "auto":
        if env["gpg"]["available"]:
            chosen = "pgp"
        elif env["sigstore"]["cosign_available"]:
            chosen = "sigstore"
        else:
            chosen = "skip"

    steps: list[WizardStep]
    if chosen == "pgp":
        steps = _pgp_steps()
    elif chosen == "sigstore":
        steps = _sigstore_steps()
    elif chosen == "skip":
        steps = [WizardStep(1, "Signing disabled",
                            "# nothing to do — packages will not be signed")]
    else:
        raise ValueError(f"Unknown method: {method!r}")

    result = WizardResult(method=chosen, tools_available=env, steps=steps)

    if persist_to is not None:
        _write_persist(result, persist_to)
        result.config_path = str(persist_to)

    return result


def render_text(result: WizardResult) -> str:
    """Human-readable rendering for terminal output."""
    out: list[str] = []
    out.append(f"🪄  {tr('signing.setup.welcome')}")
    out.append("")
    out.append("🔧  Araçlar:")
    gpg = result.tools_available.get("gpg", {})
    sig = result.tools_available.get("sigstore", {})
    out.append(f"   • gpg: {'✅' if gpg.get('available') else '❌'} "
               f"{gpg.get('path', '')}")
    out.append(f"   • cosign: {'✅' if sig.get('cosign_available') else '❌'} "
               f"{sig.get('cosign_version', '')}")
    out.append("")
    out.append(f"📋  Yöntem: {result.method}")
    out.append("")
    for s in result.steps:
        out.append(f"  {s.order}. {s.title}")
        out.append(f"     $ {s.command}")
        if s.rationale:
            out.append(f"     💡 {s.rationale}")
    out.append("")
    if result.config_path:
        out.append(f"💾  Yapılandırma kaydedildi: {result.config_path}")
    out.append(f"\n✅  {tr('signing.setup.done')}")
    return "\n".join(out)
