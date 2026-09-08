"""S6: fuzz hedefleri (hypothesis) + CSP e2e kilidi."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent


# --- downloader SSRF guard: toplam-fonksiyon ozelligi --------------------------

@given(st.one_of(
    st.from_regex(r"[a-z]{1,12}\.(invalid|test|example)", fullmatch=True),
    st.from_regex(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", fullmatch=True),
    st.text(alphabet="ab :/%?#@!", max_size=30),
))
@settings(max_examples=300, deadline=None)  # DNS cozumleme suresi degisken
def test_assert_public_host_total(host):
    """Herhangi bir girdide ya None doner ya ValueError; baska istisna yok."""
    from core.downloader import assert_public_host

    try:
        assert_public_host(host, allow_private_hosts=False)
    except ValueError:
        pass


@given(st.sampled_from([
    "127.0.0.1", "10.1.2.3", "192.168.0.1", "172.16.0.1", "169.254.169.254",
    "224.0.0.1", "0.0.0.0", "::1", "::ffff:127.0.0.1", "fe80::1",
]))
def test_private_literals_always_rejected(host):
    from core.downloader import assert_public_host

    if host == "fe80::1":
        # IPv6 zone-id'siz link-local: ipaddress de cozer, guard reddeder.
        pass
    with pytest.raises(ValueError):
        assert_public_host(host, allow_private_hosts=False)


@given(st.text(alphabet="abcdefghijklmnop0123456789-.", min_size=1, max_size=40))
@settings(max_examples=200, deadline=None)
def test_redirect_scheme_guard_total(newurl):
    """Yonlendirme hedefi ne olursa olsun: ya Request doner ya ValueError."""
    from core.downloader import _SchemeGuardRedirectHandler

    h = _SchemeGuardRedirectHandler(require_https=True,
                                    allow_private_hosts=True)
    req = urllib.request.Request("https://example.com/x.deb")
    try:
        out = h.redirect_request(req, None, 302, "Found", {}, newurl)
        assert isinstance(out, urllib.request.Request)
    except ValueError:
        pass


# --- marketplace: ad guvenligi ozelligi -----------------------------------------

@given(st.text(max_size=70))
@settings(max_examples=300)
def test_plugin_name_never_escapes_dir(name):
    from core.plugins.marketplace import PLUGIN_DIR, is_valid_plugin_name

    if is_valid_plugin_name(name):
        dest = (PLUGIN_DIR / f"{name}.py").resolve()
        assert str(dest).startswith(str(PLUGIN_DIR.resolve()))
        assert ".." not in dest.parts


@given(st.text(min_size=1, max_size=200))
@settings(max_examples=200)
def test_downloader_scheme_rejects_non_http(url):
    """http(s) disi sema her zaman ValueError (SSRF/host bagimsiz)."""
    from core.downloader import _validate_download_url

    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in ("http", "https"):
        with pytest.raises(ValueError):
            _validate_download_url(url, True, allow_private_hosts=True)


# --- CSP e2e kilidi ---------------------------------------------------------------

def _csp() -> str:
    conf = json.loads((ROOT / "desktop" / "src-tauri" / "tauri.conf.json").read_text())
    return conf["app"]["security"]["csp"] or ""


def test_csp_present_and_strict():
    csp = _csp()
    assert csp, "CSP null olamaz (S0 karari)"
    lowered = csp.lower()
    assert "'unsafe-inline'" not in lowered
    assert "'unsafe-eval'" not in lowered
    assert "*" not in lowered.replace("http://asset.localhost", "").replace("http://ipc.localhost", "")
    for directive in ("object-src 'none'", "base-uri 'none'",
                      "frame-ancestors 'none'", "script-src 'self'"):
        assert directive in csp, directive


def test_index_html_has_no_inline_scripts():
    html = (ROOT / "desktop" / "index.html").read_text()
    for line in html.splitlines():
        s = line.strip().lower()
        if s.startswith("<script") and "src=" not in s:
            raise AssertionError(f"inline script bulundu: {line.strip()[:80]}")
        assert "onload=" not in s and "onerror=" not in s, line.strip()[:80]


def test_csp_covers_ipc_channel():
    # Sidecar relay invoke() kullanir: connect-src ipc: sart.
    assert "ipc:" in _csp()
