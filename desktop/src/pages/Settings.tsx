import { useCallback, useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { call } from "../lib/rpc";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";

/** Setting keys mirror the PyQt6 settings_dialog for full parity. */
interface SettingsShape {
  language: string;
  theme: string;
  aur_check: boolean;
  distrobox_fallback: boolean;
  clamav_scan: boolean;
  snapshot: boolean;
  dry_run: boolean;
  allow_insecure_http: boolean;
  timeout_seconds: number;
  output_dir: string;
  verbose: boolean;
  auto_sign: boolean;
}

const DEFAULTS: SettingsShape = {
  language: "tr",
  theme: "dark",
  aur_check: true,
  distrobox_fallback: false,
  clamav_scan: true,
  snapshot: true,
  dry_run: false,
  allow_insecure_http: false,
  timeout_seconds: 120,
  output_dir: "",
  verbose: false,
  auto_sign: false,
};

const BOOL_FIELDS: { key: keyof SettingsShape; label: string; hint?: string }[] = [
  { key: "aur_check", label: "AUR güncelleme kontrolü", hint: "Kurulumdan önce AUR'da daha yeni sürüm ara" },
  { key: "distrobox_fallback", label: "Distrobox geri dönüşü", hint: "Uyumsuz paketleri konteynerde çalıştırmayı öner" },
  { key: "clamav_scan", label: "ClamAV malware taraması", hint: "Dönüşüm öncesi antivirüs taraması (clamscan gerekli)" },
  { key: "snapshot", label: "Otomatik yedek (snapshot)", hint: "Kurulumdan önce mevcut paketin yedeğini al" },
  { key: "dry_run", label: "Kuru çalıştırma (dry-run)", hint: "Gerçek kurulum yapmadan simüle et" },
  { key: "allow_insecure_http", label: "Güvensiz HTTP'ye izin ver", hint: "Yalnızca http:// URL indirmelerine izin ver (önerilmez)" },
  { key: "verbose", label: "Ayrıntılı log", hint: "Daha fazla hata ayıklama çıktısı" },
  { key: "auto_sign", label: "Otomatik imzalama", hint: "Dönüştürülen paketleri otomatik imzala" },
];

export function Settings() {
  const { toast } = useToast();
  const [settings, setSettings] = useState<SettingsShape>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // C2: profiles
  const [profiles, setProfiles] = useState<{ name: string; active: boolean }[]>([]);
  const [newProfile, setNewProfile] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const raw = await call<Partial<SettingsShape>>("settings.get");
      setSettings({ ...DEFAULTS, ...raw });
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadProfiles = useCallback(async () => {
    try {
      const list = await call<{ name: string; active: boolean }[]>("profile.list");
      if (Array.isArray(list)) setProfiles(list);
    } catch {
      // Profile support unavailable (old sidecar) - leave the card empty.
    }
  }, []);

  useEffect(() => {
    void load();
    void loadProfiles();
  }, [load, loadProfiles]);

  const set = <K extends keyof SettingsShape>(key: K, value: SettingsShape[K]) =>
    setSettings((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await call("settings.set", settings);
      toast("success", "Ayarlar kaydedildi");
      // Apply theme immediately.
      document.documentElement.setAttribute("data-theme", settings.theme === "light" ? "light" : "dark");
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const refreshAll = useCallback(async () => {
    await Promise.all([load(), loadProfiles()]);
  }, [load, loadProfiles]);

  const handleCreateProfile = async () => {
    const name = newProfile.trim();
    if (!name) return;
    setProfileBusy(true);
    try {
      await call("profile.create", { name });
      setNewProfile("");
      await loadProfiles();
      toast("success", `Profil oluşturuldu: ${name}`);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setProfileBusy(false);
    }
  };

  const handleSwitchProfile = async (name: string) => {
    setProfileBusy(true);
    try {
      await call("profile.switch", { name });
      await refreshAll();
      toast("success", `Profil değiştirildi: ${name}`);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setProfileBusy(false);
    }
  };

  const handleDeleteProfile = async (name: string) => {
    setProfileBusy(true);
    try {
      await call("profile.delete", { name });
      await loadProfiles();
      toast("success", `Profil silindi: ${name}`);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setProfileBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4 p-5">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-60 w-full" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Görünüm & Dil</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">Dil</span>
              <select
                value={settings.language}
                onChange={(e) => set("language", e.target.value)}
                className="h-10 rounded-[var(--radius-input)] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 text-sm text-[var(--text-primary)]"
              >
                <option value="tr">Türkçe</option>
                <option value="en">English</option>
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">Tema</span>
              <select
                value={settings.theme}
                onChange={(e) => set("theme", e.target.value)}
                className="h-10 rounded-[var(--radius-input)] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 text-sm text-[var(--text-primary)]"
              >
                <option value="dark">Koyu</option>
                <option value="light">Açık</option>
                <option value="system">Sistem</option>
              </select>
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Dönüştürme & Güvenlik</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {BOOL_FIELDS.map(({ key, label, hint }) => (
              <label key={key} className="flex items-start justify-between gap-4">
                <span>
                  <span className="block text-sm font-medium text-[var(--text-primary)]">{label}</span>
                  {hint && <span className="block text-xs text-[var(--text-muted)]">{hint}</span>}
                </span>
                <input
                  type="checkbox"
                  checked={settings[key] as boolean}
                  onChange={(e) => set(key, e.target.checked as SettingsShape[typeof key])}
                  className="mt-1 h-4 w-4 accent-[var(--brand-blue)]"
                />
              </label>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Gelişmiş</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">Zaman aşımı (saniye)</span>
              <Input
                type="number"
                min={10}
                max={3600}
                value={settings.timeout_seconds}
                onChange={(e) => set("timeout_seconds", Number(e.target.value) || 120)}
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">Çıktı dizini (boş = varsayılan)</span>
              <Input
                placeholder="/home/kullanici/paketler"
                value={settings.output_dir}
                onChange={(e) => set("output_dir", e.target.value)}
              />
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Profiller</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {profiles.length === 0 && (
              <p className="text-sm text-[var(--text-muted)]">
                Profil yüklenemedi veya kullanılamıyor.
              </p>
            )}
            {profiles.map((p) => (
              <div key={p.name} className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="active-profile"
                    checked={p.active}
                    disabled={p.active || profileBusy}
                    onChange={() => void handleSwitchProfile(p.name)}
                    className="h-4 w-4 accent-[var(--brand-blue)]"
                  />
                  <span className="font-medium text-[var(--text-primary)]">{p.name}</span>
                  {p.active && (
                    <span className="text-xs text-[var(--text-muted)]">(etkin)</span>
                  )}
                </label>
                {p.name !== "default" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={profileBusy}
                    onClick={() => void handleDeleteProfile(p.name)}
                  >
                    <Trash2 size={14} /> Sil
                  </Button>
                )}
              </div>
            ))}
            <div className="flex items-center gap-2 pt-1">
              <Input
                placeholder="Yeni profil adı…"
                value={newProfile}
                onChange={(e) => setNewProfile(e.target.value)}
              />
              <Button onClick={() => void handleCreateProfile()} disabled={profileBusy}>
                <Plus size={15} /> Oluştur
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end pb-4">
          <Button onClick={() => void handleSave()} disabled={saving}>
            <Save size={15} /> {saving ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </div>
      </div>
    </div>
  );
}
