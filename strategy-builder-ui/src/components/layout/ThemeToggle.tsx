"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

// Cycle order: system → light → dark → system. `theme` is the stored choice
// ("system" | "light" | "dark"); `resolvedTheme` is what's actually applied.
const NEXT: Record<string, string> = {
  system: "light",
  light: "dark",
  dark: "system",
};

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // next-themes only knows the theme after mount; render a stable placeholder
  // during SSR/first paint to avoid a hydration mismatch. This is the official
  // next-themes mount-gate pattern; the one-time setState in effect is
  // intentional and safe here.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  const current = theme ?? "system";
  const label =
    current === "system"
      ? "테마: 시스템"
      : current === "light"
        ? "테마: 라이트"
        : "테마: 다크";

  const Icon =
    !mounted || current === "system" ? Monitor : current === "dark" ? Moon : Sun;

  return (
    <button
      type="button"
      onClick={() => setTheme(NEXT[current] ?? "system")}
      className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-ring"
      aria-label={`${label} (클릭하여 전환)`}
      title={label}
    >
      <Icon
        className="w-5 h-5 text-slate-600 dark:text-slate-400"
        aria-hidden="true"
      />
    </button>
  );
}
