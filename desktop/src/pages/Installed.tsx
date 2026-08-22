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

function statusToPill(status: string): PipelineStatus {
  if (status === "success" || status === "installed") return "success";
  if (status === "failed" || status === "error") return "failed";
  if (status === "cancelled") return "cancelled";
  return "pending";
}

export function Installed() {
  const { toast } = useToast();
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

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

  return (
    <div className="h-full overflow-y-auto p-5">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Kurulanlar / Geçmiş ({records.length})</CardTitle>
          <div className="flex items-center gap-2">
            <Input
              placeholder="Filtrele…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="h-9 w-56"
            />
            <Button variant="secondary" size="sm" onClick={() => void load()}>
              <RefreshCw size={14} /> Yenile
            </Button>
            <Button variant="danger" size="sm" onClick={() => void handleClear()} disabled={!records.length}>
              <Trash2 size={14} /> Temizle
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
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-left text-xs uppercase tracking-wide text-[var(--text-muted)]">
                  <th className="py-2 pr-3">Tarih</th>
                  <th className="py-2 pr-3">Paket</th>
                  <th className="py-2 pr-3">Tür</th>
                  <th className="py-2 pr-3">Durum</th>
                  <th className="py-2 pr-3">Kaynak dosya</th>
                  <th className="py-2">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
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
                          aria-label={`uninstall ${r.package_name}`}
                          title="Kaldır"
                          onClick={() => void handleUninstall(r.package_name)}
                          className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--danger)]"
                        >
                          <Trash2 size={14} />
                        </button>
                        <button
                          aria-label={`rollback ${r.package_name}`}
                          title="Geri al"
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
          )}
        </CardContent>
      </Card>
    </div>
  );
}
