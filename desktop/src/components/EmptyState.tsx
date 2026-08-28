import type { LucideIcon } from "lucide-react";
import { memo, type ReactNode } from "react";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

// Faz 10 (4.2): saf goruntu bileseni — memo ile gereksiz re-render onlenir.
export const EmptyState = memo(function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--bg-elevated)]">
        <Icon size={26} className="text-[var(--text-muted)]" />
      </div>
      <h3 className="text-base font-semibold text-[var(--text-primary)]">{title}</h3>
      {description && (
        <p className="max-w-sm text-sm text-[var(--text-secondary)]">{description}</p>
      )}
      {action}
    </div>
  );
});
