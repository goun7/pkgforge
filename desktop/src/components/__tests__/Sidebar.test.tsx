import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "../Sidebar";

describe("Sidebar (Faz 10 1.2)", () => {
  it("renders navigation items and section titles", () => {
    render(<Sidebar active="convert" onNavigate={vi.fn()} />);
    expect(screen.getByText("Dönüştür")).toBeInTheDocument();
    expect(screen.getByText("Kütüphane")).toBeInTheDocument();
    expect(screen.getByText("Kurulanlar")).toBeInTheDocument();
  });

  it("calls onNavigate when a nav item is clicked", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<Sidebar active="convert" onNavigate={onNavigate} />);
    await user.click(screen.getByRole("button", { name: "Ayarlar" }));
    expect(onNavigate).toHaveBeenCalledWith("settings");
  });

  it("marks the active page with aria-current", () => {
    render(<Sidebar active="convert" onNavigate={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Dönüştür" })).toHaveAttribute("aria-current", "page");
  });

  it("shows recent pages when provided", () => {
    render(<Sidebar active="convert" onNavigate={vi.fn()} recent={["settings", "reports"]} />);
    expect(screen.getByText("Son sayfalar")).toBeInTheDocument();
  });
});
