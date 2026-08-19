"""Programmatic UI audit: widget tree, geometry, empty labels, i18n keys."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QFrame
from PyQt6.QtCore import QTimer

from i18n import init_language
init_language("tr")

from ui.styles import build_stylesheet
from ui.main_window import MainWindow

app = QApplication(sys.argv)
app.setStyleSheet(build_stylesheet("dark"))
window = MainWindow()
window.resize(1100, 760)
window.show()

issues = []


def audit_widget(w, depth=0, path=""):
    name = w.objectName() or w.__class__.__name__
    p = f"{path}/{name}"
    geo = w.geometry()
    if w.isVisible() and (geo.width() == 0 or geo.height() == 0):
        issues.append(f"ZERO-SIZE visible widget: {p} geo={geo.getRect()}")
    if isinstance(w, QLabel):
        txt = w.text()
        if w.isVisible() and txt == "" and not w.pixmap():
            issues.append(f"EMPTY visible label: {p}")
        if txt and txt.startswith("tr(") or (txt and txt.endswith(")") and "." in txt and len(txt) < 40 and txt.count(".") == 1 and txt.replace(".", "").replace("_", "").isalnum()):
            issues.append(f"POSSIBLE untranslated key: {p} text={txt!r}")
    if isinstance(w, QPushButton):
        if w.isVisible() and not w.text() and not w.icon():
            issues.append(f"EMPTY visible button: {p}")
    for child in w.findChildren(QWidget, "", options=w.FindChildOption.FindDirectChildrenOnly) if False else []:
        pass
    for child in w.children():
        if isinstance(child, QWidget):
            audit_widget(child, depth + 1, p)


def run_audit():
    audit_widget(window)

    # i18n key completeness: tr vs en
    from i18n.lang_tr import STRINGS as TR
    from i18n.lang_en import STRINGS as EN
    missing_en = set(TR) - set(EN)
    missing_tr = set(EN) - set(TR)
    if missing_en:
        issues.append(f"keys in TR but not EN: {sorted(missing_en)}")
    if missing_tr:
        issues.append(f"keys in EN but not TR: {sorted(missing_tr)}")

    # Find tr() calls in code that have no string entry
    import re
    used = set()
    for py in list(Path(".").rglob("*.py")):
        s = str(py)
        if ".venv" in s or "utest" in s or "build" in s:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in re.finditer(r'tr\("([^"]+)"', text):
            used.add(m.group(1))
    undefined = sorted(k for k in used if k not in TR)
    if undefined:
        issues.append(f"tr() keys used but undefined in lang files: {undefined}")
    unused = sorted(set(TR) - used)
    print(f"i18n: {len(TR)} tr keys, {len(EN)} en keys, {len(used)} used in code")
    if unused:
        print(f"note: {len(unused)} defined-but-unused keys (first 10): {unused[:10]}")

    # Widget tree summary
    def tree(w, depth=0, out=None):
        if out is None:
            out = []
        name = w.objectName() or w.__class__.__name__
        txt = ""
        if isinstance(w, (QLabel, QPushButton)) and w.text():
            txt = f' "{w.text()[:40]}"'
        out.append("  " * depth + f"{name}{txt} {w.geometry().width()}x{w.geometry().height()}")
        for child in w.children():
            if isinstance(child, QWidget):
                tree(child, depth + 1, out)
        return out

    lines = tree(window)
    print(f"widget tree: {len(lines)} widgets")
    Path("utest/widget_tree.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"\nISSUES FOUND: {len(issues)}")
    for i in issues:
        print(" -", i)
    app.quit()


QTimer.singleShot(600, run_audit)
app.exec()
print("AUDIT DONE")
