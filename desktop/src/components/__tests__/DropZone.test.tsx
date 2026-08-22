import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DropZone, filterAcceptedPaths } from "../DropZone";

describe("filterAcceptedPaths", () => {
  it("keeps .deb and .rpm, drops others", () => {
    expect(
      filterAcceptedPaths(["/a/pkg_1.0.deb", "/b/x.rpm", "/c/readme.txt"]),
    ).toEqual(["/a/pkg_1.0.deb", "/b/x.rpm"]);
  });

  it("is case-insensitive", () => {
    expect(filterAcceptedPaths(["/a/PKG.DEB"])).toEqual(["/a/PKG.DEB"]);
  });
});

describe("DropZone", () => {
  it("renders the drop hint", () => {
    render(<DropZone onPaths={() => {}} browse={async () => []} />);
    expect(screen.getByRole("button", { name: "drop-zone" })).toBeInTheDocument();
  });

  it("passes browsed paths through the filter", async () => {
    const onPaths = vi.fn();
    const browse = vi.fn().mockResolvedValue(["/a/p.deb", "/b/x.txt"]);
    render(<DropZone onPaths={onPaths} browse={browse} />);
    fireEvent.click(screen.getByRole("button", { name: "drop-zone" }));
    await vi.waitFor(() => expect(onPaths).toHaveBeenCalledTimes(1));
    expect(onPaths).toHaveBeenCalledWith(["/a/p.deb"]);
  });

  it("does not call onPaths when nothing accepted", async () => {
    const onPaths = vi.fn();
    const browse = vi.fn().mockResolvedValue(["/b/x.txt"]);
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
