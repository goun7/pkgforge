import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Timer, Search, Loader2, CalendarClock } from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { DeltaStatus, CrossCheckReport, ScheduleState } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";

export function Updates() {
  const { toast } = useToast();
  const [delta, setDelta] = useState<DeltaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [pkgName, setPkgName] = useState("");
  const [checking, setChecking] = useState(false);
  const [cross, setCross] = useState<CrossCheckReport | null>(null);
  const [schedule, setSchedule] = useState<ScheduleState | null>(null);
  const [intervalInput, setIntervalInput] = useState("24");

  const loadDelta = useCallback(async () => {
    setLoading(true);
    try {
      const res = await call<DeltaStatus>("delta.status");
      setDelta(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadSchedule = useCallback(async () => {
    try {
      const res = await call<ScheduleState>("schedule.get");
      setSchedule(res);
      setIntervalInput(String(res.interval_hours));
    } catch (e) {
      toast("error", (e as Error).message);
    }
  }, [toast]);

  useEffect(() => {
    void loadDelta();
    void loadSchedule();
  }, [loadDelta, loadSchedule]);

  const handleScheduleToggle = async (enabled: boolean) => {
    try {
      await call("schedule.set", { enabled });
      void loadSchedule();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleScheduleInterval = async () => {
    const h = parseFloat(intervalInput);
    if (!h || h < 1) {
      toast("error", "Aralık en az 1 saat olmalı");
      return;
    }
    try {
      await call("schedule.set", { interval_hours: h });
      void loadSchedule();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleEnable = async () => {
    try {
      const res = await call<{ requires_privilege?: boolean; message?: string }>("delta.enable");
      if (res.requires_privilege) {
        toast("info", res.message ?? "Delta auto-update etkinleştirme yetkili işlem gerektiriyor (pkexec)");
      }
      void loadDelta();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleDisable = async () => {
    try {
      const res = await call<{ requires_privilege?: boolean; message?: string }>("delta.disable");
      if (res.requires_privilege) {
        toast("info", res.message ?? "Delta auto-update kapatma yetkili işlem gerektiriyor (pkexec)");
      }
      void loadDelta();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleCrossCheck = async () => {
    if (!pkgName.trim()) {
      toast("error", "Bir paket adı girin");
      return;
    }
    setChecking(true);
    setCross(null);
    const un = await onEvent<{ ok: boolean; result?: CrossCheckReport; error?: string }>(
      "event/cross_check_done",
      (p) => {
        setChecking(false);
        if (p.ok && p.result) setCross(p.result);
        else toast("error", p.error ?? "Cross-check başarısız");
        void un();
      },
    );
    try {
      await call("system.cross_check", { package_name: pkgName });
    } catch (e) {
      setChecking(false);
      toast("error", (e as Error).message);
    }
  };

  return (
    <div className="h-full space-y-4 overflow-y-auto p-5">
      {/* Delta auto-update card */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Delta Auto-Update</CardTitle>
          <Button variant="secondary" size="sm" onClick={() => void loadDelta()}>
            <RefreshCw size={14} /> Yenile
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-16 w-full" />
          ) : delta ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Timer size={18} className="text-[var(--text-muted)]" />
                <div className="flex items-center gap-2 text-sm">
                  <Badge tone={delta.installed ? "success" : "neutral"}>
                    {delta.installed ? "Timer kurulu" : "Timer kurulu değil"}
                  </Badge>
                  <Badge tone={delta.active ? "success" : "neutral"}>
                    {delta.active ? "Aktif" : "Pasif"}
                  </Badge>
                </div>
              </div>
              {delta.next_run && (
                <p className="text-xs text-[var(--text-muted)]">Sonraki çalışma: {delta.next_run}</p>
              )}
              <div className="flex gap-2">
                <Button size="sm" onClick={() => void handleEnable()} disabled={delta.active}>
                  Etkinleştir
                </Button>
                <Button variant="secondary" size="sm" onClick={() => void handleDisable()} disabled={!delta.installed}>
                  Kapat
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Scheduled tasks card (B3) */}
      <Card>
        <CardHeader>
          <CardTitle>Zamanlanmış Görevler</CardTitle>
        </CardHeader>
        <CardContent>
          {schedule ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <CalendarClock size={18} className="text-[var(--text-muted)]" />
                <Badge tone={schedule.enabled ? "success" : "neutral"}>
                  {schedule.enabled ? "Etkin" : "Devre dışı"}
                </Badge>
                {schedule.next_run && (
                  <span className="text-xs text-[var(--text-muted)]">Sonraki: {schedule.next_run}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={1}
                  value={intervalInput}
                  onChange={(e) => setIntervalInput(e.target.value)}
                  className="h-9 w-24"
                />
                <span className="text-xs text-[var(--text-muted)]">saat arayla</span>
                <Button size="sm" variant="secondary" onClick={() => void handleScheduleInterval()}>
                  Kaydet
                </Button>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => void handleScheduleToggle(true)} disabled={schedule.enabled}>
                  Etkinleştir
                </Button>
                <Button size="sm" variant="secondary" onClick={() => void handleScheduleToggle(false)} disabled={!schedule.enabled}>
                  Kapat
                </Button>
              </div>
              {schedule.last_run && (
                <p className="text-xs text-[var(--text-muted)]">Son çalışma: {schedule.last_run}</p>
              )}
            </div>
          ) : (
            <Skeleton className="h-16 w-full" />
          )}
        </CardContent>
      </Card>

      {/* Cross-check card */}
      <Card>
        <CardHeader>
          <CardTitle>Kaynak Karşılaştırma (Cross-Check)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex items-center gap-2">
            <Input
              placeholder="Paket adı…"
              value={pkgName}
              onChange={(e) => setPkgName(e.target.value)}
              className="h-9 flex-1"
            />
            <Button onClick={() => void handleCrossCheck()} disabled={checking}>
              {checking ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              Karşılaştır
            </Button>
          </div>
          {checking && <Skeleton className="h-20 w-full" />}
          {cross && (
            <div className="rounded-md border border-[var(--border-subtle)] p-3 text-sm">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th className="py-1 pr-3">Kaynak</th>
                    <th className="py-1">Versiyon</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-[var(--border-subtle)]/50">
                    <td className="py-1.5 pr-3">Yerel</td>
                    <td className="py-1.5 font-mono">{cross.local_version || "—"}</td>
                  </tr>
                  <tr className="border-t border-[var(--border-subtle)]/50">
                    <td className="py-1.5 pr-3">AUR</td>
                    <td className="py-1.5 font-mono">{cross.aur_version || "—"}</td>
                  </tr>
                  <tr className="border-t border-[var(--border-subtle)]/50">
                    <td className="py-1.5 pr-3">Flatpak</td>
                    <td className="py-1.5 font-mono">{cross.flatpak_version || "—"}</td>
                  </tr>
                </tbody>
              </table>
              <div className="mt-2 flex items-center gap-2">
                <Badge tone="success">Öneri: {cross.recommended_source}</Badge>
              </div>
              {cross.recommendation_reason && (
                <p className="mt-1 text-xs text-[var(--text-muted)]">{cross.recommendation_reason}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
