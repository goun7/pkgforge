import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { Button, type ButtonProps } from "./Button";

export interface AsyncButtonProps extends ButtonProps {
  /** Dogru iken spinner gosterir ve butonu devre disi birakir. */
  busy?: boolean;
  /** Bos durumda gosterilecek simge; busy iken yerini spinner'a birakir. */
  icon?: ReactNode;
}

/** Async eylemler icin tutarli Button: busy iken spinner + disabled. */
export function AsyncButton({ busy = false, disabled, icon, children, ...props }: AsyncButtonProps) {
  return (
    <Button disabled={disabled || busy} {...props}>
      {busy ? <Loader2 size={14} className="animate-spin" /> : icon}
      {children}
    </Button>
  );
}
