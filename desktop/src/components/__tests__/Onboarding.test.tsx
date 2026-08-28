import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Onboarding } from "../Onboarding";

describe("Onboarding (Faz 10 1.8)", () => {
  it("opens on first run", () => {
    render(<Onboarding />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Başla" })).toBeInTheDocument();
  });

  it("marks seen and closes on start", async () => {
    const user = userEvent.setup();
    render(<Onboarding />);
    await user.click(screen.getByRole("button", { name: "Başla" }));
    expect(localStorage.getItem("pkgforge.onboarding.seen")).toBe("1");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("does not open if already seen", () => {
    localStorage.setItem("pkgforge.onboarding.seen", "1");
    render(<Onboarding />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
