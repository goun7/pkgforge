"""End-to-end test of the install-decision gate through the real pipeline.

Forces a WARNING compatibility report so the pipeline reaches the gate, then
simulates the UI approving after a delay. Validates:
  1. The pipeline BLOCKS at the gate (does not finish/cleanup early).
  2. The converted package still exists when the decision is recorded.
  3. After approval, install proceeds (dry-run) and finished emits success.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QCoreApplication, QTimer, QThread

from i18n import init_language
init_language("tr")

# ~/.config is read-only under the test sandbox, so force dry_run via patch.
import i18n as _i18n
_real_load_setting = _i18n.load_setting
def _load_setting(key, default=None):
    if key == "dry_run":
        return True  # install step becomes a no-op success
    return _real_load_setting(key, default)
_i18n.load_setting = _load_setting  # type: ignore[attr-defined]

import core.pipeline as pipeline_mod
pipeline_mod.load_setting = _load_setting  # type: ignore[attr-defined]
from core.pipeline import ConversionPipeline
from core.compatibility_checker import (
    CheckResult, CheckSeverity, CompatibilityReport,
)

DEB = Path("utest/hello_1.0.0-1_amd64.deb")

# Force a WARNING report so we hit the decision gate.
def fake_checks(pkg_path, file_list, depends, tools):
    rep = CompatibilityReport()
    rep.checks.append(CheckResult(
        name="Namcap Analizi",
        severity=CheckSeverity.WARNING,
        message="1 uyarı tespit edildi (hata yok)",
        details=["hello W: test warning"],
    ))
    return rep

pipeline_mod.run_compatibility_checks = fake_checks

app = QCoreApplication(sys.argv)
pipeline = ConversionPipeline()

state = {"gate_reached": False, "pkg_existed_at_decision": None,
         "finished": None, "approved_at": None}

thread = QThread()
pipeline.moveToThread(thread)


def on_compat_ready(report):
    state["gate_reached"] = True
    print(f"[UI] compatibility_ready received (overall={report.overall.value})")
    # Simulate the user reading the report for a moment, then approving.
    def approve():
        pkg = pipeline._result.converted_pkg
        state["pkg_existed_at_decision"] = bool(pkg and pkg.exists())
        state["approved_at"] = "after-delay"
        print(f"[UI] approving now; converted pkg exists at decision time: "
              f"{state['pkg_existed_at_decision']} ({pkg})")
        pipeline.approve_install()
    QTimer.singleShot(700, approve)


def on_finished(result):
    state["finished"] = result
    print(f"[pipeline] finished: success={result.success} msg={result.message!r}")
    app.quit()


pipeline.compatibility_ready.connect(on_compat_ready)
pipeline.finished.connect(on_finished)
pipeline.log_message.connect(lambda m, lvl: print(f"  [{lvl}] {m}"))

thread.started.connect(lambda: pipeline.run(DEB))
thread.start()

# Safety watchdog so the test cannot hang forever.
QTimer.singleShot(60000, lambda: (print("WATCHDOG TIMEOUT"), app.quit()))

app.exec()
thread.quit()
thread.wait(5000)

print("\n=== RESULT ===")
print("gate reached:", state["gate_reached"])
print("pkg existed at decision time:", state["pkg_existed_at_decision"])
r = state["finished"]
if r is None:
    print("FAIL: pipeline never finished")
    sys.exit(1)
ok = (state["gate_reached"] and state["pkg_existed_at_decision"] and r.success)  # type: ignore[attr-defined]
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)