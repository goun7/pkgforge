"""Coverage itmesi - pipeline uyumluluk karar kapisu dallari."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.pipeline as PL
from core.compatibility_checker import CheckSeverity
from core.pipeline import ConversionPipeline


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def _meta():
    return NS(name="demo", version="1.0", arch="x86_64",
              arch_mapped="x86_64", arch_compatible=True,
              already_installed=False, file_list=[], depends=[])


def _report(sev):
    return NS(checks=[], overall=sev)


def _set_conv(self, pkg):
    self._async_success = True
    self._async_pkg_path = pkg


@pytest.fixture()
def gate(qapp, monkeypatch, tmp_path):
    deb = tmp_path / "g.deb"
    deb.write_bytes(b"D")
    pkg = tmp_path / "cikti.pkg.tar.zst"
    pkg.write_bytes(b"P")
    mp = monkeypatch
    mp.setattr(PL, "discover_tools",
               lambda: NS(missing_required=[], missing_optional=[], debtap=""))
    mp.setattr(PL, "create_temp_dir", lambda: tmp_path / "tmpd")
    (tmp_path / "tmpd").mkdir()
    mp.setattr(PL, "validate_mime_type", lambda p, t: "app/zst")
    mp.setattr(PL, "validate_file_size", lambda *a, **k: None)
    mp.setattr(PL, "sha256_hash", lambda p: "ab" * 32)
    mp.setattr(PL, "verify_deb_signature",
               lambda p, t: NS(has_signature=False, detail="imza yok"))
    mp.setattr("core.security.check_compression_bomb", lambda p, t: None)
    mp.setattr("i18n.load_setting", lambda k, d=False: False)
    mp.setattr(PL, "analyze_package", lambda p, t: _meta())
    mp.setattr(ConversionPipeline, "_convert_deb",
               lambda self, dp, od: _set_conv(self, pkg))
    installed = []
    mp.setattr(ConversionPipeline, "_do_install",
               lambda self, pp, pn: installed.append(pn))
    pipe = ConversionPipeline()
    return pipe, deb, installed


@pytest.fixture()
def err_report(monkeypatch):
    monkeypatch.setattr(PL, "run_compatibility_checks",
                        lambda *a, **k: _report(CheckSeverity.ERROR))


@pytest.fixture()
def warn_report(monkeypatch):
    monkeypatch.setattr(PL, "run_compatibility_checks",
                        lambda *a, **k: _report(CheckSeverity.WARNING))


@pytest.fixture()
def pass_report(monkeypatch):
    monkeypatch.setattr(PL, "run_compatibility_checks",
                        lambda *a, **k: _report(CheckSeverity.PASS))


def test_error_dismissed(gate, err_report):
    pipe, deb, installed = gate
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe._run_pipeline(deb)
    assert pipe._result.success is False
    assert "onaylanmad" in pipe._result.message
    assert installed == []


def test_error_batch_skip_is_success(gate, err_report):
    pipe, deb, installed = gate
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe._skip_install_message = "toplu mod: kurulum atlandi"
    pipe._run_pipeline(deb)
    assert pipe._result.success is True
    assert pipe._result.message == "toplu mod: kurulum atlandi"
    assert installed == []


def test_error_approved_installs(gate, err_report):
    pipe, deb, installed = gate
    pipe._decision_made = True
    pipe._decision_approved = True
    pipe._run_pipeline(deb)
    assert installed == ["demo"]


def test_warning_dismissed_message(gate, warn_report):
    pipe, deb, _installed = gate
    pipe._decision_made = True
    pipe._decision_approved = False
    pipe._decision_message = "kullanici vazgecti"
    pipe._run_pipeline(deb)
    assert pipe._result.success is False
    assert "vazgecti" in pipe._result.message


def test_warning_approved_installs(gate, warn_report):
    pipe, deb, installed = gate
    pipe._decision_made = True
    pipe._decision_approved = True
    pipe._run_pipeline(deb)
    assert installed == ["demo"]


def test_pass_auto_approves(gate, pass_report):
    pipe, deb, installed = gate
    pipe._run_pipeline(deb)
    assert installed == ["demo"]


def test_cancel_before_compat(gate, pass_report):
    pipe, deb, installed = gate
    pipe._cancelled = True
    pipe._run_pipeline(deb)
    assert installed == []