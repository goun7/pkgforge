# UX Modernizasyonu — 2026 standartlari (Faz 5b)

Tarih: 2026-08-27  Durum: ONAYLI (kullanici: 'Her birini planlayip otonom olarak tamamla')

## Baglam

2026 UI/UX arastirmasindan (terminal uzerinden) cikan standartlar: erisilebilirlik-
oncelikli, tasarim tokenlari, amacli hareket (purposeful motion), stratejik
minimalizm, uyarlanabilir arayuzler. Mevcut Tauri frontend'i zaten guclu bir temele
sahip: tokens.css (renk/yuzey/radius/golge/tipografi, dark+light), Button/Input/Dialog
bilesenlerinde focus-visible ve aria. Bu alt sistem kalan bosluklari kapatir.

## Mevcut durum analizi

- tokens.css : renk, yüzey, metin, semantik, border, radius, golge, tipografi VAR.
  Hareket (duration/easing) tokenlari YOK. prefers-reduced-motion YOK.
- Button/Input : focus-visible halkasi VAR.
- Dialog       : role/aria-modal/aria-label/Escape VAR.
- Sidebar nav  : transition-colors VAR ama focus-visible halkasi YOK (klavye
  gezinmesinde gorunur odak eksik).

## Kapsam

1. Hareket tasarim tokenlari (tokens.css):
   --duration-fast: 120ms, --duration-base: 200ms, --duration-slow: 320ms,
   --ease-standard: cubic-bezier(0.2,0,0,1), --ease-decelerate: cubic-bezier(0,0,0,1).
2. prefers-reduced-motion destegi (styles/index.css): kullanici hareketi azaltmayi
   sectiyse tum animasyon/gecisleri kapatan global medya sorgusu (erisilebilirlik).
3. Sidebar nav butonlarina focus-visible halkasi (klavye erisilebilirligi).
4. Button gecisinin hareket tokenlarina baglanmasi (transition-all -> sure tokeni).

Kapsam disi: uyarlanabilir/ajan UI (ayri, genis alt sistem), PyQt6 QSS animasyonlari
(Qt stil sayfalari sinirli; PyQt6 erisilebilirlik zaten Qt varsayilanlarinda).

## Test plani

- Vitest: tokens.css'de yeni hareket tokenlari ve index.css'de prefers-reduced-motion
  medya sorgusunun varligi (css icerik testi).
- Vitest: Sidebar nav butonlarinin focus-visible sinifi icerdigi.
- Mevcut vitest suiti (79 test) + tsc+vite build temiz kalir.
- Python tarafi degismez; tam suit %100 / 0 FAILED korunur.

## Uygulama sirasi

1. tokens.css hareket tokenlari + index.css reduced-motion
2. Sidebar focus-visible + Button gecis tokeni
3. Vitest testleri + build + commit