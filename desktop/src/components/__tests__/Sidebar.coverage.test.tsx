import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Sidebar } from "../Sidebar";

const COLLAPSE = "Kenar çubuğunu daralt";
const EXPAND = "Kenar çubuğunu genişlet";

describe("Sidebar — Faz 19b kapsam dalları", () => {
  beforeEach(() => {
    localStorage.removeItem("pkgforge.sidebar.compact");
  });

  it("kompakt düğmesi: etiketler gizlenir, localStorage'a yazılır", () => {
    render(<Sidebar active="convert" onNavigate={vi.fn()} />);
    // Tam modda marka metni görünür.
    expect(screen.getByText("PkgForge")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(COLLAPSE));
    // Kompakt: marka metni kaybolur, aria-label genişletmeye döner.
    expect(screen.queryByText("PkgForge")).not.toBeInTheDocument();
    expect(screen.getByLabelText(EXPAND)).toBeInTheDocument();
    expect(localStorage.getItem("pkgforge.sidebar.compact")).toBe("1");
    // Geri aç.
    fireEvent.click(screen.getByLabelText(EXPAND));
    expect(screen.getByText("PkgForge")).toBeInTheDocument();
    expect(localStorage.getItem("pkgforge.sidebar.compact")).toBe("0");
  });

  it("kompakt modda 'son sayfalar' bölümü gizlenir", () => {
    const recent = ["settings"];
    render(
      <Sidebar active="convert" onNavigate={vi.fn()} recent={recent} />,
    );
    expect(screen.getByText("Son sayfalar")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(COLLAPSE));
    expect(screen.queryByText("Son sayfalar")).not.toBeInTheDocument();
  });

  it("bölüm daraltma: başlık tıklanınca öğeler gizlenir, tekrar açılır", () => {
    render(<Sidebar active="convert" onNavigate={vi.fn()} />);
    // 'AUR Gözat' Keşif bölümündedir.
    expect(screen.getByRole("button", { name: "AUR Gözat" })).toBeInTheDocument();
    const sectionBtn = screen.getByRole("button", { name: /Keşfet/ });
    fireEvent.click(sectionBtn);
    expect(
      screen.queryByRole("button", { name: "AUR Gözat" }),
    ).not.toBeInTheDocument();
    fireEvent.click(sectionBtn);
    expect(screen.getByRole("button", { name: "AUR Gözat" })).toBeInTheDocument();
  });

  it("son sayfalar öğesi tıklanınca onNavigate id ile çağrılır", () => {
    const onNavigate = vi.fn();
    const recent = ["reports"];
    render(
      <Sidebar active="convert" onNavigate={onNavigate} recent={recent} />,
    );
    // 'Raporlar' hem recent hem ana menüde olabilir; recent (DOM'da önce) [0].
    fireEvent.click(screen.getAllByRole("button", { name: "Raporlar" })[0]);
    expect(onNavigate).toHaveBeenCalledWith("reports");
  });

  it("localStorage erişilemezse kompakt mod false kalır; toggle yine çalışır", () => {
    const orig = window.localStorage;
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: () => {
          throw new Error("yasak");
        },
        setItem: () => {
          throw new Error("yasak");
        },
      },
      configurable: true,
    });
    try {
      render(<Sidebar active="convert" onNavigate={vi.fn()} />);
      // getItem patladı → compact=false → tam mod render.
      expect(screen.getByText("PkgForge")).toBeInTheDocument();
      // toggleCompact setItem patlar ama state yine de değişir.
      fireEvent.click(screen.getByLabelText(COLLAPSE));
      expect(screen.queryByText("PkgForge")).not.toBeInTheDocument();
    } finally {
      Object.defineProperty(window, "localStorage", {
        value: orig,
        configurable: true,
      });
    }
  });

  it("geçersiz recent id'ler sessizce elenir", () => {
    const recent = ["convert", "bozulmus-id", "tools"];
    render(
      <Sidebar
        active="convert"
        onNavigate={vi.fn()}
        recent={recent}
      />,
    );
    // Aktif sayfa (convert) listeden düşer; bozuk id render edilmez.
    expect(screen.getAllByText("Dönüştür").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.queryByRole("button", { name: "bozulmus-id" }),
    ).not.toBeInTheDocument();
  });
});
