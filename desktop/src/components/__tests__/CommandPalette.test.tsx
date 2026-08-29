import { fireEvent, render, screen } from "@testing-library/react";
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
    // Faz 10 (5.4): eslesme <mark> ile vurgulanir; erisilebilir ad uzerinden dogrula.
    expect(screen.getByRole("option", { name: /Convert/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Settings/ })).not.toBeInTheDocument();
  });

  it("matches a subsequence (fuzzy) query", async () => {
    const user = userEvent.setup();
    render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Security"), mkCmd("b", "Convert")]} />);
    await user.type(getPaletteInput(), "scrty");
    // Faz 10 (5.4): alt dizi vurgusu metni boler; erisilebilir ad uzerinden dogrula.
    expect(screen.getByRole("option", { name: /Security/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Convert/ })).not.toBeInTheDocument();
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

describe("CommandPalette keyboard navigation", () => {
  it("focuses the search input after opening", async () => {
    render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Convert")]} />);
    await vi.waitFor(() => expect(getPaletteInput()).toHaveFocus(), { timeout: 5000 });
  });

  it("resets the query and the list when reopened", async () => {
    const user = userEvent.setup();
    const commands = [mkCmd("a", "Convert"), mkCmd("b", "Settings")];
    const { rerender } = render(<CommandPalette open onClose={vi.fn()} commands={commands} />);
    await user.type(getPaletteInput(), "conv");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    rerender(<CommandPalette open={false} onClose={vi.fn()} commands={commands} />);
    rerender(<CommandPalette open onClose={vi.fn()} commands={commands} />);
    expect(getPaletteInput().value).toBe("");
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("moves the selection with ArrowDown/ArrowUp and clamps at both ends", () => {
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[mkCmd("a", "Alpha"), mkCmd("b", "Beta"), mkCmd("c", "Gamma")]}
      />,
    );
    const input = getPaletteInput();
    const opts = () => screen.getAllByRole("option");
    expect(opts()[0]).toHaveAttribute("aria-selected", "true");
    // zaten 0'da — yukari ok sinirda kalir
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(opts()[0]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(opts()[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" }); // sonuncuda sinirlanir
    expect(opts()[2]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(opts()[1]).toHaveAttribute("aria-selected", "true");
  });

  it("runs the highlighted command on Enter and closes", () => {
    const actionA = vi.fn();
    const actionB = vi.fn();
    const onClose = vi.fn();
    render(
      <CommandPalette
        open
        onClose={onClose}
        commands={[
          { id: "a", label: "Alpha", action: actionA },
          { id: "b", label: "Beta", action: actionB },
        ]}
      />,
    );
    const input = getPaletteInput();
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(actionA).not.toHaveBeenCalled();
    expect(actionB).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does nothing on Enter when there are no results", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} commands={[mkCmd("a", "Convert")]} />);
    await user.type(getPaletteInput(), "zzz");
    expect(screen.getByText("Sonuç yok")).toBeInTheDocument();
    fireEvent.keyDown(getPaletteInput(), { key: "Enter" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} commands={[mkCmd("a", "Convert")]} />);
    fireEvent.keyDown(getPaletteInput(), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on backdrop mousedown but not on dialog mousedown", () => {
    const onClose = vi.fn();
    const { container } = render(<CommandPalette open onClose={onClose} commands={[mkCmd("a", "Convert")]} />);
    const backdrop = container.firstChild as HTMLElement; // sabit overlay
    fireEvent.mouseDown(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.mouseDown(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1); // degismez
  });

  it("selects an option when the pointer enters it", () => {
    render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Alpha"), mkCmd("b", "Beta")]} />);
    const buttons = screen.getAllByRole("option").map((o) => o.querySelector("button") as HTMLButtonElement);
    fireEvent.mouseOver(buttons[1]);
    const opts = screen.getAllByRole("option");
    expect(opts[1]).toHaveAttribute("aria-selected", "true");
    expect(opts[0]).toHaveAttribute("aria-selected", "false");
  });
});

describe("CommandPalette highlighting & filtering", () => {
  it("highlights a substring match in the middle of the label", async () => {
    const user = userEvent.setup();
    const { container } = render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Convert")]} />);
    await user.type(getPaletteInput(), "nve");
    const mark = container.querySelector("mark");
    expect(mark).not.toBeNull();
    expect(mark!.textContent).toBe("nve");
    expect(screen.getByRole("option", { name: /Convert/ })).toBeInTheDocument();
  });

  it("highlights fuzzy characters individually and keeps the trailing text", async () => {
    const user = userEvent.setup();
    const { container } = render(<CommandPalette open onClose={vi.fn()} commands={[mkCmd("a", "Security")]} />);
    await user.type(getPaletteInput(), "scr");
    const marks = Array.from(container.querySelectorAll("mark")).map((m) => m.textContent);
    // vurgu, etiketin orijinal karakterlerini kullanir ("S" buyuk harf kalir)
    expect(marks).toEqual(["S", "c", "r"]);
    expect(screen.getByRole("option", { name: /Security/ })).toBeInTheDocument();
  });

  it("shows the hint when a command provides one", () => {
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[{ id: "a", label: "Convert", hint: "Ctrl+D", action: vi.fn() }]}
      />,
    );
    expect(screen.getByText("Ctrl+D")).toBeInTheDocument();
  });

  it("orders results by fuzzy score and trims/lowercases the query", async () => {
    const user = userEvent.setup();
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[mkCmd("a", "Offset"), mkCmd("b", "Settings"), mkCmd("c", "Convert")]}
      />,
    );
    await user.type(getPaletteInput(), " SET");
    const opts = screen.getAllByRole("option");
    expect(opts).toHaveLength(2);
    expect(opts[0]).toHaveTextContent("Settings"); // indeks 0 → en yuksek puan
    expect(opts[1]).toHaveTextContent("Offset"); // indeks 3 → dusuk puan
  });
});

describe("CommandPalette recent commands (Faz 9 5.8)", () => {
  it("orders multiple recents newest-first", async () => {
    const user = userEvent.setup();
    const commands = [mkCmd("a", "Alpha"), mkCmd("b", "Beta"), mkCmd("c", "Gamma")];
    const { unmount } = render(<CommandPalette open onClose={vi.fn()} commands={commands} />);
    await user.click(screen.getByText("Gamma"));
    await user.click(screen.getByText("Beta"));
    unmount();
    render(<CommandPalette open onClose={vi.fn()} commands={commands} />);
    const opts = screen.getAllByRole("option");
    expect(opts.map((o) => o.textContent)).toEqual(["Beta", "Gamma", "Alpha"]);
  });

  it("dedupes recents and caps the list at five", async () => {
    const user = userEvent.setup();
    const commands = [
      mkCmd("a", "Alpha"),
      mkCmd("b", "Bravo"),
      mkCmd("c", "Charlie"),
      mkCmd("d", "Delta"),
      mkCmd("e", "Echo"),
      mkCmd("f", "Foxtrot"),
    ];
    render(<CommandPalette open onClose={vi.fn()} commands={commands} />);
    for (const label of ["Foxtrot", "Echo", "Delta", "Charlie", "Bravo", "Alpha", "Alpha"]) {
      await user.click(screen.getByText(label));
    }
    // "f" cap disinda kalir; ikinci "Alpha" tiklamasi kopya olusturmaz.
    expect(JSON.parse(localStorage.getItem("pkgforge.palette.recent") ?? "[]")).toEqual([
      "a",
      "b",
      "c",
      "d",
      "e",
    ]);
  });

  it("swallows localStorage failures while loading and saving recents", async () => {
    const user = userEvent.setup();
    const getItemSpy = vi
      .spyOn(localStorage, "getItem")
      .mockImplementation(() => {
        throw new Error("storage disabled");
      });
    const setItemSpy = vi
      .spyOn(localStorage, "setItem")
      .mockImplementation(() => {
        throw new Error("storage disabled");
      });
    try {
      const action = vi.fn();
      const onClose = vi.fn();
      render(<CommandPalette open onClose={onClose} commands={[{ id: "a", label: "Convert", action }]} />);
      // loadRecent hata yakalar → liste yine de render edilir
      expect(screen.getByRole("option", { name: /Convert/ })).toBeInTheDocument();
      await user.click(screen.getByText("Convert"));
      // saveRecent hata yakalar; eylem ve kapanis yine de gerceklesir
      expect(action).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    } finally {
      getItemSpy.mockRestore();
      setItemSpy.mockRestore();
    }
  });
});
