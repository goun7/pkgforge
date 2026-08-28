import { useEffect, useState } from "react";
import { GitCompare, Loader2, ArrowRight } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { SbomDiff } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { PathPicker, PKG_DIALOG_FILTERS } from "../components/PathPicker";
import { EmptyState } from "../components/EmptyState";
import { useToast } from "../components/ui/Toast";

function fmtSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
  return bytes + " B";
}

export function Compare() {
  const { toast } = useToast();
  const [oldPath, setOldPath] = useState("");
  const [newPath, setNewPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [diff, setDiff] = useState<SbomDiff | null>(null);

  useEffect(() => {
    let un: (() => void) | undefined;
    void onEvent<{ ok: boolean; result?: SbomDiff; error?: string }>(
      "event/compare_done",
      (p) => {
        setBusy(false);
        if (p.ok && p.result) setDiff(p.result);
        else toast("error", p.error ?? "Karşılaştırma başarısız");
      },
    ).then((u) => { un = u; });
    return () => { if (un) un(); };
  }, [toast]);

  const handleCompare = async () => {
    if (!oldPath.trim() || !newPath.trim()) {
      toast("error", "İki paket yolu da gerekli");
      return;
    }
    setBusy(true);
    setDiff(null);
    try {
      await call("compare.diff", { old_path: oldPath, new_path: newPath });
    } catch (e) {
      setBusy(false);
      toast("error", (e as Error).message);
    }
  };

  const noChange = diff &&
    !diff.added_files.length && !diff.removed_files.length && !diff.changed_files.length &&
    !diff.added_deps.length && !diff.removed_deps.length && !diff.version_changes.length;

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader>
          <CardTitle>Paket Karşılaştırma</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-[var(--text-muted)]">
            İki paket sürümünü SBOM üzerinden karşılaştır: dosya listesi, boyut ve bağımlılık farkları.
          </p>
          <div className="flex flex-col gap-2">
            <PathPicker
              placeholder="Eski paket yolu (.pkg.tar.zst)…"
              value={oldPath}
              onChange={setOldPath}
              filters={PKG_DIALOG_FILTERS}
              title="Eski paketi seç"
            />
            <PathPicker
              placeholder="Yeni paket yolu (.pkg.tar.zst)…"
              value={newPath}
              onChange={setNewPath}
              filters={PKG_DIALOG_FILTERS}
              title="Yeni paketi seç"
            />
          </div>
          <Button onClick={() => void handleCompare()} disabled={busy}>
            {busy ? <Loader2 size={15} className="animate-spin" /> : <GitCompare size={15} />}
            Karşılaştır
          </Button>

          {!diff && !busy && (
            <EmptyState
              icon={GitCompare}
              title="Henüz karşılaştırma yok"
              description="İki paket seçip Karşılaştır düğmesine basın; dosya, boyut ve bağımlılık farkları burada görünecek."
            />
          )}

          {diff && (
            <div className="space-y-3 pt-2">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium">{diff.old_name} {diff.old_version}</span>
                <ArrowRight size={14} className="text-[var(--text-muted)]" />
                <span className="font-medium">{diff.new_name} {diff.new_version}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div className="rounded-md bg-[var(--bg-elevated)] p-2 text-center">
                  <div className="text-lg font-semibold">{diff.old_total_files} → {diff.new_total_files}</div>
                  <div className="text-xs text-[var(--text-muted)]">dosya</div>
                </div>
                <div className="rounded-md bg-[var(--bg-elevated)] p-2 text-center">
                  <div className="text-lg font-semibold">{fmtSize(diff.old_total_size)} → {fmtSize(diff.new_total_size)}</div>
                  <div className="text-xs text-[var(--text-muted)]">boyut</div>
                </div>
                <div className="rounded-md bg-[var(--bg-elevated)] p-2 text-center">
                  <div className="text-lg font-semibold text-[var(--success)]">+{diff.added_files.length}</div>
                  <div className="text-xs text-[var(--text-muted)]">eklenen</div>
                </div>
                <div className="rounded-md bg-[var(--bg-elevated)] p-2 text-center">
                  <div className="text-lg font-semibold text-[var(--danger)]">-{diff.removed_files.length}</div>
                  <div className="text-xs text-[var(--text-muted)]">silinen</div>
                </div>
              </div>

              {noChange && <Badge tone="success">Fark yok — paketler aynı</Badge>}

              {diff.added_deps.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Yeni bağımlılıklar</h4>
                  <div className="flex flex-wrap gap-1">
                    {diff.added_deps.map((d) => <Badge key={d} tone="success">{d}</Badge>)}
                  </div>
                </div>
              )}
              {diff.removed_deps.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Kaldırılan bağımlılıklar</h4>
                  <div className="flex flex-wrap gap-1">
                    {diff.removed_deps.map((d) => <Badge key={d} tone="danger">{d}</Badge>)}
                  </div>
                </div>
              )}
              {diff.version_changes.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Versiyon değişiklikleri</h4>
                  <div className="space-y-1">
                    {diff.version_changes.map((vc, i) => (
                      <div key={i} className="rounded-md bg-[var(--bg-elevated)] px-3 py-1.5 text-xs">
                        <span className="font-medium">{vc.dep}</span>: {vc.old} → {vc.new}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {diff.changed_files.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    Değişen dosyalar ({diff.changed_files.length})
                  </h4>
                  <div className="max-h-48 space-y-1 overflow-y-auto">
                    {diff.changed_files.map((cf, i) => (
                      <div key={i} className="truncate rounded-md bg-[var(--bg-elevated)] px-3 py-1.5 font-mono text-xs">
                        {cf.path}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {(diff.added_files.length > 0 || diff.removed_files.length > 0) && (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {diff.added_files.length > 0 && (
                    <div>
                      <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--success)]">Eklenen dosyalar</h4>
                      <div className="max-h-40 space-y-1 overflow-y-auto">
                        {diff.added_files.map((f) => (
                          <div key={f} className="truncate rounded-md bg-[var(--bg-elevated)] px-3 py-1 font-mono text-xs">{f}</div>
                        ))}
                      </div>
                    </div>
                  )}
                  {diff.removed_files.length > 0 && (
                    <div>
                      <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--danger)]">Silinen dosyalar</h4>
                      <div className="max-h-40 space-y-1 overflow-y-auto">
                        {diff.removed_files.map((f) => (
                          <div key={f} className="truncate rounded-md bg-[var(--bg-elevated)] px-3 py-1 font-mono text-xs">{f}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
