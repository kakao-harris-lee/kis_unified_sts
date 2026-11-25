import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Sans_KR } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/layout";
import { Providers } from "@/components/providers/Providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const notoSansKR = Noto_Sans_KR({
  variable: "--font-noto-sans-kr",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "KIS TOS 운영 상태",
  description: "TOS 런타임이 내보낸 읽기 전용 운영 상태",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // suppressHydrationWarning: next-themes sets the theme class on <html>
    // before hydration, which would otherwise trip a mismatch warning.
    <html lang="ko" suppressHydrationWarning>
      <body
        className={`${notoSansKR.variable} ${geistSans.variable} ${geistMono.variable} antialiased min-h-screen`}
      >
        {/* The <Suspense> that used to wrap this tree existed for
            AssetClassContext's useSearchParams() bailout. That provider went
            with the dashboard pages (legacy removal L5) and nothing left in the
            shell reads search params, so the boundary has nothing to catch. */}
        <Providers>
          <Navigation />
          <main className="min-h-[calc(100vh-4rem)]">{children}</main>
          <footer className="border-t border-slate-200 dark:border-slate-800">
            <div className="max-w-7xl mx-auto px-4 py-4">
              <p className="text-center text-sm text-slate-500">
                조회 결과는 거래 실행 권한을 부여하지 않습니다.
              </p>
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
