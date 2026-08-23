// PkgForge desktop i18n bridge (F4.11).
// Scope (honest): covers the Faz-3/4 Settings cards and batch controls.
// Full-app translation remains future work; legacy pages stay Turkish.

export type Lang = "tr" | "en";

export const dict = {
  tr: {
    profilesTitle: "Profiller",
    profilesCreate: "Oluştur",
    profilesDelete: "Sil",
    backupTitle: "Yedekleme & Senkronizasyon",
    backupSaveServer: "Sunucuyu Kaydet",
    backupPush: "Buluta Gönder",
    backupPull: "Buluttan Çek",
    dbusTitle: "D-Bus Servisi",
    dbusStart: "Başlat",
    dbusRunning: "Çalışıyor",
    dbusStopped: "Kapalı",
    batchInstallSerial: "Kur (seri)",
  },
  en: {
    profilesTitle: "Profiles",
    profilesCreate: "Create",
    profilesDelete: "Delete",
    backupTitle: "Backup & Sync",
    backupSaveServer: "Save Server",
    backupPush: "Push to Cloud",
    backupPull: "Pull from Cloud",
    dbusTitle: "D-Bus Service",
    dbusStart: "Start",
    dbusRunning: "Running",
    dbusStopped: "Stopped",
    batchInstallSerial: "Install (serial)",
  },
} as const;

export type I18nKey = keyof typeof dict.tr;

export function tFor(lang: string): ((k: I18nKey) => string) {
  const d = (dict as Record<string, Record<string, string>>)[lang] ?? dict.tr;
  return (k) => d[k] ?? dict.tr[k];
}
