"""Coverage itmesi — core/pipeline.py karar kapisu ve yasam dongusu."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from PyQt6.QtCore import QCoreApplication

import core.pipeline as PL
from core.pipeline import (
    STEP_LABELS,
    ConversionPipeline,
    PipelineResult,
    PipelineStep,
)


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture()
def pipe(qapp, monkeypatch):
    monkeypatch.setattr(PL, "discover_tools",
                        lambda: NS(missing_required=[], missing_optional=[]))
    return ConversionPipeline()


def test_step_enum_and_labels():
    assert len(STEP_LABELS) == len(PipelineStep)
    assert PipelineStep.SECURITY == 0 and PipelineStep.INSTALL == 5
    assert all(isinstance(v, str) and v for v in STEP_LABELS.values())


def test_result_defaults():
    r = PipelineResult()
    assert r.success is False and r.converted_pkg is None
    assert r.sha256 == "" and r.metadata is None


def test_cancel_wakes_and_forwards(pipe):
    calls = []
    fake = NS(cancel=lambda: calls.append("c"))
    pipe._deb_converter = fake
    pipe._rpm_converter = None
    pipe._installer = None
    pipe.cancel()
    assert pipe._cancelled is True
    assert calls == ["c"]


def test_approve_and_dismiss_flags(pipe):
    pipe.approve_install()
    assert pipe._decision_made is True and pipe._decision_approved is True

    pipe2 = pipe
    pipe2._decision_made = False
    pipe2.dismiss_install()
    assert pipe2._decision_approved is False
    assert pipe2._decision_message is None

    pipe3 = pipe
    pipe3._decision_message = None
    pipe3.dismiss_install("distrobox tercih edildi")
    assert pipe3._decision_message == "distrobox tercih edildi"


def test_wait_for_decision_predecided(pipe):
    pipe._decision_made = True
    pipe._decision_approved = True
    assert pipe._wait_for_decision() is True

    pipe._decision_approved = False
    assert pipe._wait_for_decision() is False


def test_run_staged_without_path(pipe):
    got = []
    pipe.finished.connect(lambda r: got.append(r))
    pipe.run_staged()
    assert len(got) == 1
    assert got[0].success is False
    assert "dosya yolu verilmedi" in got[0].message


def test_stage_then_run_staged_invokes_run(pipe, monkeypatch, tmp_path):
    f = tmp_path / "x.deb"
    f.write_bytes(b"x")
    called = []
    monkeypatch.setattr(ConversionPipeline, "run",
                        lambda self, p, forced=None: called.append(p))
    pipe.stage(f)
    pipe.run_staged()
    assert called == [f]


def test_record_history_failure_tolerated(pipe, monkeypatch, tmp_path):
    import core.history_db as HD

    def boom():
        raise RuntimeError("db yok")
    monkeypatch.setattr(HD, "HistoryDB", boom)
    pipe._result.message = "hata"
    pipe._record_history(tmp_path / "x.rpm")


def test_record_history_success_path(pipe, monkeypatch, tmp_path):
    import core.history_db as HD
    recorded = {}

    class FakeDB:
        def add_record(self, **kw):
            recorded.update(kw)
    monkeypatch.setattr(HD, "HistoryDB", FakeDB)
    pipe._result.sha256 = "abc"
    pipe._result.success = True
    pipe._result.message = "tamam"
    f = tmp_path / "paket.deb"
    f.write_bytes(b"x")
    pipe._record_history(f)
    assert recorded["package_name"] == "paket.deb"
    assert recorded["package_type"] == "deb"
    assert recorded["status"] == "success"


def test_run_catches_unexpected(pipe, monkeypatch, tmp_path):
    got = []
    pipe.finished.connect(lambda r: got.append(r))

    def boom(fp):
        raise ValueError("patlama")
    monkeypatch.setattr(ConversionPipeline, "_run_pipeline", boom)
    f = tmp_path / "x.rpm"
    f.write_bytes(b"x")
    pipe.run(f)
    assert len(got) == 1
    assert got[0].success is False and "Beklenmeyen hata" in got[0].message
