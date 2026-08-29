import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider, useToast } from "../Toast";
import { InfoTip } from "../InfoTip";

const actionSpy = vi.fn();
const LONG_MSG = "x".repeat(130);
const LONG_TRUNCATED = "x".repeat(120) + "\u2026";

function Harness() {
  const { toast } = useToast();
  return (
    <div>
      <button onClick={() => toast("success", "basarili", { label: "GeriAl", onClick: () => {} })}>
        fire
      </button>
      <button onClick={() => toast("error", "hata olustu")}>fireErr</button>
      <button onClick={() => toast("warning", "uyari mesaji")}>fireWarn</button>
      <button onClick={() => toast("info", "bilgi mesaji")}>fireInfo</button>
      <button onClick={() => toast("info", "geri alinabilir", { label: "GeriAl", onClick: actionSpy })}>
        fireAction
      </button>
      <button onClick={() => toast("info", LONG_MSG)}>fireLong</button>
      <button
        onClick={() => {
          for (let i = 1; i <= 5; i++) toast("info", `coklu-${i}`);
        }}
      >
        fireFive
      </button>
    </div>
  );
}

function renderWithHarness() {
  return render(
    <ToastProvider>
      <Harness />
    </ToastProvider>,
  );
}

describe("Toast (Faz 10 1.4)", () => {
  it("shows a toast with an action button", async () => {
    const user = userEvent.setup();
    renderWithHarness();
    await user.click(screen.getByRole("button", { name: "fire" }));
    expect(screen.getByText("basarili")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "GeriAl" })).toBeInTheDocument();
  });

  it("dismisses a toast via the close button", async () => {
    const user = userEvent.setup();
    renderWithHarness();
    await user.click(screen.getByRole("button", { name: "fireErr" }));
    expect(screen.getByText("hata olustu")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bildirimi kapat" }));
    expect(screen.queryByText("hata olustu")).not.toBeInTheDocument();
  });

  it("renders warning and info toasts", async () => {
    const user = userEvent.setup();
    renderWithHarness();
    await user.click(screen.getByRole("button", { name: "fireWarn" }));
    await user.click(screen.getByRole("button", { name: "fireInfo" }));
    expect(screen.getByText("uyari mesaji")).toBeInTheDocument();
    expect(screen.getByText("bilgi mesaji")).toBeInTheDocument();
    expect(screen.getAllByRole("status")).toHaveLength(2);
  });

  it("action button runs the callback and dismisses the toast", async () => {
    actionSpy.mockReset();
    const user = userEvent.setup();
    renderWithHarness();
    await user.click(screen.getByRole("button", { name: "fireAction" }));
    expect(screen.getByText("geri alinabilir")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "GeriAl" }));
    expect(actionSpy).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("geri alinabilir")).not.toBeInTheDocument();
  });

  it("auto-dismisses a non-error toast after 4s", async () => {
    vi.useFakeTimers();
    try {
      renderWithHarness();
      fireEvent.click(screen.getByRole("button", { name: "fireInfo" }));
      expect(screen.getByText("bilgi mesaji")).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3999);
      });
      expect(screen.getByText("bilgi mesaji")).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(screen.queryByText("bilgi mesaji")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps an error toast visible for 8s", async () => {
    vi.useFakeTimers();
    try {
      renderWithHarness();
      fireEvent.click(screen.getByRole("button", { name: "fireErr" }));
      expect(screen.getByText("hata olustu")).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4000);
      });
      expect(screen.getByText("hata olustu")).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4000);
      });
      expect(screen.queryByText("hata olustu")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows at most 4 toasts, dropping the oldest", async () => {
    const user = userEvent.setup();
    renderWithHarness();
    await user.click(screen.getByRole("button", { name: "fireFive" }));
    expect(screen.queryByText("coklu-1")).not.toBeInTheDocument();
    for (const i of [2, 3, 4, 5]) {
      expect(screen.getByText(`coklu-${i}`)).toBeInTheDocument();
    }
    expect(screen.getAllByRole("status")).toHaveLength(4);
  });

  it("truncates long messages and toggles the detail view", async () => {
    const user = userEvent.setup();
    renderWithHarness();
    await user.click(screen.getByRole("button", { name: "fireLong" }));
    expect(screen.getByText(LONG_TRUNCATED)).toBeInTheDocument();
    expect(screen.queryByText(LONG_MSG)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ayr\u0131nt\u0131" }));
    expect(screen.getByText(LONG_MSG)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Gizle" }));
    expect(screen.getByText(LONG_TRUNCATED)).toBeInTheDocument();
    expect(screen.queryByText(LONG_MSG)).not.toBeInTheDocument();
  });

  it("short messages have no detail toggle", async () => {
    const user = userEvent.setup();
    renderWithHarness();
    await user.click(screen.getByRole("button", { name: "fireInfo" }));
    expect(screen.queryByRole("button", { name: "Ayr\u0131nt\u0131" })).not.toBeInTheDocument();
  });
});

describe("InfoTip (Faz 10 1.4)", () => {
  it("renders a tooltip with the text", () => {
    render(<InfoTip text="aciklama metni" />);
    expect(screen.getByRole("tooltip")).toHaveTextContent("aciklama metni");
  });

  it("wires the trigger to the bubble via aria-describedby", () => {
    const { container } = render(<InfoTip text="ipucu metni" />);
    const bubble = screen.getByRole("tooltip");
    const trigger = container.querySelector("[aria-describedby]");
    expect(trigger).not.toBeNull();
    expect(trigger!.getAttribute("aria-describedby")).toBe(bubble.id);
    expect(trigger).toHaveAttribute("aria-label", "ipucu metni");
  });
});
