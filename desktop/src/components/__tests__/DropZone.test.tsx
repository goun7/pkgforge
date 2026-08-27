import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DropZone, filterAcceptedPaths } from "../DropZone";

describe("filterAcceptedPaths", () => {
  it("forwards every path (backend intake classifies)", () => {
    expect(
      filterAcceptedPaths(["/a/pkg_1.0.deb", "/b/x.rpm", "/c/app.tar.gz"]),
    ).toEqual(["/a/pkg_1.0.deb", "/b/x.rpm", "/c/app.tar.gz"]);
  });

  it("drops empty entries only", () => {
    expect(filterAcceptedPaths(["/a/PKG.DEB", ""])).toEqual(["/a/PKG.DEB"]);
  });
});

describe("DropZone", () => {
  it("renders the drop hint", () => {
    render(<DropZone onPaths={() => {}} browse={async () => []} />);
    expect(screen.getByRole("button", { name: "drop-zone" })).toBeInTheDocument();
  });

  it("passes browsed paths through to the backend", async () => {
    const onPaths = vi.fn();
    const browse = vi.fn().mockResolvedValue(["/a/p.deb", "/b/app.tar.gz"]);
    render(<DropZone onPaths={onPaths} browse={browse} />);
    fireEvent.click(screen.getByRole("button", { name: "drop-zone" }));
    await vi.waitFor(() => expect(onPaths).toHaveBeenCalledTimes(1));
    expect(onPaths).toHaveBeenCalledWith(["/a/p.deb", "/b/app.tar.gz"]);
  });

  it("does not call onPaths when nothing selected", async () => {
    const onPaths = vi.fn();
    const browse = vi.fn().mockResolvedValue([]);
    render(<DropZone onPaths={onPaths} browse={browse} />);
    fireEvent.click(screen.getByRole("button", { name: "drop-zone" }));
    await vi.waitFor(() => expect(browse).toHaveBeenCalled());
    expect(onPaths).not.toHaveBeenCalled();
  });

  it("ignores clicks when disabled", () => {
    const browse = vi.fn();
    render(<DropZone onPaths={() => {}} browse={browse} disabled />);
    fireEvent.click(screen.getByRole("button", { name: "drop-zone" }));
    expect(browse).not.toHaveBeenCalled();
  });
});
