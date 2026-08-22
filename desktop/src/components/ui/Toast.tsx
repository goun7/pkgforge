import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info } from "lucide-react";
import { cn } from "../../lib/utils";

type ToastKind = "success" | "warning" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastContextValue {
  toast: (kind: ToastKind, message: string) => void;
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

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const toast = useCallback((kind: ToastKind, message: string) => {
    const id = nextId.current++;
    setItems((prev) => [...prev, { id, kind, message }]);
    setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

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
              <p className="text-sm text-[var(--text-primary)]">{t.message}</p>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
