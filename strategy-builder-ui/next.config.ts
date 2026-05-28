import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Upstream UI keeps /api/* calls. The app/api catch-all route proxies those
  // requests server-side so it can attach dashboard auth headers when configured.
};

export default nextConfig;
