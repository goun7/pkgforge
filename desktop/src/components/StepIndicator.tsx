import { Check, X, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";

export const PIPELINE_STEPS = [
  "security",
  "malware",
  "analysis",
  "conversion",
  "compatibility",
  "install",
] as const;

export type StepStatus = "pending" | "running" | "done" | "error" | "warning";

export interface StepIndicatorProps {
  /** Map of step name -> status. Missing steps render as pending. */
  statuses: Record<string, StepStatus>;
  labels?: Record<string, string>;
}

export function StepIndicator({ statuses, labels }: StepIndicatorProps) {
  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STEPS.map((step, i) => {
        const status = statuses[step] ?? "pending";
        const Icon =
          status === "done" ? Check
          : status === "error" ? X
          : status === "warning" ? AlertTriangle
          : status === "running" ? Loader2
          : null;
        return (
          <div key={step} className="flex items-center">
            <div className="flex flex-col items-center gap-1.5">
              <div
                data-step={step}
                data-status={status}
                data-testid={`step-${step}`}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full border-2 transition-colors",
                  status === "done" && "border-transparent bg-[var(--success)] text-white",
                  status === "error" && "border-transparent bg-[var(--danger)] text-white",
                  status === "warning" && "border-transparent bg-[var(--warning)] text-white",
                  status === "running" && "border-[var(--brand-blue)] text-[var(--brand-blue)]",
                  status === "pending" && "border-[var(--border-strong)] text-[var(--text-muted)]",
                )}
              >
                {Icon ? (
                  <Icon size={16} className={status === "running" ? "animate-spin" : ""} />
                ) : (
                  <span className="text-xs font-semibold">{i + 1}</span>
                )}
              </div>
              <span className="text-[10px] capitalize text-[var(--text-secondary)]">
                {labels?.[step] ?? step}
              </span>
            </div>
            {i < PIPELINE_STEPS.length - 1 && (
              <div className="mx-1 mb-5 h-px w-6 bg-[var(--border-strong)]" />
            )}
          </div>
        );
      })}
    </div>
  );
}
