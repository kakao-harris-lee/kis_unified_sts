import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "next-themes";
import { describe, expect, it } from "vitest";

import ThemeToggle from "./ThemeToggle";

function renderToggle() {
  return render(
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <ThemeToggle />
    </ThemeProvider>,
  );
}

describe("ThemeToggle", () => {
  it("renders an accessible theme button", async () => {
    renderToggle();
    // After mount it reflects the current theme; default is system.
    expect(
      await screen.findByRole("button", { name: /테마/ }),
    ).toBeInTheDocument();
  });

  it("cycles system → light → dark on repeated clicks", async () => {
    const user = userEvent.setup();
    renderToggle();

    const button = await screen.findByRole("button", { name: /테마: 시스템/ });
    await user.click(button);
    expect(
      await screen.findByRole("button", { name: /테마: 라이트/ }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /테마: 라이트/ }));
    expect(
      await screen.findByRole("button", { name: /테마: 다크/ }),
    ).toBeInTheDocument();
  });
});
