import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// The ResizeObserver stub that used to sit here existed for @visx/responsive
// ParentSize, which only the deleted chart components used (legacy removal L5).
//
// jsdom lacks matchMedia, which next-themes (enableSystem) reads to detect the
// OS color scheme. Provide a stub defaulting to "no preference" (light).
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent() {
      return false;
    },
  })) as unknown as typeof window.matchMedia;
}

afterEach(() => {
  cleanup();
});
