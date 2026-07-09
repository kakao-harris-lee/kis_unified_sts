import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom lacks ResizeObserver, which @visx/responsive ParentSize relies on.
// Provide a no-op stub so visx-based charts can mount under test without
// throwing. (Guarded so a real implementation, if present, is not clobbered.)
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

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
