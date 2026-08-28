import { Dialog } from "./Dialog";
import { Button } from "./Button";
import { AsyncButton } from "./AsyncButton";
import { AlertTriangle } from "lucide-react";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Yikici eylemler icin onay penceresi (3.2). */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Onayla",
  cancelLabel = "Vazgeç",
  danger = true,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onCancel} title={title}>
      <div className="flex items-start gap-3">
        {danger && (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--danger)]/15">
            <AlertTriangle size={20} className="text-[var(--danger)]" />
          </div>
        )}
        <p className="text-sm text-[var(--text-secondary)]">{message}</p>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </Button>
        <AsyncButton variant={danger ? "danger" : "primary"} busy={busy} onClick={onConfirm}>
          {confirmLabel}
        </AsyncButton>
      </div>
    </Dialog>
  );
}
