import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "./ui/Button";
import { getLang } from "../lib/lang";
import { tFor } from "../lib/i18n";

interface Props {
  children: ReactNode;
  /** Faz 8 (8.1): "full" tum ekran, "page" sayfa ici kompakt gorunum. */
  variant?: "full" | "page";
}

interface State {
  error: Error | null;
}

/** Render hatasinda tum uygulamayi beyaz ekrana dusmekten kurtarir;
 *  kullaniciya aciklama + yeniden yukleme eylemi gosterir. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      const t = tFor(getLang());
      // Faz 8 (8.1): sayfa duzeyli sinir — sadece ilgili sayfa hata durumuna
      // gecer, uygulama ayakta kalir; "Tekrar dene" siniri sifirlar.
      if (this.props.variant === "page") {
        return (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--danger)]/15">
              <AlertTriangle size={22} className="text-[var(--danger)]" />
            </div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">{t("errTitle")}</h2>
            <p className="max-w-sm break-words text-xs text-[var(--text-muted)]">
              {this.state.error.message}
            </p>
            <Button variant="secondary" size="sm" onClick={() => this.setState({ error: null })}>
              {t("errRetry")}
            </Button>
          </div>
        );
      }
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[var(--bg-base)] p-8 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--danger)]/15">
            <AlertTriangle size={26} className="text-[var(--danger)]" />
          </div>
          <h1 className="text-lg font-bold text-[var(--text-primary)]">{t("errTitle")}</h1>
          <p className="max-w-md text-sm text-[var(--text-secondary)]">{t("errDesc")}</p>
          <pre className="max-w-lg overflow-auto rounded-md bg-[var(--bg-elevated)] p-3 text-xs text-[var(--danger)]">
            {this.state.error.message}
          </pre>
          <Button variant="primary" onClick={() => window.location.reload()}>
            {t("errReload")}
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
