import { useCallback, useEffect, useState } from "react";
import { Package, Container, Boxes, Loader2, FolderOpen } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { FlatpakApp, ExportResult } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { PathPicker, PKG_DIALOG_FILTERS } from "../components/PathPicker";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { cn } from "../lib/utils";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

/** Faz 7 (6.2): Flatpak listesi icin modul duzeyi onbellek. */
let flatpakCache: FlatpakApp[] | null = null;

/** Testler icin onbellegi sifirlar. */
export function __resetFlatpakCache(): void {
  flatpakCache = null;
}

export function Export() {
  const { toast } = useToast();
  const lang = useLang();
  const t = tFor(lang);

  // AppImage -> DEB
  const [appimagePath, setAppimagePath] = useState("");
  const [appimageBusy, setAppimageBusy] = useState(false);
  const [appimageResult, setAppimageResult] = useState<ExportResult | null>(null);

  // Flatpak -> DEB
  const [flatpakApps, setFlatpakApps] = useState<FlatpakApp[]>([]);
  const [flatpakLoading, setFlatpakLoading] = useState(true);
  const [selectedApp, setSelectedApp] = useState<string>("");
  const [flatpakBusy, setFlatpakBusy] = useState(false);
  const [flatpakResult, setFlatpakResult] = useState<ExportResult | null>(null);

  // OCI
  const [ociPath, setOciPath] = useState("");
  const [ociTag, setOciTag] = useState("");
  const [ociBusy, setOciBusy] = useState(false);
  const [ociResult, setOciResult] = useState<ExportResult | null>(null);

  const loadFlatpak = useCallback(
    async (force = false) => {
      // Faz 7 (6.2): sayfa degisince gereksiz yeniden yuklemeyi onlemek icin
      // sonuc onbellege alinir; Yenile dugmesi force=true ile tazeler.
      if (!force && flatpakCache) {
        setFlatpakApps(flatpakCache);
        setFlatpakLoading(false);
        return;
      }
      setFlatpakLoading(true);
      try {
        const res = await call<FlatpakApp[]>("export.flatpak_list");
        flatpakCache = res;
        setFlatpakApps(res);
      } catch (e) {
        toast("error", (e as Error).message);
      } finally {
        setFlatpakLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void loadFlatpak();
  }, [loadFlatpak]);

  // shared export-done listener (one per active op)
  const subscribeExportDone = async (
    setBusy: (b: boolean) => void,
    setResult: (r: ExportResult) => void,
  ) => {
    const un = await onEvent<{ ok: boolean; result?: ExportResult; error?: string }>(
      "event/export_done",
      (p) => {
        setBusy(false);
        if (p.ok && p.result) {
          setResult(p.result);
          if (p.result.ok) toast("success", p.result.message);
          else toast("error", p.result.message);
        } else {
          toast("error", p.error ?? t("expFail"));
        }
        void un();
      },
    );
  };

  const handleAppimage = async () => {
    if (!appimagePath.trim()) {
      toast("error", t("expNeedAppimage"));
      return;
    }
    setAppimageBusy(true);
    setAppimageResult(null);
    await subscribeExportDone(setAppimageBusy, setAppimageResult);
    try {
      await call("export.appimage_to_deb", { appimage_path: appimagePath });
    } catch (e) {
      setAppimageBusy(false);
      toast("error", (e as Error).message);
    }
  };

  const handleFlatpak = async () => {
    if (!selectedApp) {
      toast("error", t("expNeedFlatpak"));
      return;
    }
    setFlatpakBusy(true);
    setFlatpakResult(null);
    await subscribeExportDone(setFlatpakBusy, setFlatpakResult);
    try {
      await call("export.flatpak_to_deb", { app_id: selectedApp });
    } catch (e) {
      setFlatpakBusy(false);
      toast("error", (e as Error).message);
    }
  };

  const handleOci = async () => {
    if (!ociPath.trim()) {
      toast("error", t("expNeedPkg"));
      return;
    }
    setOciBusy(true);
    setOciResult(null);
    await subscribeExportDone(setOciBusy, setOciResult);
    try {
      await call("export.oci", { pkg_path: ociPath, tag: ociTag || undefined });
    } catch (e) {
      setOciBusy(false);
      toast("error", (e as Error).message);
    }
  };

  const resultBadge = (r: ExportResult | null, onRetry?: () => void) =>
    r ? (
      <div className="mt-2 flex items-center gap-2">
        <Badge tone={r.ok ? "success" : "danger"}>{r.ok ? t("exportSuccess") : t("exportFailed")}</Badge>
        <span className="truncate text-xs text-[var(--text-muted)]">{r.message}</span>
        {!r.ok && onRetry && (
          <button
            onClick={onRetry}
            className="shrink-0 text-xs font-semibold text-[var(--brand-blue)] hover:underline"
          >
            {t("commonRetry")}
          </button>
        )}
      </div>
    ) : null;

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* AppImage -> DEB */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package size={17} className="text-[var(--brand-blue)]" />
              AppImage → DEB
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <PathPicker
              placeholder={t("exportAppimagePh")}
              value={appimagePath}
              onChange={setAppimagePath}
              filters={[{ name: "AppImage", extensions: ["AppImage", "appimage"] }]}
              title={t("exportSelectAppimage")}
            />
            <Button size="sm" onClick={() => void handleAppimage()} disabled={appimageBusy}>
              {appimageBusy ? <Loader2 size={14} className="animate-spin" /> : <FolderOpen size={14} />}
              {t("exportConvert")}
            </Button>
            {appimageBusy && <Skeleton className="h-8 w-full" />}
            {resultBadge(appimageResult, () => void handleAppimage())}
            {appimageResult?.ok && appimageResult.deb_path && (
              <p className="truncate text-xs font-mono text-[var(--text-secondary)]">{appimageResult.deb_path}</p>
            )}
          </CardContent>
        </Card>

        {/* Flatpak -> DEB */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Boxes size={17} className="text-[var(--brand-ember)]" />
              Flatpak → DEB
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={() => void loadFlatpak(true)}>{t("toolsRefresh")}</Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {flatpakLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : flatpakApps.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">{t("exportFlatpakEmpty")}</p>
            ) : (
              <div className="max-h-40 overflow-y-auto rounded-md border border-[var(--border-subtle)]">
                {flatpakApps.map((app) => (
                  <button
                    key={app.app_id}
                    onClick={() => setSelectedApp(app.app_id)}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-xs transition-colors",
                      selectedApp === app.app_id
                        ? "bg-[var(--brand-blue)]/12 text-[var(--brand-blue)]"
                        : "hover:bg-[var(--bg-elevated)]",
                    )}
                  >
                    <span className="truncate">{app.name || app.app_id}</span>
                    <span className="ml-2 shrink-0 text-[var(--text-muted)]">{app.version}</span>
                  </button>
                ))}
              </div>
            )}
            <Button size="sm" onClick={() => void handleFlatpak()} disabled={flatpakBusy || !selectedApp}>
              {flatpakBusy ? <Loader2 size={14} className="animate-spin" /> : <FolderOpen size={14} />}
              {t("exportConvert")}
            </Button>
            {flatpakBusy && <Skeleton className="h-8 w-full" />}
            {resultBadge(flatpakResult, () => void handleFlatpak())}
          </CardContent>
        </Card>

        {/* OCI container */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Container size={17} className="text-[var(--success)]" />
              OCI Container
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <PathPicker
              placeholder={t("exportOciPh")}
              value={ociPath}
              onChange={setOciPath}
              filters={PKG_DIALOG_FILTERS}
              title={t("exportSelectPkg")}
            />
            <Input
              placeholder={t("exportOciTag")}
              value={ociTag}
              onChange={(e) => setOciTag(e.target.value)}
              className="h-9"
            />
            <Button size="sm" onClick={() => void handleOci()} disabled={ociBusy}>
              {ociBusy ? <Loader2 size={14} className="animate-spin" /> : <Container size={14} />}
              {t("exportOciCreate")}
            </Button>
            {ociBusy && <Skeleton className="h-8 w-full" />}
            {resultBadge(ociResult, () => void handleOci())}
            {ociResult?.ok && ociResult.output_path && (
              <p className="truncate text-xs font-mono text-[var(--text-secondary)]">{ociResult.output_path}</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
