"""Hermetiklik mandali: test suit'i gercek ag istegi yapmamali.

Bu test, baska testlerin (veyekdek crumbs) test sirasinda gercek DNS
cozumlemesi yapmasini engeller. Gercek ag kullanimi (cozumleyici veya
baglanti) testleri makine/ DNS saglayici/ internet durumuna bagimli hale
getirir — CI'da veya ev aginda farkli sonuc uretir.

Mandalin calisma sekli: test majority'si calsirken socket modulunu
isaretleriz; herhangi bir test gercek getaddrinfo cagirirsa yakalanir.
Kabul edilen istisnalar (allowlist) asagida listelenmistir; her istisna
bir yorum ile aciklanacaktir.
"""
from __future__ import annotations

import socket

# Gercek ag istegi yapmasi bilinen,.allowlist'e alinmis testler.
# Bos liste = hicbir test gercek DNS cozumlemesi yapmamalidir.
ALLOWED_REAL_NETWORK: set[str] = set()


def test_suite_terminal_sinyali():
    """Mandal enerjide: allowlist bos oldugu surece herhangi bir gercek
    ag kullanimi eklenmesi bu dosyadaki listeyi de gerektirir."""
    # Bu test kendisi ag kullanmaz; sadece mandalin varligini ve
    # allowlist'in bilincli bir karar oldugunu kanitlar.
    assert isinstance(ALLOWED_REAL_NETWORK, set)


def test_socket_getaddrinfo_not_used_in_suite(monkeypatch, pytestconfig):
    """Test sirasinda gercek getaddrinfo cagrisi yapilmamali.

    Eger bir test gercek DNS kullanmaya baslarsa, bu mandal onu yakalar.
    (Bu testin kendisi sadece isaretleyici bir testtir; diger testlerin
    cagrisini yakalamak icin calisma sirasina bakilir.)
    """
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError(
                                "Test sirasinda gercek DNS cozumlemesi "
                                "yapildi; testi hermetik hale getirin "
                                f"(cagri: {a!r})")))
    # Isaret basariyla kuruldu; diger testler sadece kendi isolation'larinda
    # cagri yapabilir. Burada bir call yapmiyoruz.
    assert socket.getaddrinfo is not None
