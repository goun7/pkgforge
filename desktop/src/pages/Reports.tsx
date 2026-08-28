import { useCallback, useEffect, useState } from "react";
import { Activity, Gauge, Camera, ShieldCheck, Loader2, RefreshCw } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { HealthStats, BenchmarkReport, SnapshotStatus, RollbackVerifyResult } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { EmptyState } from "../components/EmptyState";
import { useToast } from "../components/ui/Toast";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

export function Reports() {
  const { toast } = useToast();
  const t = tFor(useLang());
  const [health, setHealth] = useState<HealthStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [bench, setBench] = useState<BenchmarkReport | null>(null);
  const [benching, setBenching] = useState(false);
  const [snap, setSnap] = useState<SnapshotStatus | null>(null);
  const [snapBusy, setSnapBusy] = useState(false);
  const [rollback, setRollback] = useState<RollbackVerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  const loadHealth = useCallback(async () => {
    setLoading(true);
    try {
      const res = await call<HealthStats>("system.health");
      setHealth(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadSnap = useCallback(async () => {
    try {
      const res = await call<SnapshotStatus>("system.snapshot_status");
      setSnap(res);
    } catch (e) {
      toast("error", (e as Error).message);
    }
  }, [toast]);

  useEffect(() => {
    void loadHealth();
    void loadSnap();
  }, [loadHealth, loadSnap]);

  // snapshot kur/kaldir sonucu pkexec yetki diyaloğundan sonra event/snapshot_done ile gelir
  useEffect(() => {
    let un: (() => void) | undefined;
    void onEvent<{ ok: boolean; result?: { ok: boolean; message: string }; error?: string }>(
      "event/snapshot_done",
      (p) => {
        setSnapBusy(false);
        if (p.ok && p.result) {
          if (p.result.ok) toast("success", p.result.message);
          else toast("error", p.result.message);
        } else {
          toast("error", p.error ?? "Snapshot işlemi başarısız");
        }
        void loadSnap();
      },
    ).then((u) => { un = u; });
    return () => { if (un) un(); };
  }, [toast, loadSnap]);

  const handleBenchmark = async () => {
    setBenching(true);
    setBench(null);
    const un = await onEvent<{ ok: boolean; result?: BenchmarkReport; error?: string }>(
      "event/bench_done",
      (p) => {
        setBenching(false);
        if (p.ok && p.result) setBench(p.result);
        else toast("error", p.error ?? "Benchmark başarısız");
        void un();
      },
    );
    try {
      await call("system.benchmark", { quick: true });
    } catch (e) {
      setBenching(false);
      toast("error", (e as Error).message);
    }
  };

  const handleVerifyRollback = async () => {
    setVerifying(true);
    setRollback(null);
    const un = await onEvent<{ ok: boolean; result?: RollbackVerifyResult; error?: string }>(
      "event/system_done",
      (p) => {
        setVerifying(false);
        if (p.ok && p.result) setRollback(p.result);
        else toast("error", p.error ?? "Rollback doğrulama başarısız");
        void un();
      },
    );
    try {
      await call("system.verify_rollback");
    } catch (e) {
      setVerifying(false);
      toast("error", (e as Error).message);
    }
  };

  const handleSnapInstall = async () => {
    setSnapBusy(true);
    try {
      await call("system.snapshot_install", { max_age_days: 7 });
    } catch (e) {
      setSnapBusy(false);
      toast("error", (e as Error).message);
    }
  };

  const handleSnapRemove = async () => {
    setSnapBusy(true);
    try {
      await call("system.snapshot_remove");
    } catch (e) {
      setSnapBusy(false);
      toast("error", (e as Error).message);
    }
  };

  return (
    <div className="h-full space-y-4 overflow-y-auto p-5">
      {/* Health dashboard */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Sağlık Raporu</CardTitle>
          <Button variant="secondary" size="sm" onClick={() => void loadHealth()}>
            <RefreshCw size={14} /> {t("commonRefresh")}
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : health ? (
            health.total === 0 ? (
              <EmptyState
                icon={Activity}
                title="Henüz kayıtlı dönüşüm yok"
                description="İlk dönüşümünüzü yaptığınızda başarı oranı ve sağlık metrikleri burada görünecek."
              />
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-6">
                  {/* success rate ring */}
                  <div
                    className="flex h-24 w-24 items-center justify-center rounded-full"
                    style={{
                      background: `conic-gradient(var(--brand-blue) ${health.success_rate}%, var(--bg-elevated) 0)`,
                    }}
                  >
                    <div className="flex h-18 w-18 flex-col items-center justify-center rounded-full bg-[var(--bg-surface)]">
                      <span className="text-xl font-bold">{health.success_rate}%</span>
                      <span className="text-[10px] text-[var(--text-muted)]">başarı</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
                    <span className="text-[var(--text-muted)]">Toplam</span>
                    <span className="font-medium">{health.total}</span>
                    <span className="text-[var(--text-muted)]">Kurulu</span>
                    <span className="font-medium">{health.installed}</span>
                    <span className="text-[var(--text-muted)]">Dönüştürüldü</span>
                    <span className="font-medium">{health.converted}</span>
                    <span className="text-[var(--text-muted)]">Başarısız</span>
                    <span className="font-medium text-[var(--danger)]">{health.failed}</span>
                  </div>
                </div>
                {/* type distribution */}
                <div>
                  <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Tür Dağılımı</h4>
                  <div className="space-y-1">
                    {Object.entries(health.by_type).map(([type, count]) => {
                      const pct = health.total ? (count / health.total) * 100 : 0;
                      return (
                        <div key={type} className="flex items-center gap-2 text-xs">
                          <span className="w-12 text-[var(--text-secondary)]">{type}</span>
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                            <div className="h-full rounded-full bg-[var(--brand-gradient)]" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-16 text-right text-[var(--text-muted)]">{count} ({pct.toFixed(0)}%)</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )
          ) : null}
        </CardContent>
      </Card>

      {/* Benchmark */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Benchmark</CardTitle>
          <Button size="sm" onClick={() => void handleBenchmark()} disabled={benching}>
            {benching ? <Loader2 size={14} className="animate-spin" /> : <Gauge size={14} />}
            Benchmark Çalıştır
          </Button>
        </CardHeader>
        <CardContent>
          {benching && <Skeleton className="h-20 w-full" />}
          {bench && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="py-1 pr-3">Test</th>
                  <th className="py-1 pr-3">Süre</th>
                  <th className="py-1 pr-3">Bellek</th>
                  <th className="py-1">Durum</th>
                </tr>
              </thead>
              <tbody>
                {bench.results.map((r) => (
                  <tr key={r.name} className="border-t border-[var(--border-subtle)]/50">
                    <td className="py-1.5 pr-3">{r.name}</td>
                    <td className="py-1.5 pr-3 font-mono">{r.duration_ms}ms</td>
                    <td className="py-1.5 pr-3 font-mono">{r.memory_peak_kb}KB</td>
                    <td className="py-1.5">
                      <Badge tone={r.passed ? "success" : "danger"}>{r.passed ? "geçti" : "kaldı"}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Snapshot cleanup */}
      <Card>
        <CardHeader>
          <CardTitle>Snapshot Temizlik Servisi</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <Camera size={16} className="text-[var(--text-muted)]" />
              {snap ? (
                <Badge tone={String(snap.installed ?? snap.active ?? false) === "true" ? "success" : "neutral"}>
                  {String(snap.installed ?? snap.active ?? false) === "true" ? "Kurulu" : "Kurulu değil"}
                </Badge>
              ) : (
                <Skeleton className="h-5 w-20" />
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => void handleSnapInstall()} disabled={snapBusy}>
                {snapBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                Kur
              </Button>
              <Button variant="danger" size="sm" onClick={() => void handleSnapRemove()} disabled={snapBusy}>
                Kaldır
              </Button>
            </div>
          </div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            Kurulum yönetici yetkisi ister; ekranda gelecek parola/onay penceresini (pkexec) onaylayın.
          </p>
        </CardContent>
      </Card>

      {/* Rollback verify */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Rollback Doğrulama</CardTitle>
          <Button size="sm" onClick={() => void handleVerifyRollback()} disabled={verifying}>
            {verifying ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
            Rollback Doğrula
          </Button>
        </CardHeader>
        <CardContent>
          {verifying && <Skeleton className="h-16 w-full" />}
          {rollback && (
            <div className="rounded-md border border-[var(--border-subtle)] p-3 text-sm">
              <div className="mb-2 flex items-center gap-2">
                <Activity size={15} className="text-[var(--text-muted)]" />
                {rollback.backend === "none" ? (
                  <Badge tone="neutral">Snapshot altyapısı yok</Badge>
                ) : (
                  <Badge tone={rollback.verified ? "success" : "warning"}>
                    {rollback.verified ? "Doğrulandı" : "Doğrulanamadı"}
                  </Badge>
                )}
                {rollback.backend !== "none" && (
                  <span className="text-xs text-[var(--text-muted)]">backend: {rollback.backend}</span>
                )}
              </div>
              {rollback.backend === "none" ? (
                <p className="text-xs text-[var(--text-muted)]">
                  Rollback doğrulaması Btrfs veya ZFS dosya sistemi gerektirir; sisteminizde
                  bunlardan biri kurulu değil. Bu bir hata değil — sisteminiz ext4 gibi farklı
                  bir dosya sistemi kullanıyor olabilir.
                </p>
              ) : (
                <>
                  {rollback.detail && <p className="text-xs text-[var(--text-muted)]">{rollback.detail}</p>}
                  {rollback.snapshot_name && (
                    <p className="mt-1 text-xs font-mono text-[var(--text-secondary)]">{rollback.snapshot_name}</p>
                  )}
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
