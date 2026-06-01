import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // Standalone output is required for the slim Linux Docker image.
  // On Windows local dev it fails with EPERM on symlinks unless run as admin /
  // Developer Mode, so we only enable it when NEXT_OUTPUT=standalone (the
  // Dockerfile sets this).
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" as const } : {}),
  experimental: {
    typedRoutes: true,
  },
  images: { remotePatterns: [{ protocol: "https", hostname: "**.blob.core.windows.net" }] },
};

export default config;
