import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "brand";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

const toneClasses: Record<Tone, string> = {
  neutral: "bg-[var(--bg-elevated)] text-[var(--text-secondary)]",
  success: "bg-[var(--success)]/15 text-[var(--success)]",
  warning: "bg-[var(--warning)]/15 text-[var(--warning)]",
  danger: "bg-[var(--danger)]/15 text-[var(--danger)]",
  info: "bg-[var(--info)]/15 text-[var(--info)]",
  brand: "bg-[var(--brand-blue)]/15 text-[var(--brand-blue)]",
};

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, tone = "neutral", ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  ),
);
Badge.displayName = "Badge";
