import { useCallback, useEffect, useState } from "react";
import { Package, Container, Boxes, Loader2, FolderOpen } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { FlatpakApp, ExportResult } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { cn } from "../lib/utils";

export function Export() {
  const { toast } = useToast();

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

  const loadFlatpak = useCallback(async () => {
    setFlatpakLoading(true);
    try {
      const res = await call<FlatpakApp[]>("export.flatpak_list");
      setFlatpakApps(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setFlatpakLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadFlatpak();
  }, [loadFlatpak]);

  // shared export-done listener (one per active op)
  const subscribeExportDone = async (
    setBusy: (b: boolean) => void,
    setResult: (r: ExportResult) => void,
  ) => {
    const un = await onEvent<{ ok: boolean; result?: ExportResult; error?: string }>(
      "event.export_done",
      (p) => {
        setBusy(false);
        if (p.ok && p.result) {
          setResult(p.result);
          if (p.result.ok) toast("success", p.result.message);
          else toast("error", p.result.message);
        } else {
          toast("error", p.error ?? "Dışa aktarma başarısız");
        }
        void un();
      },
    );
  };

  const handleAppimage = async () => {
    if (!appimagePath.trim()) {
      toast("error", "Bir AppImage dosyası seçin");
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
      toast("error", "Bir Flatpak uygulaması seçin");
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
      toast("error", "Bir .pkg.tar.zst paketi seçin");
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

  const resultBadge = (r: ExportResult | null) =>
    r ? (
      <div className="mt-2 flex items-center gap-2">
        <Badge tone={r.ok ? "success" : "danger"}>{r.ok ? "Başarılı" : "Başarısız"}</Badge>
        <span className="truncate text-xs text-[var(--text-muted)]">{r.message}</span>
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
            <div className="flex items-center gap-2">
              <Input
                placeholder="AppImage yolu…"
                value={appimagePath}
                onChange={(e) => setAppimagePath(e.target.value)}
                className="h-9 flex-1"
              />
            </div>
            <Button size="sm" onClick={() => void handleAppimage()} disabled={appimageBusy}>
              {appimageBusy ? <Loader2 size={14} className="animate-spin" /> : <FolderOpen size={14} />}
              Dönüştür
            </Button>
            {appimageBusy && <Skeleton className="h-8 w-full" />}
            {resultBadge(appimageResult)}
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
            <Button variant="ghost" size="sm" onClick={() => void loadFlatpak()}>Yenile</Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {flatpakLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : flatpakApps.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">Flatpak uygulaması bulunamadı.</p>
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
              Dönüştür
            </Button>
            {flatpakBusy && <Skeleton className="h-8 w-full" />}
            {resultBadge(flatpakResult)}
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
            <Input
              placeholder="Paket yolu (.pkg.tar.zst)…"
              value={ociPath}
              onChange={(e) => setOciPath(e.target.value)}
              className="h-9"
            />
            <Input
              placeholder="İmaj tag'i (opsiyonel)…"
              value={ociTag}
              onChange={(e) => setOciTag(e.target.value)}
              className="h-9"
            />
            <Button size="sm" onClick={() => void handleOci()} disabled={ociBusy}>
              {ociBusy ? <Loader2 size={14} className="animate-spin" /> : <Container size={14} />}
              İmaj Oluştur
            </Button>
            {ociBusy && <Skeleton className="h-8 w-full" />}
            {resultBadge(ociResult)}
            {ociResult?.ok && ociResult.output_path && (
              <p className="truncate text-xs font-mono text-[var(--text-secondary)]">{ociResult.output_path}</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
