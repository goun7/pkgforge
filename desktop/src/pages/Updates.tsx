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
import { InfoTip } from "../components/ui/InfoTip";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

export function Updates() {
  const { toast } = useToast();
  const lang = useLang();
  const t = tFor(lang);
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
      toast("error", t("updIntervalMin"));
      return;
    }
    try {
      await call("schedule.set", { interval_hours: h });
      void loadSchedule();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleScheduleRun = async () => {
    try {
      await call("schedule.run", { force: true });
      toast("success", t("schedRan"));
      void loadSchedule();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleEnable = async () => {
    try {
      const res = await call<{ requires_privilege?: boolean; message?: string }>("delta.enable");
      if (res.requires_privilege) {
        toast("info", res.message ?? t("updDeltaEnablePriv"));
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
        toast("info", res.message ?? t("updDeltaDisablePriv"));
      }
      void loadDelta();
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  const handleCrossCheck = async () => {
    if (!pkgName.trim()) {
      toast("error", t("updNeedName"));
      return;
    }
    setChecking(true);
    setCross(null);
    const un = await onEvent<{ ok: boolean; result?: CrossCheckReport; error?: string }>(
      "event/cross_check_done",
      (p) => {
        setChecking(false);
        if (p.ok && p.result) setCross(p.result);
        else toast("error", p.error ?? t("updCrossFail"));
        void un();
      },
    );
    try {
      await call("system.cross_check", { package_name: pkgName });
    } catch (e) {
      un();
      setChecking(false);
      toast("error", (e as Error).message);
    }
  };

  return (
    <div className="h-full space-y-4 overflow-y-auto p-5">
      {/* Delta auto-update card */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>
            <span className="flex items-center gap-1.5">
              {t("updatesDeltaTitle")}
              <InfoTip text={t("helpDelta")} />
            </span>
          </CardTitle>
          <Button variant="secondary" size="sm" onClick={() => void loadDelta()}>
            <RefreshCw size={14} /> {t("toolsRefresh")}
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
                    {delta.installed ? t("updatesTimerInstalled") : t("updatesTimerNot")}
                  </Badge>
                  <Badge tone={delta.active ? "success" : "neutral"}>
                    {delta.active ? t("updatesActive") : t("updatesInactive")}
                  </Badge>
                </div>
              </div>
              {delta.next_run && (
                <p className="text-xs text-[var(--text-muted)]">{t("updatesNextRun")} {delta.next_run}</p>
              )}
              <div className="flex gap-2">
                <Button size="sm" onClick={() => void handleEnable()} disabled={delta.active}>
                  {t("updatesEnable")}
                </Button>
                <Button variant="secondary" size="sm" onClick={() => void handleDisable()} disabled={!delta.installed}>
                  {t("updatesDisable")}
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Scheduled tasks card (B3) */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-1.5">
              {t("updatesSchedTitle")}
              <InfoTip text={t("helpSchedule")} />
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {schedule ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <CalendarClock size={18} className="text-[var(--text-muted)]" />
                <Badge tone={schedule.enabled ? "success" : "neutral"}>
                  {schedule.enabled ? t("updatesEnabled") : t("updatesDisabledState")}
                </Badge>
                {schedule.next_run && (
                  <span className="text-xs text-[var(--text-muted)]">{t("updatesNext")} {schedule.next_run}</span>
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
                <span className="text-xs text-[var(--text-muted)]">{t("updatesEvery")}</span>
                <Button size="sm" variant="secondary" onClick={() => void handleScheduleInterval()}>
                  {t("updatesSave")}
                </Button>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => void handleScheduleToggle(true)} disabled={schedule.enabled}>
                  {t("updatesEnable")}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => void handleScheduleToggle(false)} disabled={!schedule.enabled}>
                  {t("updatesDisable")}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => void handleScheduleRun()}>
                  {t("schedRunNow")}
                </Button>
              </div>
              {schedule.last_run && (
                <p className="text-xs text-[var(--text-muted)]">{t("updatesLastRun")} {schedule.last_run}</p>
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
          <CardTitle className="flex items-center gap-2"><CalendarClock size={16} /> {t("updatesCrossTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex items-center gap-2">
            <Input
              placeholder={t("updatesPkgPh")}
              value={pkgName}
              onChange={(e) => setPkgName(e.target.value)}
              className="h-9 flex-1"
            />
            <Button onClick={() => void handleCrossCheck()} disabled={checking}>
              {checking ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              {t("updatesCompare")}
            </Button>
          </div>
          {checking && <Skeleton className="h-20 w-full" />}
          {cross && (
            <div className="rounded-md border border-[var(--border-subtle)] p-3 text-sm">
              <table className="w-full text-xs">
                <caption className="sr-only">{t("updCrossCaption")}</caption>
                <thead>
                  <tr className="text-left text-[var(--text-muted)]">
                    <th scope="col" className="py-1 pr-3">{t("updatesSource")}</th>
                    <th scope="col" className="py-1">{t("updatesVersion")}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-[var(--border-subtle)]/50">
                    <td className="py-1.5 pr-3">{t("updatesLocal")}</td>
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
                <Badge tone="success">{t("updatesRecommended")} {cross.recommended_source}</Badge>
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
