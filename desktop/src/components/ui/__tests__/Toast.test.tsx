import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ToastProvider, useToast } from "../Toast";
import { InfoTip } from "../InfoTip";

function Harness() {
  const { toast } = useToast();
  return (
    <div>
      <button onClick={() => toast("success", "basarili", { label: "GeriAl", onClick: () => {} })}>
        fire
      </button>
      <button onClick={() => toast("error", "hata olustu")}>fireErr</button>
    </div>
  );
}

describe("Toast (Faz 10 1.4)", () => {
  it("shows a toast with an action button", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Harness />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "fire" }));
    expect(screen.getByText("basarili")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "GeriAl" })).toBeInTheDocument();
  });

  it("dismisses a toast via the close button", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Harness />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "fireErr" }));
    expect(screen.getByText("hata olustu")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bildirimi kapat" }));
    expect(screen.queryByText("hata olustu")).not.toBeInTheDocument();
  });
});

describe("InfoTip (Faz 10 1.4)", () => {
  it("renders a tooltip with the text", () => {
    render(<InfoTip text="aciklama metni" />);
    expect(screen.getByRole("tooltip")).toHaveTextContent("aciklama metni");
  });
});
