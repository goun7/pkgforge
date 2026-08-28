import { render, screen } from "@testing-library/react";
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
