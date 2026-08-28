import { useCallback, useEffect, useState } from "react";
import { PackageCheck, RefreshCw, Trash2, Undo2 } from "lucide-react";
import { call } from "../lib/rpc";
import type { HistoryRecord } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { StatusPill, type PipelineStatus } from "../components/StatusPill";
import { EmptyState } from "../components/EmptyState";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

function statusToPill(status: string): PipelineStatus {
  if (status === "success" || status === "installed") return "success";
  if (status === "failed" || status === "error") return "failed";
  if (status === "cancelled") return "cancelled";
  return "pending";
}

export function Installed() {
  const { toast } = useToast();
  const t = tFor(useLang());
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [pageCount, setPageCount] = useState(50);
  const [confirm, setConfirm] = useState<
    null | { type: "clear" } | { type: "uninstall"; pkg: string }
  >(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await call<HistoryRecord[]>("history.list", { limit: 200 });
      setRecords(list);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleUninstall = async (name: string) => {
    try {
      const res = await call<{ requires_privilege?: boolean }>("history.uninstall", { name });
      if (res.requires_privilege) {
        toast("info", `${name}: kaldırma yetkili işlem gerektiriyor (pkexec) — Faz 1'de etkin`);
      }
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleRollback = async (name: string) => {
    try {
      const res = await call<{ requires_privilege?: boolean; backup?: string }>(
        "history.rollback",
        { name },
      );
      if (res.requires_privilege) {
        toast("info", `${name}: geri alma yetkili işlem gerektiriyor (pkexec) — Faz 1'de etkin`);
      }
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleClear = async () => {
    try {
      await call("history.clear");
      toast("success", "Geçmiş temizlendi");
      void load();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const visible = records.filter(
    (r) =>
      !filter ||
      r.package_name.toLowerCase().includes(filter.toLowerCase()) ||
      r.original_file.toLowerCase().includes(filter.toLowerCase()),
  );
  // Faz 7 (6.3): cok kayitta tabloyu sinirla, "daha fazla" ile ac.
  const shown = visible.slice(0, pageCount);

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Kurulanlar / Geçmiş ({records.length})</CardTitle>
          <div className="flex items-center gap-2">
            <Input
              placeholder={t("commonFilter")}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="h-9 w-56"
            />
            <Button variant="secondary" size="sm" onClick={() => void load()}>
              <RefreshCw size={14} /> {t("commonRefresh")}
            </Button>
            <Button variant="danger" size="sm" onClick={() => setConfirm({ type: "clear" })} disabled={!records.length}>
              <Trash2 size={14} /> {t("commonClear")}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : visible.length === 0 ? (
            <EmptyState
              icon={PackageCheck}
              title="Henüz kayıt yok"
              description="Dönüştürdüğünüz ve kurduğunuz paketler burada listelenecek."
            />
          ) : (
            <>
            <table className="w-full text-sm">
              <caption className="sr-only">Kurulan paketler geçmişi</caption>
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-left text-xs uppercase tracking-wide text-[var(--text-muted)]">
                  <th scope="col" className="py-2 pr-3">Tarih</th>
                  <th scope="col" className="py-2 pr-3">Paket</th>
                  <th scope="col" className="py-2 pr-3">Tür</th>
                  <th scope="col" className="py-2 pr-3">Durum</th>
                  <th scope="col" className="py-2 pr-3">Kaynak dosya</th>
                  <th scope="col" className="py-2">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.id} className="border-b border-[var(--border-subtle)]/50">
                    <td className="py-2.5 pr-3 text-xs text-[var(--text-secondary)]">{r.timestamp}</td>
                    <td className="py-2.5 pr-3 font-medium text-[var(--text-primary)]">{r.package_name}</td>
                    <td className="py-2.5 pr-3 text-[var(--text-secondary)]">{r.package_type}</td>
                    <td className="py-2.5 pr-3">
                      <StatusPill status={statusToPill(r.status)} />
                    </td>
                    <td className="max-w-[220px] truncate py-2.5 pr-3 text-xs text-[var(--text-muted)]">
                      {r.original_file}
                    </td>
                    <td className="py-2.5">
                      <div className="flex gap-1">
                        <button
                          aria-label={`${t("commonRemove")} ${r.package_name}`}
                          title={t("commonRemove")}
                          onClick={() => setConfirm({ type: "uninstall", pkg: r.package_name })}
                          className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--danger)]"
                        >
                          <Trash2 size={14} />
                        </button>
                        <button
                          aria-label={`${t("commonRollback")} ${r.package_name}`}
                          title={t("commonRollback")}
                          onClick={() => void handleRollback(r.package_name)}
                          className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--warning)]"
                        >
                          <Undo2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {visible.length > pageCount && (
              <div className="mt-3 flex justify-center">
                <Button variant="secondary" size="sm" onClick={() => setPageCount((c) => c + 50)}>
                  {t("loadMore")} ({visible.length - pageCount})
                </Button>
              </div>
            )}
            </>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.type === "clear" ? t("confirmClearTitle") : t("confirmUninstallTitle")}
        message={
          confirm?.type === "clear"
            ? t("confirmClearMsg")
            : confirm?.type === "uninstall"
              ? `${confirm.pkg} ${t("confirmUninstallMsg")}`
              : ""
        }
        confirmLabel={t("confirmConfirm")}
        cancelLabel={t("confirmCancel")}
        onConfirm={() => {
          if (confirm?.type === "clear") void handleClear();
          else if (confirm?.type === "uninstall") void handleUninstall(confirm.pkg);
          setConfirm(null);
        }}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
