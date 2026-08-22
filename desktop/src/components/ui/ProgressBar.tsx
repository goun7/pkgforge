import { cn } from "../../lib/utils";

export interface ProgressBarProps {
  value: number; // 0-100
  className?: string;
  gradient?: boolean;
}

export function ProgressBar({ value, className, gradient = false }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "h-2 w-full overflow-hidden rounded-full bg-[var(--bg-elevated)]",
        className,
      )}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-300",
          gradient ? "bg-[var(--brand-gradient)]" : "bg-[var(--brand-blue)]",
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
