import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { WhatsNew } from "../WhatsNew";

describe("WhatsNew (Faz 10 1.7)", () => {
  it("stays hidden for a first-time user", () => {
    render(<WhatsNew />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens for a returning user when the version changed", () => {
    localStorage.setItem("pkgforge.onboarding.seen", "1");
    localStorage.setItem("pkgforge.whatsnew.seen", "1.0.0");
    render(<WhatsNew />);
    expect(screen.getByText("Yenilikler")).toBeInTheDocument();
  });

  it("marks the version seen on close", async () => {
    const user = userEvent.setup();
    localStorage.setItem("pkgforge.onboarding.seen", "1");
    localStorage.setItem("pkgforge.whatsnew.seen", "1.0.0");
    render(<WhatsNew />);
    const closeButtons = screen.getAllByRole("button", { name: "Kapat" });
    await user.click(closeButtons[closeButtons.length - 1]);
    expect(localStorage.getItem("pkgforge.whatsnew.seen")).toBe("2.0.0");
  });
});
