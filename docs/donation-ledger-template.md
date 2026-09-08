# Bağış Defteri Şablonu (donation ledger)

Her bağışta BİR satır. Amaç üç ayrı hesabı tek yerden tutmak:
VİVK istisna takibi (transfer başına 66.935 TL, 2026) + bozdurma maliyeti
(FIFO) + yıllık beyan kanıtı. Bu şablon vergi tavsiyesi değildir; SMMM
ve (bekleyen) özelge cevabıyla birlikte kullanılır.

## Kurallar

- Dil DAİMA "destek/bağış" — asla "ödeme", "fiyat", "satın al" yazma.
- Karşılık vaat ETME (isim listesi, erken erişim, rozet, öncelik dahil).
- Her transferin TL karşılığı, alındığı günkü kurdan yazılır.
- Yıllık toplam + en büyük tek transfer ayrıca izlenir.

## Tablo

| # | Tarih | Zincir | TX hash | Tutar (kripto) | TL karşılığı | Kümülatif yıl | Not |
|---|-------|--------|---------|----------------|--------------|---------------|-----|
| 1 | YYYY-AA-GG | SOL | ... | 0.5 SOL | 0 TL | 0 TL | örnek satır |
| | | | | | | | |

## Bozdurma kaydı (ayrı tablo — satış ayrı vergisel olaydır)

| Tarih | Kaynak TX | Miktar | Satış TL | Maliyet (FIFO) | Borsa |
|-------|-----------|--------|----------|----------------|-------|
| | | | | | |

## Yıl sonu kontrol listesi

- [ ] En büyük tek transfer ≤ 66.935 TL mi? (değilse VİV beyannamesi: 1 ay)
- [ ] Bozdurma olduysa FIFO maliyet tablosu hazır mı?
- [ ] Cüzdan ekstreleri + bu defter SMMM'ye verildi mi?
- [ ] README/Giveth dilinde "ödeme/karşılık" dili tarandı mı?
