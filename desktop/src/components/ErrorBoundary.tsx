import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "./ui/Button";

interface Props {
  children: ReactNode;
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
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[var(--bg-base)] p-8 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--danger)]/15">
            <AlertTriangle size={26} className="text-[var(--danger)]" />
          </div>
          <h1 className="text-lg font-bold text-[var(--text-primary)]">Bir şeyler ters gitti</h1>
          <p className="max-w-md text-sm text-[var(--text-secondary)]">
            Arayüz beklenmeyen bir hatayla karşılaştı. Sayfayı yeniden yüklemeyi
            deneyebilir, sorun sürerse log'lara bakabilirsiniz.
          </p>
          <pre className="max-w-lg overflow-auto rounded-md bg-[var(--bg-elevated)] p-3 text-xs text-[var(--danger)]">
            {this.state.error.message}
          </pre>
          <Button variant="primary" onClick={() => window.location.reload()}>
            Yeniden Yükle
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
