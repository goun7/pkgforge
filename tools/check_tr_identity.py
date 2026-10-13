"""Yeni eklenen anahtarlarin TR degerleri HEAD agacinda gercekten var mi?

Kodda literaller tr() ile degistirilmeden ONCE ayni metin koda gomulu idi; bu
dogrulama, `git diff HEAD` ile eklenen her TR degerinin HEAD'deki kaynak
agacinda birebir bulundugunu kontrol eder. Boylece "TR cikti degismedi" iddiasi
varsayim degil, olcum olur.

Kullanim: PYTHONPATH=. python tools/check_tr_identity.py
Cikis: eksik/eslesen sayilari + bulunamayan anahtarlarin listesi.
"""
import ast
import re
import subprocess
import sys

diff = subprocess.run(["git", "diff", "HEAD", "--", "i18n/lang_tr.py"],
                      capture_output=True, text=True, check=True).stdout

# Eklenen satirlar: '+"anahtar": "deger",'  (deger tek satirlik JSON gibi)
EKLENEN = re.compile(r'^\+\s+"([^"]+)":\s+"((?:[^"\\]|\\.)*)",\s*$', re.MULTILINE)
yeni = {m.group(1): m.group(2) for m in EKLENEN.finditer(diff)}
if not yeni:
    print("diff'te eklenen anahtar bulunamadi (tek satirlik olmayanlar atlandi)")

# Kaynak agaci HEAD'den oku (tek seferlik, hizli)
dosyalar = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD", "core", "cli.py",
                           "main.py", "ui", "i18n"],
                          capture_output=True, text=True, check=True).stdout.split()
kaynaklar = {}
for dosya in dosyalar:
    if not dosya.endswith(".py"):
        continue
    kaynaklar[dosya] = subprocess.run(
        ["git", "show", f"HEAD:{dosya}"],
        capture_output=True, text=True, check=False).stdout

_butun = "\n".join(kaynaklar.values())

kusur, dogru, atlanan = [], 0, 0
for anahtar, deger in sorted(yeni.items()):
    duz = ast.literal_eval(f'"{deger}"')
    on_ek = duz.split("{", 1)[0].rstrip()
    if len(on_ek) < 6:
        atlanan += 1
        continue
    if on_ek in _butun:
        dogru += 1
    else:
        kusur.append(f"{anahtar}: {on_ek[:60]!r}")

print(f"eklenen anahtar: {len(yeni)}  HEAD'de bulunan: {dogru}  "
      f"kisa/onemsiz: {atlanan}  BULUNAMAYAN: {len(kusur)}")
for k in kusur:
    print("  -", k)
sys.exit(1 if kusur else 0)
