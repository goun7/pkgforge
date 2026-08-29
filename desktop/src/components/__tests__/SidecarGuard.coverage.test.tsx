import { render, screen, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { SidecarGuard } from "../SidecarGuard";
import { ToastProvider } from "../ui/Toast";
import * as rpc from "../../lib/rpc";

describe("SidecarGuard — Faz 19 toast dalları", () => {
  let fire: (ok: boolean) => void = () => undefined;

  beforeEach(() => {
    let captured: ((ok: boolean) => void) | null = null;
    vi.spyOn(rpc, "onSidecarStatus").mockImplementation((cb) => {
      captured = cb;
      return () => undefined;
    });
    render(
      <ToastProvider>
        <SidecarGuard />
      </ToastProvider>,
    );
    fire = (ok: boolean) => act(() => captured?.(ok));
  });

  it("koptu → uyarı; düzeldi → başarı; tekrar koptu → yeniden uyarı", async () => {
    // İlk kopuş: uyarı toast'u (1 adet).
    fire(false);
    expect(
      await screen.findAllByText(/Arka uç bağlantısı koptu/),
    ).toHaveLength(1);
    // Aynı kopuklukta tekrar tetiklenmez (down ref) — hâlâ 1.
    fire(false);
    expect(
      await screen.findAllByText(/Arka uç bağlantısı koptu/),
    ).toHaveLength(1);
    // Düzelme: başarı toast'u.
    fire(true);
    expect(
      await screen.findAllByText(/Arka uç bağlantısı yeniden kuruldu/),
    ).toHaveLength(1);
    // Yeniden kopuş: down.current false'tu — ikinci uyarı toast'u (2 adet).
    fire(false);
    expect(
      await screen.findAllByText(/Arka uç bağlantısı koptu/),
    ).toHaveLength(2);
  });
});
