import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";

/**
 * Regresyon kilidi: Topbar'daki arama butonu App'te hiç bağlanmamıştı
 * (onSearchClick geçirilmiyordu), bu yüzden ⌘K ipuçlu buton gerçek
 * uygulamada HİÇ render edilmiyordu. Topbar.test.tsx ise butonu prop
 * verilmiş hâliyle sınadığı için testler yeşil kalıyordu.
 *
 * Bu dosya Topbar'ı MOCKLAMAZ — App'in gerçek kompozisyonunu sınar.
 */

const invokeMock = vi.fn((..._args: unknown[]) => Promise.resolve(null));
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

// Pencere kabugu/uygulama katili stub'lari: App'in kendi dallari test edilir.
vi.mock("../components/ui/Toast", () => ({
  ToastProvider: ({ children }: any) => <>{children}</>,
}));
vi.mock("../components/SidecarGuard", () => ({ SidecarGuard: () => null }));
vi.mock("../components/Onboarding", () => ({ Onboarding: () => null }));
vi.mock("../components/WhatsNew", () => ({ WhatsNew: () => null }));
vi.mock("../components/FeatureTour", () => ({ FeatureTour: () => null }));
vi.mock("../components/ShortcutsDialog", () => ({ ShortcutsDialog: () => null }));
vi.mock("../components/TopbarActions", () => ({
  TopbarActions: () => <div data-testid="topbar-actions" />,
}));
vi.mock("../components/Sidebar", () => ({
  Sidebar: () => <nav data-testid="sidebar" />,
}));
vi.mock("../components/CommandPalette", () => ({
  CommandPalette: ({ open }: any) =>
    open ? <div data-testid="command-palette" /> : null,
}));
vi.mock("../pages/Convert", () => ({ Convert: () => <div data-testid="page-convert" /> }));

beforeEach(() => invokeMock.mockClear());

describe("App -> Topbar arama baglantisi (mock'siz kompozisyon)", () => {
  it("arama butonu render edilir", async () => {
    render(<App />);
    await screen.findByTestId("page-convert");
    // Topbar gercek bilesen olarak render edildigi icin buton gercekten gorunur
    expect(screen.queryByRole("button", { name: /ara|search/i })).not.toBeNull();
  });

  it("butona tiklamak komut paletini acar", async () => {
    render(<App />);
    await screen.findByTestId("page-convert");
    expect(screen.queryByTestId("command-palette")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /ara|search/i }));
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });
});
