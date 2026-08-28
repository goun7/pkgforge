import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "../Button";
import { Badge } from "../Badge";
import { Input } from "../Input";
import { Skeleton } from "../Skeleton";
import { ProgressBar } from "../ProgressBar";

describe("UI primitives (Faz 10 1.5)", () => {
  it("Button renders children and fires onClick", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Kaydet</Button>);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("Button respects disabled", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Sil
      </Button>,
    );
    await user.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("Badge applies tone class", () => {
    render(<Badge tone="success">OK</Badge>);
    expect(screen.getByText("OK").className).toContain("success");
  });

  it("Input forwards props and accepts typing", async () => {
    const user = userEvent.setup();
    render(<Input placeholder="ara" aria-label="arama" />);
    const inp = screen.getByLabelText("arama");
    await user.type(inp, "abc");
    expect(inp).toHaveValue("abc");
  });

  it("Skeleton renders with custom class", () => {
    const { container } = render(<Skeleton className="h-10" />);
    expect(container.firstChild).toHaveClass("h-10");
  });

  it("ProgressBar exposes aria values and clamps to 100", () => {
    render(<ProgressBar value={150} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });

  it("ProgressBar indeterminate omits aria-valuenow", () => {
    render(<ProgressBar value={0} indeterminate />);
    expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  });
});
