import { useCallback, useEffect, useMemo, useState } from "react";
import { CloudDownload, CloudUpload, HardDriveDownload, HardDriveUpload, Plus, Save, Trash2 } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import { tFor, type I18nKey } from "../lib/i18n";
import { setLang } from "../lib/lang";
import { applyTheme } from "../lib/theme";
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
  compat_policy: string;
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
  compat_policy: "standard",
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
  const [tab, setTab] = useState<"general" | "profiles" | "cloud">("general");
  // C2: profiles
  const [profiles, setProfiles] = useState<{ name: string; active: boolean }[]>([]);
  const [newProfile, setNewProfile] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  // C3: backup & cloud sync
  const [backupPath, setBackupPath] = useState("");
  const [importPath, setImportPath] = useState("");
  const [syncUrl, setSyncUrl] = useState("");
  const [syncUser, setSyncUser] = useState("");
  const [syncPass, setSyncPass] = useState("");
  const [syncBusy, setSyncBusy] = useState(false);
  // C1: D-Bus service
  const [dbusStatus, setDbusStatus] = useState<
    { available: boolean; running: boolean; bus_name: string } | null
  >(null);
  const [dbusBusy, setDbusBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const raw = await call<
        Partial<SettingsShape> & { sync_url?: string; sync_username?: string }
      >("settings.get");
      setSettings({ ...DEFAULTS, ...raw });
      setSyncUrl(typeof raw.sync_url === "string" ? raw.sync_url : "");
      setSyncUser(typeof raw.sync_username === "string" ? raw.sync_username : "");
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

  const loadDbusStatus = useCallback(async () => {
    try {
      const st = await call<{
        available: boolean;
        running: boolean;
        bus_name: string;
      }>("dbus.status");
      setDbusStatus(st);
    } catch {
      setDbusStatus(null);
    }
  }, []);

  useEffect(() => {
    void load();
    void loadProfiles();
    void loadDbusStatus();
  }, [load, loadProfiles, loadDbusStatus]);

  // F4.11: live tr/en bridge for the Faz-3/4 cards.
  const t = useMemo(() => tFor(settings.language), [settings.language]);

  // F5.20: broadcast the chosen language to the shared store so every other
  // mounted page (e.g. Convert) re-renders in the new language live.
  useEffect(() => {
    if (settings.language === "tr" || settings.language === "en") {
      setLang(settings.language);
    }
  }, [settings.language]);

  const set = <K extends keyof SettingsShape>(key: K, value: SettingsShape[K]) =>
    setSettings((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await call("settings.set", settings);
      toast("success", t("setSaved"));
      // Apply theme immediately (system tercihini de cozer).
      applyTheme(settings.theme);
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

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    void onEvent<{ ok: boolean; error?: string; result?: { path?: string } }>(
      "event/sync_done",
      (payload) => {
        if (payload.ok) {
          toast("success", `Bulut işlemi tamamlandı${payload.result?.path ? ": " + payload.result.path : ""}`);
        } else {
          toast("error", payload.error ?? "Bulut işlemi başarısız");
        }
      },
    ).then((fn) => {
      unlisten = fn as () => void;
    });
    return () => unlisten?.();
  }, [toast]);

  const runSyncCall = async (method: string, params: Record<string, unknown>, done: string) => {
    setSyncBusy(true);
    try {
      await call(method, params);
      if (done) toast("success", done);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setSyncBusy(false);
    }
  };

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    void onEvent<{ ok: boolean; error?: string }>(
      "event/dbus_done",
      (payload) => {
        if (payload.ok) {
          toast("success", "D-Bus servisi yayında");
        } else {
          toast("error", payload.error ?? "D-Bus servisi başlatılamadı");
        }
        void loadDbusStatus();
      },
    ).then((fn) => {
      unlisten = fn as () => void;
    });
    return () => unlisten?.();
  }, [toast, loadDbusStatus]);

  const handleDbusStart = async () => {
    setDbusBusy(true);
    try {
      await call("dbus.start");
    } catch (e) {
      toast("error", (e as Error).message);
      setDbusBusy(false);
    }
    // status refresh arrives via event/dbus_done handler
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
        {/* Faz 7: ayar sekmeleri (10) */}
        <div className="flex gap-1 border-b border-[var(--border-subtle)]">
          {(
            [
              { id: "general", labelKey: "setTabGeneral" },
              { id: "profiles", labelKey: "setTabProfiles" },
              { id: "cloud", labelKey: "setTabCloud" },
            ] as { id: "general" | "profiles" | "cloud"; labelKey: I18nKey }[]
          ).map(({ id, labelKey }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={
                "rounded-t-md px-3 py-2 text-sm font-medium transition-colors " +
                (tab === id
                  ? "border-b-2 border-[var(--brand-blue)] text-[var(--brand-blue)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]")
              }
            >
              {t(labelKey)}
            </button>
          ))}
        </div>

        {tab === "general" && (<>
        <Card>
          <CardHeader>
            <CardTitle>{t("setAppearance")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">{t("setLang")}</span>
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
              <span className="text-[var(--text-secondary)]">
                {t("setCompat")}
              </span>
              <select
                value={settings.compat_policy}
                onChange={(e) => set("compat_policy", e.target.value)}
                className="h-10 rounded-[var(--radius-input)] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 text-sm text-[var(--text-primary)]"
              >
                <option value="standard">{t("setCompatStandard")}</option>
                <option value="strict">{t("setCompatStrict")}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">{t("setTheme")}</span>
              <select
                value={settings.theme}
                onChange={(e) => {
                  set("theme", e.target.value);
                  applyTheme(e.target.value); // aninda onizleme
                }}
                className="h-10 rounded-[var(--radius-input)] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 text-sm text-[var(--text-primary)]"
              >
                <option value="dark">{t("setThemeDark")}</option>
                <option value="light">{t("setThemeLight")}</option>
                <option value="system">{t("setThemeSystem")}</option>
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

        </>)}

        {tab === "profiles" && (<>
        <Card>
          <CardHeader>
            <CardTitle>{t("profilesTitle")}</CardTitle>
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
                    <Trash2 size={14} /> {t("profilesDelete")}
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
                <Plus size={15} /> {t("profilesCreate")}
              </Button>
            </div>
          </CardContent>
        </Card>

        </>)}

        {tab === "cloud" && (<>
        <Card>
          <CardHeader>
            <CardTitle>{t("backupTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {/* Local zip backup */}
            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[var(--text-primary)]">Yerel yedek (zip)</span>
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Yedek yolu (boş = varsayılan)…"
                  value={backupPath}
                  onChange={(e) => setBackupPath(e.target.value)}
                />
                <Button
                  disabled={syncBusy}
                  onClick={() => void runSyncCall("sync.export", { output_path: backupPath || undefined }, "Yedek oluşturuldu")}
                >
                  <HardDriveDownload size={15} /> Dışa Aktar
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Geri yüklenecek yedek dosyası…"
                  value={importPath}
                  onChange={(e) => setImportPath(e.target.value)}
                />
                <Button
                  disabled={syncBusy}
                  onClick={() => void runSyncCall("sync.import", { backup_path: importPath }, "Yedek geri yüklendi")}
                >
                  <HardDriveUpload size={15} /> İçe Aktar
                </Button>
              </div>
            </div>

            {/* WebDAV */}
            <div className="flex flex-col gap-2 border-t border-[var(--border-subtle)] pt-3">
              <span className="text-sm font-medium text-[var(--text-primary)]">WebDAV bulut senkronizasyonu</span>
              <Input
                placeholder="https://sunucu/dav/"
                value={syncUrl}
                onChange={(e) => setSyncUrl(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="Kullanıcı adı"
                  value={syncUser}
                  onChange={(e) => setSyncUser(e.target.value)}
                />
                <Input
                  type="password"
                  placeholder="Şifre"
                  value={syncPass}
                  onChange={(e) => setSyncPass(e.target.value)}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={syncBusy}
                  onClick={() =>
                    void runSyncCall(
                      "sync.config",
                      {
                        sync_url: syncUrl,
                        sync_username: syncUser,
                        ...(syncPass ? { sync_password: syncPass } : {}),
                      },
                      "Senkron ayarları kaydedildi",
                    )
                  }
                >
                  <Save size={14} /> {t("backupSaveServer")}
                </Button>
                <Button
                  size="sm"
                  disabled={syncBusy || !syncUrl.trim()}
                  onClick={() => void runSyncCall("sync.push", {}, "")}
                >
                  <CloudUpload size={14} /> {t("backupPush")}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={syncBusy || !syncUrl.trim()}
                  onClick={() => void runSyncCall("sync.pull", {}, "")}
                >
                  <CloudDownload size={14} /> {t("backupPull")}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("dbusTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {dbusStatus === null ? (
              <p className="text-sm text-[var(--text-muted)]">
                D-Bus durumu okunamadı.
              </p>
            ) : (
              <>
                <p className="text-sm text-[var(--text-secondary)]">
                  Üçüncü taraf araçlar aynı JSON-RPC yöntemlerini oturum
                  veriyolu üzerinden çağırabilir.
                </p>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {dbusStatus.bus_name}
                  </span>
                  <span
                    className={
                      "rounded-full px-2 py-0.5 text-xs " +
                      (dbusStatus.running
                        ? "bg-emerald-500/15 text-emerald-400"
                        : "bg-[var(--bg-elevated)] text-[var(--text-muted)]")
                    }
                  >
                    {dbusStatus.running ? t("dbusRunning") : t("dbusStopped")}
                  </span>
                </div>
                {!dbusStatus.available && (
                  <p className="text-xs text-[var(--text-muted)]">
                    jeepney paketi gerekli: pip install jeepney
                  </p>
                )}
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    disabled={dbusBusy || !dbusStatus.available || dbusStatus.running}
                    onClick={() => void handleDbusStart()}
                  >
                    {t("dbusStart")}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
        </>)}

        <div className="flex justify-end pb-4">
          <Button onClick={() => void handleSave()} disabled={saving}>
            <Save size={15} /> {saving ? t("setSaving") : t("updatesSave")}
          </Button>
        </div>
      </div>
    </div>
  );
}
