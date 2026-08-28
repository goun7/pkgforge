import { Badge } from "./ui/Badge";
import { useLang } from "../lib/lang";
import { tFor, type I18nKey } from "../lib/i18n";

export type PipelineStatus = "success" | "failed" | "pending" | "running" | "cancelled";

const toneMap: Record<PipelineStatus, "success" | "danger" | "neutral" | "info" | "warning"> = {
  success: "success",
  failed: "danger",
  pending: "neutral",
  running: "info",
  cancelled: "warning",
};

const labelKeyMap: Record<PipelineStatus, I18nKey> = {
  success: "statusSuccess",
  failed: "statusFailed",
  pending: "statusPending",
  running: "statusRunning",
  cancelled: "statusCancelled",
};

export function StatusPill({ status }: { status: PipelineStatus }) {
  const t = tFor(useLang());
  return <Badge tone={toneMap[status]}>{t(labelKeyMap[status])}</Badge>;
}
