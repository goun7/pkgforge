import { useCallback, useEffect, useState } from "react";
import { PackageCheck, RefreshCw, Trash2, Undo2, Rows3 } from "lucide-react";
import { cn } from "../lib/utils";
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
import { tFor, type I18nKey } from "../lib/i18n";

function statusToPill(status: string): PipelineStatus {
  if (status === "success" || status === "installed") return "success";
  if (status === "failed" || status === "error") return "failed";
  if (status === "cancelled") return "cancelled";
  return "pending";
}

/** Faz 8 (2.5): siralanabilir sutunlar. */
type SortCol = "timestamp" | "package_name" | "package_type" | "status";

export function Installed() {
  const { toast } = useToast();
  const t = tFor(useLang());
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  // Faz 8 (6.2): filtre sayfa degisince kaybolmasin.
  const [filter, setFilter] = useState(() => {
    try {
      return sessionStorage.getItem("pkgforge.installed.filter") ?? "";
    } catch {
      return "";
    }
  });
  useEffect(() => {
    try {
      sessionStorage.setItem("pkgforge.installed.filter", filter);
    } catch {
      /* depolama yok */
    }
  }, [filter]);
  const [pageCount, setPageCount] = useState(50);
  // Faz 9 (5.4): tablo yogunlugu (rahat/kompakt), kalici.
  const [density, setDensity] = useState<"comfortable" | "compact">(() => {
    try {
      return localStorage.getItem("pkgforge.density") === "compact" ? "compact" : "comfortable";
    } catch {
      return "comfortable";
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("pkgforge.density", density);
    } catch {
      /* depolama yok */
    }
  }, [density]);
  const toggleDensity = () => setDensity((d) => (d === "compact" ? "comfortable" : "compact"));
  const [sortCol, setSortCol] = useState<SortCol>("timestamp");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const toggleSort = (col: SortCol) => {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir(col === "timestamp" ? "desc" : "asc");
    }
  };
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
        toast("info", `${name}: ${t("instPrivUninstall")}`);
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
        toast("info", `${name}: ${t("instPrivRollback")}`);
      }
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  // Faz 9 (5.7): temizleme oncesi kayitlari yakala, "Geri Al" eylemi sun.
  const handleRestore = async (backup: HistoryRecord[]) => {
    try {
      await call("history.restore", { records: backup });
      toast("success", t("instRestored"));
      void load();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleClear = async () => {
    try {
      const backup = await call<HistoryRecord[]>("history.list", { limit: 10000 });
      await call("history.clear");
      void load();
      toast("success", t("instCleared"), {
        label: t("commonUndo"),
        onClick: () => void handleRestore(backup),
      });
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
  // Faz 8 (2.5): secilen sutuna gore sirala.
  const sorted = [...visible].sort((a, b) => {
    const av = String(a[sortCol] ?? "");
    const bv = String(b[sortCol] ?? "");
    const cmp = av.localeCompare(bv);
    return sortDir === "asc" ? cmp : -cmp;
  });
  // Faz 7 (6.3): cok kayitta tabloyu sinirla, "daha fazla" ile ac.
  const shown = sorted.slice(0, pageCount);

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2"><PackageCheck size={16} /> {t("instTitle")} ({records.length})</CardTitle>
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
            <Button
              variant="secondary"
              size="sm"
              onClick={toggleDensity}
              title={t("densityToggle")}
              aria-label={t("densityToggle")}
            >
              <Rows3 size={14} /> {density === "compact" ? t("densityCompact") : t("densityComfortable")}
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
              title={t("instEmptyTitle")}
              description={t("instEmptyDesc")}
            />
          ) : (
            <>
            <table className={cn("w-full text-sm", density === "compact" && "dense")}>
              <caption className="sr-only">{t("instCaption")}</caption>
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-left text-xs uppercase tracking-wide text-[var(--text-muted)]">
                  {([
                    { col: "timestamp", labelKey: "instColDate" },
                    { col: "package_name", labelKey: "instColPkg" },
                    { col: "package_type", labelKey: "instColType" },
                    { col: "status", labelKey: "instColStatus" },
                  ] as { col: SortCol; labelKey: I18nKey }[]).map(({ col, labelKey }) => (
                    <th key={col} scope="col" className="py-2 pr-3">
                      <button
                        onClick={() => toggleSort(col)}
                        aria-label={t(labelKey)}
                        title={sortCol === col && sortDir === "asc" ? t("sortDesc") : t("sortAsc")}
                        className="inline-flex items-center gap-1 hover:text-[var(--text-primary)]"
                      >
                        {t(labelKey)}
                        {sortCol === col && <span aria-hidden="true">{sortDir === "asc" ? "▲" : "▼"}</span>}
                      </button>
                    </th>
                  ))}
                  <th scope="col" className="py-2 pr-3">{t("instColSource")}</th>
                  <th scope="col" className="py-2">{t("instColActions")}</th>
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
