import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Chip } from "./Chip";

describe("Chip", () => {
  it("renders label and count and fires onClick", () => {
    const onClick = vi.fn();
    render(
      <Chip active={false} onClick={onClick} count={3}>
        All
      </Chip>,
    );
    const btn = screen.getByRole("button", { name: /All/ });
    expect(btn).toHaveTextContent("All");
    expect(btn).toHaveTextContent("3");
    btn.click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders the dot when dotClass is provided", () => {
    const { container } = render(
      <Chip active onClick={() => {}} count={0} dotClass="bg-red-500">
        NYT
      </Chip>,
    );
    expect(container.querySelector(".bg-red-500")).not.toBeNull();
  });
});
