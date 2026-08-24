"""Faz 5 (F5.11) — HTTP API router paketleri.

core/api_server.py'nin god-module yapisini kucultmek icin JSON-RPC
handler'lari alan bazli router modullerine bolunur. api_server bir facade
olarak kalir: handler'lari buradan import edip METHODS sozlugune kaydeder,
boylece mevcut testler (core.api_server.handle_X erisimi dahil) degismez.

Router'lar:
  meta     — uygulama/sistem/ayarlar/polika (stateless)
"""
from __future__ import annotations
