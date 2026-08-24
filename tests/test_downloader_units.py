"""Coverage itmesi — core/downloader.py sema korumali yonlendirme."""
from __future__ import annotations

import urllib.request

import pytest

from core.downloader import _SchemeGuardRedirectHandler


def _req():
    return urllib.request.Request("https://ornek.test/paket.deb")


def test_redirect_to_non_http_scheme_rejected():
    h = _SchemeGuardRedirectHandler(require_https=False)
    with pytest.raises(ValueError) as ei:
        h.redirect_request(_req(), None, 302, "Found", {}, "ftp://x/y")
    assert "şema" in str(ei.value)


def test_https_downgrade_blocked_with_require_https():
    h = _SchemeGuardRedirectHandler(require_https=True)
    with pytest.raises(ValueError) as ei:
        h.redirect_request(_req(), None, 302, "Found", {}, "http://x/y")
    assert "MITM" in str(ei.value)


def test_http_allowed_when_require_https_false():
    h = _SchemeGuardRedirectHandler(require_https=False)
    out = h.redirect_request(_req(), None, 302, "Found", {},
                             "http://x/y.deb")
    assert isinstance(out, urllib.request.Request)
    assert out.full_url == "http://x/y.deb"


def test_https_redirect_allowed_when_require_https():
    h = _SchemeGuardRedirectHandler(require_https=True)
    out = h.redirect_request(_req(), None, 301, "Moved", {},
                             "https://mirror.test/paket.deb")
    assert isinstance(out, urllib.request.Request)
