"""Launch PkgForge GUI offscreen and grab screenshots of every surface."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from i18n import init_language
init_language("tr")

from ui.styles import build_stylesheet
from ui.main_window import MainWindow

app = QApplication(sys.argv)
app.setApplicationName("PkgForge")
app.setStyleSheet(build_stylesheet("dark"))

shots = Path("utest/shots")
shots.mkdir(exist_ok=True)

window = MainWindow()
window.resize(1100, 760)
window.show()


def grab_main():
    window.grab().save(str(shots / "01_main_dark.png"))
    print("saved 01_main_dark.png")

    # Light theme variant
    app.setStyleSheet(build_stylesheet("light"))
    window.grab().save(str(shots / "02_main_light.png"))
    print("saved 02_main_light.png")
    app.setStyleSheet(build_stylesheet("dark"))

    # Settings dialog
    try:
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(window)
        dlg.resize(560, 620)
        dlg.grab().save(str(shots / "03_settings.png"))
        print("saved 03_settings.png")
        dlg.close()
    except Exception as exc:
        print("settings dialog failed:", exc)

    # History dialog
    try:
        from ui.history_dialog import HistoryDialog
        dlg = HistoryDialog(window)
        dlg.resize(760, 520)
        dlg.grab().save(str(shots / "04_history.png"))
        print("saved 04_history.png")
        dlg.close()
    except Exception as exc:
        print("history dialog failed:", exc)

    # Result dialog with a real report (from the converted test package)
    try:
        from config import discover_tools
        from core.package_analyzer import analyze_package
        from core.compatibility_checker import run_compatibility_checks
        from ui.result_dialog import ResultDialog

        tools = discover_tools()
        meta = analyze_package(Path("utest/hello_1.0.0-1_amd64.deb"), tools)
        pkg = Path("utest/out/native_build/pkgout/hello-1.0.0-1-x86_64.pkg.tar.zst")
        report = run_compatibility_checks(pkg, meta.file_list, meta.depends, tools)
        dlg = ResultDialog(
            report=report,
            metadata=meta,
            signature=None,
            sha256="ab" * 32,
            show_distrobox=False,
            parent=window,
        )
        dlg.resize(860, 720)
        dlg.grab().save(str(shots / "05_result_dialog.png"))
        print("saved 05_result_dialog.png")
        dlg.close()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print("result dialog failed:", exc)

    # About box
    try:
        window._show_about()
        for w in app.topLevelWidgets():
            if w.isVisible() and w.__class__.__name__ == "QMessageBox":
                w.grab().save(str(shots / "06_about.png"))
                print("saved 06_about.png")
                w.close()
    except Exception as exc:
        print("about failed:", exc)

    app.quit()


QTimer.singleShot(800, grab_main)
app.exec()
print("DONE")
