import { render, screen, act } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ShortcutsDialog } from "../ShortcutsDialog";

describe("ShortcutsDialog (Faz 9 5.1)", () => {
  it("is hidden until the open-shortcuts event fires", () => {
    render(<ShortcutsDialog />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new Event("pkgforge:open-shortcuts"));
    });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("lists the command palette shortcut", () => {
    render(<ShortcutsDialog />);
    act(() => {
      window.dispatchEvent(new Event("pkgforge:open-shortcuts"));
    });
    expect(screen.getByText("Ctrl/⌘ + K")).toBeInTheDocument();
    expect(screen.getByText("Alt + 1…9")).toBeInTheDocument();
  });
});
