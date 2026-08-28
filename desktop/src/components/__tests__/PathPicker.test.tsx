import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PathPicker } from "../PathPicker";

describe("PathPicker (Faz 10 1.6)", () => {
  it("fires onChange when typing", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PathPicker value="" onChange={onChange} placeholder="/yol" />);
    await user.type(screen.getByPlaceholderText("/yol"), "a");
    expect(onChange).toHaveBeenCalledWith("a");
  });

  it("uses the injected browse to set a path", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const browse = vi.fn().mockResolvedValue(["/tmp/paket.deb"]);
    render(<PathPicker value="" onChange={onChange} browse={browse} />);
    await user.click(screen.getByRole("button"));
    expect(browse).toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith("/tmp/paket.deb");
  });
});
