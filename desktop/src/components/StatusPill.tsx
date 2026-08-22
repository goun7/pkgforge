import { Badge } from "./ui/Badge";

export type PipelineStatus = "success" | "failed" | "pending" | "running" | "cancelled";

const toneMap: Record<PipelineStatus, "success" | "danger" | "neutral" | "info" | "warning"> = {
  success: "success",
  failed: "danger",
  pending: "neutral",
  running: "info",
  cancelled: "warning",
};

export function StatusPill({ status }: { status: PipelineStatus }) {
  return <Badge tone={toneMap[status]}>{status}</Badge>;
}
