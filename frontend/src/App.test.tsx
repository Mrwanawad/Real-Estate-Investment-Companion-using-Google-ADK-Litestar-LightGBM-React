import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "./App";
import i18n, { directionFor } from "./i18n";

afterEach(async () => {
  await act(() => i18n.changeLanguage("en"));
});

describe("directionFor", () => {
  it("maps Arabic to rtl and English to ltr", () => {
    expect(directionFor("ar-EG")).toBe("rtl");
    expect(directionFor("ar")).toBe("rtl");
    expect(directionFor("en")).toBe("ltr");
  });
});

describe("App", () => {
  it("shows the synthetic data banner", () => {
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("Synthetic demo data");
  });

  it("switches document direction when the language toggles", async () => {
    render(<App />);
    expect(document.documentElement.dir).toBe("ltr");

    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    await screen.findByText("بيانات تجريبية مصطنعة");
    expect(document.documentElement.dir).toBe("rtl");

    fireEvent.click(screen.getByRole("button", { name: "English" }));
    await screen.findByText("Synthetic demo data");
    expect(document.documentElement.dir).toBe("ltr");
  });
});
