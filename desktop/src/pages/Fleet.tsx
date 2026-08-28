import { useEffect, useState } from "react";
import {
  Server, UploadCloud, Download, PackageOpen, RefreshCw,
} from "lucide-react";
import { call, onEvent } from "../lib/rpc";
import type { FleetStatus } from "../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { AsyncButton } from "../components/ui/AsyncButton";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { InfoTip } from "../components/ui/InfoTip";
import { useLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

export function Fleet() {
  const { toast } = useToast();
  const lang = useLang();
  const t = tFor(lang);
  const [status, setStatus] = useState<FleetStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncBusy, setSyncBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      const res = await call<FleetStatus>("fleet.status");
      setStatus(res);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let unsub: (() => void) | undefined;
    void onEvent<{ ok: boolean; error?: string }>(
      "event/sync_done",
      (p) => {
        setSyncBusy(false);
        if (p.ok) toast("success", t("fleetSyncDone"));
        else toast("error", p.error ?? t("fleetSyncFail"));
      },
    ).then((u) => { unsub = u; });
    return () => { if (unsub) unsub(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast]);

  const syncPush = async () => {
    setSyncBusy(true);
    try { await call("sync.push"); }
    catch (e) { setSyncBusy(false); toast("error", (e as Error).message); }
  };

  const syncPull = async () => {
    setSyncBusy(true);
    try { await call("sync.pull"); }
    catch (e) { setSyncBusy(false); toast("error", (e as Error).message); }
  };

  const syncExport = async () => {
    setSyncBusy(true);
    try {
      await call("sync.export");
      setSyncBusy(false);
      toast("success", t("fleetExportDone"));
    } catch (e) { setSyncBusy(false); toast("error", (e as Error).message); }
  };

  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle>
              <span className="flex items-center gap-1.5">
                {t("fleetTitle")}
                <InfoTip text={t("helpFleet")} />
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <AsyncButton onClick={() => void load()} busy={busy} icon={<RefreshCw size={16} />}>
                {t("toolsRefresh")}
              </AsyncButton>
              {status ? <Badge>{status.policy_level}</Badge> : null}
              {status ? (
                <span className="text-xs text-[var(--text-secondary)]">
                  <Server size={14} className="mr-1 inline" />
                  {status.history_count} {t("fleetHistory")}
                </span>
              ) : null}
            </div>
          </CardContent>
        </Card>

        {status ? (
          <Card>
            <CardHeader><CardTitle>{t("fleetBackends")}</CardTitle></CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {status.backend_names.map((name) => {
                  const b = status.backends[name] ?? { configured: false, available: false };
                  return (
                    <li key={name} className="flex items-center gap-2 text-sm">
                      <Badge>{b.available ? t("fleetReady") : t("fleetMissing")}</Badge>
                      <span>{name}</span>
                      {b.configured ? <Badge>{t("fleetConfigured")}</Badge> : null}
                    </li>
                  );
                })}
              </ul>
              <p className="mt-3 text-xs text-[var(--text-secondary)]">
                {t("fleetAge")} {status.age_available ? t("fleetHave") : t("fleetNone")}
              </p>
            </CardContent>
          </Card>
        ) : null}

        {status ? (
          <Card>
            <CardHeader><CardTitle>{t("fleetSummary")}</CardTitle></CardHeader>
            <CardContent>
              <ul className="space-y-1 text-sm">
                <li>{t("fleetProfiles")} {status.profiles.join(", ") || "-"}</li>
                <li>{t("fleetSync")} {status.sync_configured ? t("fleetConfigured") : t("fleetNone")}</li>
                <li>{t("fleetPolicy")} {status.policy_level}</li>
              </ul>
            </CardContent>
          </Card>
        ) : null}

        <Card>
          <CardHeader><CardTitle>{t("fleetActions")}</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <AsyncButton onClick={syncPush} busy={syncBusy} icon={<UploadCloud size={16} />}>
                Push
              </AsyncButton>
              <AsyncButton onClick={syncPull} busy={syncBusy} icon={<Download size={16} />}>
                Pull
              </AsyncButton>
              <AsyncButton variant="outline" onClick={syncExport} busy={syncBusy} icon={<PackageOpen size={16} />}>
                {t("fleetBackup")}
              </AsyncButton>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
