import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";
import { cn } from "../../lib/utils";

type ToastKind = "success" | "warning" | "error" | "info";

/** Istege bagli eylem butonu (orn. "Geri al"). */
export interface ToastAction {
  label: string;
  onClick: () => void;
}

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
  action?: ToastAction;
}

interface ToastContextValue {
  toast: (kind: ToastKind, message: string, action?: ToastAction) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

const kindIcon: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
  info: Info,
};

const kindColor: Record<ToastKind, string> = {
  success: "text-[var(--success)]",
  warning: "text-[var(--warning)]",
  error: "text-[var(--danger)]",
  info: "text-[var(--info)]",
};

/** Ayni anda en fazla bu kadar toast gorunur; en eski dusurulur. */
const MAX_VISIBLE = 4;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const toast = useCallback(
    (kind: ToastKind, message: string, action?: ToastAction) => {
      const id = nextId.current++;
      setItems((prev) => [...prev, { id, kind, message, action }].slice(-MAX_VISIBLE));
      // Hata toast'lari okunacak kadar uzun kalir.
      const ttl = kind === "error" ? 8000 : 4000;
      timers.current.set(id, setTimeout(() => dismiss(id), ttl));
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 flex-col gap-2"
      >
        {items.map((t) => {
          const Icon = kindIcon[t.kind];
          return (
            <div
              key={t.id}
              role="status"
              className="pointer-events-auto flex items-start gap-2.5 rounded-[var(--radius-input)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3 shadow-[var(--shadow-md)]"
            >
              <Icon size={17} className={cn("mt-0.5 shrink-0", kindColor[t.kind])} />
              <div className="min-w-0 flex-1">
                <p className="break-words text-sm text-[var(--text-primary)]">{t.message}</p>
                {t.action && (
                  <button
                    onClick={() => {
                      t.action?.onClick();
                      dismiss(t.id);
                    }}
                    className="mt-1 text-xs font-semibold text-[var(--brand-blue)] hover:underline"
                  >
                    {t.action.label}
                  </button>
                )}
              </div>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Bildirimi kapat"
                className="shrink-0 rounded p-0.5 text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
