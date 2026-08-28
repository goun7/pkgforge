import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

const BOOL_FIELDS: { key: keyof SettingsShape; labelKey: I18nKey; hintKey: I18nKey }[] = [
  { key: "aur_check", labelKey: "setBoolAurCheck", hintKey: "setBoolAurCheckHint" },
  { key: "distrobox_fallback", labelKey: "setBoolDistrobox", hintKey: "setBoolDistroboxHint" },
  { key: "clamav_scan", labelKey: "setBoolClamav", hintKey: "setBoolClamavHint" },
  { key: "snapshot", labelKey: "setBoolSnapshot", hintKey: "setBoolSnapshotHint" },
  { key: "dry_run", labelKey: "setBoolDryRun", hintKey: "setBoolDryRunHint" },
  { key: "allow_insecure_http", labelKey: "setBoolInsecure", hintKey: "setBoolInsecureHint" },
  { key: "verbose", labelKey: "setBoolVerbose", hintKey: "setBoolVerboseHint" },
  { key: "auto_sign", labelKey: "setBoolAutoSign", hintKey: "setBoolAutoSignHint" },
];

/** Faz 8 (10.1): ayar arama indeksi (etiket + ipucu + hedef sekme). */
const SEARCH_INDEX: { labelKey: I18nKey; hintKey?: I18nKey; tab: "general" | "profiles" | "cloud" }[] = [
  { labelKey: "setLang", tab: "general" },
  { labelKey: "setCompat", tab: "general" },
  { labelKey: "setTheme", tab: "general" },
  ...BOOL_FIELDS.map((f) => ({ labelKey: f.labelKey, hintKey: f.hintKey, tab: "general" as const })),
  { labelKey: "setTimeout", tab: "general" },
  { labelKey: "setOutputDir", tab: "general" },
  { labelKey: "profilesTitle", tab: "profiles" },
  { labelKey: "backupTitle", tab: "cloud" },
  { labelKey: "setWebdavTitle", tab: "cloud" },
  { labelKey: "dbusTitle", tab: "cloud" },
];

export function Settings() {
  const { toast } = useToast();
  const [settings, setSettings] = useState<SettingsShape>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState<"general" | "profiles" | "cloud">("general");
  const [searchQuery, setSearchQuery] = useState("");
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
  const [appVersion, setAppVersion] = useState<string | null>(null);

  // Faz 9 (2.8): uygulama surumunu footer icin getir.
  useEffect(() => {
    let alive = true;
    call<{ name: string; version: string }>("app.version")
      .then((res) => {
        if (alive) setAppVersion(res.version);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

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

  // Faz 8 (10.2): varsayilanlara sifirla.
  const handleReset = async () => {
    setSaving(true);
    try {
      await call("settings.set", DEFAULTS);
      setSettings(DEFAULTS);
      applyTheme(DEFAULTS.theme);
      toast("success", t("setResetDone"));
    } catch (err) {
      toast("error", (err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  // Faz 8 (10.3): ayarlari JSON olarak disa/ice aktar.
  const fileInputRef = useRef<HTMLInputElement>(null);
  const handleExportSettings = () => {
    try {
      const blob = new Blob([JSON.stringify(settings, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "pkgforge-settings.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast("error", (err as Error).message);
    }
  };
  const handleImportFile = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text()) as Partial<SettingsShape>;
      await call("settings.set", parsed);
      setSettings({ ...DEFAULTS, ...parsed });
      toast("success", t("setImportDone"));
    } catch {
      toast("error", t("setImportFail"));
    }
  };

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
      toast("success", `${t("setProfileCreated")}: ${name}`);
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
      toast("success", `${t("setProfileSwitched")}: ${name}`);
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
      toast("success", `${t("setProfileDeleted")}: ${name}`);
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
          toast("success", `${t("setCloudDone")}${payload.result?.path ? ": " + payload.result.path : ""}`);
        } else {
          toast("error", payload.error ?? t("setCloudFail"));
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
          toast("success", t("setDbusPublished"));
        } else {
          toast("error", payload.error ?? t("setDbusFail"));
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

  // Faz 8 (10.1): ayar arama sonuclari.
  const q = searchQuery.trim().toLowerCase();
  const searchMatches = q
    ? SEARCH_INDEX.filter((entry) => {
        const label = t(entry.labelKey).toLowerCase();
        const hint = entry.hintKey ? t(entry.hintKey).toLowerCase() : "";
        return label.includes(q) || hint.includes(q);
      })
    : [];

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        {/* Faz 8 (10.1/10.2): ayar arama + varsayilanlara sifirla */}
        <div className="flex items-center gap-2">
          <Input
            placeholder={t("setSearchPh")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1"
          />
          <Button variant="ghost" size="sm" onClick={() => void handleReset()} disabled={saving}>
            {t("setResetDefaults")}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleExportSettings} disabled={saving}>
            <HardDriveDownload size={14} /> {t("setExportSettings")}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => fileInputRef.current?.click()} disabled={saving}>
            <HardDriveUpload size={14} /> {t("setImportSettings")}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleImportFile(file);
              e.target.value = "";
            }}
          />
        </div>

        {q ? (
          <Card>
            <CardContent className="flex flex-col gap-1 pt-3">
              {searchMatches.length === 0 ? (
                <p className="px-3 py-2 text-sm text-[var(--text-muted)]">{t("setSearchNoResult")}</p>
              ) : (
                searchMatches.map((m) => (
                  <button
                    key={m.labelKey}
                    onClick={() => { setTab(m.tab); setSearchQuery(""); }}
                    className="flex flex-col gap-0.5 rounded-md px-3 py-2 text-left hover:bg-[var(--bg-elevated)]"
                  >
                    <span className="text-sm font-medium text-[var(--text-primary)]">{t(m.labelKey)}</span>
                    {m.hintKey && <span className="text-xs text-[var(--text-muted)]">{t(m.hintKey)}</span>}
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        ) : (
          <>
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
                <option value="oled">{t("setThemeOled")}</option>
                <option value="system">{t("setThemeSystem")}</option>
              </select>
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("setConvertSecTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {BOOL_FIELDS.map(({ key, labelKey, hintKey }) => (
              <label key={key} className="flex items-start justify-between gap-4">
                <span>
                  <span className="block text-sm font-medium text-[var(--text-primary)]">{t(labelKey)}</span>
                  <span className="block text-xs text-[var(--text-muted)]">{t(hintKey)}</span>
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
            <CardTitle>{t("setAdvancedTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">{t("setTimeout")}</span>
              <Input
                type="number"
                min={10}
                max={3600}
                value={settings.timeout_seconds}
                onChange={(e) => set("timeout_seconds", Number(e.target.value) || 120)}
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[var(--text-secondary)]">{t("setOutputDir")}</span>
              <Input
                placeholder={t("setOutputDirPh")}
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
                {t("setProfilesUnavailable")}
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
                    <span className="text-xs text-[var(--text-muted)]">{t("setProfileActive")}</span>
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
                placeholder={t("setNewProfilePh")}
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
              <span className="text-sm font-medium text-[var(--text-primary)]">{t("setLocalBackup")}</span>
              <div className="flex items-center gap-2">
                <Input
                  placeholder={t("setBackupPathPh")}
                  value={backupPath}
                  onChange={(e) => setBackupPath(e.target.value)}
                />
                <Button
                  disabled={syncBusy}
                  onClick={() => void runSyncCall("sync.export", { output_path: backupPath || undefined }, t("setBackupCreated"))}
                >
                  <HardDriveDownload size={15} /> {t("setBackupExportBtn")}
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  placeholder={t("setImportPathPh")}
                  value={importPath}
                  onChange={(e) => setImportPath(e.target.value)}
                />
                <Button
                  disabled={syncBusy}
                  onClick={() => void runSyncCall("sync.import", { backup_path: importPath }, t("setBackupRestored"))}
                >
                  <HardDriveUpload size={15} /> {t("setBackupImportBtn")}
                </Button>
              </div>
            </div>

            {/* WebDAV */}
            <div className="flex flex-col gap-2 border-t border-[var(--border-subtle)] pt-3">
              <span className="text-sm font-medium text-[var(--text-primary)]">{t("setWebdavTitle")}</span>
              <Input
                placeholder="https://sunucu/dav/"
                value={syncUrl}
                onChange={(e) => setSyncUrl(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder={t("setWebdavUserPh")}
                  value={syncUser}
                  onChange={(e) => setSyncUser(e.target.value)}
                />
                <Input
                  type="password"
                  placeholder={t("setWebdavPassPh")}
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
                      t("setSyncSaved"),
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
                {t("setDbusUnavailable")}
              </p>
            ) : (
              <>
                <p className="text-sm text-[var(--text-secondary)]">
                  {t("setDbusDesc")}
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
                    {t("setDbusJeepney")}
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
          </>
        )}

        <div className="flex justify-end pb-4">
          <Button onClick={() => void handleSave()} disabled={saving}>
            <Save size={15} /> {saving ? t("setSaving") : t("updatesSave")}
          </Button>
        </div>

        {/* Faz 9 (2.8): uygulama surumu */}
        {appVersion && (
          <p className="pb-4 text-center text-xs text-[var(--text-muted)]">
            PkgForge {t("aboutVersion")} {appVersion}
          </p>
        )}
      </div>
    </div>
  );
}
