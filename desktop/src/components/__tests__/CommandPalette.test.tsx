import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette, type Command } from "../CommandPalette";

const mkCmd = (id: string, label: string, action = vi.fn()): Command => ({ id, label, action });

function getPaletteInput(): HTMLInputElement {
  return screen.getByRole("dialog").querySelector("input") as HTMLInputElement;
}

describe("CommandPalette (Faz 9 4.4)", () => {
  it("renders all commands when the query is empty", () => {
    render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Convert"), mkCmd("b", "Settings")]} />);
    expect(screen.getByText("Convert")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("filters commands by substring query", async () => {
    const user = userEvent.setup();
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[mkCmd("a", "Convert"), mkCmd("b", "Settings"), mkCmd("c", "Reports")]}
      />,
    );
    await user.type(getPaletteInput(), "conv");
    expect(screen.getByText("Convert")).toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
  });

  it("matches a subsequence (fuzzy) query", async () => {
    const user = userEvent.setup();
    render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Security"), mkCmd("b", "Convert")]} />);
    await user.type(getPaletteInput(), "scrty");
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.queryByText("Convert")).not.toBeInTheDocument();
  });

  it("hides non-matching commands for a nonsense query", async () => {
    const user = userEvent.setup();
    render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Convert")]} />);
    await user.type(getPaletteInput(), "zzzzz");
    expect(screen.queryByText("Convert")).not.toBeInTheDocument();
  });

  it("runs the command action and closes on click", async () => {
    const user = userEvent.setup();
    const action = vi.fn();
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} commands={[{ id: "a", label: "Convert", action }]} />);
    await user.click(screen.getByText("Convert"));
    expect(action).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when closed", () => {
    const { container } = render(<CommandPalette open={false} onClose={vi.fn()} commands={[mkCmd("a", "Convert")]} />);
    expect(container.firstChild).toBeNull();
  });

  it("pins a recently used command to the top (Faz 9 5.8)", async () => {
    const user = userEvent.setup();
    const commands = [mkCmd("a", "Alpha"), mkCmd("b", "Beta"), mkCmd("c", "Gamma")];
    const { unmount } = render(<CommandPalette open onClose={vi.fn()} commands={commands} />);
    await user.click(screen.getByText("Gamma"));
    unmount();
    expect(JSON.parse(localStorage.getItem("pkgforge.palette.recent") ?? "[]")).toContain("c");
    render(<CommandPalette open onClose={vi.fn()} commands={commands} />);
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("Gamma");
  });
});
