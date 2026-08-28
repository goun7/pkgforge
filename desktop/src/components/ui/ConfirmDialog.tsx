import { Dialog } from "./Dialog";
import { Button } from "./Button";
import { AsyncButton } from "./AsyncButton";
import { AlertTriangle } from "lucide-react";
import { useLang } from "../../lib/lang";
import { tFor } from "../../lib/i18n";

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
  confirmLabel,
  cancelLabel,
  danger = true,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const t = tFor(useLang());
  const confirmText = confirmLabel ?? t("confirmConfirm");
  const cancelText = cancelLabel ?? t("confirmCancel");
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
          {cancelText}
        </Button>
        <AsyncButton variant={danger ? "danger" : "primary"} busy={busy} onClick={onConfirm}>
          {confirmText}
        </AsyncButton>
      </div>
    </Dialog>
  );
}
