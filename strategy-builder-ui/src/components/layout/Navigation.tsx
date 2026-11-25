"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity } from "lucide-react";
import ThemeToggle from "@/components/layout/ThemeToggle";

// One entry, because one page is left. Cockpit, Positions, Signals, Risk,
// Market, Universe, Coverage, Evidence, Events, Trades, 실험, 전략 빌더 and
// 전략 실행 were removed with their pages (legacy removal L5): every API they
// linked to was deleted from services/dashboard in L4, so each entry was a link
// to a screen that could only render errors.
const navItems = [{ href: "/tos", label: "TOS", icon: Activity }];

export function Navigation() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
      <div className="w-full px-4">
        <div className="relative flex h-16 w-full max-w-full min-w-0 items-center justify-between gap-2 overflow-hidden pr-10 sm:overflow-visible sm:pr-0">
          {/* 로고 — `/tos` directly, not `/`, so the one link in the shell does
              not take the root redirect hop. */}
          <Link
            href="/tos"
            className="flex shrink-0 items-center gap-3 focus-ring rounded-lg"
            aria-label="TOS 운영 상태 홈"
          >
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Activity className="w-6 h-6 text-white" aria-hidden="true" />
            </div>
            <div className="hidden sm:block">
              <h1 className="font-bold text-lg text-slate-900 dark:text-slate-100">
                KIS TOS
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                운영 상태 · 읽기 전용
              </p>
            </div>
          </Link>

          {/* 네비게이션 */}
          <nav
            className="scrollbar-thin flex max-w-[calc(100vw-128px)] flex-none items-center gap-1 overflow-x-auto px-1 sm:max-w-none sm:flex-1"
            aria-label="메인 네비게이션"
          >
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  aria-label={item.label}
                  className={`flex shrink-0 items-center gap-2 px-2 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors focus-ring ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                  }`}
                >
                  <Icon className="w-4 h-4" aria-hidden="true" />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* 우측 영역: 테마 토글. The 모의/실전 mode badge read AuthProvider's
              `/api/auth/status` poll and the gear opened SettingsModal, which
              drove the KIS login/mode-switch endpoints — all deleted in L4. */}
          <div className="fixed right-4 top-4 z-[60] flex shrink-0 items-center gap-2 bg-white dark:bg-slate-900 sm:static sm:z-10">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  );
}

export default Navigation;
