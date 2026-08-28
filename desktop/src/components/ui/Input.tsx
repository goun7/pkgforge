import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-[var(--radius-input)] bg-[var(--bg-elevated)] px-3 text-sm text-[var(--text-primary)]",
        "border border-[var(--border-subtle)] placeholder:text-[var(--text-muted)]",
        "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--brand-blue)]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
