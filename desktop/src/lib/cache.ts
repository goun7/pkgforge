// Faz 8 (6.1): basit sureli bellek-ici cache (stale-while-revalidate).
// Sik degismeyen sayfa verileri her mount'ta yeniden cekilmesin.
const store = new Map<string, { value: unknown; ts: number }>();

/** Anahtar icin cache'li deger; yoksa veya TTL asilmissa null doner. */
export function cacheGet<T>(key: string, ttlMs: number): T | null {
  const hit = store.get(key);
  if (!hit) return null;
  if (Date.now() - hit.ts > ttlMs) return null;
  return hit.value as T;
}

/** Cache'e deger yazar (zaman damgasi simdi). */
export function cacheSet<T>(key: string, value: T): void {
  store.set(key, { value, ts: Date.now() });
}

/** Bir anahtari cache'den dusurur (orn. elle yenileme). */
export function cacheInvalidate(key: string): void {
  store.delete(key);
}
