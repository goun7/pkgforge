"""F2.3 — SSRF guard + plugin uzak-kod onayi."""
from __future__ import annotations

import urllib.request
from typing import ClassVar

import pytest

import cli
from core.downloader import (
    _SchemeGuardRedirectHandler,
    assert_public_host,
    download_package,
)


@pytest.mark.parametrize("host", [
    "127.0.0.1", "::1", "10.0.0.5", "192.168.1.1", "172.16.9.9",
    "169.254.169.254", "224.0.0.1", "0.0.0.0",
])
def test_private_literal_hosts_rejected(host):
    with pytest.raises(ValueError):
        assert_public_host(host)


def test_public_literal_ip_passes():
    assert_public_host("8.8.8.8")  # harfi harfine IP: DNS yok, hermetik
    assert_public_host("1.1.1.1")


def test_empty_host_rejected():
    with pytest.raises(ValueError):
        assert_public_host("")
    with pytest.raises(ValueError):
        assert_public_host(None)


def test_unresolvable_host_fail_closed(monkeypatch):
    # Gercek DNS yerine deterministik cozumleyici: .invalid TLD (RFC 2606)
    # her zaman cozumsuzdur — test ag durumundan etkilenmez (onceki surum
    # gercek getaddrinfo cagrisiydi).
    import socket as _socket
    from unittest import mock

    def sahte_cozumleyici(host, *a, **kw):
        raise _socket.gaierror(8, "cozumlenemedi")

    with mock.patch("core.downloader.socket.getaddrinfo",
                    side_effect=sahte_cozumleyici), pytest.raises(ValueError):
        assert_public_host("yok-boyle-host.invalid")


def test_readable_hostname_passes_without_dns(monkeypatch):
    # README-adresi gibi gercek bir hostname DNS olmadan da gecmeli:
    # guard sadece cozum basarisini sayar, gercek bir aga cikis yapmaz.
    import socket as _socket
    from unittest import mock

    def sahte_cozumleyici(host, *a, **kw):
        return [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    with mock.patch("core.downloader.socket.getaddrinfo",
                    side_effect=sahte_cozumleyici):
        assert_public_host("example.com")


def test_opt_in_bypasses_guard():
    assert_public_host("127.0.0.1", allow_private_hosts=True)
    assert_public_host("cozulemeyen.invalid", allow_private_hosts=True)


def test_redirect_to_private_host_blocked():
    h = _SchemeGuardRedirectHandler(require_https=False,
                                    allow_private_hosts=False)
    req = urllib.request.Request("https://example.com/x.deb")
    with pytest.raises(ValueError):
        h.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1/evil.deb")
    with pytest.raises(ValueError):
        h.redirect_request(req, None, 302, "Found", {}, "http://169.254.169.254/x")


def test_download_package_rejects_loopback(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr("core.downloader._open_url",
                        lambda *a, **k: opened.append(1))
    with pytest.raises(ValueError):
        download_package("https://127.0.0.1/p.deb", dest_dir=tmp_path)
    assert opened == []

    class _Bos:
        headers: ClassVar[dict] = {}
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self, n=-1):
            return b""
    # opt-in ile guard gecer, indirme denenir
    monkeypatch.setattr("core.downloader._open_url", lambda *a, **k: _Bos())
    out = download_package("https://127.0.0.1/p.deb", dest_dir=tmp_path,
                           allow_private_hosts=True)
    assert out.is_file()


def test_plugin_install_needs_confirm(monkeypatch, capsys):
    import argparse

    monkeypatch.setattr("core.plugins.marketplace.install_plugin",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("calismamali")))
    ns = argparse.Namespace(plugin_action="install", name="x", force=False,
                            version="latest", yes=False)
    assert cli._cmd_plugin(ns) == 1
    assert "onay" in capsys.readouterr().out.lower()
