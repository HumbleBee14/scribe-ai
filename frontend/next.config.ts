import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next 16 currently emits a broken `.next/dev/types/validator.ts` on this Windows setup.
  // We keep strict app type-checking via `npm run typecheck` and only bypass the framework
  // generated validator during `next build` on win32 until the upstream bug is fixed.
  typescript: {
    ignoreBuildErrors: process.platform === "win32",
  },
};

export default nextConfig;
