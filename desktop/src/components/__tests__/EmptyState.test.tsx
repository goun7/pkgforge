import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Package } from "lucide-react";
import { EmptyState } from "../EmptyState";

describe("EmptyState (Faz 9 4.6)", () => {
  it("renders title and description", () => {
    render(<EmptyState icon={Package} title="Nothing here" description="Try a different search" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Try a different search")).toBeInTheDocument();
  });

  it("renders an optional action", () => {
    render(<EmptyState icon={Package} title="Empty" action={<button type="button">Do it</button>} />);
    expect(screen.getByRole("button", { name: "Do it" })).toBeInTheDocument();
  });

  it("omits description when not provided", () => {
    render(<EmptyState icon={Package} title="Only title" />);
    expect(screen.getByText("Only title")).toBeInTheDocument();
  });
});
