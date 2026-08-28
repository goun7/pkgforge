// Faz 8 (1.7): cogullastirma ve yerel bicimlendirme yardimcilari.

/** Basit tr/en cogullastirma. count 1 ise singular, aksi halde plural.
 *  withCount=true ise basin sayiyi da ekler ("5 kayit" / "1 kayit"). */
export function plural(count: number, singular: string, pluralForm: string, withCount = true): string {
  const word = count === 1 ? singular : pluralForm;
  return withCount ? `${count} ${word}` : word;
}

/** Yerel sayi bicimlendirme (orn. tr icin 1.234). */
export function fmtNumber(n: number, lang: string): string {
  try {
    return new Intl.NumberFormat(lang === "tr" ? "tr-TR" : "en-US").format(n);
  } catch {
    return String(n);
  }
}

/** Yerel tarih/saat bicimlendirme; gecersiz girdide ham degeri dondurur. */
export function fmtDate(input: string | number | Date, lang: string): string {
  try {
    const d = typeof input === "object" ? input : new Date(input);
    if (Number.isNaN(d.getTime())) return String(input);
    return new Intl.DateTimeFormat(lang === "tr" ? "tr-TR" : "en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(d);
  } catch {
    return String(input);
  }
}
