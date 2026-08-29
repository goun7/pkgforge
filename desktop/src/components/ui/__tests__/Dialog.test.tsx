import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Dialog } from "../Dialog";
import { ConfirmDialog } from "../ConfirmDialog";

describe("Dialog (Faz 10 1.3)", () => {
  it("renders nothing when closed", () => {
    render(
      <Dialog open={false} onClose={vi.fn()} title="T">
        <p>x</p>
      </Dialog>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders title and children when open", () => {
    render(
      <Dialog open onClose={vi.fn()} title="Baslik">
        <p>icerik</p>
      </Dialog>,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Baslik")).toBeInTheDocument();
    expect(screen.getByText("icerik")).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="T">
        <button>btn</button>
      </Dialog>,
    );
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("closes on backdrop mousedown; content clicks do not close", () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="T">
        <p>icerik</p>
      </Dialog>,
    );
    fireEvent.click(screen.getByText("icerik"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByRole("dialog").parentElement!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders without title (no close X button)", () => {
    render(
      <Dialog open onClose={vi.fn()}>
        <p>basliksiz</p>
      </Dialog>,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByLabelText("Kapat")).not.toBeInTheDocument();
  });

  it("odak tuzağı: son odaktağırdan Tab ilk ogeye döner; Shift+Tab son'a atlar", () => {
    render(
      <Dialog open onClose={vi.fn()}>
        <button>bir</button>
        <button>iki</button>
      </Dialog>,
    );
    const first = screen.getByText("bir");
    const second = screen.getByText("iki");
    // Odağı son ogeye tasima + Tab → ilk ogeye donmeli.
    second.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    // Shift+Tab ilk ogeyken → son ogeye atlamali.
    first.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(second);
  });

  it("odaklanabilir oge yokken Tab varsayılan davranisi engellenir", () => {
    const { unmount } = render(
      <Dialog open onClose={vi.fn()}>
        <p>yok</p>
      </Dialog>,
    );
    // Dinleyiciyi render'dan SONRA kaydet: bilesen effect'i zaten window'a
    // kendi dinleyicisini ekledi; bizimki onun ARDINDAN calisir ve
    // preventDefault'un sonucunu gorur.
    const prevented: boolean[] = [];
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Tab") prevented.push(e.defaultPrevented);
    };
    window.addEventListener("keydown", listener);
    try {
      fireEvent.keyDown(window, { key: "Tab" });
      expect(prevented).toContain(true);
    } finally {
      window.removeEventListener("keydown", listener);
      unmount();
    }
  });

  it("odak dialogu açan öğeye geri döner (unmount)", async () => {
    const opener = document.createElement("button");
    opener.textContent = "opener";
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = render(
      <Dialog open onClose={vi.fn()} title="T">
        <p>x</p>
      </Dialog>,
    );
    unmount();
    expect(document.activeElement).toBe(opener);
    document.body.removeChild(opener);
  });
});

describe("ConfirmDialog (Faz 10 1.3)", () => {
  it("fires onConfirm and onCancel", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Emin misin?"
        message="Silinecek"
        confirmLabel="Evet"
        cancelLabel="Vazgec"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByText("Silinecek")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Evet" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Vazgec" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("uses i18n default labels when none provided", () => {
    render(
      <ConfirmDialog open title="T" message="M" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Onayla" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeInTheDocument();
  });
});
