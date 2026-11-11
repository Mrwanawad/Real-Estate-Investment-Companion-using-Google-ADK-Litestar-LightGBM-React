import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./markdown";

describe("Markdown", () => {
  it("renders paragraphs, bold and bullets", () => {
    const { container } = render(<Markdown text={"Hello **world**\n\n- one\n- two **b**"} />);
    expect(container.querySelectorAll("p")).toHaveLength(1);
    expect(container.querySelector("strong")?.textContent).toBe("world");
    expect(container.querySelectorAll("li")).toHaveLength(2);
  });

  it("never injects raw html", () => {
    const { container } = render(<Markdown text={"<img src=x onerror=alert(1)> **ok**"} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img");
  });
});
