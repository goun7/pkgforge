"""Tests for subprocess_converters: Signal class + real CLI-mode conversions.

The Signal tests are pure. The converter tests run REAL conversions of the
hello .deb and hello .rpm fixtures through the CLI (non-Qt) backend, which
exercises analyze -> extract -> security -> PKGBUILD -> makepkg end to end.
"""

import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEB_FIXTURE = PROJECT_ROOT / "utest" / "hello_1.0.0-1_amd64.deb"
_RPM_BUILD_OUT = (PROJECT_ROOT / ".test_home" / "rpmbuild" / "RPMS"
                  / "x86_64" / "hello-1.0.0-1.x86_64.rpm")
_RPM_COMMITTED = PROJECT_ROOT / "utest" / "fixtures" / "hello-1.0.0-1.x86_64.rpm"
RPM_FIXTURE = _RPM_BUILD_OUT if _RPM_BUILD_OUT.is_file() else _RPM_COMMITTED


class TestSignal(unittest.TestCase):

    def test_connect_emit(self):
        from core.subprocess_converters import Signal
        sig = Signal()
        got = []
        sig.connect(lambda *a: got.append(a))
        sig.emit(1, "two")
        self.assertEqual(got, [(1, "two")])

    def test_multiple_callbacks(self):
        from core.subprocess_converters import Signal
        sig = Signal()
        a, b = [], []
        sig.connect(lambda *x: a.append(x))
        sig.connect(lambda *x: b.append(x))
        sig.emit("v")
        self.assertEqual(a, [("v",)])
        self.assertEqual(b, [("v",)])

    def test_disconnect(self):
        from core.subprocess_converters import Signal
        sig = Signal()
        got = []
        cb = lambda *a: got.append(a)
        sig.connect(cb)
        sig.disconnect(cb)
        sig.emit("x")
        self.assertEqual(got, [])

    def test_callback_exception_isolated(self):
        from core.subprocess_converters import Signal
        sig = Signal()
        got = []
        def bad(*a):
            raise RuntimeError("boom")
        sig.connect(bad)
        sig.connect(lambda *a: got.append(a))
        # A raising callback must not prevent later callbacks from running
        sig.emit("ok")
        self.assertEqual(got, [("ok",)])


@unittest.skipUnless(DEB_FIXTURE.is_file(), "hello .deb fixture missing")
@unittest.skipUnless(__import__("shutil").which("makepkg"), "makepkg gerekli (Arch-only derleme)")
class TestNativeDebConverterSubprocess(unittest.TestCase):

    def test_real_deb_conversion(self):
        import tempfile

        from config import discover_tools
        from core.subprocess_converters import NativeDebConverterSubprocess

        tools = discover_tools()
        conv = NativeDebConverterSubprocess(tools)
        done = threading.Event()
        result = {}
        def on_finished(success, msg, pkg):
            result["success"] = success
            result["msg"] = msg
            result["pkg"] = pkg
            done.set()
        conv.finished.connect(on_finished)

        with tempfile.TemporaryDirectory() as td:
            conv.convert(DEB_FIXTURE, Path(td))
            self.assertTrue(done.wait(timeout=120), "conversion timed out")
            self.assertTrue(result["success"], result.get("msg"))
            self.assertIsNotNone(result["pkg"])
            self.assertTrue(Path(result["pkg"]).is_file())
            self.assertTrue(result["pkg"].name.endswith(".pkg.tar.zst"))


@unittest.skipUnless(RPM_FIXTURE.is_file(), "hello .rpm fixture missing")
@unittest.skipUnless(__import__("shutil").which("makepkg"), "makepkg gerekli (Arch-only derleme)")
class TestRpmConverterSubprocess(unittest.TestCase):

    def test_real_rpm_conversion(self):
        import tempfile

        from config import discover_tools
        from core.package_analyzer import analyze_package
        from core.subprocess_converters import RpmConverterSubprocess

        tools = discover_tools()
        meta = analyze_package(RPM_FIXTURE, tools)
        conv = RpmConverterSubprocess(tools)
        done = threading.Event()
        result = {}
        def on_finished(success, msg, pkg):
            result["success"] = success
            result["msg"] = msg
            result["pkg"] = pkg
            done.set()
        conv.finished.connect(on_finished)

        with tempfile.TemporaryDirectory() as td:
            conv.convert(RPM_FIXTURE, Path(td), meta)
            self.assertTrue(done.wait(timeout=120), "conversion timed out")
            self.assertTrue(result["success"], result.get("msg"))
            self.assertIsNotNone(result["pkg"])
            self.assertTrue(Path(result["pkg"]).is_file())


if __name__ == "__main__":
    unittest.main()
